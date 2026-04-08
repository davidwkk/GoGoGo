"""User repository — DB access for users table."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.user import User


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Fetch a user by their ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by their email address."""
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, username: str, email: str, hashed_password: str) -> User:
    """Create a new user."""
    user = User(username=username, email=email, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_username(db: Session, user_id: UUID, username: str) -> User | None:
    """Update a user's username. Returns the updated user or None if not found."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.username = username
    db.commit()
    db.refresh(user)
    return user


def update_password(db: Session, user_id: UUID, hashed_password: str) -> User | None:
    """Update a user's password. Returns the updated user or None if not found."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.hashed_password = hashed_password
    db.commit()
    db.refresh(user)
    return user
