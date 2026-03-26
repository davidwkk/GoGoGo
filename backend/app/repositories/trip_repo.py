"""Trip repository — DB access for trips table."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.trip import Trip


def create_trip(
    db: Session,
    user_id: int,
    session_id: int | None,
    title: str,
    destination: str,
    itinerary_json: dict,
) -> Trip:
    """Create a new trip."""
    trip = Trip(
        user_id=user_id,
        session_id=session_id,
        title=title,
        destination=destination,
        itinerary_json=itinerary_json,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def get_trip_by_id(db: Session, trip_id: int) -> Trip | None:
    """Fetch a trip by ID."""
    result = db.execute(select(Trip).where(Trip.id == trip_id))
    return result.scalar_one_or_none()


def get_trips_by_user(db: Session, user_id: int) -> list[Trip]:
    """Fetch all trips for a user, ordered by created_at descending."""
    result = db.execute(
        select(Trip)
        .where(Trip.user_id == user_id)
        .order_by(Trip.created_at.desc())
    )
    return list(result.scalars().all())


def delete_trip(db: Session, trip_id: int, user_id: int) -> bool:
    """Delete a trip. Returns True if deleted, False if not found or not owned."""
    trip = get_trip_by_id(db, trip_id)
    if trip is None or trip.user_id != user_id:
        return False
    db.delete(trip)
    db.commit()
    return True
