"""Gemini 3 Flash agent — tool-calling loop + structured output.

Key implementation notes:
- MAX_ITERATIONS = 5 to prevent infinite loops
- Iterate ALL function_calls: response.function_calls may have multiple entries
- Append response.candidates[0].content as-is to messages (preserves thought_signature)
- response_schema ONLY on final generate_content call (not mid-loop)
- Manual history management: append model turns AND tool responses between iterations
- System prompt: prefs_section = f"User preferences: {preferences}" if preferences else ""
"""

from __future__ import annotations

import time
from google.genai import Client, types
from loguru import logger

from app.agent.callbacks import log_agent_finish, log_tool_call, log_tool_response
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

# Map tool names to callables
_TOOL_MAP = {
    "get_attraction": get_attraction,
    "get_weather": get_weather,
    "search_web": search_web,
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "get_transport": get_transport,
    "build_embed_url": build_embed_url,
}

MAX_ITERATIONS = 5

# Demo-grade client — single instance reused
_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        api_key = settings.GEMINI_API_KEY
        if settings.LLM_PROXY_ENABLED:
            logger.info(f"[AGENT] Using VPN proxy: {settings.SOCKS5_PROXY_URL}")
            http_opts = types.HttpOptionsDict(
                client_args={"proxy": settings.SOCKS5_PROXY_URL}
            )
            _client = Client(api_key=api_key, http_options=http_opts)
        else:
            _client = Client(api_key=api_key)
    return _client


