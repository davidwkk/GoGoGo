"""Streaming service — unified LLM loop with finalize_trip_plan."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from uuid import uuid4

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
            except Exception:
                pass
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
    return PriceRange(min=round(pr.min / 100) * 100, max=round(pr.max / 100) * 100)


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
    The 'messages' parameter is the accumulated conversation state from the streaming loop.
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
        "the user's original request in the conversation history.\n"
        "IMPORTANT: For each flight, you MUST include the booking_url from the search_flights "
        "tool results. Round all budget values (total_hkd, flights_hkd, hotels_hkd, "
        "activities_hkd) to the nearest multiple of 100 (e.g., 3000, 5200, 10800).\n"
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
    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=final_contents,
        config=config,
    )

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
        '- FLIGHTS: default ROUND-TRIP; one-way only if user says "one-way".\n'
        "- ATTRACTIONS: at least 1 per travel day (3-day trip = 3+ attractions).\n"
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
        "  4. Once confirmed, call ALL of: search_flights, search_hotels, get_weather, get_attraction (1+ per travel day).\n"
        "  5. After ALL tools return, call finalize_trip_plan() with NO arguments — it reads the conversation to extract trip details.\n"
        "     Do NOT return text instead.\n\n"
        "## Enrichment Fields\n"
        "Populate ALL of the following fields from tool results:\n"
        "- Activity: opening_hours, admission_fee_hkd, rating, review_count, tips, image_url, thumbnail_url, booking_url, address\n"
        "- Hotel: star_rating, guest_rating, image_url, embed_map_url\n"
        "- Flight: duration_minutes, cabin_class\n"
        "- TripItinerary: estimated_total_budget_hkd (compute from flights + hotels + activities)\n"
        "- DayPlan: theme, notes, estimated_daily_budget_hkd\n\n"
        "## Rules\n"
        "- Never invent dates, destinations, or prices.\n"
        "- Use HKD for Asian destinations.\n"
        "- Markdown formatting.\n"
        f"{prefs_section}"
    )


SSE_KEEPALIVE = ": keepalive\n\n"


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
        types.HttpOptionsDict(client_args={"proxy": settings.SOCKS5_PROXY_URL})
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
            "search_flights, search_hotels, get_weather, get_attraction (at least once each). "
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
                try:
                    # Use sync client wrapped in asyncio.to_thread to avoid blocking the event loop
                    # (async streaming via client.aio doesn't work with SOCKS5 proxy in some regions)
                    def sync_stream():
                        return client.models.generate_content_stream(
                            model=model,
                            contents=messages,
                            config=config,
                        )

                    stream = await asyncio.to_thread(sync_stream)
                except Exception as call_err:
                    logger.bind(
                        event="generate_content_stream_error",
                        service="chat",
                        trace_id=trace_id,
                        error_type=type(call_err).__name__,
                        error_message=str(call_err),
                        model=model,
                        messages_count=len(messages),
                        messages_roles=[m.role for m in messages],
                        system_instruction_len=len(system_instruction),
                    ).error(f"generate_content_stream failed: {call_err}")
                    raise

                round_text_parts: list[types.Part] = []
                round_func_parts: list[types.Part] = []
                chunks: list = []

                for chunk in stream:
                    chunks.append(chunk)
                    if chunk.text:
                        round_text_parts.append(types.Part.from_text(text=chunk.text))
                        accumulated_text += chunk.text
                        yield SSE({"chunk": chunk.text})

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
