from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPreference


class TripParameters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    destination: str
    start_date: str
    end_date: str
    group_type: str
    group_size: int
    purpose: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    session_id: str | None = Field(
        default=None,
        description="None on first message; UUID anonymous token or logged-in session",
    )
    force_new_session: bool = Field(
        default=False,
        description="If true, backend will create a new session even when an active one exists",
    )
    generate_plan: bool = Field(
        default=False,
        description="If true, caller expects a structured trip plan (itinerary) response.",
    )
    trip_parameters: TripParameters | None = None
    user_preferences: UserPreference = Field(default_factory=UserPreference)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    text: str
    itinerary: dict | None = None
    message_type: str = "chat"
    trip_saved: bool = False
    trip_id: int | None = None
