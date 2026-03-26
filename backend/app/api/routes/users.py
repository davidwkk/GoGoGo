"""User profile routes — GET /users/me and PATCH /users/me."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import get_user_profile, update_user_profile

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's profile including preferences."""
    profile = get_user_profile(db, current_user["user_id"])
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return profile


@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user's username and/or preferences."""
    prefs_dict = None
    if body.preferences is not None:
        prefs_dict = body.preferences.model_dump()

    profile = update_user_profile(
        db,
        current_user["user_id"],
        username=body.username,
        preferences=prefs_dict,
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return profile
