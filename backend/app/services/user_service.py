"""User service — business logic for user profile operations."""

from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.repositories.preference_repo import get_preferences, upsert_preferences
from app.repositories.user_repo import get_user_by_id, update_username, update_password
from app.schemas.user import UserPreference
from app.core.security import verify_password, get_password_hash


def get_user_profile(db: Session, user_id: UUID) -> dict | None:
    """
    Fetch full user profile including preferences.
    Returns a dict suitable for UserResponse schema.
    """
    logger.bind(
        event="service_get_user_profile",
        layer="service",
        user_id=str(user_id),
    ).debug(f"SERVICE: Getting profile for user={user_id}")

    user = get_user_by_id(db, user_id)
    if not user:
        logger.bind(
            event="service_get_user_profile_not_found",
            layer="service",
            user_id=str(user_id),
        ).warning(f"SERVICE: User {user_id} not found")
        return None

    prefs = get_preferences(db, user_id)
    # Convert stored preferences dict back to UserPreference model if present
    user_prefs = None
    if prefs:
        try:
            user_prefs = UserPreference.model_validate(prefs)
        except Exception:
            user_prefs = None

    logger.bind(
        event="service_get_user_profile_result",
        layer="service",
        user_id=str(user_id),
        username=user.username,
    ).debug(f"SERVICE: Returning profile for user={user_id}")
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
    logger.bind(
        event="service_update_user_profile",
        layer="service",
        user_id=str(user_id),
        username=username,
        has_preferences=preferences is not None,
    ).debug(f"SERVICE: Updating profile for user={user_id}")

    # Verify user exists
    user = get_user_by_id(db, user_id)
    if not user:
        logger.bind(
            event="service_update_user_profile_not_found",
            layer="service",
            user_id=str(user_id),
        ).warning(f"SERVICE: User {user_id} not found for profile update")
        return None

    # Update username if provided
    if username is not None:
        user = update_username(db, user_id, username)
        logger.bind(
            event="service_username_updated",
            layer="service",
            user_id=str(user_id),
            username=username,
        ).info(f"SERVICE: Username updated to '{username}' for user={user_id}")

    # Upsert preferences if provided
    if preferences is not None:
        upsert_preferences(db, user_id, preferences)
        logger.bind(
            event="service_preferences_updated",
            layer="service",
            user_id=str(user_id),
        ).info(f"SERVICE: Preferences upserted for user={user_id}")

    # Return updated profile
    updated = get_user_profile(db, user_id)
    logger.bind(
        event="service_update_user_profile_done",
        layer="service",
        user_id=str(user_id),
    ).info(f"SERVICE: Profile updated for user={user_id}")
    return updated


def change_password(
    db: Session,
    user_id: UUID,
    current_password: str,
    new_password: str,
) -> tuple[bool, str]:
    """
    Change user's password.
    Returns (success, error_message).
    """
    logger.bind(
        event="service_change_password",
        layer="service",
        user_id=str(user_id),
    ).debug(f"SERVICE: Password change attempt for user={user_id}")

    user = get_user_by_id(db, user_id)
    if not user:
        logger.bind(
            event="service_change_password_user_not_found",
            layer="service",
            user_id=str(user_id),
        ).warning(f"SERVICE: Password change failed — user not found: {user_id}")
        return (False, "User not found")

    if not verify_password(current_password, user.hashed_password):
        logger.bind(
            event="service_change_password_invalid_current",
            layer="service",
            user_id=str(user_id),
        ).warning(
            f"SERVICE: Password change failed — invalid current password for user={user_id}"
        )
        return (False, "Current password is incorrect")

    hashed = get_password_hash(new_password)
    update_password(db, user_id, hashed)
    logger.bind(
        event="service_change_password_success",
        layer="service",
        user_id=str(user_id),
    ).info(f"SERVICE: Password changed successfully for user={user_id}")
    return (True, "")
