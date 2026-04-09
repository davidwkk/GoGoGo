"""User repository — DB access for users table."""

from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.user import User


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Fetch a user by their ID."""
    result = db.query(User).filter(User.id == user_id).first()
    logger.bind(
        event="db_get_user_by_id",
        layer="repository",
        user_id=str(user_id),
        found=result is not None,
    ).debug(f"DB: get_user_by_id — user={user_id} found={result is not None}")
    return result


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by their email address."""
    result = db.query(User).filter(User.email == email).first()
    logger.bind(
        event="db_get_user_by_email",
        layer="repository",
        email=email,
        found=result is not None,
    ).debug(f"DB: get_user_by_email — email={email} found={result is not None}")
    return result


def create_user(db: Session, username: str, email: str, hashed_password: str) -> User:
    """Create a new user."""
    user = User(username=username, email=email, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.bind(
        event="db_create_user",
        layer="repository",
        user_id=str(user.id),
        username=username,
        email=email,
    ).info(f"DB: User created — id={user.id} username={username}")
    return user


def update_username(db: Session, user_id: UUID, username: str) -> User | None:
    """Update a user's username. Returns the updated user or None if not found."""
    user = get_user_by_id(db, user_id)
    if not user:
        logger.bind(
            event="db_update_username_not_found",
            layer="repository",
            user_id=str(user_id),
        ).warning(f"DB: User {user_id} not found for username update")
        return None
    user.username = username
    db.commit()
    db.refresh(user)
    logger.bind(
        event="db_update_username",
        layer="repository",
        user_id=str(user_id),
        username=username,
    ).info(f"DB: Username updated — user={user_id} username={username}")
    return user


def update_password(db: Session, user_id: UUID, hashed_password: str) -> User | None:
    """Update a user's password. Returns the updated user or None if not found."""
    user = get_user_by_id(db, user_id)
    if not user:
        logger.bind(
            event="db_update_password_not_found",
            layer="repository",
            user_id=str(user_id),
        ).warning(f"DB: User {user_id} not found for password update")
        return None
    user.hashed_password = hashed_password
    db.commit()
    db.refresh(user)
    logger.bind(
        event="db_update_password",
        layer="repository",
        user_id=str(user_id),
    ).info(f"DB: Password updated — user={user_id}")
    return user
