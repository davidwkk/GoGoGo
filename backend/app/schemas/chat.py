"""Chat request/response schemas."""

from pydantic import BaseModel


class TripItinerary(BaseModel):
    destination: str
    duration_days: int
    summary: str
    days: list
    hotels: list
    flights: list
    weather_summary: str
    map_embed_url: str | None = None


class ChatRequest(BaseModel):
    message: str
    session_id: int | None = None


class ChatResponse(BaseModel):
    session_id: int
    itinerary: TripItinerary