def _log_usage(response) -> dict | None:
    """Extract and log token usage from response."""
    try:
        usage = response.usage_metadata
        if usage:
            token_usage = {
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "candidates_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            }
            logger.bind(
                event="token_usage",
                **token_usage,
            ).info("Token usage")
            return token_usage
    except Exception:
        pass
    return None


def _build_system_prompt(preferences: dict | None = None) -> str:
    prefs_section = f"User preferences: {preferences}" if preferences else ""
    return (
        "You are a helpful travel planning assistant backed by real-time data. "
        "IMPORTANT RULES:\n"
        "1. EVERY itinerary item (flight, hotel, attraction, transport, weather) MUST be "
        "fetched via a tool call — never invent prices, times, or names.\n"
        "2. If you don't have data for something, use the search tool first.\n"
        "3. When a user asks to plan a trip, you MUST call the relevant tools to gather:\n"
        "   - Flights (search_flights)\n"
        "   - Hotels (search_hotels)\n"
        "   - Attractions (get_attraction)\n"
        "   - Weather (get_weather)\n"
        "   - Transport between locations (get_transport)\n"
        "4. Always use HKD for prices when the destination is in Asia.\n"
        "5. Dates should be ISO 8601 format (YYYY-MM-DD).\n"
        f"{prefs_section}"
    )


async def run_agent(
    user_message: str,
    conversation_history: list[types.Content] | None = None,
    preferences: dict | None = None,
    trace_id: str | None = None,
) -> str:
    """
    Run the agent loop in chat (non-structured) mode.
    Returns plain text response.
    """
    model = settings.GEMINI_LITE_MODEL

    start_ms = time.perf_counter() * 1000
    logger.bind(
        event="agent_start",
        service="agent",
        trace_id=trace_id,
        model=model,
        agent_mode="chat",
        user_message_preview=user_message[:100],
    ).info("Agent start")
    client = _get_client()
    system_instruction = _build_system_prompt(preferences)

    messages: list[types.Content] = list(conversation_history or [])

    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)],
    )
    messages.append(user_content)

    for iteration in range(MAX_ITERATIONS):
        logger.bind(
            event="agent_iteration",
            service="agent",
            trace_id=trace_id,
            model=model,
            iteration=iteration + 1,
            max_iterations=MAX_ITERATIONS,
            message_history_len=len(messages),
        ).debug("Agent iteration")

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=ALL_TOOLS,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            ),
        )

        logger.bind(
            event="llm_call",
            service="agent",
            trace_id=trace_id,
            model=model,
            iteration=iteration + 1,
        ).info("Calling generate_content")
        response = client.models.generate_content(
            model=model,
            contents=messages,
            config=config,
        )
        token_usage = _log_usage(response)

        # Append model content as-is (preserves thought_signature)
        if response.candidates and response.candidates[0].content:
            messages.append(response.candidates[0].content)

        # Handle function calls
        if response.function_calls:
            for fc in response.function_calls:
                tool_name = fc.name
                if not tool_name:
                    continue
                args = dict(fc.args) if fc.args else {}
                log_tool_call(
                    tool_name, args, trace_id=trace_id, service="agent", model=model
                )

                # Execute tool
                tool_fn = _TOOL_MAP.get(tool_name)
                tool_start = time.perf_counter() * 1000
                tool_duration_ms: float | None = None
                if tool_fn:
                    try:
                        result = await tool_fn(**args)
                        tool_duration_ms = time.perf_counter() * 1000 - tool_start
                        logger.bind(
                            event="tool_result",
                            service="agent",
                            trace_id=trace_id,
                            model=model,
                            tool=tool_name,
                            tool_result_preview=str(result)[:200],
                            tool_duration_ms=round(tool_duration_ms, 1),
                        ).info("Tool result")
                    except Exception as e:
                        tool_duration_ms = time.perf_counter() * 1000 - tool_start
                        logger.bind(
                            event="tool_error",
                            service="agent",
                            trace_id=trace_id,
                            model=model,
                            tool=tool_name,
                            tool_error=f"{type(e).__name__}: {str(e)}",
                            tool_duration_ms=round(tool_duration_ms, 1),
                        ).error("Tool exception")
                        result = {"error": str(e)}
                else:
                    logger.bind(
                        event="tool_error",
                        service="agent",
                        trace_id=trace_id,
                        model=model,
                        tool=tool_name,
                        tool_error=f"Unknown tool: {tool_name}",
                    ).warning("Unknown tool")
                    result = {"error": f"Unknown tool: {tool_name}"}

                log_tool_response(
                    tool_name,
                    result,
                    duration_ms=tool_duration_ms,
                    trace_id=trace_id,
                    service="agent",
                    model=model,
                )

                # Build tool response part
                fn_response = types.Part.from_function_response(
                    name=tool_name,
                    response=result,
                )
                tool_content = types.Content(role="tool", parts=[fn_response])
                messages.append(tool_content)
        else:
            # No function calls — plain text response, loop done
            text = response.text or ""
            latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)
            logger.bind(
                event="agent_finish",
                service="agent",
                trace_id=trace_id,
                model=model,
                agent_mode="chat",
                iterations=iteration + 1,
                max_iterations=MAX_ITERATIONS,
                response_preview=text[:200],
                token_usage=token_usage,
                latency_ms=latency_ms,
            ).info("Agent finished")
            return text

    # Max iterations reached
    latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)
    logger.bind(
        event="agent_finish",
        service="agent",
        trace_id=trace_id,
        model=model,
        agent_mode="chat",
        iterations=MAX_ITERATIONS,
        max_iterations=MAX_ITERATIONS,
        latency_ms=latency_ms,
        tool_error="max_iterations_reached",
    ).warning("Agent max iterations")
    return "I ran out of time planning your trip. Please try again."


