"""Chat request/response schemas."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: int | None = None


class ChatResponse(BaseModel):
    session_id: int
    itinerary: dict  # TripItinerary as dict