"""Tests for TripItinerary schema validation."""

from __future__ import annotations

from datetime import date as Date, datetime as DateTime

import pytest

from app.schemas.enums import FlightDirection
from app.schemas.itinerary import (
    Activity,
    DayPlan,
    FlightInfo,
    FlightStop,
    HotelInfo,
    TripItinerary,
)
from tests.fixtures.MOCK_ITINERARY import MOCK_ITINERARY


class TestTripItineraryValidation:
    """Test TripItinerary Pydantic model validation."""

    def test_mock_itinerary_serializes(self):
        """MOCK_ITINERARY roundtrips through JSON dump/load."""
        json_str = MOCK_ITINERARY.model_dump_json()
        restored = TripItinerary.model_validate_json(json_str)
        assert restored.destination == MOCK_ITINERARY.destination
        assert restored.duration_days == MOCK_ITINERARY.duration_days
        assert len(restored.days) == len(MOCK_ITINERARY.days)
        assert len(restored.hotels) == len(MOCK_ITINERARY.hotels)
        assert len(restored.flights) == len(MOCK_ITINERARY.flights)

    def test_valid_minimal_itinerary(self):
        """TripItinerary validates with minimal required fields."""
        itinerary = TripItinerary(
            destination="Hong Kong",
            duration_days=1,
            summary="Quick HK trip.",
            days=[
                DayPlan(
                    day_number=1,
                    date=Date(2025, 7, 1),
                    morning=[],
                    afternoon=[],
                    evening=[],
                ),
            ],
            hotels=[],
            flights=[],
            weather_summary="Hot and humid.",
        )
        assert itinerary.destination == "Hong Kong"
        assert itinerary.duration_days == 1

    def test_activity_model(self):
        """Activity model validates with all fields."""
        activity = Activity(
            name="Victoria Peak",
            description="Iconic hill with panoramic views.",
            location="Central, Hong Kong",
            map_url="https://maps.google.com/...",
            estimated_duration_minutes=120,
        )
        assert activity.name == "Victoria Peak"
        assert activity.estimated_duration_minutes == 120

    def test_day_plan_with_activities(self):
        """DayPlan validates with morning/afternoon/evening activities."""
        day = DayPlan(
            day_number=1,
            date=Date(2025, 7, 1),
            morning=[
                Activity(
                    name="Star Ferry",
                    description="Iconic ferry crossing Victoria Harbour.",
                    location="Central, Hong Kong",
                    estimated_duration_minutes=30,
                ),
            ],
            afternoon=[],
            evening=[
                Activity(
                    name="Temple Street Night Market",
                    description="Famous night market in Yau Ma Tei.",
                    location="Yau Ma Tei, Hong Kong",
                    estimated_duration_minutes=90,
                ),
            ],
        )
        assert day.day_number == 1
        assert len(day.morning) == 1
        assert len(day.evening) == 1

    def test_hotel_info_model(self):
        """HotelInfo validates with required fields."""
        hotel = HotelInfo(
            name="Grand Hyatt Hong Kong",
            check_in_date=Date(2025, 7, 1),
            check_out_date=Date(2025, 7, 3),
            price_per_night_min_hkd=1800.0,
            price_per_night_max_hkd=2500.0,
        )
        assert hotel.name == "Grand Hyatt Hong Kong"
        assert hotel.price_per_night_min_hkd == 1800.0

    def test_flight_info_with_stops(self):
        """FlightInfo validates with intermediate stops."""
        flight = FlightInfo(
            direction=FlightDirection.OUTBOUND,
            airline="Cathay Pacific",
            flight_number="CX883",
            departure_airport="HKG",
            arrival_airport="LAX",
            departure_time=DateTime(2025, 7, 1, 0, 30, 0),
            arrival_time=DateTime(2025, 7, 1, 21, 30, 0),
            stops=[
                FlightStop(
                    airport_code="NRT",
                    airport_name="Narita International Airport",
                    arrival_time=DateTime(2025, 7, 1, 8, 0, 0),
                    departure_time=DateTime(2025, 7, 1, 10, 0, 0),
                ),
            ],
        )
        assert flight.direction == FlightDirection.OUTBOUND
        assert len(flight.stops) == 1
        assert flight.stops[0].airport_code == "NRT"

    def test_flight_info_with_booking_url(self):
        """FlightInfo validates with booking_url."""
        flight = FlightInfo(
            direction=FlightDirection.OUTBOUND,
            airline="Cathay Pacific",
            flight_number="CX883",
            departure_airport="HKG",
            arrival_airport="LAX",
            departure_time=DateTime(2025, 7, 1, 0, 30, 0),
            arrival_time=DateTime(2025, 7, 1, 21, 30, 0),
            stops=[],
            booking_url="https://www.google.com/flights/CX883",
        )
        assert flight.booking_url == "https://www.google.com/flights/CX883"

    def test_flight_info_booking_url_is_optional(self):
        """FlightInfo booking_url is optional and defaults to None."""
        flight = FlightInfo(
            direction=FlightDirection.OUTBOUND,
            airline="Cathay Pacific",
            flight_number="CX883",
            departure_airport="HKG",
            arrival_airport="LAX",
            departure_time=DateTime(2025, 7, 1, 0, 30, 0),
            arrival_time=DateTime(2025, 7, 1, 21, 30, 0),
            stops=[],
        )
        assert flight.booking_url is None

    def test_invalid_duration_days_rejected(self):
        """duration_days must be >= 1."""
        with pytest.raises(Exception):
            TripItinerary(
                destination="HK",
                duration_days=0,  # invalid
                summary="Bad trip.",
                days=[],
                hotels=[],
                flights=[],
                weather_summary="Fine.",
            )

    def test_invalid_activity_duration_rejected(self):
        """estimated_duration_minutes must be >= 0."""
        with pytest.raises(Exception):
            Activity(
                name="Bad Activity",
                description="Test",
                location="HK",
                estimated_duration_minutes=-10,  # invalid
            )

    def test_model_json_schema_is_dict(self):
        """model_json_schema returns a dict suitable for Gemini response_json_schema."""
        schema = TripItinerary.model_json_schema()
        assert isinstance(schema, dict)
        assert "destination" in schema["properties"]
        assert "days" in schema["properties"]
        assert "hotels" in schema["properties"]
        assert "flights" in schema["properties"]
