"""Message persistence service — Minqi owns this."""

from uuid import UUID, uuid4

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import delete, func, select
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
        logger.bind(
            event="guest_created",
            layer="service",
            guest_id=str(guest_uuid),
        ).info(f"DB: Guest created — guest_id={guest_uuid}")
    else:
        logger.bind(
            event="guest_found",
            layer="service",
            guest_id=str(guest_uuid),
        ).debug(f"DB: Guest found — guest_id={guest_uuid}")
    return guest


def list_sessions_for_guest(db: Session, guest_id: UUID) -> list[ChatSession]:
    result = db.execute(
        select(ChatSession)
        .where(ChatSession.guest_id == guest_id)
        .order_by(ChatSession.is_favorite.desc(), ChatSession.created_at.desc())
    )
    sessions = list(result.scalars().all())
    logger.bind(
        event="db_list_sessions_guest",
        layer="service",
        guest_id=str(guest_id),
        count=len(sessions),
    ).debug(f"DB: Found {len(sessions)} sessions for guest")
    return sessions


def append_message(
    db: Session,
    session_id: int,
    role: str,
    content: str,
    message_type: str | None = None,
) -> Message:
    """Append a message to a chat session."""
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        message_type=message_type,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    logger.bind(
        event="db_message_append",
        layer="service",
        session_id=session_id,
        message_id=message.id,
        role=role,
        message_type=message_type,
        content_len=len(content),
    ).debug(
        f"DB: Message appended — msg_id={message.id} session={session_id} role={role}"
    )
    return message


def append_tool_message(
    db: Session,
    session_id: int,
    tool_name: str,
    args: dict,
    result: dict,
) -> Message:
    """Append a tool call + result pair as a function-role message."""
    import json

    payload = json.dumps({"tool": tool_name, "args": args, "result": result})
    message = Message(
        session_id=session_id,
        role="function",
        content=payload,
        message_type="tool_result",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    logger.bind(
        event="db_tool_message_append",
        layer="service",
        session_id=session_id,
        message_id=message.id,
        tool_name=tool_name,
    ).debug(f"DB: Tool message appended — msg_id={message.id} tool={tool_name}")
    return message


def update_message_content(
    db: Session,
    message_id: int,
    content: str,
    message_type: str | None = None,
    thinking_steps: list | None = None,
) -> Message | None:
    """Update the content of an existing message."""
    result = db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if message is None:
        logger.bind(
            event="db_message_update_not_found",
            layer="service",
            message_id=message_id,
        ).warning(f"DB: Message {message_id} not found for update")
        return None
    message.content = content
    if message_type is not None:
        message.message_type = message_type
    if thinking_steps is not None:
        message.thinking_steps = thinking_steps
    db.commit()
    db.refresh(message)
    logger.bind(
        event="db_message_update",
        layer="service",
        message_id=message_id,
        message_type=message_type,
    ).debug(f"DB: Message updated — msg_id={message_id}")
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
    messages = list(result.scalars().all())
    logger.bind(
        event="db_get_session_messages",
        layer="service",
        session_id=session_id,
        count=len(messages),
    ).debug(f"DB: Fetched {len(messages)} messages for session {session_id}")
    return messages


def create_session(
    db: Session,
    user_id: UUID | None = None,
    title: str = "New Chat",
    guest_id: UUID | None = None,
) -> ChatSession:
    """Create a new chat session."""
    if title == "New Chat":
        # Number sessions per owner so sidebar shows New Chat 1, New Chat 2, ...
        # Use the highest existing "New Chat N" number + 1 to avoid duplicates
        def get_max_chat_number(owner_id: UUID | None, owner_field: str) -> int:
            filter_condition = (
                ChatSession.user_id == owner_id
                if owner_field == "user_id"
                else ChatSession.guest_id == owner_id
            )
            result = db.execute(select(ChatSession.title).where(filter_condition))
            titles = [row[0] for row in result.fetchall()]
            max_num = 0
            for t in titles:
                if t.startswith("New Chat "):
                    try:
                        num = int(t.split("New Chat ")[1])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
            return max_num

        if user_id is not None:
            max_num = get_max_chat_number(user_id, "user_id")
            title = f"New Chat {max_num + 1}"
        elif guest_id is not None:
            max_num = get_max_chat_number(guest_id, "guest_id")
            title = f"New Chat {max_num + 1}"

    session = ChatSession(
        user_id=user_id,
        title=title,
        guest_id=guest_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.bind(
        event="db_session_created",
        layer="service",
        session_id=session.id,
        user_id=str(user_id) if user_id else None,
        guest_id=str(guest_id) if guest_id else None,
        title=title,
    ).info(f"DB: Session created — id={session.id} title={title}")
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
    session = result.scalar_one_or_none()
    logger.bind(
        event="db_get_session",
        layer="service",
        session_id=session_id,
        found=session is not None,
    ).debug(f"DB: Get session {session_id} — found={session is not None}")
    return session


def list_sessions_for_user(db: Session, user_id: UUID) -> list[ChatSession]:
    result = db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.is_favorite.desc(), ChatSession.created_at.desc())
    )
    sessions = list(result.scalars().all())
    logger.bind(
        event="db_list_sessions_user",
        layer="service",
        user_id=str(user_id),
        count=len(sessions),
    ).debug(f"DB: Found {len(sessions)} sessions for user")
    return sessions


