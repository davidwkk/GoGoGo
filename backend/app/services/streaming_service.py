"""Streaming service — orchestrates LLM, tools, DB persistence, and SSE formatting."""

import asyncio
import json
import time as time_mod
from typing import AsyncIterator
from uuid import uuid4

from google.genai import Client, types
from loguru import logger
from sqlalchemy.orm import Session

from app.agent.tools import (
    ALL_TOOLS,
    build_embed_url,
)
from app.agent.tools.attractions import get_attraction
from app.agent.tools.flights import search_flights
from app.agent.tools.hotels import search_hotels
from app.agent.tools.search import search_web
from app.agent.tools.transport import get_transport
from app.agent.tools.weather import get_weather
from app.core.config import settings
from app.services.message_service import append_message, update_message_content
from app.utils.stream_utils import _sync_stream_to_async

# Sync tool_map for the Gemini SDK (uses _make_sync wrappers internally)
tool_map = {
    "get_attraction": get_attraction,
    "get_weather": get_weather,
    "search_web": search_web,
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "get_transport": get_transport,
    "build_embed_url": build_embed_url,
}


async def stream_agent_response(
    message: str,
    session_id: int,
    db: Session,
    preferences: dict | None = None,
    trace_id: str | None = None,
) -> AsyncIterator[str]:
    """
    Stream agent thinking + tool calls + text via TRUE SSE streaming.

    Uses generate_content_stream() to receive text chunks as they arrive.
    When function_call parts appear in the stream, executes tools and continues
    the stream with results — all visible to the user in real-time.

    Yields SSE events:
      - chunk:       text content streamed in real-time
      - model_thought: reasoning thoughts (when include_thoughts=True)
      - tool_call:   tool name + args being executed
      - tool_result: tool response (or error)
      - done:        stream complete
      - error:       error message if something fails

    Persists assistant text chunks to the DB as they arrive.
    """
    trace_id = trace_id or str(uuid4())
    model = settings.GEMINI_LITE_MODEL
    start_ms = time_mod.perf_counter() * 1000
    chunk_index = 0

    logger.bind(
        event="stream_start",
        service="chat",
        trace_id=trace_id,
        model=model,
        session_id=session_id,
        user_message_preview=message,
        preferences=preferences,
    ).info("Stream agent thoughts started")

    assistant_msg = append_message(
        db, session_id=session_id, role="assistant", content=""
    )
    assistant_text = ""

    def _elapsed_ms() -> float:
        return round(time_mod.perf_counter() * 1000 - start_ms, 1)

    def _flush_assistant_text() -> None:
        nonlocal assistant_text
        update_message_content(db, assistant_msg.id, assistant_text)

    http_opts = (
        types.HttpOptionsDict(client_args={"proxy": settings.SOCKS5_PROXY_URL})
        if settings.LLM_PROXY_ENABLED
        else None
    )
    client = Client(api_key=settings.GEMINI_API_KEY, http_options=http_opts)

    prefs_section = f"User preferences: {preferences}" if preferences else ""
    system_instruction = (
        "You are a helpful travel planning assistant backed by real-time data. "
        "IMPORTANT RULES:\n"
        "1. EVERY itinerary item (flight, hotel, attraction, transport, weather) MUST be "
        "fetched via a tool call — never invent prices, times, or names.\n"
        "2. If you don't have data for something, use the search tool first.\n"
        "3. When a user asks about weather, you MUST call the get_weather tool.\n"
        "4. Always use HKD for prices when the destination is in Asia.\n"
        "5. Dates should be ISO 8601 format (YYYY-MM-DD).\n"
        "6. Format your responses using Markdown (headers, bold, lists, code blocks) — "
        "it will be rendered on the frontend.\n"
        f"{prefs_section}"
    )

    logger.bind(
        event="system_instruction",
        service="chat",
        trace_id=trace_id,
        system_instruction=system_instruction,
        tools_count=len(ALL_TOOLS),
        tool_names=[t.__name__ for t in ALL_TOOLS],
    ).info("System instruction prepared")

    messages: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        )
    ]

    MAX_TOOL_ROUNDS = 5
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=ALL_TOOLS,
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.HIGH,
            include_thoughts=True,
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    current_messages: list[types.Content] = list(messages)
    tool_round = 0
    total_tool_calls = 0
    prompt_tokens_first_chunk: int | None = None
    cumulative_candidates_tokens = 0
    cumulative_total_tokens = 0

    try:
        while tool_round < MAX_TOOL_ROUNDS:
            logger.bind(
                event="stream_round_start",
                service="chat",
                trace_id=trace_id,
                model=model,
                tool_round=tool_round + 1,
                max_tool_rounds=MAX_TOOL_ROUNDS,
                elapsed_ms=_elapsed_ms(),
            ).info(f"Starting tool round at +{_elapsed_ms()}ms")

            stream = client.models.generate_content_stream(
                model=model,
                contents=current_messages,
                config=config,
            )

            # Phase 1: Stream and collect parts (don't execute tools yet)
            round_text_parts: list[types.Part] = []
            round_func_parts: list[types.Part] = []
            usage: types.GenerateContentResponseUsageMetadata | None = None
            round_finish_reason: str | None = None

            yield f"data: {json.dumps({'status': 'thinking'})}\n\n"

            async for chunk in _sync_stream_to_async(stream):
                chunk_start_ms = _elapsed_ms()
                # Track function call IDs we've already processed from chunk.function_calls
                # to avoid double-counting when the same calls appear in candidate.content.parts
                chunk_function_call_ids: set[str] = set()
                # Map function_call.id -> thought_signature from candidate parts
                thought_signatures: dict[str, bytes] = {}

                # Check for function_calls directly on chunk (not just in candidates)
                chunk_function_calls = getattr(chunk, "function_calls", None)
                if chunk_function_calls:
                    fc_names = [
                        getattr(fc, "name", None) for fc in chunk_function_calls
                    ]
                    logger.bind(
                        event="chunk_function_calls",
                        service="chat",
                        trace_id=trace_id,
                        elapsed_ms=chunk_start_ms,
                        count=len(chunk_function_calls),
                        tools=fc_names,
                    ).info(
                        f"Chunk has {len(chunk_function_calls)} function call(s): {fc_names}"
                    )
                    # First pass: collect thought_signatures from candidate content parts
                    if candidates := chunk.candidates:
                        candidate = candidates[0]
                        if candidate.content and candidate.content.parts:
                            for p in candidate.content.parts:
                                fc = getattr(p, "function_call", None)
                                if fc:
                                    ts = getattr(p, "thought_signature", None)
                                    if ts:
                                        fc_id = getattr(fc, "id", None)
                                        if fc_id:
                                            thought_signatures[fc_id] = ts
                    # Convert chunk-level function calls to Part format
                    for fc in chunk_function_calls:
                        fc_id = getattr(fc, "id", None)
                        if fc_id:
                            chunk_function_call_ids.add(fc_id)
                        ts = thought_signatures.get(fc_id) if fc_id else None
                        part = types.Part(function_call=fc, thought_signature=ts)
                        round_func_parts.append(part)

                # Accumulate usage metadata
                usage = getattr(chunk, "usage_metadata", None)
                if usage:
                    if prompt_tokens_first_chunk is None:
                        prompt_tokens_first_chunk = getattr(
                            usage, "prompt_token_count", None
                        )
                    chunk_cand_tokens = getattr(usage, "candidates_token_count", None)
                    chunk_total_tokens = getattr(usage, "total_token_count", None)
                    if chunk_cand_tokens is not None:
                        cumulative_candidates_tokens = chunk_cand_tokens
                    if chunk_total_tokens is not None:
                        cumulative_total_tokens = chunk_total_tokens

                candidates = chunk.candidates
                if not candidates:
                    continue
                candidate = candidates[0]
                if not candidate.content:
                    continue
                content = candidate.content
                parts = getattr(content, "parts", None)
                if not parts:
                    continue

                finish_reason = (
                    str(candidate.finish_reason)
                    if hasattr(candidate, "finish_reason") and candidate.finish_reason
                    else None
                )
                # Capture for post-stream check
                round_finish_reason = finish_reason

                for part in parts:
                    part_thought = getattr(part, "thought", None)
                    part_text = getattr(part, "text", None)
                    part_func = getattr(part, "function_call", None)
                    thought_sig = getattr(part, "thought_signature", None)

                    if part_thought:
                        if part_text:
                            chunk_index += 1
                            # Truncate long thoughts for log readability
                            preview = part_text[:120].replace("\n", " ")
                            logger.bind(
                                event="chunk_thought",
                                service="chat",
                                trace_id=trace_id,
                                elapsed_ms=chunk_start_ms,
                                chunk_index=chunk_index,
                                length=len(part_text),
                            ).info(f"💭 {preview}...")
                            yield f"data: {json.dumps({'model_thought': part_text})}\n\n"
                        elif thought_sig:
                            logger.bind(
                                event="chunk_thought_sig",
                                service="chat",
                                trace_id=trace_id,
                                elapsed_ms=chunk_start_ms,
                            ).debug(f"Thought sig ({len(thought_sig)} bytes)")
                    elif part_func is not None:
                        # Skip if this function call was already processed from chunk.function_calls
                        fc_id = getattr(part_func, "id", None)
                        if fc_id and fc_id in chunk_function_call_ids:
                            continue
                        chunk_index += 1
                        round_func_parts.append(part)
                        fc_name = getattr(part_func, "name", None) or ""
                        fc_args = dict(part_func.args) if part_func.args else {}
                        logger.bind(
                            event="chunk_func",
                            service="chat",
                            trace_id=trace_id,
                            elapsed_ms=chunk_start_ms,
                            chunk_index=chunk_index,
                            tool=fc_name,
                            args_keys=list(fc_args.keys()) if fc_args else [],
                        ).info(f"🔧 {fc_name}()")
                    elif part_text is not None and part_text != "":
                        chunk_index += 1
                        preview = part_text[:80].replace("\n", " ")
                        logger.bind(
                            event="chunk_text",
                            service="chat",
                            trace_id=trace_id,
                            elapsed_ms=chunk_start_ms,
                            chunk_index=chunk_index,
                            length=len(part_text),
                        ).info(f"✏️  {preview}...")
                        assistant_text += part_text
                        _flush_assistant_text()
                        yield f"data: {json.dumps({'chunk': part_text})}\n\n"
                        round_text_parts.append(part)

                await asyncio.sleep(0)

            # Log what was collected
            fc_names = [
                getattr(getattr(p, "function_call", None), "name", None)
                for p in round_func_parts
            ]
            logger.bind(
                event="stream_round_complete",
                service="chat",
                trace_id=trace_id,
                tool_round=tool_round + 1,
                elapsed_ms=_elapsed_ms(),
                text_parts=len(round_text_parts),
                func_parts=len(round_func_parts),
                func_tools=fc_names,
                assistant_len=len(assistant_text),
            ).info(
                f"Round complete: text_chunks={len(round_text_parts)}, "
                f"tools=[{', '.join(str(n) for n in fc_names)}], "
                f"output_len={len(assistant_text)}"
            )

            # Log usage metadata on final chunk of this round
            if usage:
                cand_tokens = getattr(usage, "candidates_token_count", None)
                total_tokens = getattr(usage, "total_token_count", None)
                logger.bind(
                    event="stream_tokens",
                    service="chat",
                    trace_id=trace_id,
                    elapsed_ms=_elapsed_ms(),
                    prompt=prompt_tokens_first_chunk,
                    candidates=cand_tokens,
                    total=total_tokens,
                ).info(
                    f"Tokens | prompt={prompt_tokens_first_chunk}, total={total_tokens}"
                )

            # Check if LLM is done - if finish_reason is STOP and no function calls, exit early
            if round_finish_reason == "STOP" and not round_func_parts:
                latency_ms = round(time_mod.perf_counter() * 1000 - start_ms, 1)
                _flush_assistant_text()
                logger.bind(
                    event="stream_done",
                    service="chat",
                    trace_id=trace_id,
                    model=model,
                    elapsed_ms=_elapsed_ms(),
                    latency_ms=latency_ms,
                    total_chunks=chunk_index,
                    total_tool_calls=total_tool_calls,
                    prompt_tokens=prompt_tokens_first_chunk,
                    candidates_tokens=cumulative_candidates_tokens,
                    total_tokens=cumulative_total_tokens,
                    assistant_text_length=len(assistant_text),
                ).info(
                    f"Stream completed at +{_elapsed_ms()}ms (LLM done, no more tools) — tokens: prompt={prompt_tokens_first_chunk}, candidates={cumulative_candidates_tokens}, total={cumulative_total_tokens}"
                )
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            # Phase 2: Execute tools AFTER stream is exhausted
            tool_response_parts: list[types.Part] = []
            if round_func_parts:
                for part in round_func_parts:
                    part_func = getattr(part, "function_call", None)
                    if not part_func:
                        continue

                    tool_name = getattr(part_func, "name", None) or ""
                    if not tool_name:
                        continue

                    fc_id = getattr(part_func, "id", None)
                    args = dict(part_func.args) if part_func.args else {}
                    total_tool_calls += 1

                    logger.bind(
                        event="tool_call",
                        service="chat",
                        trace_id=trace_id,
                        tool=tool_name,
                        elapsed_ms=_elapsed_ms(),
                    ).info(f"⚡ {tool_name}()")

                    yield f"data: {json.dumps({'status': f'calling_{tool_name}'})}\n\n"
                    yield f"data: {json.dumps({'tool_call': tool_name, 'args': args})}\n\n"

                    tool_fn = tool_map.get(tool_name)
                    tool_start = time_mod.perf_counter() * 1000
                    if tool_fn:
                        try:
                            result = await tool_fn(**args)
                            tool_duration_ms = round(
                                time_mod.perf_counter() * 1000 - tool_start, 1
                            )
                            logger.bind(
                                event="tool_done",
                                service="chat",
                                trace_id=trace_id,
                                tool=tool_name,
                                duration_ms=tool_duration_ms,
                            ).info(f"✅ {tool_name} done ({tool_duration_ms}ms)")
                        except Exception as e:
                            tool_duration_ms = round(
                                time_mod.perf_counter() * 1000 - tool_start, 1
                            )
                            logger.bind(
                                event="tool_error",
                                service="chat",
                                trace_id=trace_id,
                                tool=tool_name,
                                error=f"{type(e).__name__}: {str(e)}",
                                duration_ms=tool_duration_ms,
                            ).error(
                                f"❌ {tool_name} failed ({tool_duration_ms}ms): {type(e).__name__}: {str(e)}"
                            )
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                        logger.bind(
                            event="tool_error",
                            service="chat",
                            trace_id=trace_id,
                            tool=tool_name,
                        ).warning(f"❓ {tool_name}: unknown tool")

                    yield f"data: {json.dumps({'tool_result': tool_name, 'result': result})}\n\n"
                    yield f"data: {json.dumps({'status': 'processing_results'})}\n\n"

                    fn_response_part = types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response=result,
                            id=fc_id,
                        )
                    )
                    tool_response_parts.append(fn_response_part)

            if not round_func_parts:
                # No function calls - stream completed normally
                latency_ms = round(time_mod.perf_counter() * 1000 - start_ms, 1)
                _flush_assistant_text()
                logger.bind(
                    event="stream_done",
                    service="chat",
                    trace_id=trace_id,
                    model=model,
                    elapsed_ms=_elapsed_ms(),
                    latency_ms=latency_ms,
                    total_chunks=chunk_index,
                    total_tool_calls=total_tool_calls,
                    prompt_tokens=prompt_tokens_first_chunk,
                    candidates_tokens=cumulative_candidates_tokens,
                    total_tokens=cumulative_total_tokens,
                    assistant_text_length=len(assistant_text),
                ).info(
                    f"Stream completed at +{_elapsed_ms()}ms — tokens: prompt={prompt_tokens_first_chunk}, candidates={cumulative_candidates_tokens}, total={cumulative_total_tokens}"
                )
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            tool_round += 1
            logger.bind(
                event="stream_round_end",
                service="chat",
                trace_id=trace_id,
                model=model,
                elapsed_ms=_elapsed_ms(),
                tool_round=tool_round,
                tools_executed=len(round_func_parts),
            ).info(f"Tool round complete at +{_elapsed_ms()}ms")

            # Phase 3: Build proper message history
            # Gemini expects: one Content(role="model") with all parts merged,
            # then one Content(role="user") with all function responses merged
            model_parts = round_text_parts + round_func_parts
            if model_parts:
                current_messages.append(types.Content(role="model", parts=model_parts))
            if tool_response_parts:
                current_messages.append(
                    types.Content(role="user", parts=tool_response_parts)
                )

        # Max tool rounds reached
        latency_ms = round(time_mod.perf_counter() * 1000 - start_ms, 1)
        logger.bind(
            event="stream_done",
            service="chat",
            trace_id=trace_id,
            model=model,
            elapsed_ms=_elapsed_ms(),
            latency_ms=latency_ms,
            total_chunks=chunk_index,
            total_tool_calls=total_tool_calls,
            prompt_tokens=prompt_tokens_first_chunk,
            candidates_tokens=cumulative_candidates_tokens,
            total_tokens=cumulative_total_tokens,
            tool_error="max_tool_rounds_reached",
        ).warning(
            f"Max tool rounds at +{_elapsed_ms()}ms — tokens: prompt={prompt_tokens_first_chunk}, candidates={cumulative_candidates_tokens}, total={cumulative_total_tokens}"
        )
        too_many_calls_text = (
            "I needed to make too many tool calls. Please try a more specific question."
        )
        assistant_text += too_many_calls_text
        _flush_assistant_text()
        yield f"data: {json.dumps({'chunk': too_many_calls_text})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        latency_ms = round(time_mod.perf_counter() * 1000 - start_ms, 1)
        logger.bind(
            event="stream_error",
            service="chat",
            trace_id=trace_id,
            elapsed_ms=_elapsed_ms(),
            latency_ms=latency_ms,
            chunks=chunk_index,
            tools=total_tool_calls,
            error=f"{type(e).__name__}: {str(e)}",
        ).error(f"Stream error at +{latency_ms}ms: {type(e).__name__}: {str(e)}")
        _flush_assistant_text()
        yield f"data: {json.dumps({'error': f'An error occurred: {e}'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
