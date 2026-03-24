from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db

router = APIRouter()


class TripCreate(BaseModel):
    title: str
    destination: str
    itinerary_json: dict


class TripResponse(BaseModel):
    id: int
    title: str
    destination: str
    itinerary_json: dict


@router.get("", response_model=list[TripResponse])
async def list_trips(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # TODO: Fetch via trip_repo
    return []


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # TODO: Fetch via trip_repo
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
async def create_trip(
    body: TripCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # TODO: Create via trip_repo
    return TripResponse(id=1, **body.model_dump())
