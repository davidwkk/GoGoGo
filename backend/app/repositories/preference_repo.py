"""Preference repository — upsert user preferences."""

from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models.preference import UserPreference


def upsert_preferences(db: Session, user_id: UUID, preferences: dict) -> UserPreference:
    """Insert or update preferences for a user. Uses upsert to avoid race conditions."""
    stmt = pg_insert(UserPreference).values(
        user_id=user_id, preferences_json=preferences
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserPreference.user_id],
        set_={"preferences_json": preferences},
    )
    db.execute(stmt)
    db.commit()
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    assert pref is not None, "Preference row must exist after upsert"
    return pref


def get_preferences(db: Session, user_id: UUID) -> dict | None:
    """Get preferences for a user. Returns None if not set."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    return pref.preferences_json if pref else None
