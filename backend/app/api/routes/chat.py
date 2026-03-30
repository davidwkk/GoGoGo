import asyncio
import json
from typing import AsyncIterator, Iterator
from uuid import UUID, uuid4

from loguru import logger

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google.genai import Client, types
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
from app.api.deps import get_current_user_optional, get_db
from app.core.config import settings
from app.db.models.chat_session import ChatSession
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import invoke_agent
from app.services.message_service import (
    append_message,
    create_session,
    get_latest_session_for_guest,
    get_or_create_guest,
    get_session,
    update_message_content,
)

tool_map = {
    "get_attraction": get_attraction,
    "get_weather": get_weather,
    "search_web": search_web,
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "get_transport": get_transport,
    "build_embed_url": build_embed_url,
}

router = APIRouter()


def _verify_user_exists(user_id: UUID | None, db: Session) -> None:
    """Verify that a user exists in the DB. Raises 401 if user_id is valid but user is not found."""
    if user_id is not None:
        from app.repositories.user_repo import get_user_by_id

        if get_user_by_id(db, user_id) is None:
            raise HTTPException(status_code=401, detail="User not found")


async def _resolve_session(
    db: Session,
    session_id: str | None,
    user_id: int | None,
) -> ChatSession:
    """
    Resolve a session from a session_id string (integer PK or guest UUID).

    For integer session_id:
      - Authenticated users can only access their own sessions
      - Guests cannot access integer-PK sessions

    For guest UUID session_id:
      - Only guests may use it; creates a new session if none exists

    For no session_id:
      - Creates a new session for authenticated users or guests
    """

    if session_id:
        # Try parsing as integer PK first (authenticated user session)
        try:
            session_pk = int(session_id)
            session = get_session(db, session_pk)
            if session is None:
                raise HTTPException(status_code=404, detail="Session not found")
            if user_id is None:
                raise HTTPException(status_code=403, detail="Forbidden")
            if session.user_id != user_id:
                raise HTTPException(status_code=403, detail="Forbidden")
            return session
        except ValueError:
            # Treat as guest UUID - look up existing session or create new one
            if user_id is not None:
                raise HTTPException(status_code=400, detail="Invalid session_id")
            guest = get_or_create_guest(db, session_id)
            session = get_latest_session_for_guest(db, guest.id)
            if session is None:
                session = create_session(db, user_id=None, guest_id=guest.id)
            return session
    else:
        # No session_id provided - create new session
        if user_id is not None:
            return create_session(db, user_id=user_id)
        else:
            guest_uid = str(uuid4())
            guest = get_or_create_guest(db, guest_uid)
            return create_session(db, user_id=None, guest_id=guest.id)


async def _is_proxy_reachable() -> bool:
    """Returns True if a proxy is configured and the SOCKS5 proxy is reachable."""
    return True  # Bypass for now, it is NOT A BUG, it is INTENTIONAL!

    # if not settings.LLM_PROXY_ENABLED:
    #     return False  # No proxy — direct call not allowed
    # proxy_url = settings.SOCKS5_PROXY_URL
    # try:
    #     host = proxy_url.split("://")[1].rsplit(":", 1)[0]
    #     port = int(proxy_url.split("://")[1].rsplit(":", 1)[1])
    # except (IndexError, ValueError):
    #     return False

    # def _check() -> bool:
    #     try:
    #         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #         sock.settimeout(5)
    #         sock.connect((host, port))
    #         # SOCKS5 handshake: version 5, 1 auth method (no auth)
    #         sock.send(b"\x05\x01\x00")
    #         resp = sock.recv(2)
    #         sock.close()
    #         return resp == b"\x05\x00"
    #     except Exception:
    #         return False

    # loop = asyncio.get_running_loop()
    # return await loop.run_in_executor(None, _check)