def patch_chat_session(
    db: Session,
    session_id: int,
    *,
    title: str | None = None,
    is_favorite: bool | None = None,
) -> ChatSession | None:
    if title is None and is_favorite is None:
        return None
    result = db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        logger.bind(
            event="db_session_patch_not_found",
            layer="service",
            session_id=session_id,
        ).warning(f"DB: Session {session_id} not found for patch")
        return None
    if title is not None:
        session.title = title
    if is_favorite is not None:
        session.is_favorite = is_favorite
    db.commit()
    db.refresh(session)
    logger.bind(
        event="db_session_patched",
        layer="service",
        session_id=session_id,
        title_set=title is not None,
        favorite_set=is_favorite is not None,
    ).debug(f"DB: Session patched — id={session_id}")
    return session


def update_session_title(
    db: Session, session_id: int, title: str
) -> ChatSession | None:
    """Rename session title (convenience wrapper)."""
    return patch_chat_session(db, session_id, title=title)


def clear_session_messages(db: Session, session_id: int) -> bool:
    """Delete all messages in a session, keeping the session itself."""
    db.execute(delete(Message).where(Message.session_id == session_id))
    db.commit()
    logger.bind(
        event="db_session_messages_cleared",
        layer="service",
        session_id=session_id,
    ).info(f"DB: Cleared messages for session {session_id}")
    return True


def delete_all_sessions(db: Session, user_id: UUID) -> int:
    """
    Delete all sessions and all their messages for a user.
    Returns the number of sessions deleted.
    """
    count_result = db.execute(
        select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)
    )
    count = count_result.scalar() or 0
    db.execute(delete(ChatSession).where(ChatSession.user_id == user_id))
    db.commit()
    logger.bind(
        event="db_delete_all_user_sessions",
        layer="service",
        user_id=str(user_id),
        deleted_count=count,
    ).info(f"DB: Deleted {count} sessions for user")
    return count


def delete_all_guest_sessions(db: Session, guest_id: UUID) -> int:
    """
    Delete all sessions and all their messages for a guest.
    Returns the number of sessions deleted.
    """
    count_result = db.execute(
        select(func.count(ChatSession.id)).where(ChatSession.guest_id == guest_id)
    )
    count = count_result.scalar() or 0
    db.execute(delete(ChatSession).where(ChatSession.guest_id == guest_id))
    db.commit()
    logger.bind(
        event="db_delete_all_guest_sessions",
        layer="service",
        guest_id=str(guest_id),
        deleted_count=count,
    ).info(f"DB: Deleted {count} sessions for guest")
    return count


def delete_session(db: Session, session_id: int) -> bool:
    """
    Delete a session and all its messages.

    Cascade delete is handled by SQLAlchemy relationship configuration.
    """
    session = db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    ).scalar_one_or_none()
    if session is None:
        logger.bind(
            event="db_delete_session_not_found",
            layer="service",
            session_id=session_id,
        ).warning(f"DB: Session {session_id} not found for deletion")
        return False

    db.delete(session)
    db.commit()
    logger.bind(
        event="db_session_deleted",
        layer="service",
        session_id=session_id,
    ).info(f"DB: Session {session_id} deleted")
    return True


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
    session = result.scalar_one_or_none()
    logger.bind(
        event="db_get_latest_session_guest",
        layer="service",
        guest_id=str(guest_id),
        session_id=session.id if session else None,
    ).debug(f"DB: Latest session for guest — found={session is not None}")
    return session


def get_active_session_by_user(db: Session, user_id: UUID) -> ChatSession | None:
    """
    Get the most recent chat session for a user (used for page refresh/session resume).

    Note: we don't have an explicit ended/status field yet, so "active" means
    "latest by created_at".
    """
    result = db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    logger.bind(
        event="db_get_active_session_user",
        layer="service",
        user_id=str(user_id),
        session_id=session.id if session else None,
    ).debug(f"DB: Active session for user — found={session is not None}")
    return session


