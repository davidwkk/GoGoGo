"""Chat router — HTTP concerns only (parse request, call service, return response)."""

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google.genai import Client, types
from loguru import logger
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, verify_user_exists
from app.core.config import settings
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import invoke_agent
from app.services.message_service import append_message, resolve_session
from app.services.streaming_service import stream_agent_response

router = APIRouter()


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
    verify_user_exists(user_id, db)

    # Get or create session
    session = await resolve_session(db, body.session_id, user_id)

    # Save user message
    append_message(
        db,
        session_id=session.id,
        role="user",
        content=body.message,
    )

    prefs_dict = body.user_preferences.model_dump() if body.user_preferences else None
    trace_id = str(uuid4())

    return StreamingResponse(
        stream_agent_response(
            message=body.message,
            session_id=session.id,
            db=db,
            preferences=prefs_dict,
            trace_id=trace_id,
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
    trace_id = str(uuid4())

    # ── Router layer: log incoming request ────────────────────────────────
    logger.bind(
        event="router_request",
        layer="router",
        trace_id=trace_id,
        user_id=str(user_id) if user_id else None,
        session_id=str(body.session_id) if body.session_id else None,
        generate_plan=body.generate_plan,
        message_preview=body.message[:100],
        has_preferences=body.user_preferences is not None,
    ).info("ROUTER: Received chat request")

    # Verify user exists in DB (valid token but user deleted → 401)
    verify_user_exists(user_id, db)

    # Get or create session
    session = await resolve_session(db, body.session_id, user_id)

    logger.bind(
        event="router_session",
        layer="router",
        trace_id=trace_id,
        session_id=session.id,
        is_new_session=body.session_id is None,
    ).info(f"ROUTER: Session resolved — session_id={session.id}")

    # Save user message
    append_message(
        db,
        session_id=session.id,
        role="user",
        content=body.message,
    )

    # Invoke agent
    prefs_dict = None
    if body.user_preferences:
        prefs_dict = body.user_preferences.model_dump()

    trip_params_dict = None
    if body.trip_parameters:
        trip_params_dict = body.trip_parameters.model_dump()

    logger.bind(
        event="router_agent_invocation",
        layer="router",
        trace_id=trace_id,
        generate_plan=body.generate_plan,
        preferences_keys=list(prefs_dict.keys()) if prefs_dict else [],
        trip_parameters_keys=list(trip_params_dict.keys()) if trip_params_dict else [],
    ).info("ROUTER: Calling invoke_agent")

    result = await invoke_agent(
        user_message=body.message,
        user_id=user_id,
        session_id=session.id,
        generate_plan=body.generate_plan,
        preferences=prefs_dict,
        trip_parameters=trip_params_dict,
        db=db,
        trace_id=trace_id,
    )

    # ── Router layer: log full LLM response for debugging ─────────────────
    if body.generate_plan and result.itinerary:
        # Detailed itinerary logging for trip planning
        itinerary_dict = result.itinerary.model_dump(mode="json")
        logger.bind(
            event="router_llm_response_full",
            layer="router",
            trace_id=trace_id,
            message_type=result.message_type,
            # Full itinerary structure for debugging
            itinerary_destination=result.itinerary.destination,
            itinerary_duration_days=result.itinerary.duration_days,
            itinerary_flights_count=len(result.itinerary.flights)
            if result.itinerary.flights
            else 0,
            itinerary_hotels_count=len(result.itinerary.hotels)
            if result.itinerary.hotels
            else 0,
            itinerary_days_count=len(result.itinerary.days)
            if result.itinerary.days
            else 0,
            # Full raw itinerary JSON for deep debugging
            itinerary_json=json.dumps(itinerary_dict, indent=2, ensure_ascii=False),
        ).info(
            f"ROUTER: Full LLM response (trip plan) — "
            f"destination={result.itinerary.destination}, "
            f"days={result.itinerary.duration_days}, "
            f"flights={len(result.itinerary.flights) if result.itinerary.flights else 0}, "
            f"hotels={len(result.itinerary.hotels) if result.itinerary.hotels else 0}, "
            f"days_detail={len(result.itinerary.days) if result.itinerary.days else 0}"
        )
    else:
        # Plain chat response logging
        logger.bind(
            event="router_llm_response_full",
            layer="router",
            trace_id=trace_id,
            message_type=result.message_type,
            response_preview=result.text[:500] if result.text else "",
            response_length=len(result.text) if result.text else 0,
            has_itinerary=result.itinerary is not None,
        ).info(
            f"ROUTER: Full LLM response — "
            f"type={result.message_type}, "
            f"length={len(result.text) if result.text else 0}"
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

    logger.bind(
        event="router_response_sent",
        layer="router",
        trace_id=trace_id,
        session_id=session.id,
        message_type=result.message_type,
    ).info(f"ROUTER: Response sent — type={result.message_type}")

    return result
