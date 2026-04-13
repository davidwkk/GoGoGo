"""Streaming service — unified LLM loop with finalize_trip_plan."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from uuid import UUID, uuid4

from google.genai import Client, types
from loguru import logger
from sqlalchemy.orm import Session

from app.agent.tools import (
    ALL_TOOLS,
    build_embed_url,
    get_attraction,
    get_transport,
    get_weather,
    search_flights,
    search_hotels,
    search_web,
)
from app.core.config import settings
from app.db.models.message import Message
from app.schemas.itinerary import PriceRange, TripItinerary
from app.services.message_service import (
    append_message,
    append_tool_message,
    get_session_messages,
    update_message_content,
)
from app.services.trip_service import save_trip

# Sync tool_map for the Gemini SDK
TOOL_MAP = {
    "get_attraction": get_attraction,
    "get_weather": get_weather,
    "search_web": search_web,
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "get_transport": get_transport,
    "build_embed_url": build_embed_url,
}

MAX_TOOL_ROUNDS = 20
TIMEOUT_SECONDS = 120.0


# ──────────────────────────────────────────────────────────────────────────────
# Message history helpers
# ──────────────────────────────────────────────────────────────────────────────


def _format_error_message(error: Exception) -> str:
    """Convert raw exceptions into user-friendly error messages."""
    error_str = str(error)
    error_type = type(error).__name__

    # Connection / network errors
    if "Server disconnected" in error_str or "Connection reset" in error_str:
        return "Connection lost. Please check your internet and try again."
    if "ConnectTimeout" in error_str or "ConnectError" in error_str:
        return "Could not connect to the AI service. Please check your internet connection."
    if "Timeout" in error_str:
        return "The request took too long. Please try again."

    # Proxy errors
    if "proxy" in error_str.lower():
        return "Proxy error. Please check your VPN/proxy settings and try again."

    # Gemini API errors
    if "400" in error_str and "FAILED_PRECONDITION" in error_str:
        if "User location" in error_str:
            return "AI service is not available in your region. Please try using a VPN."
        return "AI request error. Please try again."
    if "429" in error_str or "rate limit" in error_str.lower():
        return "Too many requests. Please wait a moment and try again."
    if "503" in error_str or "unavailable" in error_str.lower():
        return (
            "AI service is temporarily unavailable. Please try again in a few moments."
        )

    # Default: show type + short message
    if len(error_str) > 100:
        return f"{error_type}: {error_str[:100]}..."
    return f"{error_type}: {error_str}"


def _messages_to_content(messages: list[Message]) -> list[types.Content]:
    """
    Convert stored Message records to Gemini types.Content format.

    Handles:
    - Regular text messages (user/assistant roles)
    - Itinerary messages stored by finalize_trip_plan (assistant role, JSON content)
    - Tool result messages (function role) from previous requests
    """
    import json

    result: list[types.Content] = []
    for msg in messages:
        # Include function messages (tool results from previous requests)
        if msg.role == "function" and msg.message_type == "tool_result":
            try:
                payload = json.loads(msg.content)
                tool_name = payload.get("tool", "")
                tool_result = payload.get("result", {})
                result.append(
                    types.Content(
                        role="function",
                        parts=[
                            types.Part.from_function_response(
                                name=tool_name,
                                response=tool_result,
                            )
                        ],
                    )
                )
            except Exception as e:
                logger.bind(
                    event="message_parse_skip",
                    msg_id=msg.id,
                    session_id=msg.session_id,
                ).warning(f"Skipping malformed tool message {msg.id}: {e}")
            continue

        if msg.role not in ("user", "assistant"):
            continue
        content = msg.content or ""
        # If it's a stored itinerary message, extract just the text summary
        if msg.message_type == "itinerary":
            try:
                data = json.loads(content)
                if data.get("__type") == "itinerary":
                    itinerary_data = data.get("data", {})
                    summary = (
                        f"[Trip itinerary generated: {itinerary_data.get('destination', 'Unknown')} "
                        f"from {itinerary_data.get('start_date', '')} to {itinerary_data.get('end_date', '')}]"
                    )
                    content = summary
            except Exception:
                pass
        result.append(
            types.Content(role=msg.role, parts=[types.Part.from_text(text=content)])
        )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Tool result persistence helpers
# ──────────────────────────────────────────────────────────────────────────────


def _save_tool_result_to_db(
    db: Session,
    session_id: int,
    tool_name: str,
    args: dict,
    result: dict,
) -> None:
    """Persist a tool call + result to the DB for cross-request context."""
    try:
        append_tool_message(
            db,
            session_id=session_id,
            tool_name=tool_name,
            args=args,
            result=result,
        )
    except Exception:
        # Non-fatal — log but don't interrupt the stream
        logger.bind(event="tool_db_save_error", tool=tool_name).warning(
            "Failed to save tool result to DB"
        )


# ──────────────────────────────────────────────────────────────────────────────
# finalize_trip_plan — local function intercepted by name in the streaming loop
# ──────────────────────────────────────────────────────────────────────────────


def _round_budget_values(itinerary: TripItinerary) -> TripItinerary:
    """Round all budget values in the itinerary to the nearest multiple of 100."""
    budget = itinerary.estimated_total_budget_hkd
    if budget:
        budget.flights_hkd = _round_price_range(budget.flights_hkd)
        budget.hotels_hkd = _round_price_range(budget.hotels_hkd)
        budget.activities_hkd = _round_price_range(budget.activities_hkd)
        budget.total_hkd = _round_price_range(budget.total_hkd)
    return itinerary


def _round_price_range(pr: "PriceRange") -> "PriceRange":
    """Round min and max of a PriceRange to nearest 100."""
    return PriceRange(
        min=round(pr.min / 100) * 100 if pr.min is not None else 0,
        max=round(pr.max / 100) * 100 if pr.max is not None else 0,
    )


async def finalize_trip_plan(
    preferences: dict | None = None,
    messages: list[types.Content] | None = None,
) -> dict:
    """
    Produces a structured TripItinerary from all information already gathered
    in the conversation. Does NOT call external APIs — all trip data was
    already fetched by the agent during the information gathering phase.

    Trip parameters (destination, dates, purpose, group) are extracted from the
    user\'s original request in the conversation history.

    Makes exactly ONE generate_content() call with response_json_schema=TripItinerary.

    Args:
        preferences: Optional user preferences dict.
        messages: Accumulated conversation state from the streaming loop (list of
            Gemini Content objects with user/assistant/function messages).

    Returns:
        dict with "itinerary" key containing TripItinerary JSON, or "error" key
        if validation fails or required tool results are missing.
    """

    # ── Validation guard: required tool results in context ─────────────────────
    # Gemini SDK uses role="function" for tool responses
    def _has_tool(name: str) -> bool:
        return any(
            getattr(part.function_response, "name", None) == name
            for m in (messages or [])
            if m.role == "function" and m.parts
            for part in m.parts or []
            if hasattr(part, "function_response") and part.function_response
        )

    has_flights = _has_tool("search_flights")
    has_hotels = _has_tool("search_hotels")
    has_weather = _has_tool("get_weather")
    has_attractions = _has_tool("get_attraction")
    if not all([has_flights, has_hotels, has_weather, has_attractions]):
        missing = [
            n
            for n, found in [
                ("search_flights", has_flights),
                ("search_hotels", has_hotels),
                ("get_weather", has_weather),
                ("get_attraction", has_attractions),
            ]
            if not found
        ]
        return {
            "error": (
                f"Not enough trip data gathered yet. "
                f"Missing tools: {', '.join(missing)}. "
                f"Call all of: search_flights, search_hotels, get_weather, get_attraction."
            )
        }

    # ── Build context prompt ────────────────────────────────────────────────────
    prefs_section = f"User preferences: {preferences}" if preferences else ""
    context_prompt = (
        "Based on all the information gathered in this conversation, "
        "produce a complete trip itinerary as a TripItinerary JSON object.\n\n"
        "All necessary data (flights, hotels, attractions, weather, transport) "
        "was already fetched by the agent and is available in the conversation history below. "
        "Extract the trip parameters (destination, dates, purpose, group details) from "
        "the user's original request in the conversation history.\n\n"
        "## Title Generation (CRITICAL)\n"
        "The 'title' field is REQUIRED. Generate a descriptive title that captures:\n"
        "- Travel DATE (e.g. 'Apr 1-3, 2026' or 'Spring 2026')\n"
        "- DESTINATION (e.g. 'Tokyo', 'Bali', 'Paris')\n"
        "- Travel TYPE (e.g. solo, family, couple, friends, group)\n"
        "- Travel STYLE (e.g. vacation, romantic getaway, adventure, honeymoon, business)\n"
        "- Number of TRAVELERS (e.g. '2 people', 'Family of 4', 'Solo')\n"
        "Format examples:\n"
        "- '3-Day Tokyo Family Vacation Apr 1-3 | 4 People'\n"
        "- '2-Person Bali Romantic Getaway Jun 15-20'\n"
        "- 'Solo Kyoto Adventure May 10-15'\n"
        "- 'Paris Couple Getaway Dec 20-27 | 2 People'\n\n"
        "CRITICAL: You MUST copy these fields DIRECTLY from tool results without modification:\n"
        "- Activity: wiki_url, map_url (ONLY if the attraction has a specific physical location like a temple, tower, museum, theme park — DO NOT include map_url for vague areas like 'shopping street', 'night market', 'shopping district'), opening_hours, admission_fee_hkd, rating, review_count, tips, image_url, thumbnail_url, booking_url, address\n"
        "- Hotel: hotel_class_int, reviews, location_rating, amenities, description, star_rating, guest_rating, image_url, check_in_time, check_out_time, embed_map_url, booking_url\n"
        "CRITICAL for Hotel images: You MUST use the image_url field DIRECTLY from the search_hotels tool result as the image_url for the Hotel card. Do NOT generate or fetch your own image — only use the image_url provided by the search_hotels tool.\n"
        "- Flight: duration_minutes, airplane, travel_class, departure_airport_name, arrival_airport_name, price_hkd, booking_url\n\n"
        "IMPORTANT: Round all budget values (total_hkd, flights_hkd, hotels_hkd, "
        "activities_hkd) to the nearest multiple of 100 (e.g., 3000, 5200, 10800).\n\n"
        "## Tips Generation (CRITICAL)\n"
        "- You MUST generate at least 1 tip for EVERY activity in days[].morning[], days[].afternoon[], and days[].evening[].\n"
        "- The correct field path is: days[].morning[].tips, days[].afternoon[].tips, days[].evening[].tips — each Activity has a tips: list[str] | None field.\n"
        "- Generate practical tips based ONLY on the information available in the tool results (reviews, ratings, descriptions, amenities, opening_hours, weather_summary).\n"
        "- Tips should include useful reminders like best time to visit, optimal duration, photography spots, dress code, weather-appropriate clothing, or insider knowledge.\n"
        "- If a tool result provides tips information, extract and refine it. If no tips data is available, generate a sensible tip from available context (e.g., 'Best visited in the morning to avoid crowds' based on opening hours and rating).\n"
        "- ALWAYS factor in the weather of each trip day: if rain is expected, suggest indoor alternatives or umbrella; if it's hot, suggest hydration and shade breaks; if it's cold, suggest warm clothing layers.\n"
        "- NEVER leave tips as null or empty for any activity — every activity MUST have at least 1 tip.\n\n"
        f"{prefs_section}"
    )

    http_opts = (
        types.HttpOptionsDict(client_args={"proxy": settings.SOCKS5_PROXY_URL})
        if settings.LLM_PROXY_ENABLED
        else None
    )
    client = Client(api_key=settings.GEMINI_API_KEY, http_options=http_opts)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=TripItinerary.model_json_schema(),
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL
        ),
    )

    final_contents: list = (messages or []) + [
        types.Content(role="user", parts=[types.Part.from_text(text=context_prompt)])
    ]
    FINALIZE_TIMEOUT_SECONDS = 40.0

    # ── Log exact LLM request for performance analysis ───────────────────
    def _serialize_content_for_log(c: types.Content) -> dict:
        """Serialize types.Content to a dict for logging."""
        parts_list = []
        for p in c.parts or []:
            if p.text:
                parts_list.append({"text": p.text})
            elif p.function_call:
                parts_list.append(
                    {
                        "function_call": {
                            "name": p.function_call.name,
                            "args": dict(p.function_call.args)
                            if p.function_call.args
                            else {},
                        }
                    }
                )
            elif p.function_response:
                parts_list.append(
                    {
                        "function_response": {
                            "name": getattr(p.function_response, "name", None),
                            "response": (
                                p.function_response.response
                                if p.function_response
                                else None
                            ),
                        }
                    }
                )
            elif p.thought:
                parts_list.append({"thought": "[thought signature]"})
        return {"role": c.role, "parts": parts_list}

    finalize_messages_log = [_serialize_content_for_log(m) for m in final_contents]
    finalize_config_log = {
        "response_mime_type": config.response_mime_type,
        "thinking_level": (
            config.thinking_config.thinking_level.name
            if config.thinking_config and config.thinking_config.thinking_level
            else None
        ),
    }

    logger.bind(
        event="llm_request",
        service="chat",
        event_type="finalize_trip_plan",
        model=settings.GEMINI_LITE_MODEL,
        messages_count=len(final_contents),
        config=finalize_config_log,
        messages_preview=[
            {
                **finalize_messages_log[i],
                "parts": [
                    "...".join(
                        p.get("text", p.get("function_call", {}).get("name", ""))
                        for p in (finalize_messages_log[i].get("parts") or [])[:2]
                    )
                ],
            }
            for i in range(len(finalize_messages_log))
        ],
    ).debug(
        f"🤖 LLM finalize_trip_plan request | model={settings.GEMINI_LITE_MODEL} | "
        f"messages={len(final_contents)} | config={finalize_config_log}"
    )

    def sync_generate():
        return client.models.generate_content(
            model=settings.GEMINI_LITE_MODEL,
            contents=final_contents,
            config=config,
        )

    async with asyncio.timeout(FINALIZE_TIMEOUT_SECONDS):
        response = await asyncio.to_thread(sync_generate)

    # Log token usage for finalize call
    usage = getattr(response, "usage_metadata", None)
    if usage:
        logger.bind(
            event="llm_tokens",
            service="chat",
            event_type="finalize_trip_plan",
            model=settings.GEMINI_LITE_MODEL,
            prompt_tokens=usage.prompt_token_count,
            completion_tokens=usage.candidates_token_count,
            total_tokens=usage.total_token_count,
        ).debug(
            f"🤖 LLM finalize_trip_plan tokens: "
            f"prompt={usage.prompt_token_count} "
            f"completion={usage.candidates_token_count} "
            f"total={usage.total_token_count}"
        )

    logger.bind(
        event="llm_response",
        service="chat",
        event_type="finalize_trip_plan",
        model=settings.GEMINI_LITE_MODEL,
        response_text=(response.text or "")[:20000],
    ).debug(f"🤖 LLM finalize_trip_plan response: {(response.text or '')[:20000]}")

    text = response.text or ""
    try:
        itinerary = TripItinerary.model_validate_json(text)
    except Exception as e:
        logger.bind(
            event="finalize_parse_error", error=str(e), response_preview=text[:500]
        ).error("Failed to parse TripItinerary from finalize_trip_plan")
        return {"error": f"Failed to generate trip plan: {e}"}

    # Post-process: round budget values to nearest 100
    itinerary = _round_budget_values(itinerary)

    return {"itinerary": itinerary.model_dump(mode="json")}


# ──────────────────────────────────────────────────────────────────────────────
# Unified streaming loop
# ──────────────────────────────────────────────────────────────────────────────


def _build_system_instruction(preferences: dict | None = None) -> str:
    from datetime import date

    today = date.today().isoformat()
    prefs_section = f"User preferences: {preferences}" if preferences else ""
    commands_section = (
        f"User instructions: {preferences.get('trip_planning_commands', '')}"
        if preferences and preferences.get("trip_planning_commands")
        else ""
    )
    return (
        f"You are a travel planning assistant. Today is {today}.\n\n"
        "## Required Info\n"
        "Ask for ALL in ONE message:\n"
        "  1. Destination (city)\n"
        "  2. Start & end date (Month Day, e.g., May 4 to May 7)\n"
        "     - After today → this year; before today → next year\n"
        "  3. Purpose (vacation, business, honeymoon, family visit, etc.)\n"
        "  4. Group type & size (solo=1, couple=2; ask for others)\n\n"
        "## Tools\n"
        "- get_weather, search_flights, search_hotels, get_attraction, get_transport, search_web\n\n"
        "## Tool Rules\n"
        "- FLIGHTS: For round-trips, you MUST call search_flights TWICE:\n"
        "    1. Outbound leg: departure=<origin>, arrival=<dest>, date=< outbound_date>, return_date=<return_date>\n"
        "    2. Return leg: departure=<dest>, arrival=<origin>, date=<return_date>, return_date=None\n"
        "  IMPORTANT: Use IATA AIRPORT codes only (3 letters, uppercase). "
        "City/metro codes will return 0 results.\n"
        "  ALWAYS assume departure is HKG (Hong Kong International Airport) unless user specifies a different departure city.\n"
        "  ALWAYS use a SINGLE airport code for arrival — never comma-separated codes. "
        "When a city has multiple airports (e.g., Tokyo has HND and NRT), pick ONE:\n"
        "    - Tokyo: HND (Haneda) is closer to central Tokyo; NRT (Narita) is farther but has more international routes. Prefer HND.\n"
        "    - London: LHR (Heathrow) or LGW (Gatwick) — prefer LHR for international flights.\n"
        "    - New York: JFK or EWR — prefer JFK.\n"
        "    - Paris: CDG (Charles de Gaulle) or ORY (Orly) — prefer CDG.\n"
        "    - Shanghai: PVG (Pudong) or SHA (Hongqiao) — prefer PVG for international.\n"
        "    - Beijing: PEK (Capital) or PKX (Daxing) — prefer PEK.\n"
        "    - Seoul: ICN (Incheon) or GMP (Gimpo) — prefer ICN for international.\n"
        "    - Singapore: SIN (Changi).\n"
        "    - Bangkok: BKK (Suvarnabhumi) or DMK (Don Mueang) — prefer BKK.\n"
        "    - Osaka: KIX (Kansai) or ITM (Itami) — prefer KIX for international.\n"
        "    - Taipei: TPE (Taoyuan) or TSA (Songshan) — prefer TPE.\n"
        "  FLIGHT RETRY: If search_flights returns 0 results or an error, do NOT give up. Try different approaches:\n"
        "    - If a city has multiple airports, try the OTHER airport (e.g., Tokyo: try NRT if HND fails, or vice versa).\n"
        "    - Try different dates (nearby days often have more flight options).\n"
        "    - Check if the destination code is correct — SerpAPI may not support all regional airports.\n"
        "    - Keep retrying with different airport codes or dates until you get actual flight results.\n"
        "    - You MUST have at least 1 outbound flight result before proceeding. Do NOT call finalize_trip_plan if all flight searches return 0 results.\n"
        "  Example (HKG→Tokyo Haneda May 15, return May 17):\n"
        "    Call 1: search_flights(departure=HKG, arrival=HND, date=2026-05-15, return_date=2026-05-17)\n"
        "    Call 2: search_flights(departure=HND, arrival=HKG, date=2026-05-17, return_date=None)\n"
        '  One-way: only if user explicitly says "one-way".\n'
        "  Each result includes a 'direction' field ('outbound' or 'return') so you know which leg it is.\n"
        "- HOTELS: Call search_hotels with the destination city and check-in/check-out dates.\n"
        "  HOTEL RETRY: If search_hotels returns 0 results or an error, do NOT give up. Try different approaches:\n"
        "    - Try the city name alone without specific area/district.\n"
        "    - Try the broader region or nearby landmark name.\n"
        "    - Try alternative spelling or common variations of the city name.\n"
        "    - Keep retrying with different destination strings until you get actual hotel results.\n"
        "    - You MUST have at least 1 hotel result before proceeding. Do NOT call finalize_trip_plan if all hotel searches return 0 results.\n"
        "- ATTRACTIONS: at least 2 per full travel day (a day with only 1 attraction is not acceptable — always plan at least 2 events/attractions per full day, while it can be just 1 activity for a half day: arriving the destination after 3pm).\n"
        "- ATTRACTION RETRY: If get_attraction returns a 404 error (attraction not found), try an alternative name:\n"
        "    - Remove common suffixes like 'Temple', 'Shrine', 'Museum', 'Park', 'Tower' and retry.\n"
        "    - Or add '_(city)' disambiguation suffix (e.g., 'Senso-ji' → 'Senso-ji_(Tokyo)').\n"
        "    - Or try the Wikipedia search API to find the correct exact page title first.\n"
        "    - Keep retrying with different names until you have enough attractions for the itinerary.\n"
        "- Only call tools when:\n"
        '  1. User confirms "generate the plan" → call ALL required tools.\n'
        "  2. User explicitly asks for real-time data (weather, flight prices, availability).\n"
        '- Do NOT call tools just to "preview" or "gather info" upfront.\n'
        "- Do NOT call the same tool twice for the same purpose.\n\n"
        "## finalize_trip_plan\n"
        "Call ONLY when user explicitly confirms with 'yes'. Before calling:\n"
        "  1. Present a summary (destination, dates, purpose, group, preferences).\n"
        '  2. Ask for explicit confirmation by replying with "yes".\n'
        "  3. Do NOT proceed until the user replies with a clear 'yes'.\n"
        "  4. Once confirmed, call ALL of: search_flights (TWICE for round-trips), search_hotels, get_weather, get_attraction (1+ per travel day).\n"
        "  5. After ALL tools return, call finalize_trip_plan() with NO arguments — it reads the conversation to extract trip details.\n"
        "     Do NOT return text instead.\n\n"
        "## Enrichment Fields\n"
        "CRITICAL: You MUST copy these fields DIRECTLY from tool results without modification:\n"
        "- Activity: wiki_url, map_url (ONLY if the attraction has a specific physical location like a temple, tower, museum, theme park — DO NOT include map_url for vague areas like 'shopping street', 'night market', 'shopping district'), opening_hours, admission_fee_hkd, rating, review_count, tips, image_url, thumbnail_url, booking_url, address\n"
        "- Hotel: hotel_class_int, reviews, location_rating, amenities, description, star_rating, guest_rating, image_url, check_in_time, check_out_time, embed_map_url\n"
        "CRITICAL for Hotel images: You MUST use the image_url field DIRECTLY from the search_hotels tool result as the image_url for the Hotel card. Do NOT generate or fetch your own image — only use the image_url provided by the search_hotels tool.\n"
        "- Flight: duration_minutes, airplane, travel_class\n\n"
        "## Price Hallucination Prevention (CRITICAL)\n"
        "- Do NOT invent, estimate, or make up ANY prices.\n"
        "- For admission_fee_hkd: ONLY use values that appear in the tool results. If no price is provided, set admission_fee_hkd to null.\n"
        "- Do NOT guess or estimate prices for attractions, hotels, or flights.\n"
        "- Only include prices that are explicitly returned by the tools.\n\n"
        "## Tips Generation\n"
        "- Give at least 1 tip for each attraction.\n"
        "- Generate practical tips for each attraction based ONLY on the information available in tool results.\n"
        "- Tips should include useful reminders like best time to visit, optimal duration, photography spots, weather-appropriate advice, or insider knowledge.\n"
        "- If no tips information is available in the tool results, set tips to null or an empty list.\n"
        "- Do NOT make up tips that are not supported by the fetched data.\n\n"
        "## Rules\n"
        "- Never invent dates, destinations, or prices.\n"
        "- Use HKD for Asian destinations.\n"
        "- Markdown formatting.\n"
        "- If the user does not specify a departure country/city, assume HONG KONG (HKG) as the default departure.\n"
        "- For thumbnail_url and image_url: use the URL directly from the tool results if provided.\n"
        f"{prefs_section}" + (f"\n{commands_section}" if commands_section else "")
    )


SSE_KEEPALIVE = ": keepalive\n\n"
STREAM_TIMEOUT_SECONDS = 30.0  # 30s — per-chunk timeout; resets on each chunk received
STREAM_MAX_RETRIES = 2


def SSE(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _keepalive_pusher(queue: asyncio.Queue[str]) -> None:
    """Background task: put SSE keepalive comment in queue every 20s."""
    while True:
        await asyncio.sleep(20)
        await queue.put(SSE_KEEPALIVE)


async def stream_agent_response(
    message: str,
    session_id: int,
    db: Session,
    preferences: dict | None = None,
    trace_id: str | None = None,
    user_id: UUID | None = None,
) -> AsyncIterator[str]:
    """
    Unified streaming loop — replaces all three previous agent paths.

    Yields SSE events:
      - chunk:           text content streamed in real-time
      - tool_call:       tool name + args being executed
      - tool_result:     tool response (or error)
      - message_type=finalizing:  trip plan is being generated
      - message_type=itinerary:    structured TripItinerary payload
      - message_type=error:        error message
      - done:             stream complete
    """
    trace_id = trace_id or str(uuid4())
    model = settings.GEMINI_LITE_MODEL

    logger.bind(
        event="stream_start",
        service="chat",
        trace_id=trace_id,
        model=model,
        session_id=session_id,
    ).info("Unified streaming loop started")

    # ── Create assistant message in DB ──────────────────────────────────────────
    assistant_msg = append_message(
        db, session_id=session_id, role="assistant", content=""
    )
    # Emit message_id so frontend can persist thinking steps with correct numeric ID
    yield SSE({"message_id": assistant_msg.id})
    accumulated_text = ""

    def _flush_text() -> None:
        nonlocal accumulated_text
        update_message_content(db, assistant_msg.id, accumulated_text)

    http_opts = (
        types.HttpOptionsDict(
            client_args={
                "proxy": settings.SOCKS5_PROXY_URL,
                "timeout": STREAM_TIMEOUT_SECONDS,
            },
            timeout=int(STREAM_TIMEOUT_SECONDS * 1000),  # HttpOptions.timeout is ms
        )
        if settings.LLM_PROXY_ENABLED
        else None
    )
    client = Client(api_key=settings.GEMINI_API_KEY, http_options=http_opts)
    system_instruction = _build_system_instruction(preferences)

    # ── Declare finalize_trip_plan as a Gemini tool ────────────────────────────
    # NOTE: finalize_trip_plan is intercepted locally — NOT in TOOL_MAP.
    # We declare it here so the model knows it exists and can call it.
    finalize_trip_plan_decl = types.FunctionDeclaration(
        name="finalize_trip_plan",
        description=(
            "Call this when you have all required trip information and the user wants a complete trip itinerary. "
            "Before calling this function, ensure you have called ALL of: "
            "search_flights (TWICE for round-trips), search_hotels, get_weather, get_attraction (at least once each). "
            "Takes NO arguments — reads trip details from the conversation history."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    )

    # ── Load conversation history from DB ────────────────────────────────────
    history = get_session_messages(db, session_id)
    history_content = _messages_to_content(history)

    # If the last history message is the current user message (already saved to DB),
    # exclude it to avoid duplication since we add it explicitly below
    if history_content and message:
        last = history_content[-1]
        if (
            last.role == "user"
            and last.parts
            and any(p.text == message for p in last.parts)
        ):
            history_content = history_content[:-1]

    messages: list[types.Content] = history_content + [
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    ]

    tool_round = 0

    # ── Keepalive task — prevents proxy/connection idle timeouts ─────────────────
    # Background task puts SSE comments in queue; main loop drains them between rounds.
    keepalive_queue: asyncio.Queue[str] = asyncio.Queue()
    keepalive_task = asyncio.create_task(_keepalive_pusher(keepalive_queue))

    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            while tool_round < MAX_TOOL_ROUNDS:
                logger.bind(
                    event="stream_round_start",
                    service="chat",
                    trace_id=trace_id,
                    tool_round=tool_round + 1,
                    max_tool_rounds=MAX_TOOL_ROUNDS,
                ).info(f"Tool round {tool_round + 1}")

                # ── Drain any pending keepalive comments ───────────────────────────
                while not keepalive_queue.empty():
                    yield keepalive_queue.get_nowait()

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[*ALL_TOOLS, finalize_trip_plan_decl],
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.MEDIUM,
                    ),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                )

                # ── Step 1: Drain the full stream first ──────────────────────────
                # Retry loop handles transient SOCKS5 proxy/idle timeouts (60s default).
                # The google-genai client uses httpx which raises on server disconnect.
                round_text_parts: list[types.Part] = []
                round_func_parts: list[types.Part] = []
                chunks: list = []
                stream_error: Exception | None = None

                # ── Log exact LLM request for performance analysis ───────────────────
                def _serialize_content_for_log(c: types.Content) -> dict:
                    """Serialize types.Content to a dict for logging."""
                    parts_list = []
                    for p in c.parts or []:
                        if p.text:
                            parts_list.append({"text": p.text})
                        elif p.function_call:
                            parts_list.append(
                                {
                                    "function_call": {
                                        "name": p.function_call.name,
                                        "args": dict(p.function_call.args)
                                        if p.function_call.args
                                        else {},
                                    }
                                }
                            )
                        elif p.function_response:
                            parts_list.append(
                                {
                                    "function_response": {
                                        "name": getattr(
                                            p.function_response, "name", None
                                        ),
                                        "response": (
                                            p.function_response.response
                                            if p.function_response
                                            else None
                                        ),
                                    }
                                }
                            )
                        elif p.thought:
                            parts_list.append({"thought": "[thought signature]"})
                    return {"role": c.role, "parts": parts_list}

                messages_log = [_serialize_content_for_log(m) for m in messages]
                config_log = {
                    "system_instruction_length": len(system_instruction)
                    if system_instruction
                    else 0,
                    "tools_count": len(config.tools) if config.tools else 0,
                    "thinking_level": (
                        config.thinking_config.thinking_level.name
                        if config.thinking_config
                        and config.thinking_config.thinking_level
                        else None
                    ),
                }

                logger.bind(
                    event="llm_request",
                    service="chat",
                    trace_id=trace_id,
                    tool_round=tool_round + 1,
                    model=model,
                    messages_count=len(messages),
                    config=config_log,
                    messages_preview=[
                        {
                            **messages_log[i],
                            "parts": [
                                "...".join(
                                    p.get(
                                        "text",
                                        p.get("function_call", {}).get("name", ""),
                                    )
                                    for p in (messages_log[i].get("parts") or [])[:2]
                                )
                            ],
                        }
                        for i in range(len(messages_log))
                    ],
                ).debug(
                    f"🤖 LLM request round {tool_round + 1} | model={model} | "
                    f"messages={len(messages)} | config={config_log}"
                )

                for attempt in range(STREAM_MAX_RETRIES + 1):
                    try:
                        # Use sync client wrapped in asyncio.to_thread to avoid blocking the event loop
                        # (async streaming via client.aio doesn't work with SOCKS5 proxy in some regions)
                        def sync_stream():
                            return client.models.generate_content_stream(
                                model=model,
                                contents=messages,
                                config=config,
                            )

                        stream_gen = await asyncio.to_thread(sync_stream)
                        for chunk in stream_gen:
                            chunks.append(chunk)
                            if chunk.text:
                                round_text_parts.append(
                                    types.Part.from_text(text=chunk.text)
                                )
                                accumulated_text += chunk.text
                                yield SSE({"chunk": chunk.text})
                        break  # Stream completed successfully
                    except Exception as call_err:
                        is_last_attempt = attempt >= STREAM_MAX_RETRIES
                        event_name = (
                            "stream_retry_exhausted"
                            if is_last_attempt
                            else "stream_retry"
                        )
                        log = logger.bind(
                            event=event_name,
                            service="chat",
                            trace_id=trace_id,
                            attempt=attempt + 1,
                            max_retries=STREAM_MAX_RETRIES,
                            error_type=type(call_err).__name__,
                            error_message=str(call_err),
                        )
                        if is_last_attempt:
                            log.error(
                                f"Stream attempt {attempt + 1} failed: {call_err}"
                            )
                        else:
                            log.warning(
                                f"Stream attempt {attempt + 1} failed: {call_err}"
                            )
                        if attempt < STREAM_MAX_RETRIES:
                            # Emit retry_info (not error) so frontend knows to keep listening
                            yield SSE(
                                {
                                    "retry_info": f"{attempt + 1}/{STREAM_MAX_RETRIES}",
                                    "error": f"Connection lost, retrying... ({str(call_err)[:80]})",
                                }
                            )
                            continue
                        # All retries exhausted — store error for outer handler
                        stream_error = call_err
                        break

                # Log token usage from the last chunk of the stream
                if chunks:
                    last_chunk = chunks[-1]
                    usage = getattr(last_chunk, "usage_metadata", None)
                    if usage:
                        logger.bind(
                            event="llm_tokens",
                            service="chat",
                            trace_id=trace_id,
                            tool_round=tool_round + 1,
                            prompt_tokens=usage.prompt_token_count,
                            completion_tokens=usage.candidates_token_count,
                            total_tokens=usage.total_token_count,
                        ).debug(
                            f"🤖 LLM tokens round {tool_round + 1}: "
                            f"prompt={usage.prompt_token_count} "
                            f"completion={usage.candidates_token_count} "
                            f"total={usage.total_token_count}"
                        )

                if stream_error:
                    # Raise to outer exception handler for consistent error handling
                    raise stream_error

                # ── Extract consolidated function calls and thoughts from drained chunks ────
                # NOTE: We must use chunk.candidates[0].content.parts to get full Part
                # objects (which include thought_signature), NOT chunk.function_calls
                # which only extracts the FunctionCall objects and loses the signature.
                for chunk in chunks:
                    if (
                        chunk.candidates
                        and chunk.candidates[0].content
                        and chunk.candidates[0].content.parts
                    ):
                        for part in chunk.candidates[0].content.parts:
                            if part.thought:
                                # Emit intermediate thought events for frontend display
                                yield SSE({"model_thought": part.thought})
                            elif part.function_call:
                                # Preserve the full Part with thought_signature
                                round_func_parts.append(part)
                            elif part.text:
                                # Text parts are already handled above via chunk.text
                                pass

                # ── DB write: once per round ─────────────────────────────────────
                _flush_text()

                # ── Exit if no function calls (pure text response) ────────────────
                if not round_func_parts:
                    if not round_text_parts:
                        update_message_content(
                            db,
                            assistant_msg.id,
                            "Empty response from model.",
                            message_type="error",
                        )
                        yield SSE(
                            {
                                "message_type": "error",
                                "error": "Empty response from model.",
                            }
                        )
                        yield SSE({"done": True})
                        return
                    logger.bind(
                        event="stream_complete",
                        service="chat",
                        trace_id=trace_id,
                        session_id=session_id,
                        total_rounds=tool_round + 1,
                        accumulated_text_len=len(accumulated_text),
                    ).info("LLM stream completed — text response only")
                    yield SSE({"done": True})
                    return

                # ── Step 2: Detect finalize_trip_plan ────────────────────────────
                finalize_fc = next(
                    (
                        fc
                        for fc in round_func_parts
                        if getattr(getattr(fc, "function_call", None), "name", None)
                        == "finalize_trip_plan"
                    ),
                    None,
                )

                if finalize_fc:
                    logger.bind(
                        event="finalize_trip_plan_called",
                        service="chat",
                        trace_id=trace_id,
                        tool_round=tool_round,
                    ).info("🎯 finalize_trip_plan called — generating trip itinerary")
                    fc_call = finalize_fc.function_call
                    if fc_call is None:
                        tool_round += 1
                        continue

                    # Append model turn BEFORE calling finalize_trip_plan
                    model_parts = list(round_text_parts) + list(round_func_parts)
                    if model_parts:
                        messages.append(types.Content(role="model", parts=model_parts))

                    result = await finalize_trip_plan(
                        preferences=preferences,
                        messages=messages,
                    )

                    if "error" in result:
                        # Feed error back to agent as a function response — let it recover
                        messages.append(
                            types.Content(
                                role="function",
                                parts=[
                                    types.Part.from_function_response(
                                        name="finalize_trip_plan",
                                        response={"error": result["error"]},
                                    )
                                ],
                            )
                        )
                        tool_round += 1
                        continue

                    yield SSE(
                        {"message_type": "finalizing", "status": "generating_trip_plan"}
                    )
                    yield SSE(
                        {"message_type": "itinerary", "itinerary": result["itinerary"]}
                    )
                    itinerary_data = result["itinerary"]

                    # Detailed log of full itinerary for debugging
                    itinerary_json = json.dumps(itinerary_data, ensure_ascii=False)
                    logger.bind(
                        event="itinerary_detail",
                        service="chat",
                        trace_id=trace_id,
                        itinerary=itinerary_json,
                    ).debug(f"📋 Full itinerary data: {itinerary_json}")

                    logger.bind(
                        event="itinerary_generated",
                        service="chat",
                        trace_id=trace_id,
                        destination=itinerary_data.get("destination"),
                        start_date=itinerary_data.get("start_date"),
                        end_date=itinerary_data.get("end_date"),
                        days_count=len(itinerary_data.get("daily_itinerary", [])),
                    ).info(
                        f"🎉 Itinerary generated: {itinerary_data.get('destination')} "
                        f"({itinerary_data.get('start_date')} to {itinerary_data.get('end_date')})"
                    )

                    # Store itinerary in DB — JSON wrapper + message_type column
                    update_message_content(
                        db,
                        assistant_msg.id,
                        json.dumps(
                            {"__type": "itinerary", "data": result["itinerary"]}
                        ),
                        message_type="itinerary",
                    )

                    # Auto-save trip if user is authenticated.
                    # Guests (user_id is None) are not allowed to save trips.
                    if user_id is not None:
                        try:
                            itinerary_model = TripItinerary.model_validate(
                                result["itinerary"]
                            )
                            save_trip(db, user_id, session_id, itinerary_model)
                            yield SSE({"trip_saved": True})
                            logger.bind(
                                event="trip_auto_saved",
                                service="chat",
                                trace_id=trace_id,
                                user_id=str(user_id),
                                session_id=session_id,
                            ).info("Trip auto-saved")
                        except Exception as e:
                            logger.bind(
                                event="trip_auto_save_error",
                                service="chat",
                                trace_id=trace_id,
                                error=str(e),
                            ).warning(f"Failed to auto-save trip: {e}")
                    else:
                        logger.bind(
                            event="trip_auto_save_skipped_guest",
                            service="chat",
                            trace_id=trace_id,
                            session_id=session_id,
                        ).info("Trip auto-save skipped for guest user")

                    logger.bind(
                        event="stream_complete",
                        service="chat",
                        trace_id=trace_id,
                        session_id=session_id,
                        total_rounds=tool_round + 1,
                    ).info("LLM stream completed — itinerary generated")
                    yield SSE({"done": True})
                    return

                # ── Step 3: Append model turn, then execute regular tools ────────
                model_parts = list(round_text_parts) + list(round_func_parts)
                if model_parts:
                    messages.append(types.Content(role="model", parts=model_parts))

                for part in round_func_parts:
                    fc = getattr(part, "function_call", None)
                    if not fc:
                        continue
                    tool_name = fc.name
                    if tool_name == "finalize_trip_plan":
                        continue  # Already handled in Step 2
                    args = dict(fc.args) if fc.args else {}

                    logger.bind(event="tool_call", service="chat", tool=tool_name).info(
                        f"⚡ {tool_name}()"
                    )
                    yield SSE({"tool_call": tool_name, "args": args})

                    tool_fn = TOOL_MAP.get(tool_name)
                    if tool_fn:
                        try:
                            result = await tool_fn(**args)
                            logger.bind(
                                event="tool_done", service="chat", tool=tool_name
                            ).info(f"✅ {tool_name} done")
                        except Exception as e:
                            logger.bind(
                                event="tool_error",
                                service="chat",
                                tool=tool_name,
                                error=str(e),
                            ).error(f"❌ {tool_name} failed: {e}")
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                        logger.bind(
                            event="tool_unknown", service="chat", tool=tool_name
                        ).warning(f"❓ {tool_name}: unknown")

                    yield SSE({"tool_result": tool_name, "result": result})

                    # Detailed log of full tool response for debugging — no truncation
                    try:
                        result_json = json.dumps(result, ensure_ascii=False)
                    except Exception:
                        result_json = str(result)
                    logger.bind(
                        event="tool_response",
                        service="chat",
                        trace_id=trace_id,
                        tool=tool_name,
                        args=args,
                        result=result_json,
                    ).debug(f"📥 {tool_name} result: {result_json}")

                    # role="function" for Gemini tool responses
                    messages.append(
                        types.Content(
                            role="function",
                            parts=[
                                types.Part.from_function_response(
                                    name=tool_name,
                                    response=result,
                                )
                            ],
                        )
                    )

                    # Persist tool result to DB so it's available in future requests
                    _save_tool_result_to_db(
                        db, assistant_msg.session_id, tool_name, args, result
                    )

                tool_round += 1

            # Max tool rounds reached
            update_message_content(
                db,
                assistant_msg.id,
                "Max tool rounds reached — please try a more specific request.",
                message_type="error",
            )
            yield SSE(
                {
                    "message_type": "error",
                    "error": "Max tool rounds reached — please try a more specific request.",
                }
            )
            yield SSE({"done": True})

    except asyncio.TimeoutError:
        update_message_content(
            db,
            assistant_msg.id,
            "Request timed out. Please try again.",
            message_type="error",
        )
        yield SSE(
            {"message_type": "error", "error": "Request timed out. Please try again."}
        )
        yield SSE({"done": True})
    except Exception as e:
        import traceback as tb

        tb_str = tb.format_exc()
        # Build a snapshot of the current state for debugging
        msg_snapshot = [
            {"role": str(m.role), "parts_len": len(m.parts) if m.parts else 0}
            for m in messages
        ]

        logger.bind(
            event="stream_error",
            service="chat",
            trace_id=trace_id,
            error_type=type(e).__name__,
            error_message=str(e),
            model=model,
            proxy_enabled=settings.LLM_PROXY_ENABLED,
            messages_count=len(messages),
            messages_snapshot=msg_snapshot,
            traceback=tb_str,
        ).error(f"Stream error: {e}")

        error_msg = _format_error_message(e)
        update_message_content(
            db,
            assistant_msg.id,
            error_msg,
            message_type="error",
        )
        yield SSE({"message_type": "error", "error": error_msg})
        yield SSE({"done": True})
    finally:
        # Cancel the keepalive background task when the stream ends
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass
