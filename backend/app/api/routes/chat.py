from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import invoke_agent
from app.services.message_service import append_message, create_session, get_session

router = APIRouter()


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
    )

    # Save assistant response
    append_message(
        db,
        session_id=session.id,
        role="assistant",
        content=result.model_dump_json(),
    )

    return result