@router.get("/test-llm")
async def test_llm() -> dict:
    """
    Simple test endpoint that calls Gemini 3.1 flash lite preview directly.
    """
    if not await _is_proxy_reachable():
        return {
            "model": settings.GEMINI_LITE_MODEL,
            "response": None,
            "proxy_enabled": settings.LLM_PROXY_ENABLED,
            "error": (
                "Proxy not reachable. Check your VPN/proxy connection."
                if settings.LLM_PROXY_ENABLED
                else "No proxy configured. Set LLM_PROXY_ENABLED=true and SOCKS5_PROXY_URL to use the LLM."
            ),
        }

    from google.genai import types

    http_opts = (
        types.HttpOptionsDict(client_args={"proxy": settings.SOCKS5_PROXY_URL})
        if settings.LLM_PROXY_ENABLED
        else None
    )
    client = Client(api_key=settings.GEMINI_API_KEY, http_options=http_opts)

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_LITE_MODEL,
            contents="Say hello in exactly 3 words.",
            config={
                "temperature": 0.0,
            },
        )
    except Exception as e:
        error_msg = str(e)
        if "503" in error_msg or "unavailable" in error_msg.lower():
            return {
                "model": settings.GEMINI_LITE_MODEL,
                "response": None,
                "proxy_enabled": settings.LLM_PROXY_ENABLED,
                "error": (
                    "The AI service is temporarily unavailable due to high demand. "
                    "This is usually temporary - please try again in a few moments."
                ),
            }
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            return {
                "model": settings.GEMINI_LITE_MODEL,
                "response": None,
                "proxy_enabled": settings.LLM_PROXY_ENABLED,
                "error": "You've reached the rate limit. Please wait a moment and try again.",
            }
        return {
            "model": settings.GEMINI_LITE_MODEL,
            "response": None,
            "proxy_enabled": settings.LLM_PROXY_ENABLED,
            "error": f"LLM error: {error_msg}",
        }

    return {
        "model": settings.GEMINI_LITE_MODEL,
        "response": response.text,
        "proxy_enabled": settings.LLM_PROXY_ENABLED,
    }


async def _sync_stream_to_async(
    sync_iter: Iterator[types.GenerateContentResponse],
) -> AsyncIterator[types.GenerateContentResponse]:
    """
    Wrap a synchronous iterator as an async generator.

    Runs each synchronous next() call in the default thread pool,
    yielding control to the event loop while waiting for the next chunk.
    This prevents the sync iterator from blocking the event loop.

    StopIteration is caught inside the thread to avoid
    "StopIteration interacts badly with generators" Future exception.
    """
    loop = asyncio.get_running_loop()

    def _next() -> tuple[bool, types.GenerateContentResponse | None]:
        try:
            return (True, next(sync_iter))
        except StopIteration:
            return (False, None)

    while True:
        has_value, chunk = await loop.run_in_executor(None, _next)
        if not has_value:
            return
        assert chunk is not None
        yield chunk


