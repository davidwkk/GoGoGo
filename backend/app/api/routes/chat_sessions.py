"""Chat session routes — David owns route stubs; Minqi fills in logic.

POST /chat/sessions/{id}/end — end session and extract preferences
GET /chat/sessions/{id}/messages — retrieve session message history
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_optional, get_db
from app.services.message_service import (
    delete_session,
    end_session,
    get_active_session_by_user,
    get_session,
    get_session_messages,
    list_sessions_for_user,
    resolve_session,
    update_session_title,
)
from app.services.preference_service import extract_and_save_preferences

router = APIRouter()


class UpdateSessionTitleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=40)


@router.post("/sessions")
async def create_new_session(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new chat session (appears in left Chat History immediately)."""
    from app.services.message_service import create_session

    session = create_session(db, user_id=current_user["user_id"])
    return {
        "session_id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.get("/sessions")
async def list_chat_sessions(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = list_sessions_for_user(db, current_user["user_id"])
    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ]
    }


@router.patch("/sessions/{session_id}")
async def rename_chat_session(
    session_id: int,
    body: UpdateSessionTitleRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    updated = update_session_title(db, session_id, body.title)
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": updated.id,
        "title": updated.title,
        "created_at": updated.created_at.isoformat() if updated.created_at else None,
    }


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    ok = delete_session(db, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


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


@router.get("/sessions/active")
async def get_active_session_messages(
    guest_uid: str | None = Query(
        default=None, description="Guest UID from localStorage (if unauthenticated)"
    ),
    current_user: dict | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Get the active (most recent) session + message history.

    - Authenticated: returns latest session for current user
    - Guest: provide guest_uid to resolve latest guest session
    """
    user_id = current_user["user_id"] if current_user else None

    if user_id is not None:
        session = get_active_session_by_user(db, user_id)
        if session is None:
            return {"session_id": None, "messages": []}
    else:
        if not guest_uid:
            return {"session_id": None, "messages": []}
        session = await resolve_session(db, guest_uid, user_id=None)

    messages = get_session_messages(db, session.id)
    return {
        "session_id": str(session.id) if user_id is not None else str(guest_uid),
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
