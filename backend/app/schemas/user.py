from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.enums import DietaryRestriction, HotelTier, MaxStops, TravelStyle

# ─────────────────────────────────────────
# User Preference
# ─────────────────────────────────────────


class UserPreference(BaseModel):
    travel_style: TravelStyle = TravelStyle.RELAXING
    dietary_restriction: DietaryRestriction = DietaryRestriction.NONE
    hotel_tier: HotelTier = HotelTier.MID_RANGE
    budget_min_hkd: float = Field(default=5000.0, ge=0)
    budget_max_hkd: float = Field(default=20000.0, ge=0)
    max_flight_stops: MaxStops = MaxStops.ONE_STOP


# ─────────────────────────────────────────
# User Schemas
# ─────────────────────────────────────────


class UserCreate(BaseModel):
    """Registration payload."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str


class UserUpdate(BaseModel):
    """Update profile or preferences. All fields optional."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    preferences: UserPreference | None = None


class UserResponse(BaseModel):
    """Safe public schema — no password exposed."""

    id: UUID
    email: EmailStr
    username: str
    preferences: UserPreference | None = None
    created_at: str = Field(description="ISO 8601 datetime")

    model_config = {"from_attributes": True}
