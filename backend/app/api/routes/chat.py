import asyncio
import json
import socket
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google.genai import Client, types
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, get_db
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import invoke_agent
from app.services.message_service import (
    append_message,
    create_session,
    get_or_create_guest,
    get_session,
)

router = APIRouter()


def _is_proxy_reachable() -> bool:
    """Returns True if a proxy is configured and the SOCKS5 proxy is reachable."""
    if not settings.LLM_PROXY_ENABLED:
        return False  # No proxy — direct call not allowed
    proxy_url = settings.SOCKS5_PROXY_URL
    try:
        host = proxy_url.split("://")[1].rsplit(":", 1)[0]
        port = int(proxy_url.split("://")[1].rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        # SOCKS5 handshake: version 5, 1 auth method (no auth)
        sock.send(b"\x05\x01\x00")
        resp = sock.recv(2)
        sock.close()
        # Valid SOCKS5 response: version 5, method 0 (no auth accepted)
        return resp == b"\x05\x00"
    except Exception:
        return False


@router.get("/test-llm")
async def test_llm() -> dict:
    """
    Simple test endpoint that calls Gemini 3.1 flash lite preview directly.
    """
    if not _is_proxy_reachable():
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


MAX_RETRIES = 3  # 1 initial attempt + 3 retries = 4 total calls; display shows only retry count (1/3–3/3)


async def _stream_agent_thoughts(
    message: str,
    preferences: dict | None = None,
    max_retries: int = MAX_RETRIES,
) -> AsyncIterator[str]:
    """
    Stream agent thinking + tool calls + text via SSE.

    Runs the full Gemini agent loop with tools and yields SSE events for each step:
      - thought:    model is thinking / deciding what to do
      - tool_call:  tool name + args being executed
      - tool_result: tool response (or error)
      - chunk:      text content from the model
      - done:       stream complete

    Retries on transient errors (503, rate limit) with exponential backoff.
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"[_stream_agent_thoughts] Starting for message: {message[:100]}...")
    logger.info(f"[_stream_agent_thoughts] Preferences: {preferences}")

    if not _is_proxy_reachable() and not settings.LLM_PROXY_ENABLED:
        logger.warning("[_stream_agent_thoughts] Proxy not reachable")
        yield f"data: {json.dumps({'error': 'Proxy not reachable. Please check your VPN/proxy connection.'})}\n\n"
        return

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

    # Import tools from agent to reuse the same tool map
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

    tool_map = {
        "get_attraction": get_attraction,
        "get_weather": get_weather,
        "search_web": search_web,
        "search_flights": search_flights,
        "search_hotels": search_hotels,
        "get_transport": get_transport,
        "build_embed_url": build_embed_url,
    }

    messages: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        )
    ]

    MAX_ITERATIONS = 5

    def _is_transient_error(e: Exception) -> bool:
        error_type = type(e).__name__
        error_str = str(e)
        if error_type == "ServerError":
            return True
        error_lower = error_str.lower()
        return (
            "503" in error_str
            or "unavailable" in error_lower
            or "rate limit" in error_lower
            or "429" in error_str
            or "timeout" in error_lower
            or error_type.endswith("Timeout")
        )

    def _user_message(msg: str) -> str:
        if "unavailable" in msg.lower() or "503" in msg:
            return (
                "The AI service is temporarily unavailable due to high demand. "
                "This is usually temporary - please try again in a few moments."
            )
        if "rate limit" in msg.lower() or "429" in msg:
            return "You've reached the rate limit. Please wait a moment and try again."
        return "An error occurred. Please try again."

    for attempt in range(max_retries + 1):
        try:
            logger.info(
                f"[_stream_agent_thoughts] Iteration attempt {attempt + 1}/{max_retries + 1}"
            )

            for iteration in range(MAX_ITERATIONS):
                logger.info(
                    f"[_stream_agent_thoughts] Iteration {iteration + 1}/{MAX_ITERATIONS}"
                )

                # Notify frontend we're thinking
                yield f"data: {json.dumps({'thought': f'Thinking (step {iteration + 1})...'})}\n\n"

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=ALL_TOOLS,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.MINIMAL
                    ),
                )

                response = client.models.generate_content(
                    model=settings.GEMINI_LITE_MODEL,
                    contents=messages,
                    config=config,
                )

                # Append model content as-is to preserve thought_signature
                if response.candidates and response.candidates[0].content:
                    messages.append(response.candidates[0].content)

                if response.function_calls:
                    for fc in response.function_calls:
                        tool_name = fc.name or ""
                        if not tool_name:
                            continue
                        args = dict(fc.args) if fc.args else {}

                        logger.info(
                            f"[_stream_agent_thoughts] Tool call: {tool_name} | args: {str(args)[:200]}"
                        )
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

                        # Truncate result for streaming
                        result_preview = (
                            str(result)[:300] + "..."
                            if len(str(result)) > 300
                            else str(result)
                        )
                        logger.info(
                            f"[_stream_agent_thoughts] Tool {tool_name} result: {result_preview}"
                        )
                        yield f"data: {json.dumps({'tool_result': tool_name, 'result': result})}\n\n"

                        fn_response = types.Part.from_function_response(
                            name=tool_name,
                            response=result,
                        )
                        tool_content = types.Content(role="tool", parts=[fn_response])
                        messages.append(tool_content)
                        await asyncio.sleep(0)
                else:
                    # No more tool calls — final text response
                    final_text = response.text or ""
                    logger.info(
                        f"[_stream_agent_thoughts] Final response: {final_text[:200]}"
                    )
                    if final_text:
                        yield f"data: {json.dumps({'chunk': final_text})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

            # Max iterations reached
            logger.warning("[_stream_agent_thoughts] Max iterations reached")
            yield f"data: {json.dumps({'chunk': 'I ran out of time planning your trip. Please try again.'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        except Exception as e:
            error_msg = str(e)
            is_transient = _is_transient_error(e)
            logger.warning(
                f"[_stream_agent_thoughts] Exception attempt {attempt + 1}/{max_retries + 1}: "
                f"{type(e).__name__}: {error_msg[:200]} | transient={is_transient}"
            )

            if is_transient and attempt < max_retries:
                wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                logger.info(
                    f"[_stream_agent_thoughts] Transient error, retrying in {wait_time}s..."
                )
                # Skip count on attempt=0 (initial call); show 1/3–3/3 for actual retries
                if attempt > 0:
                    yield f"data: {json.dumps({'status': f'Retrying ({attempt}/{max_retries}) due to high demand...'})}\n\n"
                await asyncio.sleep(wait_time)
                continue
            else:
                user_msg = _user_message(error_msg)
                logger.error(
                    f"[_stream_agent_thoughts] Failed after {attempt + 1} attempt(s): {error_msg[:200]}"
                )
                yield f"data: {json.dumps({'error': user_msg})}\n\n"
                yield f"data: {json.dumps({'done': True, 'error': user_msg})}\n\n"
                return

    yield f"data: {json.dumps({'error': 'Failed after retries. Please try again later.'})}\n\n"


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

    # Verify user exists in DB (token may be valid but user deleted)
    if user_id is not None:
        from app.repositories.user_repo import get_user_by_id

        if get_user_by_id(db, user_id) is None:
            # User no longer exists — treat as unauthenticated (guest)
            user_id = None

    # Get or create session
    session = None
    if body.session_id:
        try:
            session_pk = int(body.session_id)
        except ValueError:
            if user_id is not None:
                raise HTTPException(status_code=400, detail="Invalid session_id")
            guest = get_or_create_guest(db, body.session_id)
            from sqlalchemy import desc, select

            from app.db.models.chat_session import ChatSession

            result = db.execute(
                select(ChatSession)
                .where(ChatSession.guest_id == guest.id)
                .order_by(desc(ChatSession.created_at))
                .limit(1)
            )
            session = result.scalar_one_or_none()
            if session is None:
                session = create_session(db, user_id=None, guest_id=guest.id)
        else:
            session = get_session(db, session_pk)
            if session is None:
                raise HTTPException(status_code=404, detail="Session not found")
            if session.user_id != user_id:
                raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if user_id is not None:
            session = create_session(db, user_id=user_id)
        else:
            # Generate new guest UID if none provided
            from uuid import uuid4

            guest_uid = body.session_id or str(uuid4())
            guest = get_or_create_guest(db, guest_uid)
            session = create_session(db, user_id=None, guest_id=guest.id)

    # Save user message
    append_message(
        db,
        session_id=session.id,
        role="user",
        content=body.message,
    )

    prefs_dict = None
    if body.user_preferences:
        prefs_dict = body.user_preferences.model_dump()

    return StreamingResponse(
        _stream_agent_thoughts(message=body.message, preferences=prefs_dict),
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

    # Verify user exists in DB (token may be valid but user deleted)
    if user_id is not None:
        from app.repositories.user_repo import get_user_by_id

        if get_user_by_id(db, user_id) is None:
            # User no longer exists — treat as unauthenticated (guest)
            user_id = None

    # Get or create session
    # session_id can be:
    #   - integer str (DB pk) for registered users
    #   - guest_uid (UUID str) for guests — resolved to latest guest session
    #   - absent → create new session
    if body.session_id:
        try:
            session_pk = int(body.session_id)
        except ValueError:
            # Treat as guest_uid (UUID string)
            if user_id is not None:
                raise HTTPException(status_code=400, detail="Invalid session_id")
            guest = get_or_create_guest(db, body.session_id)
            # Find the guest's most recent session, or create one
            from sqlalchemy import desc, select

            from app.db.models.chat_session import ChatSession

            result = db.execute(
                select(ChatSession)
                .where(ChatSession.guest_id == guest.id)
                .order_by(desc(ChatSession.created_at))
                .limit(1)
            )
            session = result.scalar_one_or_none()
            if session is None:
                session = create_session(db, user_id=None, guest_id=guest.id)
        else:
            session = get_session(db, session_pk)
            if session is None:
                raise HTTPException(status_code=404, detail="Session not found")
            # Security: verify the session belongs to the authenticated user
            if session.user_id != user_id:
                raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if user_id is not None:
            session = create_session(db, user_id=user_id)
        else:
            # Generate new guest UID if none provided
            from uuid import uuid4

            guest_uid = body.session_id or str(uuid4())
            guest = get_or_create_guest(db, guest_uid)
            session = create_session(db, user_id=None, guest_id=guest.id)

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
