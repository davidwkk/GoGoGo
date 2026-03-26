from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, Depends, HTTPException
from google.genai import Client
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import invoke_agent
from app.services.message_service import append_message, create_session, get_session

router = APIRouter()


@asynccontextmanager
async def _httpx_client() -> AsyncGenerator[httpx.Client, None]:
    if settings.LLM_PROXY_ENABLED:
        proxy = settings.SOCKS5_PROXY_URL
        with httpx.Client(proxy=proxy, timeout=30.0) as client:
            yield client
    else:
        with httpx.Client(timeout=30.0) as client:
            yield client


@router.get("/test-llm")
async def test_llm() -> dict:
    """
    Simple test endpoint that calls Gemini 3.1 flash lite preview directly.
    """
    client = Client(api_key=settings.GEMINI_API_KEY)

    async with _httpx_client() as httpx_client:
        http_opts = {"httpx_client": httpx_client} if settings.LLM_PROXY_ENABLED else {}
        response = client.models.generate_content(
            model=settings.GEMINI_LITE_MODEL,
            contents="Say hello in exactly 3 words.",
            config={
                "temperature": 0.0,
                "http_options": http_opts,
            },
        )

    return {
        "model": settings.GEMINI_LITE_MODEL,
        "response": response.text,
        "proxy_enabled": settings.LLM_PROXY_ENABLED,
    }


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    POST /chat — sync chat endpoint (Phase 1).

    If generate_plan=False: simple chat response (no full agent loop).
    If generate_plan=True: runs full agent loop → TripItinerary.

    Backend creates session if session_id is null (on first message).
    Returns session_id so frontend can store and send it on subsequent requests.
    """
    user_id = current_user["user_id"]

    # Get or create session
    # session_id from frontend is str; convert to int for DB lookup
    if body.session_id:
        try:
            session_pk = int(body.session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid session_id")
        session = get_session(db, session_pk)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = create_session(db, user_id=user_id)

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
