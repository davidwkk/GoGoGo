from __future__ import annotations

from datetime import date as Date, datetime as DateTime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import GroupType, TripPurpose
from app.schemas.itinerary import TripItinerary
from app.schemas.user import UserPreference

# ─────────────────────────────────────────
# Trip Parameters
# ─────────────────────────────────────────


class TripParameters(BaseModel):
    destination: str
    start_date: Date = Field(description="ISO 8601 date string, e.g. 2025-06-01")
    end_date: Date = Field(description="ISO 8601 date string, e.g. 2025-06-10")
    group_type: GroupType
    group_size: int = Field(ge=1)
    purpose: TripPurpose


# ─────────────────────────────────────────
# Chat History
# ─────────────────────────────────────────


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: DateTime = Field(description="ISO 8601 datetime")


# ─────────────────────────────────────────
# Chat Request / Response
# ─────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = Field(
        default=None,
        description="None on first message; UUID anonymous token or logged-in session",
    )
    generate_plan: bool = Field(
        default=False,
        description="Gate for expensive agent loop — if False, simple generate_content (no tools)",
    )
    trip_parameters: TripParameters | None = Field(
        default=None,
        description="Required only when generate_plan=True",
    )
    user_preferences: UserPreference | None = None  # None if guest


class ChatResponse(BaseModel):
    session_id: str = Field(description="Always returned so frontend can store it")
    text: str = Field(
        description="Plain text response, used when message_type is 'chat' or 'error'"
    )
    itinerary: TripItinerary | None = None
    message_type: Literal["chat", "itinerary", "error"] = "chat"
    history: list[ChatMessage] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_message_type(self) -> ChatResponse:
        if self.itinerary is not None and self.message_type != "itinerary":
            raise ValueError(
                'message_type must be "itinerary" when itinerary is populated'
            )
        return self
