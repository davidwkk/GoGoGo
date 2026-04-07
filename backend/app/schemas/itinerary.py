from __future__ import annotations

from datetime import date as Date, datetime as DateTime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import ActivityCategory, CabinClass, FlightDirection


# ─────────────────────────────────────────
# Shared / Primitives
# ─────────────────────────────────────────


class PriceRange(BaseModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)

    @model_validator(mode="after")
    def check_min_le_max(self) -> PriceRange:
        if self.min > self.max:
            raise ValueError("min must be less than or equal to max")
        return self


# ─────────────────────────────────────────
# Activity
# ─────────────────────────────────────────


class Activity(BaseModel):
    # --- Core (LLM-generated) ---
    name: str
    description: str
    location: str
    estimated_duration_minutes: int = Field(ge=0)
    category: ActivityCategory

    # --- Enriched via Tavily/SERP ---
    address: str | None = None
    map_url: str | None = None
    opening_hours: str | None = None
    admission_fee_hkd: float | None = None
    rating: float | None = None
    review_count: int | None = None
    booking_url: str | None = None
    tips: list[str] | None = None

    # --- Media (Tavily image search / SERP) ---
    image_url: str | None = None
    thumbnail_url: str | None = None


# ─────────────────────────────────────────
# Day Plan
# ─────────────────────────────────────────


class DayPlan(BaseModel):
    # --- Core ---
    day_number: int = Field(ge=1)
    date: Date = Field(description="ISO 8601 date string, e.g. 2025-06-01")
    morning: list[Activity] = Field(default_factory=list)
    afternoon: list[Activity] = Field(default_factory=list)
    evening: list[Activity] = Field(default_factory=list)

    # --- LLM-generated ---
    theme: str | None = None
    notes: str | None = None

    # --- Budget ---
    estimated_daily_budget_hkd: PriceRange | None = None


# ─────────────────────────────────────────
# Hotel
# ─────────────────────────────────────────


class HotelInfo(BaseModel):
    # --- Core (LLM-generated) ---
    name: str
    check_in_date: Date = Field(description="ISO 8601 date string")
    check_out_date: Date = Field(description="ISO 8601 date string")
    price_per_night_hkd: PriceRange

    # --- Enriched via SERP ---
    address: str | None = None
    star_rating: int | None = None
    guest_rating: float | None = None
    booking_url: str | None = None
    image_url: str | None = None
    embed_map_url: str | None = Field(
        default=None,
        description="Google Maps embed URL for the hotel location (iframe src)",
    )


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
        if (
            self.arrival_time is not None
            and self.departure_time is not None
            and self.arrival_time > self.departure_time
        ):
            raise ValueError("arrival_time cannot be later than departure_time")
        return self


class Flight(BaseModel):
    # --- Core (LLM-generated) ---
    direction: FlightDirection
    airline: str
    flight_number: str
    departure_airport: str = Field(description="IATA airport code")
    arrival_airport: str = Field(description="IATA airport code")
    departure_time: DateTime = Field(description="ISO 8601 datetime")
    arrival_time: DateTime = Field(description="ISO 8601 datetime")
    stops: Annotated[list[FlightStop], Field(default_factory=list, max_length=2)]

    # --- Enriched via SERP ---
    duration_minutes: int | None = None
    cabin_class: CabinClass | None = None
    price_hkd: float | None = None
    booking_url: str | None = None


# ─────────────────────────────────────────
# Full Itinerary
# ─────────────────────────────────────────


class BudgetBreakdown(BaseModel):
    flights_hkd: PriceRange
    hotels_hkd: PriceRange
    activities_hkd: PriceRange
    total_hkd: PriceRange


class TripItinerary(BaseModel):
    # --- Core (LLM-generated) ---
    destination: str
    duration_days: int = Field(ge=1)
    summary: str
    days: list[DayPlan]
    hotels: list[HotelInfo]
    flights: list[Flight]

    # --- Weather-enriched ---
    weather_summary: str | None = None

    # --- Budget-computed ---
    estimated_total_budget_hkd: BudgetBreakdown | None = None

    @model_validator(mode="after")
    def check_duration_matches_days(self) -> TripItinerary:
        if len(self.days) != self.duration_days:
            raise ValueError(
                f"duration_days ({self.duration_days}) must match the number of "
                f"DayPlan entries in days ({len(self.days)}). "
                f"Please ensure you generate exactly {self.duration_days} day(s) of plans."
            )
        return self
