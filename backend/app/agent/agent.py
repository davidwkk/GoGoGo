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
) -> str:
    """
    Run the agent loop in chat (non-structured) mode.
    Returns plain text response.
    """
    logger.info(f"[AGENT] run_agent called with message: {user_message[:100]}...")
    logger.info(f"[AGENT] Preferences: {preferences}")
    client = _get_client()
    system_instruction = _build_system_prompt(preferences)
    logger.info(f"[AGENT] System instruction: {system_instruction[:200]}...")

    messages: list[types.Content] = list(conversation_history or [])

    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)],
    )
    messages.append(user_content)

    for iteration in range(MAX_ITERATIONS):
        logger.info(f"[AGENT] Iteration {iteration + 1}/{MAX_ITERATIONS}")
        logger.debug(f"[AGENT] Message history length: {len(messages)}")

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=ALL_TOOLS,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            ),
        )

        logger.info(
            f"[AGENT] Calling generate_content with model: {settings.GEMINI_LITE_MODEL}"
        )
        response = client.models.generate_content(
            model=settings.GEMINI_LITE_MODEL,
            contents=messages,
            config=config,
        )
        logger.info(
            f"[AGENT] Response received. Has function_calls: {bool(response.function_calls)}"
        )
        if response.text:
            logger.info(
                f"[AGENT] Response text (first 200 chars): {response.text[:200]}"
            )

        # Append model content as-is (preserves thought_signature)
        if response.candidates and response.candidates[0].content:
            logger.debug("[AGENT] Appending candidate content to history")
            messages.append(response.candidates[0].content)

        # Handle function calls
        if response.function_calls:
            logger.info(
                f"[AGENT] Handling {len(response.function_calls)} function call(s)"
            )
            for fc in response.function_calls:
                tool_name = fc.name
                if not tool_name:
                    continue
                args = dict(fc.args) if fc.args else {}
                logger.info(
                    f"[AGENT] Tool call: {tool_name} with args: {str(args)[:200]}"
                )
                log_tool_call(tool_name, args)

                # Execute tool
                tool_fn = _TOOL_MAP.get(tool_name)
                if tool_fn:
                    try:
                        result = await tool_fn(**args)
                        logger.info(
                            f"[AGENT] Tool {tool_name} result: {str(result)[:200]}"
                        )
                    except Exception as e:
                        logger.error(
                            f"[AGENT] Tool {tool_name} exception: {type(e).__name__}: {str(e)}"
                        )
                        result = {"error": str(e)}
                else:
                    logger.warning(f"[AGENT] Unknown tool: {tool_name}")
                    result = {"error": f"Unknown tool: {tool_name}"}

                log_tool_response(tool_name, result)

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
            token_usage = _log_usage(response)
            logger.info(f"[AGENT] Final response (text only): {text[:200]}...")
            log_agent_finish(text, token_usage)
            return text

    # Max iterations reached
    logger.warning("[AGENT] Max iterations reached")
    return "I ran out of time planning your trip. Please try again."


async def run_agent_structured(
    user_message: str,
    conversation_history: list[types.Content] | None = None,
    preferences: dict | None = None,
) -> TripItinerary:
    """
    Run the full agent loop then end with a structured generate_content call
    that returns TripItinerary.

    Two-phase approach:
    Phase 1: Tool-calling loop (no response_schema) — gather all data via tools.
    Phase 2: Separate generate_content WITH response_json_schema → TripItinerary.
    """
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
        logger.debug(
            f"[AGENT] Iteration {iteration + 1}/{MAX_ITERATIONS} (tool gathering)"
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=ALL_TOOLS,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            ),
        )

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
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
                log_tool_call(tool_name, args)

                tool_fn = _TOOL_MAP.get(tool_name)
                if tool_fn:
                    try:
                        result = await tool_fn(**args)
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}

                log_tool_response(tool_name, result)

                fn_response = types.Part.from_function_response(
                    name=tool_name,
                    response=result,
                )
                tool_content = types.Content(role="tool", parts=[fn_response])
                messages.append(tool_content)
        else:
            # No more function calls — tool gathering complete
            logger.info("[AGENT] Tool gathering complete, moving to structured output")
            break
    else:
        logger.warning("[AGENT] Max iterations reached during tool gathering")

    # ── Phase 2: Structured output ─────────────────────────────────────────
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
        model=settings.GEMINI_MODEL,
        contents=all_contents,
        config=config,
    )

    raw_text = response.text
    text = raw_text if raw_text is not None else ""
    token_usage = _log_usage(response)
    log_agent_finish(text, token_usage)

    try:
        return TripItinerary.model_validate_json(text)
    except Exception as e:
        logger.error(
            f"[AGENT] Failed to parse TripItinerary: {e} | response={text[:500]}"
        )
        raise
