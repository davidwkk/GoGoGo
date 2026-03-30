"""Trip service — business logic for trip CRUD operations."""

from uuid import UUID

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
) -> dict:
    """
    Save a trip itinerary for a user.

    Serializes the TripItinerary Pydantic model to JSON for storage.
    Generates a title from destination and date range.
    """
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
    )

    return _trip_to_response(trip)


def get_trips(db: Session, user_id: UUID) -> list[dict]:
    """List all trips for a user as summary dicts."""
    trips = get_trips_by_user(db, user_id)
    return [_trip_to_response(t) for t in trips]


def get_trip(db: Session, trip_id: int, user_id: UUID) -> dict | None:
    """Get a single trip by ID. Returns None if not found or not owned."""
    trip = get_trip_by_id(db, trip_id)
    if trip is None or trip.user_id != user_id:
        return None

    # Validate and deserialize the stored JSON back to TripItinerary
    try:
        itinerary = TripItinerary.model_validate(trip.itinerary_json)
    except Exception:
        # If stored JSON is corrupted, return raw dict
        itinerary = trip.itinerary_json

    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
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
    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
    }
