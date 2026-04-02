"""Chat router — HTTP concerns only (parse request, call service, return response)."""

import json
import traceback as tb
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from google.genai import Client, types
from loguru import logger
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, verify_user_exists
from app.core.config import settings
from app.db.session import get_db
from app.schemas.chat import ChatRequest
from app.services.message_service import (
    append_message,
    resolve_session,
    get_session_messages,
)

router = APIRouter()


SYSTEM_PROMPT = """You are a helpful travel planning assistant. Respond directly to user questions about travel, destinations, flights, hotels, attractions, and trip planning. Be concise and helpful."""


def SSE(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def simple_chat_stream(
    message: str,
    session_id: int,
    db: Session,
) -> StreamingResponse:
    """
    Simple streaming chat — just sends user message directly to LLM without tools.
    """
    trace_id = str(uuid4())
    call_id = str(uuid4())[:8]

    http_opts = (
        types.HttpOptionsDict(client_args={"proxy": settings.SOCKS5_PROXY_URL})
        if settings.LLM_PROXY_ENABLED
        else None
    )
    client = Client(api_key=settings.GEMINI_API_KEY, http_options=http_opts)

    # Build conversation history
    history = get_session_messages(db, session_id)
    contents: list[types.Content] = []

    # Add history as context
    for msg in history:
        if msg.role in ("user", "assistant"):
            contents.append(
                types.Content(
                    role=msg.role, parts=[types.Part.from_text(text=msg.content)]
                )
            )

    # Add current user message
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    )

    # Save user message
    append_message(db, session_id=session_id, role="user", content=message)

    # Create assistant message placeholder
    assistant_msg = append_message(
        db, session_id=session_id, role="assistant", content=""
    )

    async def generate():
        try:
            # Use sync client like test-llm does, wrapped in asyncio.to_thread
            # to avoid blocking the event loop
            import asyncio

            def call_llm():
                return client.models.generate_content(
                    model=settings.GEMINI_LITE_MODEL,
                    contents=contents,
                    config={
                        "system_instruction": SYSTEM_PROMPT,
                        "temperature": 0.7,
                    },
                )

            response = await asyncio.to_thread(call_llm)

            # Stream the response text
            if response.text:
                accumulated = response.text
                # Stream in chunks of ~20 chars for visual effect
                import re

                chunks = re.findall(r".{1,20}(?:\s+|$)", accumulated)
                for chunk in chunks:
                    yield SSE({"chunk": chunk})
                    await asyncio.sleep(0.02)

                # Update assistant message in DB
                assistant_msg.content = accumulated
                db.commit()

        except Exception as e:
            tb_str = tb.format_exc()
            logger.bind(
                event="chat_stream_error",
                call_id=call_id,
                trace_id=trace_id,
                error_type=type(e).__name__,
                error_message=str(e),
                model=settings.GEMINI_LITE_MODEL,
                proxy_enabled=settings.LLM_PROXY_ENABLED,
                contents_count=len(contents),
                contents_roles=[c.role for c in contents],
                system_instruction_len=len(SYSTEM_PROMPT),
                traceback=tb_str,
            ).error(f"[{call_id}] Chat stream error: {e}")
            yield SSE({"message_type": "error", "error": f"[{type(e).__name__}] {e}"})

        yield SSE({"done": True})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/test-llm")
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

    # Verify user exists in DB (valid token but user deleted → 401)
    verify_user_exists(user_id, db)

    # Get or create session
    session = await resolve_session(
        db, body.session_id, user_id, force_new_session=body.force_new_session
    )

    return await simple_chat_stream(
        message=body.message,
        session_id=session.id,
        db=db,
    )
