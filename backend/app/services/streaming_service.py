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
from app.schemas.itinerary import TripItinerary
from app.services.message_service import append_message, update_message_content

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
# finalize_trip_plan — local function intercepted by name in the streaming loop
# ──────────────────────────────────────────────────────────────────────────────


async def finalize_trip_plan(
    destination: str,
    start_date: str,
    end_date: str,
    purpose: str,
    group_type: str,
    group_size: int,
    preferences: dict | None = None,
    messages: list[types.Content] | None = None,
) -> dict:
    """
    Produces a structured TripItinerary from all information already gathered
    in the conversation. Does NOT call external APIs — all trip data was
    already fetched by the agent during the information gathering phase.

    Makes exactly ONE generate_content() call with response_json_schema=TripItinerary.
    The 'messages' parameter is the accumulated conversation state from the streaming loop.
    """
    # ── Validation guard: required trip parameters ──────────────────────────────
    if not all([destination, start_date, end_date, purpose, group_type]):
        return {
            "error": (
                "Missing required trip parameters. "
                "Required: destination, start_date, end_date, purpose, group_type. "
                "Ask the user for any missing information."
            )
        }

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
        f"Trip parameters:\n"
        f"  Destination: {destination}\n"
        f"  Dates: {start_date} to {end_date}\n"
        f"  Purpose: {purpose}\n"
        f"  Group: {group_type} ({group_size} people)\n\n"
        "All necessary data (flights, hotels, attractions, weather, transport) "
        "was already fetched by the agent and is available in the conversation history below. "
        "Use that data to populate every field of the itinerary.\n"
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
        types.Content(role="user", parts=[types.Part.from_text(context_prompt)])  # type: ignore[reportCallIssue]
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

    return {"itinerary": itinerary.model_dump(mode="json")}


# ──────────────────────────────────────────────────────────────────────────────
# Unified streaming loop
# ──────────────────────────────────────────────────────────────────────────────


def _build_system_instruction(preferences: dict | None = None) -> str:
    prefs_section = f"User preferences: {preferences}" if preferences else ""
    return (
        "You are a travel planning assistant. Your goal is to help users plan trips.\n\n"
        "During the conversation:\n"
        "- Use get_weather, search_flights, search_hotels, get_attraction, get_transport, search_web\n"
        "  to answer specific questions or gather trip information.\n"
        "- If any required trip information is missing (destination, dates, purpose,\n"
        "  group details), ask the user for it before proceeding.\n\n"
        "**Before calling finalize_trip_plan, ensure you have called ALL of:**\n"
        "  1. search_flights (at least once)\n"
        "  2. search_hotels (at least once)\n"
        "  3. get_weather (at least once)\n"
        "  4. get_attraction (at least once)\n\n"
        "**If any of these have not been called, call them first, then call finalize_trip_plan.**\n"
        "**Do NOT summarize the trip in text. Always use finalize_trip_plan to produce the final plan.**\n\n"
        "TRIGGER finalize_trip_plan when:\n"
        '- User says "generate the plan", "create the itinerary", "plan my trip", etc.\n'
        '- OR you asked "shall I generate the plan now?" and user confirmed "yes"\n\n'
        'Do NOT trigger on "save to my trips" — that is a separate UI action.\n\n'
        "IMPORTANT:\n"
        "- finalize_trip_plan does NOT call external APIs — it formats data already gathered.\n"
        "- Do NOT call finalize_trip_plan with incomplete or invented parameters.\n"
        "- Never invent dates, destinations, or prices.\n"
        "- Always use HKD for prices when the destination is in Asia.\n"
        "- Dates should be ISO 8601 format (YYYY-MM-DD).\n"
        "- Format your responses using Markdown (headers, bold, lists, code blocks).\n"
        f"{prefs_section}"
    )


def SSE(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


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
            "Call this when you have all required trip information (destination, dates, purpose, "
            "group details) and the user wants a complete trip itinerary. "
            "Before calling this function, ensure you have called ALL of: "
            "search_flights, search_hotels, get_weather, get_attraction (at least once each). "
            "Do NOT call this with incomplete or invented parameters."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination city"},
                "start_date": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)",
                },
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "purpose": {"type": "string", "description": "Purpose of the trip"},
                "group_type": {
                    "type": "string",
                    "description": "Type of group (solo, couple, family, friends, business)",
                },
                "group_size": {"type": "integer", "description": "Number of people"},
            },
            "required": [
                "destination",
                "start_date",
                "end_date",
                "purpose",
                "group_type",
                "group_size",
            ],
        },
    )

    messages: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    ]

    tool_round = 0

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

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[*ALL_TOOLS, finalize_trip_plan_decl],
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.MINIMAL,
                        include_thoughts=False,
                    ),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                )

                # ── Step 1: Drain the full stream first ──────────────────────────
                stream = await client.aio.models.generate_content_stream(
                    model=model,
                    contents=messages,
                    config=config,
                )

                round_text_parts: list[types.Part] = []
                round_func_parts: list[types.Part] = []
                chunks: list = []

                async for chunk in stream:
                    chunks.append(chunk)
                    if chunk.text:
                        round_text_parts.append(types.Part.from_text(text=chunk.text))
                        accumulated_text += chunk.text
                        yield SSE({"chunk": chunk.text})

                # ── Extract consolidated function calls from drained chunks ────────
                for chunk in chunks:
                    if chunk.function_calls:
                        for fc in chunk.function_calls:
                            round_func_parts.append(types.Part(function_call=fc))

                # ── DB write: once per round ─────────────────────────────────────
                _flush_text()

                # ── Exit if no function calls (pure text response) ────────────────
                if not round_func_parts:
                    if not round_text_parts:
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
                    fc_call = finalize_fc.function_call
                    if fc_call is None:
                        tool_round += 1
                        continue

                    # Append model turn BEFORE calling finalize_trip_plan
                    model_parts = list(round_text_parts) + list(round_func_parts)
                    if model_parts:
                        messages.append(types.Content(role="model", parts=model_parts))

                    fc_args: dict = dict(fc_call.args) if fc_call.args else {}
                    result = await finalize_trip_plan(
                        **fc_args,
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
                            ).error(f"❌ {tool_name} failed")
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

                tool_round += 1

            # Max tool rounds reached
            yield SSE(
                {
                    "message_type": "error",
                    "error": "Max tool rounds reached — please try a more specific request.",
                }
            )
            yield SSE({"done": True})

    except asyncio.TimeoutError:
        yield SSE(
            {"message_type": "error", "error": "Request timed out. Please try again."}
        )
        yield SSE({"done": True})
    except Exception as e:
        import traceback

        logger.bind(
            event="stream_error",
            service="chat",
            trace_id=trace_id,
            error=f"{type(e).__name__}: {e}",
            traceback=traceback.format_exc(),
        ).error("Stream error")
        yield SSE({"message_type": "error", "error": f"An error occurred: {e}"})
        yield SSE({"done": True})