async def run_agent_structured(
    user_message: str,
    conversation_history: list[types.Content] | None = None,
    preferences: dict | None = None,
    trace_id: str | None = None,
) -> TripItinerary:
    """
    Run the full agent loop then end with a structured generate_content call
    that returns TripItinerary.

    Two-phase approach:
    Phase 1: Tool-calling loop (no response_schema) — gather all data via tools.
    Phase 2: Separate generate_content WITH response_json_schema → TripItinerary.
    """
    model = settings.GEMINI_MODEL
    start_ms = time.perf_counter() * 1000

    logger.bind(
        event="agent_start",
        service="agent",
        trace_id=trace_id,
        model=model,
        agent_mode="structured",
        user_message_preview=user_message[:100],
    ).info("Agent start")

    client = _get_client()
    system_instruction = _build_system_prompt(preferences)

    messages: list[types.Content] = list(conversation_history or [])

    user_content = types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text=user_message
                + "\n\nBased on all the information gathered above, create a detailed "
                "trip itinerary with the TripItinerary structure."
            )
        ],
    )
    messages.append(user_content)

    # ── Phase 1: Tool-calling loop ──────────────────────────────────────────
    for iteration in range(MAX_ITERATIONS):
        logger.bind(
            event="agent_iteration",
            service="agent",
            trace_id=trace_id,
            model=model,
            iteration=iteration + 1,
            max_iterations=MAX_ITERATIONS,
            phase="tool_gathering",
        ).debug("Agent iteration")

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=ALL_TOOLS,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            ),
        )

        logger.bind(
            event="llm_call",
            service="agent",
            trace_id=trace_id,
            model=model,
            iteration=iteration + 1,
            phase="tool_gathering",
        ).info("Calling generate_content")
        response = client.models.generate_content(
            model=model,
            contents=messages,
            config=config,
        )
        _log_usage(response)

        if response.candidates and response.candidates[0].content:
            messages.append(response.candidates[0].content)

        if response.function_calls:
            for fc in response.function_calls:
                tool_name = fc.name
                if not tool_name:
                    continue
                args = dict(fc.args) if fc.args else {}
                log_tool_call(
                    tool_name, args, trace_id=trace_id, service="agent", model=model
                )

                tool_fn = _TOOL_MAP.get(tool_name)
                tool_start = time.perf_counter() * 1000
                if tool_fn:
                    try:
                        result = await tool_fn(**args)
                        tool_duration_ms = time.perf_counter() * 1000 - tool_start
                    except Exception as e:
                        tool_duration_ms = time.perf_counter() * 1000 - tool_start
                        result = {"error": str(e)}
                else:
                    tool_duration_ms = None
                    result = {"error": f"Unknown tool: {tool_name}"}

                log_tool_response(
                    tool_name,
                    result,
                    duration_ms=tool_duration_ms,
                    trace_id=trace_id,
                    service="agent",
                    model=model,
                )

                fn_response = types.Part.from_function_response(
                    name=tool_name,
                    response=result,
                )
                tool_content = types.Content(role="tool", parts=[fn_response])
                messages.append(tool_content)
        else:
            # No more function calls — tool gathering complete
            logger.bind(
                event="phase_complete",
                service="agent",
                trace_id=trace_id,
                model=model,
                phase="tool_gathering",
                iterations=iteration + 1,
                max_iterations=MAX_ITERATIONS,
            ).info("Tool gathering complete, moving to structured output")
            break
    else:
        logger.bind(
            event="agent_finish",
            service="agent",
            trace_id=trace_id,
            model=model,
            agent_mode="structured",
            iterations=MAX_ITERATIONS,
            max_iterations=MAX_ITERATIONS,
            tool_error="max_iterations_reached",
        ).warning("Agent max iterations")

    # ── Phase 2: Structured output ─────────────────────────────────────────
    logger.bind(
        event="llm_call",
        service="agent",
        trace_id=trace_id,
        model=model,
        phase="structured_output",
    ).info("Calling structured generate_content")
    structured_prompt = types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text="Based on all the information gathered in the conversation above, "
                "produce a complete trip itinerary as a TripItinerary JSON object."
            )
        ],
    )
    # Include all previous messages for context
    all_contents = messages + [structured_prompt]

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_json_schema=TripItinerary.model_json_schema(),
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL
        ),
    )

    response = client.models.generate_content(
        model=model,
        contents=all_contents,
        config=config,
    )

    raw_text = response.text
    text = raw_text if raw_text is not None else ""
    token_usage = _log_usage(response)
    latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)

    log_agent_finish(
        text,
        token_usage=token_usage,
        latency_ms=latency_ms,
        trace_id=trace_id,
        service="agent",
        model=model,
        agent_mode="structured",
    )

    try:
        return TripItinerary.model_validate_json(text)
    except Exception as e:
        logger.bind(
            event="parse_error",
            service="agent",
            trace_id=trace_id,
            model=model,
            error=f"{type(e).__name__}: {e}",
            response_preview=text[:500],
            latency_ms=latency_ms,
        ).error("Failed to parse TripItinerary")
        raise
