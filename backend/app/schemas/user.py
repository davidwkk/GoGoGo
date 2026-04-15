from __future__ import annotations

from datetime import datetime as DateTime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.enums import DietaryRestriction, HotelTier, MaxStops, TravelStyle

# ─────────────────────────────────────────
# User Preference
# ─────────────────────────────────────────


class UserPreference(BaseModel):
    travel_style: TravelStyle = Field(default=TravelStyle.NO_SPECIAL_STYLE)
    dietary_restriction: DietaryRestriction = Field(
        default=DietaryRestriction.NO_RESTRICTION
    )
    hotel_tier: HotelTier = Field(default=HotelTier.MID_RANGE)
    budget_min_hkd: float = Field(default=5000.0, ge=0)
    budget_max_hkd: float = Field(default=20000.0, ge=0)
    max_flight_stops: MaxStops = Field(default=0)
    trip_planning_commands: str = Field(
        default="",
        description="Custom user instructions for trip planning (e.g., 'Prioritize commercial activities')",
    )

    @model_validator(mode="after")
    def check_budget_range(self) -> UserPreference:
        if self.budget_min_hkd > self.budget_max_hkd:
            raise ValueError("budget_min_hkd must be <= budget_max_hkd")
        return self


# ─────────────────────────────────────────
# User Schemas
# ─────────────────────────────────────────


class UserCreate(BaseModel):
    """Registration payload."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    """Update profile or preferences. All fields optional."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    preferences: UserPreference | None = None


class PasswordChange(BaseModel):
    """Change password payload."""

    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(BaseModel):
    """Safe public schema — no password exposed."""

    id: UUID
    email: EmailStr
    username: str
    preferences: UserPreference | None = None
    created_at: DateTime

    model_config = ConfigDict(from_attributes=True)
