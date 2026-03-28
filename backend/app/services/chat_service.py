"""Chat service — David owns agent invocation only."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from app.agent.agent import run_agent, run_agent_structured
from app.schemas.chat import ChatResponse

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# LLM call timeout (30s for agent responses)
TIMEOUT_SECONDS = 30.0

logger = logging.getLogger(__name__)


async def invoke_agent(
    user_message: str,
    user_id: UUID | None,
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
    logger.info(
        f"[invoke_agent] Called with generate_plan={generate_plan}, user_message: {user_message[:100]}..."
    )
    logger.info(f"[invoke_agent] user_id={user_id}, session_id={session_id}")

    try:
        if generate_plan:
            logger.info(
                "[invoke_agent] Using run_agent_structured (generate_plan=True)"
            )
            itinerary = await asyncio.wait_for(
                run_agent_structured(
                    user_message=user_message,
                    preferences=preferences,
                ),
                timeout=TIMEOUT_SECONDS,
            )
            logger.info(
                f"[invoke_agent] Structured response received, itinerary destination: {itinerary.destination if itinerary else 'None'}"
            )

            # Save trip to DB if db session provided and user is authenticated
            if db is not None and itinerary is not None and user_id is not None:
                from app.services import trip_service

                trip_service.save_trip(
                    db=db,
                    user_id=user_id,
                    session_id=session_id,
                    itinerary=itinerary,
                )
                logger.info("[invoke_agent] Trip saved to DB")

            return ChatResponse(
                session_id=session_id_str,
                text="",
                itinerary=itinerary,
                message_type="itinerary",
            )
        else:
            logger.info("[invoke_agent] Using run_agent (generate_plan=False)")
            text = await asyncio.wait_for(
                run_agent(
                    user_message=user_message,
                    preferences=preferences,
                ),
                timeout=TIMEOUT_SECONDS,
            )
            logger.info(
                f"[invoke_agent] Agent response received, text length: {len(text)}"
            )
            logger.debug(f"[invoke_agent] Agent response text: {text[:200]}...")
            return ChatResponse(
                session_id=session_id_str,
                text=text,
                itinerary=None,
                message_type="chat",
            )
    except asyncio.TimeoutError:
        logger.error("[invoke_agent] Request timed out")
        return ChatResponse(
            session_id=session_id_str,
            text="Request timed out. Please try again.",
            itinerary=None,
            message_type="error",
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "503" in error_msg or "unavailable" in error_msg:
            user_message = (
                "The AI service is temporarily unavailable due to high demand. "
                "This is usually temporary - please try again in a few moments."
            )
        elif "rate limit" in error_msg or "429" in error_msg:
            user_message = (
                "You've reached the rate limit. Please wait a moment and try again."
            )
        elif (
            "name or service not known" in error_msg
            or "errno -2" in error_msg
            or "connecterror" in error_msg
        ):
            user_message = (
                "Cannot reach the AI service — VPN may be disconnected. "
                "Please connect your VPN and try again."
            )
        else:
            user_message = f"An error occurred: {e}"
        logger.error(f"[invoke_agent] Exception: {type(e).__name__}: {str(e)}")
        return ChatResponse(
            session_id=session_id_str,
            text=user_message,
            itinerary=None,
            message_type="error",
        )
