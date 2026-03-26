"""Chat service — David owns agent invocation only."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.agent.agent import run_agent, run_agent_structured
from app.schemas.chat import ChatResponse

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Demo-grade timeout: acceptable for low-concurrency demo use.
# All httpx.AsyncClient calls use async with so connections clean up on cancel.
TIMEOUT_SECONDS = 25.0


async def invoke_agent(
    user_message: str,
    user_id: int,
    session_id: int | None = None,
    generate_plan: bool = False,
    preferences: dict | None = None,
    db: Session | None = None,
) -> ChatResponse:
    """
    Invoke the Gemini agent with the user's message.

    If generate_plan=False: simple chat via run_agent (no structured output).
    If generate_plan=True: runs full tool-calling loop + structured TripItinerary,
      then saves the trip to the database via trip_service.
    """
    session_id_str = str(session_id) if session_id else ""

    try:
        if generate_plan:
            itinerary = await asyncio.wait_for(
                run_agent_structured(
                    user_message=user_message,
                    preferences=preferences,
                ),
                timeout=TIMEOUT_SECONDS,
            )

            # Save trip to DB if db session provided
            if db is not None and itinerary is not None:
                from app.services import trip_service

                trip_service.save_trip(
                    db=db,
                    user_id=user_id,
                    session_id=session_id,
                    itinerary=itinerary,
                )

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
                ),
                timeout=TIMEOUT_SECONDS,
            )
            return ChatResponse(
                session_id=session_id_str,
                text=text,
                itinerary=None,
                message_type="chat",
            )
    except asyncio.TimeoutError:
        return ChatResponse(
            session_id=session_id_str,
            text="Request timed out. Please try again.",
            itinerary=None,
            message_type="error",
        )
    except Exception as e:
        return ChatResponse(
            session_id=session_id_str,
            text=f"An error occurred: {e}",
            itinerary=None,
            message_type="error",
        )
