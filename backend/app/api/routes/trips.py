from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_user_exists
from app.schemas.trip import TripCreate
from app.services.trip_service import save_trip
from app.services.trip_service import get_trip, get_trips

router = APIRouter()


@router.get("")
def list_trips(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all trips for the current user."""
    user_id = current_user["user_id"]
    verify_user_exists(user_id, db)
    return get_trips(db, user_id)


@router.post("")
def create_trip(
    body: TripCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create (save) a new trip itinerary for the current user."""
    user_id = current_user["user_id"]
    verify_user_exists(user_id, db)
    trace_id = str(uuid4())
    # session_id is optional here; Live uses manual save after plan generation
    return save_trip(
        db, user_id, session_id=None, itinerary=body.itinerary, trace_id=trace_id
    )


@router.get("/{trip_id}")
def get_single_trip(
    trip_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single trip by ID. Returns 404 if not found or not owned."""
    user_id = current_user["user_id"]
    verify_user_exists(user_id, db)
    trip = get_trip(db, trip_id, user_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )
    return trip


@router.delete("/{trip_id}")
def delete_single_trip(
    trip_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a trip. Returns 204 on success, 404 if not found or not owned."""
    from app.repositories.trip_repo import delete_trip

    user_id = current_user["user_id"]
    verify_user_exists(user_id, db)
    deleted = delete_trip(db, trip_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )
    return None


@router.post("/demo")
def get_demo_trip(db: Session = Depends(get_db)):
    """
    Return the seeded demo trip without requiring authentication.
    Used by the frontend Demo Trip button for quick testing.
    """
    from app.db.models.trip import Trip
    from app.schemas.itinerary import TripItinerary
    from sqlalchemy import select

    result = db.execute(
        select(Trip)
        .where(Trip.title.like("%Tokyo Spring%"))
        .order_by(Trip.created_at.desc())
    )
    trip = result.scalar_one_or_none()
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo trip not found. Please run `docker compose exec backend python /app/scripts/seed_db.py` first.",
        )
    itinerary = trip.itinerary_json or {}
    try:
        validated = TripItinerary.model_validate(itinerary)
        itinerary_data = validated.model_dump(mode="json")
    except Exception:
        # Graceful degradation - return raw if validation fails
        itinerary_data = itinerary
    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
        "duration_days": itinerary.get("duration_days", 0),
        "thumbnail_url": _extract_thumbnail_url(itinerary),
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
        "itinerary": itinerary_data,
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
