"""Message persistence service — Minqi owns this."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.message import Message
from app.db.models.chat_session import ChatSession


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
    user_id: int,
    title: str = "New Chat",
) -> ChatSession:
    """Create a new chat session."""
    session = ChatSession(
        user_id=user_id,
        title=title,
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
