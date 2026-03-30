"""Streaming service — orchestrates LLM, tools, DB persistence, and SSE formatting."""

import asyncio
import json
import time as time_mod
from typing import Any, AsyncIterator
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
        user_message_preview=message[:100],
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
            thinking_level=types.ThinkingLevel.MINIMAL,
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
                    logger.bind(
                        event="function_calls_on_chunk",
                        service="chat",
                        trace_id=trace_id,
                        elapsed_ms=chunk_start_ms,
                        function_calls=repr(chunk_function_calls)[:500],
                    ).info(
                        f"Function calls found on chunk directly at +{chunk_start_ms}ms: {chunk_function_calls}"
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

                # Log raw chunk for debugging
                logger.bind(
                    event="raw_chunk",
                    service="chat",
                    trace_id=trace_id,
                    elapsed_ms=chunk_start_ms,
                    chunk=str(chunk)[:500],
                    chunk_repr=repr(chunk),
                    has_candidates=hasattr(chunk, "candidates")
                    and chunk.candidates is not None,
                    has_function_calls=chunk_function_calls is not None,
                ).debug(
                    f"Raw chunk received at +{chunk_start_ms}ms: candidates={hasattr(chunk, 'candidates')}, candidates_value={getattr(chunk, 'candidates', None)}, function_calls={chunk_function_calls}"
                )

                candidates = chunk.candidates
                usage = getattr(chunk, "usage_metadata", None)
                if usage:
                    # Accumulate tokens from each chunk (prompt only set on first chunk)
                    if prompt_tokens_first_chunk is None:
                        prompt_tokens_first_chunk = getattr(
                            usage, "prompt_token_count", None
                        )
                    # Candidates and total are cumulative on final chunk
                    chunk_cand_tokens = getattr(usage, "candidates_token_count", None)
                    chunk_total_tokens = getattr(usage, "total_token_count", None)
                    if chunk_cand_tokens is not None:
                        cumulative_candidates_tokens = chunk_cand_tokens
                    if chunk_total_tokens is not None:
                        cumulative_total_tokens = chunk_total_tokens

                    logger.bind(
                        event="stream_chunk",
                        service="chat",
                        trace_id=trace_id,
                        model=model,
                        elapsed_ms=chunk_start_ms,
                        chunk_index=chunk_index,
                        chunk_type="usage",
                        usage={
                            "prompt_tokens": prompt_tokens_first_chunk,
                            "candidates_tokens": cumulative_candidates_tokens,
                            "total_tokens": cumulative_total_tokens,
                            "prompt_tokens_details": str(
                                getattr(usage, "prompt_tokens_details", None)
                            ),
                            "candidates_tokens_details": str(
                                getattr(usage, "candidates_tokens_details", None)
                            ),
                        },
                    ).debug(
                        f"Stream usage at +{chunk_start_ms}ms: prompt={prompt_tokens_first_chunk}, candidates={cumulative_candidates_tokens}, total={cumulative_total_tokens}"
                    )

                if not candidates:
                    logger.bind(
                        event="no_candidates",
                        service="chat",
                        trace_id=trace_id,
                        elapsed_ms=chunk_start_ms,
                    ).warning(f"Chunk has no candidates at +{chunk_start_ms}ms")
                    continue
                candidate = candidates[0]
                logger.bind(
                    event="candidate",
                    service="chat",
                    trace_id=trace_id,
                    elapsed_ms=chunk_start_ms,
                    finish_reason=str(candidate.finish_reason)
                    if hasattr(candidate, "finish_reason")
                    else None,
                    content_repr=repr(candidate.content)[:300]
                    if candidate.content
                    else None,
                    content_type=type(candidate.content).__name__
                    if candidate.content
                    else None,
                ).debug(
                    f"Candidate at +{chunk_start_ms}ms: finish_reason={getattr(candidate, 'finish_reason', None)}, content={repr(candidate.content)[:200]}"
                )
                if not candidate.content:
                    continue
                content = candidate.content
                parts = getattr(content, "parts", None)
                if not parts:
                    logger.bind(
                        event="no_parts",
                        service="chat",
                        trace_id=trace_id,
                        elapsed_ms=chunk_start_ms,
                        parts_value=parts,
                        content_type=type(content).__name__,
                    ).warning(
                        f"No parts in content at +{chunk_start_ms}ms: parts={parts}, content_type={type(content).__name__}"
                    )
                    continue

                finish_reason = (
                    str(candidate.finish_reason)
                    if hasattr(candidate, "finish_reason") and candidate.finish_reason
                    else None
                )
                # Capture for post-stream check
                round_finish_reason = finish_reason

                for part in parts:
                    # Log full part for debugging
                    logger.bind(
                        event="part",
                        service="chat",
                        trace_id=trace_id,
                        elapsed_ms=chunk_start_ms,
                        part_type=type(part).__name__,
                        part_repr=repr(part)[:300],
                        part_attrs={
                            attr: getattr(part, attr, None)
                            for attr in dir(part)
                            if not attr.startswith("_")
                        },
                    ).debug(
                        f"Part received at +{chunk_start_ms}ms: thought={getattr(part, 'thought', None)}, text={repr(getattr(part, 'text', None))[:100]}, func={getattr(part, 'function_call', None)}"
                    )

                    part_thought = getattr(part, "thought", None)
                    part_text = getattr(part, "text", None)
                    part_func = getattr(part, "function_call", None)
                    thought_sig = getattr(part, "thought_signature", None)

                    if part_thought:
                        if part_text:
                            chunk_index += 1
                            logger.bind(
                                event="stream_chunk",
                                service="chat",
                                trace_id=trace_id,
                                model=model,
                                chunk_index=chunk_index,
                                chunk_type="thought",
                                thought=part_text,
                                thought_length=len(part_text),
                                thought_signature_hex=thought_sig.hex()[:64]
                                if thought_sig
                                else None,
                                finish_reason=finish_reason,
                            ).info(f"Stream thought: {part_text[:200]}")
                            yield f"data: {json.dumps({'model_thought': part_text})}\n\n"
                        elif thought_sig:
                            # Thought with no text but has signature bytes
                            logger.bind(
                                event="stream_chunk",
                                service="chat",
                                trace_id=trace_id,
                                model=model,
                                chunk_index=chunk_index,
                                chunk_type="thought_signature",
                                thought_present=True,
                                thought_signature_hex=thought_sig.hex()[:64],
                                thought_signature_len=len(thought_sig),
                            ).info(
                                f"Thought signature present ({len(thought_sig)} bytes): {thought_sig.hex()[:32]}..."
                            )
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
                            event="stream_chunk",
                            service="chat",
                            trace_id=trace_id,
                            model=model,
                            chunk_index=chunk_index,
                            chunk_type="function_call",
                            tool_name=fc_name,
                            function_call_id=fc_id,
                            tool_args=fc_args,
                            finish_reason=finish_reason,
                        ).info(f"Stream function_call chunk: {fc_name}({fc_args})")
                    elif part_text is not None and part_text != "":
                        chunk_index += 1
                        logger.bind(
                            event="stream_chunk",
                            service="chat",
                            trace_id=trace_id,
                            model=model,
                            chunk_index=chunk_index,
                            chunk_type="text",
                            text=part_text,
                            text_length=len(part_text),
                            finish_reason=finish_reason,
                        ).info(f"Stream text chunk: {part_text}")
                        assistant_text += part_text
                        _flush_assistant_text()
                        yield f"data: {json.dumps({'chunk': part_text})}\n\n"
                        round_text_parts.append(part)
                    else:
                        # part_thought is None/falsy, part_func is None/falsy, part_text is None or ''
                        logger.bind(
                            event="skipped_part",
                            service="chat",
                            trace_id=trace_id,
                            elapsed_ms=chunk_start_ms,
                            part_thought=part_thought,
                            part_text=repr(part_text),
                            part_func=part_func,
                        ).debug(
                            f"Skipped part at +{chunk_start_ms}ms: thought={part_thought}, text={repr(part_text)}, func={part_func}"
                        )

                await asyncio.sleep(0)

            # Log what was collected
            logger.bind(
                event="stream_round_complete",
                service="chat",
                trace_id=trace_id,
                tool_round=tool_round + 1,
                elapsed_ms=_elapsed_ms(),
                round_text_parts_count=len(round_text_parts),
                round_func_parts_count=len(round_func_parts),
                round_func_parts_repr=[repr(p)[:200] for p in round_func_parts],
                assistant_text_length=len(assistant_text),
                assistant_text_preview=assistant_text[:200],
            ).info(
                f"Stream round complete at +{_elapsed_ms()}ms: text_parts={len(round_text_parts)}, func_parts={len(round_func_parts)}, assistant_text='{assistant_text[:100]}...'"
            )

            # Log usage metadata on final chunk of this round
            if usage:
                cand_tokens = getattr(usage, "candidates_token_count", None)
                total_tokens = getattr(usage, "total_token_count", None)
                logger.bind(
                    event="stream_round_usage",
                    service="chat",
                    trace_id=trace_id,
                    model=model,
                    elapsed_ms=_elapsed_ms(),
                    tool_round=tool_round + 1,
                    usage={
                        "prompt_tokens": prompt_tokens_first_chunk,
                        "candidates_tokens": cand_tokens,
                        "total_tokens": total_tokens,
                        "prompt_tokens_details": str(
                            getattr(usage, "prompt_tokens_details", None)
                        ),
                        "candidates_tokens_details": str(
                            getattr(usage, "candidates_tokens_details", None)
                        ),
                    },
                ).info(
                    f"Round token usage at +{_elapsed_ms()}ms: prompt={prompt_tokens_first_chunk}, candidates={cand_tokens}, total={total_tokens}"
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
                        model=model,
                        elapsed_ms=_elapsed_ms(),
                        tool_name=tool_name,
                        function_call_id=fc_id,
                        tool_args=args,
                        tool_round=tool_round + 1,
                    ).info(f"Executing tool at +{_elapsed_ms()}ms")

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
                                event="tool_response",
                                service="chat",
                                trace_id=trace_id,
                                model=model,
                                tool_name=tool_name,
                                tool_result_preview=str(result)[:200],
                                tool_duration_ms=tool_duration_ms,
                            ).info("Tool completed")
                        except Exception as e:
                            tool_duration_ms = round(
                                time_mod.perf_counter() * 1000 - tool_start, 1
                            )
                            import traceback

                            tb_str = traceback.format_exc()
                            logger.bind(
                                event="tool_error",
                                service="chat",
                                trace_id=trace_id,
                                model=model,
                                tool_name=tool_name,
                                tool_args=args,
                                tool_error=f"{type(e).__name__}: {str(e)}",
                                tool_traceback=tb_str,
                                tool_duration_ms=tool_duration_ms,
                            ).error(
                                f"Tool exception | tool={tool_name} | args={args} | "
                                f"error={type(e).__name__}: {str(e)[:200]} | duration_ms={tool_duration_ms}"
                            )
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                        logger.bind(
                            event="tool_error",
                            service="chat",
                            trace_id=trace_id,
                            model=model,
                            tool_name=tool_name,
                            tool_error=f"Unknown tool: {tool_name}",
                        ).warning("Unknown tool")

                    logger.bind(
                        event="tool_result",
                        service="chat",
                        trace_id=trace_id,
                        model=model,
                        elapsed_ms=_elapsed_ms(),
                        tool_name=tool_name,
                        tool_result_preview=str(result)[:200],
                    ).debug(f"Tool result at +{_elapsed_ms()}ms")
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
        import traceback as tb_mod

        latency_ms = round(time_mod.perf_counter() * 1000 - start_ms, 1)

        # Extract structured error details for APIError (google.genai errors)
        error_code: int | None = getattr(e, "code", None)
        error_status: str | None = getattr(e, "status", None)
        error_details: Any = getattr(e, "details", None)

        logger.bind(
            event="stream_error",
            service="chat",
            trace_id=trace_id,
            model=model,
            elapsed_ms=_elapsed_ms(),
            latency_ms=latency_ms,
            total_chunks=chunk_index,
            total_tool_calls=total_tool_calls,
            tool_round=tool_round,
            assistant_text_length=len(assistant_text),
            error_type=type(e).__name__,
            error_code=error_code,
            error_status=error_status,
            error_message=str(e)[:500],
            error_details=error_details,
            error_traceback=tb_mod.format_exc(),
        ).error(
            f"Stream error at +{_elapsed_ms()}ms | type={type(e).__name__} | code={error_code} | status={error_status} | "
            f"msg={str(e)[:200]} | tool_round={tool_round} | chunks={chunk_index} | "
            f"tools={total_tool_calls} | text_len={len(assistant_text)}"
        )
        _flush_assistant_text()
        yield f"data: {json.dumps({'error': f'An error occurred: {e}'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
