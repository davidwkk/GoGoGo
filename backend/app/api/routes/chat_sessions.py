"""Chat session routes — David owns route stubs; Minqi fills in logic.

POST /chat/sessions/{id}/end — end session and extract preferences
GET /chat/sessions/{id}/messages — retrieve session message history
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.message_service import end_session, get_session, get_session_messages
from app.services.preference_service import extract_and_save_preferences

router = APIRouter()


@router.post("/sessions/{session_id}/end")
async def end_chat_session(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    End a chat session and extract user preferences from conversation history.
    Triggers preference extraction via Gemini Flash-Lite and saves to DB.
    """
    # Get session and verify ownership
    session = end_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Build conversation history for preference extraction
    messages = get_session_messages(db, session_id)
    history = [{"role": msg.role, "content": msg.content} for msg in messages]

    # Extract preferences (fire and forget — don't block response)
    try:
        await extract_and_save_preferences(db, current_user["user_id"], history)
    except Exception:
        # Log but don't fail — preference extraction is best-effort
        pass

    return {"status": "session_ended", "session_id": session_id}


@router.get("/sessions/{session_id}/messages")
async def get_chat_session_messages(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all messages for a chat session."""
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    messages = get_session_messages(db, session_id)
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ],
    }
