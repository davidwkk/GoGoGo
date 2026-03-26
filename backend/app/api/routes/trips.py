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