def end_session(
    db: Session,
    session_id: int,
) -> ChatSession | None:
    """Mark a session as ended (placeholder for future extension)."""
    session = get_session(db, session_id)
    if session:
        # Could add an `ended_at` field or `status` field here
        db.commit()
        logger.bind(
            event="db_session_ended",
            layer="service",
            session_id=session_id,
        ).debug(f"DB: Session {session_id} ended")
    return session


async def resolve_session(
    db: Session,
    session_id: str | None,
    user_id: UUID | None,
    force_new_session: bool = False,
) -> ChatSession:
    """
    Resolve a session from a session_id string (integer PK or guest UUID).

    For integer session_id:
      - Authenticated users can only access their own sessions
      - Guests cannot access integer-PK sessions

    For guest UUID session_id:
      - Only guests may use it; creates a new session if none exists

    For no session_id:
      - For authenticated users: resumes latest session unless force_new_session=True
      - For guests: creates a new guest + session (frontend stores guest_uid)
    """
    if session_id:
        # Try parsing as integer PK first (authenticated user session)
        try:
            session_pk = int(session_id)
            session = get_session(db, session_pk)
            if session is None:
                logger.bind(
                    event="resolve_session_not_found",
                    layer="service",
                    session_id=session_id,
                ).warning(f"DB: Session {session_id} not found")
                raise HTTPException(status_code=404, detail="Session not found")
            if user_id is None:
                logger.bind(
                    event="resolve_session_forbidden",
                    layer="service",
                    session_id=session_id,
                ).warning("DB: Anonymous user tried to access user session")
                raise HTTPException(status_code=403, detail="Forbidden")
            if session.user_id != user_id:
                logger.bind(
                    event="resolve_session_forbidden",
                    layer="service",
                    session_id=session_id,
                    session_owner=str(session.user_id),
                    requester=str(user_id),
                ).warning("DB: User tried to access another user's session")
                raise HTTPException(status_code=403, detail="Forbidden")
            logger.bind(
                event="resolve_session_found",
                layer="service",
                session_id=session_pk,
                user_id=str(user_id),
            ).debug(f"DB: Resolved existing session {session_pk}")
            return session
        except ValueError:
            # Treat as guest UUID - look up existing session or create new one
            if user_id is not None:
                logger.bind(
                    event="resolve_session_invalid",
                    layer="service",
                    session_id=session_id,
                ).warning("DB: Authenticated user passed guest session_id")
                raise HTTPException(status_code=400, detail="Invalid session_id")
            guest = get_or_create_guest(db, session_id)
            session = get_latest_session_for_guest(db, guest.id)
            if session is None:
                session = create_session(db, user_id=None, guest_id=guest.id)
                logger.bind(
                    event="resolve_session_guest_created",
                    layer="service",
                    guest_id=str(guest.id),
                    session_id=session.id,
                ).info(f"DB: Created new guest session {session.id}")
            else:
                logger.bind(
                    event="resolve_session_guest_found",
                    layer="service",
                    guest_id=str(guest.id),
                    session_id=session.id,
                ).debug(f"DB: Resolved guest session {session.id}")
            return session
    else:
        # No session_id provided - create new session
        if user_id is not None:
            if force_new_session:
                session = create_session(db, user_id=user_id)
                logger.bind(
                    event="resolve_session_force_new",
                    layer="service",
                    user_id=str(user_id),
                    session_id=session.id,
                ).info(f"DB: Force-created new session {session.id} for user")
                return session
            session = get_active_session_by_user(db, user_id)
            if session is None:
                session = create_session(db, user_id=user_id)
                logger.bind(
                    event="resolve_session_new_for_user",
                    layer="service",
                    user_id=str(user_id),
                    session_id=session.id,
                ).info(f"DB: Created new session {session.id} for user")
            else:
                logger.bind(
                    event="resolve_session_resumed",
                    layer="service",
                    user_id=str(user_id),
                    session_id=session.id,
                ).debug(f"DB: Resumed existing session {session.id} for user")
            return session
        else:
            guest_uid = str(uuid4())
            guest = get_or_create_guest(db, guest_uid)
            session = create_session(db, user_id=None, guest_id=guest.id)
            logger.bind(
                event="resolve_session_new_guest",
                layer="service",
                guest_uid=guest_uid,
                session_id=session.id,
            ).info(f"DB: Created new guest session {session.id}")
            return session
