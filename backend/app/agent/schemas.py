"""Agent-specific Pydantic output models.

These are used by the Gemini agent for structured output (final response).
Mid-loop tool responses use plain dicts to keep things lightweight.

Gemini schema constraints:
  ✅ str, int, float, bool, list[str], enum, nested BaseModel
  ⚠️ dict[str, int] — not well supported, avoid
  ❌ Raw dict types not supported
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ─────────────────────────────────────────
# Transport
# ─────────────────────────────────────────


class TransportOption(BaseModel):
    from_location: str
    to_location: str
    transport_type: str = Field(
        description="One of: MTR, bus, taxi, train, ferry, walk"
    )
    duration: str = Field(description="Human-readable duration, e.g. '45 min' or '1h 30m'")
    cost: str = Field(description="Estimated cost, e.g. 'HKD 50' or 'Free'")
    details: str | None = None


# ─────────────────────────────────────────
# Attraction
# ─────────────────────────────────────────


class Coordinates(BaseModel):
    lat: float
    lon: float


class AttractionItem(BaseModel):
    name: str
    description: str = Field(description="Brief summary from Wikipedia")
    thumbnail_url: str | None = None
    coordinates: Coordinates | None = None
    category: str | None = None


# ─────────────────────────────────────────
# Hotel (agent tool response — NOT the same as HotelInfo in schemas/)
# ─────────────────────────────────────────


class HotelItem(BaseModel):
    name: str
    location: str
    price_per_night: str = Field(description="Price per night, e.g. 'HKD 1,200'")
    rating: str | None = Field(default=None, description="e.g. '4.5/5'")
    amenities: list[str] = Field(default_factory=list)
    booking_url: str | None = None


# ─────────────────────────────────────────
# Flight (agent tool response — NOT the same as FlightInfo in schemas/)
# ─────────────────────────────────────────


class FlightItem(BaseModel):
    airline: str
    flight_number: str
    departure: str = Field(description="Departure airport code or city")
    arrival: str = Field(description="Arrival airport code or city")
    duration: str = Field(description="e.g. '4h 30m'")
    price: str = Field(description="e.g. 'HKD 3,500'")
    booking_url: str | None = None
