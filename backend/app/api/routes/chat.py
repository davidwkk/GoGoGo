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

    response = client.models.generate_content(
        model=settings.GEMINI_LITE_MODEL,
        contents="Say hello in exactly 3 words.",
        config={
            "temperature": 0.0,
        },
    )

    return {
        "model": settings.GEMINI_LITE_MODEL,
        "response": response.text,
        "proxy_enabled": settings.LLM_PROXY_ENABLED,
    }


async def _stream_chat(
    message: str,
    preferences: dict | None = None,
    max_retries: int = 2,
) -> AsyncIterator[str]:
    """
    Stream chat response chunks via SSE.
    Uses generate_content_streaming with tools disabled for simplicity.
    Retries on transient errors (503, rate limit) with exponential backoff.
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"[_stream_chat] Starting stream for message: {message[:100]}...")
    logger.info(f"[_stream_chat] Preferences: {preferences}")
    logger.info(f"[_stream_chat] LLM_PROXY_ENABLED: {settings.LLM_PROXY_ENABLED}")
    logger.info(f"[_stream_chat] Proxy reachable: {_is_proxy_reachable()}")

    if not _is_proxy_reachable() and not settings.LLM_PROXY_ENABLED:
        logger.warning("[_stream_chat] Proxy not reachable, returning error")
        yield f"data: {json.dumps({'error': 'Proxy not reachable. Please check your VPN/proxy connection.'})}\n\n"
        return

    http_opts = (
        types.HttpOptionsDict(client_args={"proxy": settings.SOCKS5_PROXY_URL})
        if settings.LLM_PROXY_ENABLED
        else None
    )
    logger.info(
        f"[_stream_chat] Creating client with model: {settings.GEMINI_LITE_MODEL}"
    )
    client = Client(api_key=settings.GEMINI_API_KEY, http_options=http_opts)

    prefs_section = f"User preferences: {preferences}" if preferences else ""
    system_instruction = (
        "You are a helpful travel planning assistant. "
        "Keep responses concise and friendly. "
        f"{prefs_section}"
    )
    logger.info(f"[_stream_chat] System instruction: {system_instruction[:200]}...")

    def _is_transient_error(e: Exception) -> bool:
        """Check if error is a transient error that may succeed on retry."""
        error_str = str(e).lower()
        return (
            "503" in error_str
            or "unavailable" in error_str
            or "rate limit" in error_str
            or "429" in error_str
            or "timeout" in error_str
        )

    for attempt in range(max_retries + 1):
        try:
            logger.info(
                f"[_stream_chat] Starting generate_content_stream (attempt {attempt + 1})"
            )
            stream = client.models.generate_content_stream(
                model=settings.GEMINI_LITE_MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message)],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )

            chunk_count = 0
            for chunk in stream:
                logger.info(
                    f"[_stream_chat] Received chunk {chunk_count}: {repr(chunk.text)[:100] if chunk.text else 'empty'}"
                )
                if chunk.text:
                    chunk_count += 1
                    yield f"data: {json.dumps({'chunk': chunk.text})}\n\n"
                    await asyncio.sleep(0)  # Allow other coroutines to run

            logger.info(f"[_stream_chat] Stream complete. Total chunks: {chunk_count}")
            yield f"data: {json.dumps({'done': True})}\n\n"
            return  # Success

        except Exception as e:
            error_msg = str(e)
            logger.warning(
                f"[_stream_chat] Exception on attempt {attempt + 1}: {type(e).__name__}: {error_msg}"
            )

            if _is_transient_error(e) and attempt < max_retries:
                wait_time = 2**attempt  # Exponential backoff: 1s, 2s
                logger.info(
                    f"[_stream_chat] Transient error, retrying in {wait_time}s..."
                )
                yield f"data: {json.dumps({'status': f'Retrying due to high demand ({attempt + 1}/{max_retries + 1})...'})}\n\n"
                await asyncio.sleep(wait_time)
                continue
            else:
                # Non-transient error or max retries reached
                if "unavailable" in error_msg.lower() or "503" in error_msg:
                    user_message = (
                        "The AI service is temporarily unavailable due to high demand. "
                        "This is usually temporary - please try again in a few moments."
                    )
                elif "rate limit" in error_msg.lower() or "429" in error_msg:
                    user_message = "You've reached the rate limit. Please wait a moment and try again."
                else:
                    user_message = f"An error occurred: {error_msg}"
                logger.error(
                    f"[_stream_chat] Non-retryable error: {type(e).__name__}: {error_msg}"
                )
                yield f"data: {json.dumps({'error': user_message})}\n\n"
                return

    # Should not reach here, but handle it
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
            guest_uid = body.session_id or ""
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
        _stream_chat(message=body.message, preferences=prefs_dict),
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
            # Guest with no session_id — this shouldn't happen with proper frontend,
            # but handle it by requiring guest_uid
            raise HTTPException(status_code=400, detail="guest_uid required for guests")

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
