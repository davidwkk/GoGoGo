"""Message persistence service — Minqi owns this."""

from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.chat_session import ChatSession
from app.db.models.guest import Guest
from app.db.models.message import Message


def get_or_create_guest(db: Session, guest_uid: str) -> Guest:
    """Get an existing guest or create a new one."""
    guest_uuid = UUID(guest_uid)
    result = db.execute(select(Guest).where(Guest.id == guest_uuid))
    guest = result.scalar_one_or_none()
    if guest is None:
        guest = Guest(id=guest_uuid)
        db.add(guest)
        db.commit()
        db.refresh(guest)
    return guest


def append_message(
    db: Session,
    session_id: int,
    role: str,
    content: str,
) -> Message:
    """Append a message to a chat session."""
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def update_message_content(
    db: Session,
    message_id: int,
    content: str,
) -> Message | None:
    """Update the content of an existing message."""
    result = db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if message is None:
        return None
    message.content = content
    db.commit()
    db.refresh(message)
    return message


def get_session_messages(
    db: Session,
    session_id: int,
) -> list[Message]:
    """Get all messages for a session, ordered by created_at."""
    result = db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


def create_session(
    db: Session,
    user_id: int | None = None,
    title: str = "New Chat",
    guest_id: UUID | None = None,
) -> ChatSession:
    """Create a new chat session."""
    session = ChatSession(
        user_id=user_id,
        title=title,
        guest_id=guest_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(
    db: Session,
    session_id: int,
) -> ChatSession | None:
    """Get a chat session by ID."""
    result = db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))
    )
    return result.scalar_one_or_none()


def get_latest_session_for_guest(
    db: Session,
    guest_id: UUID,
) -> ChatSession | None:
    """Get the most recent chat session for a guest, or None if none exists."""
    result = db.execute(
        select(ChatSession)
        .where(ChatSession.guest_id == guest_id)
        .order_by(ChatSession.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def end_session(
    db: Session,
    session_id: int,
) -> ChatSession | None:
    """Mark a session as ended (placeholder for future extension)."""
    session = get_session(db, session_id)
    if session:
        # Could add an `ended_at` field or `status` field here
        db.commit()
    return session


async def resolve_session(
    db: Session,
    session_id: str | None,
    user_id: int | None,
) -> ChatSession:
    """
    Resolve a session from a session_id string (integer PK or guest UUID).

    For integer session_id:
      - Authenticated users can only access their own sessions
      - Guests cannot access integer-PK sessions

    For guest UUID session_id:
      - Only guests may use it; creates a new session if none exists

    For no session_id:
      - Creates a new session for authenticated users or guests
    """
    if session_id:
        # Try parsing as integer PK first (authenticated user session)
        try:
            session_pk = int(session_id)
            session = get_session(db, session_pk)
            if session is None:
                raise HTTPException(status_code=404, detail="Session not found")
            if user_id is None:
                raise HTTPException(status_code=403, detail="Forbidden")
            if session.user_id != user_id:
                raise HTTPException(status_code=403, detail="Forbidden")
            return session
        except ValueError:
            # Treat as guest UUID - look up existing session or create new one
            if user_id is not None:
                raise HTTPException(status_code=400, detail="Invalid session_id")
            guest = get_or_create_guest(db, session_id)
            session = get_latest_session_for_guest(db, guest.id)
            if session is None:
                session = create_session(db, user_id=None, guest_id=guest.id)
            return session
    else:
        # No session_id provided - create new session
        if user_id is not None:
            return create_session(db, user_id=user_id)
        else:
            guest_uid = str(uuid4())
            guest = get_or_create_guest(db, guest_uid)
            return create_session(db, user_id=None, guest_id=guest.id)
