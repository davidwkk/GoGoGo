"""Trip repository — DB access for trips table."""

from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.trip import Trip


def create_trip(
    db: Session,
    user_id: UUID,
    session_id: int | None,
    title: str,
    destination: str,
    itinerary_json: dict,
    trace_id: str | None = None,
) -> Trip:
    """Create a new trip."""
    logger.bind(
        event="repo_create_trip_start",
        layer="repository",
        trace_id=trace_id,
        user_id=str(user_id),
        session_id=session_id,
        title=title,
        destination=destination,
        itinerary_size_kb=len(str(itinerary_json)) / 1024,
    ).info("REPO: Creating trip")

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

    logger.bind(
        event="repo_create_trip_done",
        layer="repository",
        trace_id=trace_id,
        trip_id=trip.id,
        user_id=str(user_id),
    ).info(f"REPO: Trip created — id={trip.id}")

    return trip


def get_trip_by_id(
    db: Session, trip_id: int, trace_id: str | None = None
) -> Trip | None:
    """Fetch a trip by ID."""
    logger.bind(
        event="repo_get_trip_by_id",
        layer="repository",
        trace_id=trace_id,
        trip_id=trip_id,
    ).debug(f"REPO: Fetching trip by id={trip_id}")

    result = db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()

    logger.bind(
        event="repo_get_trip_by_id_result",
        layer="repository",
        trace_id=trace_id,
        trip_id=trip_id,
        found=trip is not None,
    ).debug(f"REPO: Trip {trip_id} {'found' if trip else 'not found'}")

    return trip


def get_trips_by_user(
    db: Session, user_id: UUID, trace_id: str | None = None
) -> list[Trip]:
    """Fetch all trips for a user, ordered by created_at descending."""
    logger.bind(
        event="repo_get_trips_by_user",
        layer="repository",
        trace_id=trace_id,
        user_id=str(user_id),
    ).debug(f"REPO: Fetching trips for user_id={user_id}")

    result = db.execute(
        select(Trip).where(Trip.user_id == user_id).order_by(Trip.created_at.desc())
    )
    trips = list(result.scalars().all())

    logger.bind(
        event="repo_get_trips_by_user_result",
        layer="repository",
        trace_id=trace_id,
        user_id=str(user_id),
        count=len(trips),
    ).debug(f"REPO: Found {len(trips)} trips for user")

    return trips


def delete_trip(
    db: Session, trip_id: int, user_id: UUID, trace_id: str | None = None
) -> bool:
    """Delete a trip. Returns True if deleted, False if not found or not owned."""
    logger.bind(
        event="repo_delete_trip",
        layer="repository",
        trace_id=trace_id,
        trip_id=trip_id,
        user_id=str(user_id),
    ).info(f"REPO: Deleting trip id={trip_id}")

    trip = get_trip_by_id(db, trip_id, trace_id=trace_id)
    if trip is None or trip.user_id != user_id:
        logger.bind(
            event="repo_delete_trip_denied",
            layer="repository",
            trace_id=trace_id,
            trip_id=trip_id,
            user_id=str(user_id),
            reason="not_found_or_not_owner",
        ).warning(f"REPO: Delete denied for trip {trip_id}")
        return False

    db.delete(trip)
    db.commit()

    logger.bind(
        event="repo_delete_trip_done",
        layer="repository",
        trace_id=trace_id,
        trip_id=trip_id,
    ).info(f"REPO: Trip {trip_id} deleted")

    return True
