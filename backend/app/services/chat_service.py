"""Chat service — David owns agent invocation only."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from loguru import logger

from app.agent.agent import run_agent, run_agent_structured
from app.schemas.chat import ChatResponse

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# LLM call timeout (30s for agent responses)
TIMEOUT_SECONDS = 30.0


async def invoke_agent(
    user_message: str,
    user_id: UUID | None,
    session_id: int | None = None,
    generate_plan: bool = False,
    preferences: dict | None = None,
    db: Session | None = None,
    trace_id: str | None = None,
) -> ChatResponse:
    """
    Invoke the Gemini agent with the user's message.

    If generate_plan=False: simple chat via run_agent (no structured output).
    If generate_plan=True: runs full tool-calling loop + structured TripItinerary,
      then saves the trip to the database via trip_service.
    """
    session_id_str = str(session_id) if session_id else ""
    start_ms = time.perf_counter() * 1000
    trace_id = trace_id or str(uuid4())

    logger.bind(
        event="invoke_start",
        service="chat",
        trace_id=trace_id,
        user_id=str(user_id) if user_id else None,
        session_id=session_id_str,
        generate_plan=generate_plan,
        user_message_preview=user_message[:100],
    ).info("invoke_agent called")

    try:
        if generate_plan:
            itinerary = await asyncio.wait_for(
                run_agent_structured(
                    user_message=user_message,
                    preferences=preferences,
                    trace_id=trace_id,
                ),
                timeout=TIMEOUT_SECONDS,
            )
            latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)

            # Extract summary from itinerary for logging
            tool_summary: dict = {}
            if itinerary:
                tool_summary = {
                    "destination": itinerary.destination,
                    "duration_days": itinerary.duration_days,
                    "flights_count": len(itinerary.flights) if itinerary.flights else 0,
                    "hotels_count": len(itinerary.hotels) if itinerary.hotels else 0,
                    "days_count": len(itinerary.days) if itinerary.days else 0,
                    "total_activities": sum(
                        len(day.morning) + len(day.afternoon) + len(day.evening)
                        for day in (itinerary.days or [])
                    ),
                }

            logger.bind(
                event="invoke_done",
                service="chat",
                trace_id=trace_id,
                latency_ms=latency_ms,
                message_type="itinerary",
                destination=itinerary.destination if itinerary else None,
                tool_summary=tool_summary,
            ).info("invoke_agent done — itinerary")

            # Save trip to DB if db session provided and user is authenticated
            if db is not None and itinerary is not None and user_id is not None:
                from app.services import trip_service

                trip_service.save_trip(
                    db=db,
                    user_id=user_id,
                    session_id=session_id,
                    itinerary=itinerary,
                )
                logger.bind(
                    event="trip_saved",
                    service="chat",
                    trace_id=trace_id,
                    session_id=session_id_str,
                ).info("Trip saved to DB")

            return ChatResponse(
                session_id=session_id_str,
                text="",
                itinerary=itinerary,
                message_type="itinerary",
            )
        else:
            text = await asyncio.wait_for(
                run_agent(
                    user_message=user_message,
                    preferences=preferences,
                    trace_id=trace_id,
                ),
                timeout=TIMEOUT_SECONDS,
            )
            latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)
            logger.bind(
                event="invoke_done",
                service="chat",
                trace_id=trace_id,
                latency_ms=latency_ms,
                message_type="chat",
                response_length=len(text),
                response_preview=text[:200],
            ).info("invoke_agent done — chat")
            return ChatResponse(
                session_id=session_id_str,
                text=text,
                itinerary=None,
                message_type="chat",
            )
    except asyncio.TimeoutError:
        latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)
        logger.bind(
            event="invoke_error",
            service="chat",
            trace_id=trace_id,
            latency_ms=latency_ms,
            error_type="TimeoutError",
        ).error("Request timed out")
        return ChatResponse(
            session_id=session_id_str,
            text="Request timed out. Please try again.",
            itinerary=None,
            message_type="error",
        )
    except Exception as e:
        latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)
        error_msg = str(e).lower()
        user_text: str
        if "503" in error_msg or "unavailable" in error_msg:
            user_text = (
                "The AI service is temporarily unavailable due to high demand. "
                "This is usually temporary - please try again in a few moments."
            )
        elif "rate limit" in error_msg or "429" in error_msg:
            user_text = (
                "You've reached the rate limit. Please wait a moment and try again."
            )
        elif (
            "name or service not known" in error_msg
            or "errno -2" in error_msg
            or "connecterror" in error_msg
        ):
            user_text = (
                "Cannot reach the AI service — VPN may be disconnected. "
                "Please connect your VPN and try again."
            )
        else:
            user_text = f"An error occurred: {e}"
        logger.bind(
            event="invoke_error",
            service="chat",
            trace_id=trace_id,
            latency_ms=latency_ms,
            error_type=type(e).__name__,
            error_message=str(e)[:300],
        ).error("invoke_agent exception")
        return ChatResponse(
            session_id=session_id_str,
            text=user_text,
            itinerary=None,
            message_type="error",
        )
