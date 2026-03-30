from __future__ import annotations

from datetime import date as Date, datetime as DateTime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

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
    image_url: str | None = None


# ─────────────────────────────────────────
# Day Plan
# ─────────────────────────────────────────


class DayPlan(BaseModel):
    day_number: int = Field(ge=1)
    date: Date = Field(description="ISO 8601 date string, e.g. 2025-06-01")
    morning: list[Activity] = Field(default_factory=list)
    afternoon: list[Activity] = Field(default_factory=list)
    evening: list[Activity] = Field(default_factory=list)


# ─────────────────────────────────────────
# Hotel
# ─────────────────────────────────────────


class HotelInfo(BaseModel):
    name: str
    check_in_date: Date = Field(description="ISO 8601 date string")
    check_out_date: Date = Field(description="ISO 8601 date string")
    price_per_night_min_hkd: float = Field(ge=0)
    price_per_night_max_hkd: float = Field(ge=0)

    @model_validator(mode="after")
    def check_price_range(self) -> HotelInfo:
        if self.price_per_night_min_hkd > self.price_per_night_max_hkd:
            raise ValueError(
                "price_per_night_min_hkd must be <= price_per_night_max_hkd"
            )
        return self


# ─────────────────────────────────────────
# Flight
# ─────────────────────────────────────────


class FlightStop(BaseModel):
    airport_code: str = Field(description="IATA airport code, e.g. NRT")
    airport_name: str
    arrival_time: DateTime | None = Field(default=None, description="ISO 8601 datetime")
    departure_time: DateTime | None = Field(
        default=None, description="ISO 8601 datetime"
    )

    @model_validator(mode="after")
    def check_at_least_one_time(self) -> FlightStop:
        if self.arrival_time is None and self.departure_time is None:
            raise ValueError(
                "At least one of arrival_time or departure_time must be set"
            )
        return self


class FlightInfo(BaseModel):
    direction: FlightDirection
    airline: str
    flight_number: str
    departure_airport: str = Field(description="IATA airport code")
    arrival_airport: str = Field(description="IATA airport code")
    departure_time: DateTime = Field(description="ISO 8601 datetime")
    arrival_time: DateTime = Field(description="ISO 8601 datetime")
    stops: Annotated[list[FlightStop], Field(default_factory=list, max_length=2)]
    booking_url: str | None = None


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

    @model_validator(mode="after")
    def check_duration_matches_days(self) -> TripItinerary:
        if len(self.days) != self.duration_days:
            raise ValueError(
                "duration_days must match the number of DayPlan entries in days"
            )
        return self
