from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.trip import TripCreate, TripOut, TripSummary
from app.services.trip_service import trip_service

# Added prefix and tags so it shows up nicely in the Swagger API docs
router = APIRouter(tags=["trips"])

@router.get("", response_model=list[TripSummary])
def list_trips(
    # Note: We accept any type here in case Minqi's mock returns a dict instead of a User object for now
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a list of all trips for the currently logged-in user."""
    # Handle if Minqi's mock user is a dictionary or an object
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    return trip_service.get_user_trips(db=db, user_id=user_id)

@router.get("/{trip_id}", response_model=TripOut)
def get_trip(
    trip_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the full details and itinerary of a specific trip."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    trip = trip_service.get_trip_detail(db=db, trip_id=trip_id)
    
    if not trip or trip.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
        
    return trip

@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(
    body: TripCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a new trip."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    return trip_service.save_trip(
        db=db,
        user_id=user_id,
        session_id=None,
        title=body.title,
        destination=body.destination,
        itinerary=body.itinerary_json,
    )

@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a specific trip."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    trip = trip_service.get_trip_detail(db=db, trip_id=trip_id)
    
    if not trip or trip.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
        
    trip_service.delete_trip(db=db, trip_id=trip_id)
    return None