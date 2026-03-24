from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import invoke_agent
from app.services.message_service import append_message, create_session, get_session

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    POST /chat — sync chat endpoint (Phase 1).

    Phase 1: Simple sync response with TripItinerary JSON.
    Phase 2: Upgrade to SSE streaming with agent reasoning steps.
    """
    user_id = current_user["user_id"]

    # Get or create session
    if body.session_id:
        session = await get_session(body.session_id)
    else:
        session = await create_session(user_id=user_id)

    # Save user message
    await append_message(
        session_id=session.id,
        role="user",
        content=body.message,
    )

    # Invoke agent (David owns this)
    result = await invoke_agent(
        user_message=body.message,
        user_id=user_id,
        session_id=session.id,
    )

    # Save assistant response
    await append_message(
        session_id=session.id,
        role="assistant",
        content=result.model_dump_json(),
    )

    return ChatResponse(
        session_id=session.id,
        itinerary=result,
    )
