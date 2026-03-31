from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.trip_service import get_trip, get_trips

router = APIRouter()


@router.get("")
def list_trips(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all trips for the current user."""
    user_id = current_user["user_id"]
    return get_trips(db, user_id)


@router.get("/{trip_id}")
def get_single_trip(
    trip_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single trip by ID. Returns 404 if not found or not owned."""
    user_id = current_user["user_id"]
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
    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
        "duration_days": itinerary.get("duration_days", 0),
        "thumbnail_url": _extract_thumbnail_url(itinerary),
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
        "itinerary": trip.itinerary_json,
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
