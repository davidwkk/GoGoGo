"""Trip service — business logic for trip CRUD operations."""

from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.repositories.trip_repo import (
    create_trip,
    get_trip_by_id,
    get_trips_by_user,
)
from app.schemas.itinerary import TripItinerary


def save_trip(
    db: Session,
    user_id: UUID,
    session_id: int | None,
    itinerary: TripItinerary,
    trace_id: str | None = None,
) -> dict:
    """
    Save a trip itinerary for a user.

    Serializes the TripItinerary Pydantic model to JSON for storage.
    Generates a title from destination and date range.
    """
    logger.bind(
        event="service_save_trip_start",
        layer="service",
        trace_id=trace_id,
        user_id=str(user_id),
        session_id=session_id,
        destination=itinerary.destination,
        duration_days=itinerary.duration_days,
    ).info(f"SERVICE: Saving trip for user_id={user_id}")

    itinerary_json = itinerary.model_dump(mode="json")

    # Generate title from destination and first/last date
    title = _generate_title(itinerary.destination, itinerary.days)

    trip = create_trip(
        db=db,
        user_id=user_id,
        session_id=session_id,
        title=title,
        destination=itinerary.destination,
        itinerary_json=itinerary_json,
        trace_id=trace_id,
    )

    logger.bind(
        event="service_save_trip_done",
        layer="service",
        trace_id=trace_id,
        trip_id=trip.id,
        user_id=str(user_id),
        title=title,
    ).info(f"SERVICE: Trip saved successfully — id={trip.id}, title={title}")

    return _trip_to_response(trip)


def get_trips(db: Session, user_id: UUID, trace_id: str | None = None) -> list[dict]:
    """List all trips for a user as summary dicts."""
    logger.bind(
        event="service_get_trips",
        layer="service",
        trace_id=trace_id,
        user_id=str(user_id),
    ).debug(f"SERVICE: Getting trips for user_id={user_id}")

    trips = get_trips_by_user(db, user_id, trace_id=trace_id)

    logger.bind(
        event="service_get_trips_result",
        layer="service",
        trace_id=trace_id,
        user_id=str(user_id),
        count=len(trips),
    ).debug(f"SERVICE: Found {len(trips)} trips")

    return [_trip_to_response(t) for t in trips]


def get_trip(
    db: Session, trip_id: int, user_id: UUID, trace_id: str | None = None
) -> dict | None:
    """Get a single trip by ID. Returns None if not found or not owned."""
    logger.bind(
        event="service_get_trip",
        layer="service",
        trace_id=trace_id,
        trip_id=trip_id,
        user_id=str(user_id),
    ).debug(f"SERVICE: Getting trip id={trip_id}")

    trip = get_trip_by_id(db, trip_id, trace_id=trace_id)
    if trip is None or trip.user_id != user_id:
        logger.bind(
            event="service_get_trip_not_found",
            layer="service",
            trace_id=trace_id,
            trip_id=trip_id,
            user_id=str(user_id),
        ).debug(f"SERVICE: Trip {trip_id} not found or not owned")
        return None

    # Validate and deserialize the stored JSON back to TripItinerary
    try:
        itinerary = TripItinerary.model_validate(trip.itinerary_json)
    except Exception:
        # If stored JSON is corrupted, return raw dict
        itinerary = trip.itinerary_json

    itinerary_dict = trip.itinerary_json or {}

    logger.bind(
        event="service_get_trip_result",
        layer="service",
        trace_id=trace_id,
        trip_id=trip_id,
        title=trip.title,
    ).debug(f"SERVICE: Returning trip {trip_id}")

    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
        "duration_days": itinerary_dict.get("duration_days", 0),
        "thumbnail_url": _extract_thumbnail_url(itinerary_dict),
        "itinerary": itinerary,
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
    }


def _generate_title(destination: str, days: list) -> str:
    """Generate a human-readable trip title from destination and dates."""
    if not days:
        return f"Trip to {destination}"
    dates = [d.date for d in days if d.date]
    if not dates:
        return f"Trip to {destination}"
    if len(dates) > 1:
        return f"{destination} ({dates[0]} - {dates[-1]})"
    return f"{destination} ({dates[0]})"


def _trip_to_response(trip) -> dict:
    """Convert a Trip ORM object to a response dict."""
    itinerary = trip.itinerary_json or {}
    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
        "duration_days": itinerary.get("duration_days", 0),
        "thumbnail_url": _extract_thumbnail_url(itinerary),
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
    }


def _extract_thumbnail_url(itinerary: dict) -> str | None:
    """Extract thumbnail URL from itinerary: first activity image or None."""
    days = itinerary.get("days", [])
    for day in days:
        for period in ("morning", "afternoon", "evening"):
            activities = day.get(period, [])
            if activities and len(activities) > 0:
                first = activities[0]
                if first.get("thumbnail_url"):
                    return first["thumbnail_url"]
                if first.get("image_url"):
                    return first["image_url"]
    return None
