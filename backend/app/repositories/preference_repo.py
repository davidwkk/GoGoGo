"""Preference repository — upsert user preferences."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.preference import UserPreference


def upsert_preferences(db: Session, user_id: UUID, preferences: dict) -> UserPreference:
    """Insert or update preferences for a user. Creates if not exists, updates if exists."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if pref:
        pref.preferences_json = preferences
    else:
        pref = UserPreference(user_id=user_id, preferences_json=preferences)
        db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def get_preferences(db: Session, user_id: UUID) -> dict | None:
    """Get preferences for a user. Returns None if not set."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    return pref.preferences_json if pref else None
