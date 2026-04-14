"""Chat router — HTTP concerns only (parse request, call service, return response)."""

import json
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from google.genai import Client, types
from loguru import logger
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, verify_user_exists
from app.core.config import settings
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.message_service import append_message, resolve_session
from app.services.streaming_service import stream_agent_response

router = APIRouter()


async def test_llm() -> dict:
    """
    Simple test endpoint that calls Gemini 3.1 flash lite preview directly.
    """
    from app.utils.stream_utils import _is_proxy_reachable

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


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    current_user: dict | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    POST /chat/stream — unified streaming chat endpoint.

    Streams response chunks via SSE for low-latency updates.
    The agent decides when to call tools and when to generate a trip plan.
    """

    user_id = current_user["user_id"] if current_user else None
    call_id = str(uuid4())[:8]
    trace_id = str(uuid4())

    # Verify user exists in DB (valid token but user deleted → 401)
    verify_user_exists(user_id, db)

    # Get or create session
    session = await resolve_session(
        db, body.session_id, user_id, force_new_session=body.force_new_session
    )

    # Save user message
    append_message(
        db,
        session_id=session.id,
        role="user",
        content=body.message,
    )

    prefs_dict = body.user_preferences.model_dump() if body.user_preferences else None

    logger.bind(
        event="chat_stream_request",
        call_id=call_id,
        trace_id=trace_id,
        user_id=user_id,
        session_id=session.id,
        message_preview=body.message[:100] + ("..." if len(body.message) > 100 else ""),
        message_len=len(body.message),
        force_new_session=body.force_new_session,
        proxy_enabled=settings.LLM_PROXY_ENABLED,
        proxy_url=settings.SOCKS5_PROXY_URL if settings.LLM_PROXY_ENABLED else None,
        model=settings.GEMINI_LITE_MODEL,
        has_preferences=prefs_dict is not None,
        preferences_keys=list(prefs_dict.keys()) if prefs_dict else [],
    ).info(
        f"[{call_id}] Chat stream request | user={user_id} | session={session.id} | "
        f"msg_len={len(body.message)} | proxy={settings.LLM_PROXY_ENABLED} | "
        f"prefs={bool(prefs_dict)}"
    )

    return StreamingResponse(
        stream_agent_response(
            message=body.message,
            session_id=session.id,
            db=db,
            preferences=prefs_dict,
            trace_id=trace_id,
            user_id=user_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("")
async def chat_generate(
    body: ChatRequest,
    current_user: dict | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    POST /chat — non-streaming endpoint (used by "Generate plan").

    Internally runs the same unified agent streaming loop, but consumes it server-side
    and returns a single JSON response when done.
    """
    user_id = current_user["user_id"] if current_user else None
    trace_id = str(uuid4())

    verify_user_exists(user_id, db)

    session = await resolve_session(
        db, body.session_id, user_id, force_new_session=body.force_new_session
    )

    append_message(
        db,
        session_id=session.id,
        role="user",
        content=body.message,
    )

    prefs_dict = body.user_preferences.model_dump() if body.user_preferences else None

    full_text = ""
    itinerary: dict | None = None
    message_type = "chat"
    trip_saved = False

    async for raw in stream_agent_response(
        message=body.message,
        session_id=session.id,
        db=db,
        preferences=prefs_dict,
        trace_id=trace_id,
        user_id=user_id,
    ):
        # Keepalive comments start with ":"; ignore those
        if not raw.startswith("data: "):
            continue
        try:
            payload = json.loads(raw[len("data: ") :].strip())
        except Exception:
            continue

        if "chunk" in payload and isinstance(payload["chunk"], str):
            full_text += payload["chunk"]
        if payload.get("message_type") == "itinerary" and isinstance(
            payload.get("itinerary"), dict
        ):
            itinerary = payload["itinerary"]
            message_type = "itinerary"
        if payload.get("message_type") == "error" and isinstance(
            payload.get("error"), str
        ):
            message_type = "error"
        if payload.get("trip_saved") is True:
            trip_saved = True
        if payload.get("done") is True:
            break

    # When generating a plan, ensure we return something useful even if the model streamed no text.
    if body.generate_plan and itinerary is not None and not full_text.strip():
        full_text = "Trip plan generated."

    return ChatResponse(
        session_id=str(session.id),
        text=full_text.strip(),
        itinerary=itinerary,
        message_type=message_type,
        trip_saved=trip_saved,
        trip_id=None,
    )
