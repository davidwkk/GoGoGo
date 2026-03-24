from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import FlightDirection

# ─────────────────────────────────────────
# Activity
# ─────────────────────────────────────────


class Activity(BaseModel):
    name: str
    description: str
    location: str
    map_url: str | None = None
    estimated_duration_minutes: int = Field(ge=0)


# ─────────────────────────────────────────
# Day Plan
# ─────────────────────────────────────────


class DayPlan(BaseModel):
    day_number: int = Field(ge=1)
    date: str = Field(description="ISO 8601 date string, e.g. 2025-06-01")
    morning: list[Activity] = Field(default_factory=list)
    afternoon: list[Activity] = Field(default_factory=list)
    evening: list[Activity] = Field(default_factory=list)


# ─────────────────────────────────────────
# Hotel
# ─────────────────────────────────────────


class HotelInfo(BaseModel):
    name: str
    check_in_date: str = Field(description="ISO 8601 date string")
    check_out_date: str = Field(description="ISO 8601 date string")
    price_per_night_min_hkd: float = Field(ge=0)
    price_per_night_max_hkd: float = Field(ge=0)


# ─────────────────────────────────────────
# Flight
# ─────────────────────────────────────────


class FlightStop(BaseModel):
    airport_code: str = Field(description="IATA airport code, e.g. NRT")
    airport_name: str
    arrival_time: str | None = Field(default=None, description="ISO 8601 datetime")
    departure_time: str | None = Field(default=None, description="ISO 8601 datetime")


class FlightInfo(BaseModel):
    direction: FlightDirection
    airline: str
    flight_number: str
    departure_airport: str = Field(description="IATA airport code")
    arrival_airport: str = Field(description="IATA airport code")
    departure_time: str = Field(description="ISO 8601 datetime")
    arrival_time: str = Field(description="ISO 8601 datetime")
    stops: list[FlightStop] = Field(default_factory=list, max_length=2)


# ─────────────────────────────────────────
# Full Itinerary
# ─────────────────────────────────────────


class TripItinerary(BaseModel):
    destination: str
    duration_days: int = Field(ge=1)
    summary: str
    days: list[DayPlan]
    hotels: list[HotelInfo]
    flights: list[FlightInfo]
    weather_summary: str
