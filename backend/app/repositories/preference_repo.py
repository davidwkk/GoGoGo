"""Preference repository — upsert user preferences."""

from uuid import UUID

from loguru import logger
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models.preference import UserPreference


def upsert_preferences(db: Session, user_id: UUID, preferences: dict) -> UserPreference:
    """Insert or update preferences for a user. Uses upsert to avoid race conditions."""
    logger.bind(
        event="db_upsert_preferences_start",
        layer="repository",
        user_id=str(user_id),
    ).debug(f"DB: Upserting preferences for user={user_id}")

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
    if pref is None:
        logger.bind(
            event="db_upsert_preferences_error",
            layer="repository",
            user_id=str(user_id),
        ).error(f"DB: Preference row for user {user_id} not found after upsert")
        raise RuntimeError(f"Preference row for user {user_id} not found after upsert")
    logger.bind(
        event="db_upsert_preferences_done",
        layer="repository",
        user_id=str(user_id),
    ).debug(f"DB: Preferences upserted for user={user_id}")
    return pref


def get_preferences(db: Session, user_id: UUID) -> dict | None:
    """Get preferences for a user. Returns None if not set."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    found = pref is not None
    logger.bind(
        event="db_get_preferences",
        layer="repository",
        user_id=str(user_id),
        found=found,
    ).debug(f"DB: Get preferences — user={user_id} found={found}")
    return pref.preferences_json if pref else None