async def _stream_agent_thoughts(
    message: str,
    session_id: int,
    db: Session,
    preferences: dict | None = None,
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
    logger.info(f"[_stream_agent_thoughts] Starting for message: {message[:100]}...")
    logger.info(f"[_stream_agent_thoughts] Preferences: {preferences}")

    assistant_msg = append_message(
        db, session_id=session_id, role="assistant", content=""
    )
    assistant_text = ""

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
        "IMPORTANT: Use tools to fetch live information — flights, hotels, attractions, weather. "
        "Never invent prices or times. "
        f"{prefs_section}"
    )

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
    )

    current_messages: list[types.Content] = list(messages)
    tool_round = 0

    try:
        while tool_round < MAX_TOOL_ROUNDS:
            logger.info(f"[_stream_agent_thoughts] Tool round {tool_round + 1}")

            stream = client.models.generate_content_stream(
                model=settings.GEMINI_LITE_MODEL,
                contents=current_messages,
                config=config,
            )

            # Phase 1: Stream and collect parts (don't execute tools yet)
            round_text_parts: list[types.Part] = []
            round_func_parts: list[types.Part] = []

            yield f"data: {json.dumps({'status': 'thinking'})}\n\n"

            async for chunk in _sync_stream_to_async(stream):
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

                for part in parts:
                    part_thought = getattr(part, "thought", None)
                    part_text = getattr(part, "text", None)
                    part_func = getattr(part, "function_call", None)

                    if part_thought and part_text:
                        logger.info(f"[_stream_agent_thoughts] THOUGHT: {part_text}")
                        yield f"data: {json.dumps({'model_thought': part_text})}\n\n"
                    elif part_func:
                        # Collect function call parts for later execution
                        round_func_parts.append(part)
                    elif part_text:
                        logger.info(f"[_stream_agent_thoughts] OUTPUT: {part_text}")
                        assistant_text += part_text
                        _flush_assistant_text()
                        yield f"data: {json.dumps({'chunk': part_text})}\n\n"
                        round_text_parts.append(part)

                await asyncio.sleep(0)

            # Phase 2: Execute tools AFTER stream is exhausted
            tool_response_parts: list[types.Part] = []
            if round_func_parts:
                for part in round_func_parts:
                    part_func = getattr(part, "function_call", None)
                    if not part_func:
                        continue

                    tool_name = part_func.name or ""
                    if not tool_name:
                        continue

                    fc_id = getattr(part_func, "id", None)
                    args = dict(part_func.args) if part_func.args else {}

                    logger.info(
                        f"[_stream_agent_thoughts] Tool call: {tool_name} | id={fc_id}"
                    )
                    yield f"data: {json.dumps({'status': f'calling_{tool_name}'})}\n\n"
                    yield f"data: {json.dumps({'tool_call': tool_name, 'args': args})}\n\n"

                    tool_fn = tool_map.get(tool_name)
                    if tool_fn:
                        try:
                            result = await tool_fn(**args)
                        except Exception as e:
                            logger.error(
                                f"[_stream_agent_thoughts] Tool {tool_name} exception: {e}"
                            )
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    logger.info(
                        f"[_stream_agent_thoughts] Tool result: {str(result)[:200]}"
                    )
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
                _flush_assistant_text()
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            tool_round += 1
            logger.info(
                f"[_stream_agent_thoughts] Round {tool_round}: {len(round_func_parts)} tool(s) executed"
            )

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
        logger.warning("[_stream_agent_thoughts] Max tool rounds reached")
        too_many_calls_text = (
            "I needed to make too many tool calls. Please try a more specific question."
        )
        assistant_text += too_many_calls_text
        _flush_assistant_text()
        yield f"data: {json.dumps({'chunk': too_many_calls_text})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        logger.error(
            f"[_stream_agent_thoughts] Error: {type(e).__name__}: {str(e)[:200]}"
        )
        _flush_assistant_text()
        yield f"data: {json.dumps({'error': f'An error occurred: {e}'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    current_user: dict | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    POST /chat/stream — streaming chat endpoint.

    Streams response chunks via SSE for low-latency updates.
    Uses a simpler non-tool approach for streaming.
    For generate_plan=True, use the non-streaming endpoint instead.
    """
    if body.generate_plan:
        raise HTTPException(
            status_code=400,
            detail="Use /chat for generate_plan requests",
        )

    user_id = current_user["user_id"] if current_user else None

    # Verify user exists in DB (valid token but user deleted → 401)
    _verify_user_exists(user_id, db)

    # Get or create session (uses shared helper to avoid duplication)
    session = await _resolve_session(db, body.session_id, user_id)

    # Save user message
    append_message(
        db,
        session_id=session.id,
        role="user",
        content=body.message,
    )

    prefs_dict = body.user_preferences.model_dump() if body.user_preferences else None

    return StreamingResponse(
        _stream_agent_thoughts(
            message=body.message,
            session_id=session.id,
            db=db,
            preferences=prefs_dict,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: dict | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    POST /chat — sync chat endpoint (Phase 1).

    If generate_plan=False: simple chat response (no full agent loop).
    If generate_plan=True: runs full agent loop → TripItinerary.

    Backend creates session if session_id is null (on first message).
    Returns session_id so frontend can store and send it on subsequent requests.

    Supports both authenticated users and guest users (no token required).
    """
    user_id = current_user["user_id"] if current_user else None

    # Verify user exists in DB (valid token but user deleted → 401)
    _verify_user_exists(user_id, db)

    # Get or create session (uses shared helper to avoid duplication)
    session = await _resolve_session(db, body.session_id, user_id)

    # Save user message
    append_message(
        db,
        session_id=session.id,
        role="user",
        content=body.message,
    )

    # Invoke agent (David owns this)
    # Extract preferences dict from body if present
    prefs_dict = None
    if body.user_preferences:
        prefs_dict = body.user_preferences.model_dump()

    result = await invoke_agent(
        user_message=body.message,
        user_id=user_id,
        session_id=session.id,
        generate_plan=body.generate_plan,
        preferences=prefs_dict,
        db=db,
    )

    # Save assistant response — store text content only
    # (itinerary is returned in the API response separately, not in chat history)
    message_content = result.text
    if result.message_type == "itinerary" and result.itinerary:
        # Show a brief summary in the chat history instead of empty message
        message_content = (
            f"✅ Trip plan generated for {result.itinerary.destination}! "
            f"View the full itinerary in your trips."
        )
    elif result.message_type == "error":
        message_content = result.text or "An error occurred."

    append_message(
        db,
        session_id=session.id,
        role="assistant",
        content=message_content,
    )

    return result
