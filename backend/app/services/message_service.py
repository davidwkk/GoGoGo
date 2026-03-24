"""Message persistence service — Minqi owns this."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.message import Message
from app.db.models.chat_session import ChatSession


async def append_message(
    db: AsyncSession,
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
    await db.commit()
    await db.refresh(message)
    return message


async def get_session_messages(
    db: AsyncSession,
    session_id: int,
) -> list[Message]:
    """Get all messages for a session, ordered by created_at."""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def create_session(
    db: AsyncSession,
    user_id: int,
    title: str = "New Chat",
) -> ChatSession:
    """Create a new chat session."""
    session = ChatSession(
        user_id=user_id,
        title=title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(
    db: AsyncSession,
    session_id: int,
) -> ChatSession | None:
    """Get a chat session by ID."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))
    )
    return result.scalar_one_or_none()


async def end_session(
    db: AsyncSession,
    session_id: int,
) -> ChatSession | None:
    """Mark a session as ended (placeholder for future extension)."""
    session = await get_session(db, session_id)
    if session:
        # Could add an `ended_at` field or `status` field here
        await db.commit()
    return session
