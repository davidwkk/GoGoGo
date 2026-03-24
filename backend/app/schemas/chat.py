from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import GroupType, TripPurpose
from app.schemas.itinerary import TripItinerary
from app.schemas.user import UserPreference

# ─────────────────────────────────────────
# Trip Parameters
# ─────────────────────────────────────────


class TripParameters(BaseModel):
    destination: str
    start_date: str = Field(description="ISO 8601 date string, e.g. 2025-06-01")
    end_date: str = Field(description="ISO 8601 date string, e.g. 2025-06-10")
    group_type: GroupType
    group_size: int = Field(ge=1)
    purpose: TripPurpose
    is_round_trip: bool = True


# ─────────────────────────────────────────
# Chat History
# ─────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = Field(description="'user' or 'assistant'")
    content: str
    created_at: str = Field(description="ISO 8601 datetime")


# ─────────────────────────────────────────
# Chat Request / Response
# ─────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = (
        None  # None on first message; UUID anonymous token or logged-in session
    )
    trip_parameters: TripParameters
    user_preferences: UserPreference | None = None  # None if guest


class ChatResponse(BaseModel):
    session_id: str  # always returned so frontend can store it
    itinerary: TripItinerary
    history: list[ChatMessage] = Field(default_factory=list)
