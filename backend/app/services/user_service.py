"""User service — business logic for user profile operations."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.preference_repo import get_preferences, upsert_preferences
from app.repositories.user_repo import get_user_by_id, update_username
from app.schemas.user import UserPreference


def get_user_profile(db: Session, user_id: UUID) -> dict | None:
    """
    Fetch full user profile including preferences.
    Returns a dict suitable for UserResponse schema.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    prefs = get_preferences(db, user_id)
    # Convert stored preferences dict back to UserPreference model if present
    user_prefs = None
    if prefs:
        try:
            user_prefs = UserPreference.model_validate(prefs)
        except Exception:
            user_prefs = None

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "preferences": user_prefs,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def update_user_profile(
    db: Session,
    user_id: UUID,
    username: str | None = None,
    preferences: dict | None = None,
) -> dict | None:
    """
    Update user profile fields.
    Returns updated profile dict or None if user not found.
    """
    # Verify user exists
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    # Update username if provided
    if username is not None:
        user = update_username(db, user_id, username)

    # Upsert preferences if provided
    if preferences is not None:
        upsert_preferences(db, user_id, preferences)

    # Return updated profile
    return get_user_profile(db, user_id)
