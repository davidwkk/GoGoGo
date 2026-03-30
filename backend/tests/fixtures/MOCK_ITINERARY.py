"""MOCK_ITINERARY — hardcoded TripItinerary fixture to unblock Minqi and Xuan.

This fixture provides a realistic 3-day Tokyo trip that can be used
for UI development and testing before the real agent is ready.
"""

from __future__ import annotations

from datetime import date, datetime

from app.schemas.enums import FlightDirection
from app.schemas.itinerary import (
    Activity,
    DayPlan,
    FlightInfo,
    HotelInfo,
    TripItinerary,
)

MOCK_ITINERARY = TripItinerary(
    destination="Tokyo, Japan",
    duration_days=5,
    summary=(
        "A 5-day cultural immersion in Tokyo covering historic temples, "
        "modern districts, authentic cuisine, and day trips to nearby landmarks."
    ),
    days=[
        DayPlan(
            day_number=1,
            date=date(2025, 6, 1),
            morning=[
                Activity(
                    name="Senso-ji Temple",
                    description="Tokyo's oldest temple in Asakusa. Arrive early to avoid crowds.",
                    location="Asakusa, Tokyo",
                    estimated_duration_minutes=120,
                ),
            ],
            afternoon=[
                Activity(
                    name="Tokyo Skytree",
                    description="Iconic observation tower with panoramic city views.",
                    location="Sumida, Tokyo",
                    estimated_duration_minutes=90,
                ),
            ],
            evening=[
                Activity(
                    name="Ramen in Akihabara",
                    description="Explore anime districts and grab late-night ramen.",
                    location="Akihabara, Tokyo",
                    estimated_duration_minutes=60,
                ),
            ],
        ),
        DayPlan(
            day_number=2,
            date=date(2025, 6, 2),
            morning=[
                Activity(
                    name="Meiji Shrine",
                    description="Serene Shinto shrine surrounded by a forest in Shibuya.",
                    location="Shibuya, Tokyo",
                    estimated_duration_minutes=90,
                ),
            ],
            afternoon=[
                Activity(
                    name="Shibuya Crossing & Harajuku",
                    description="Experience the world's busiest intersection and trendy Harajuku fashion.",
                    location="Shibuya, Tokyo",
                    estimated_duration_minutes=120,
                ),
            ],
            evening=[
                Activity(
                    name="Izakaya dinner in Golden Gai",
                    description="Cozy tiny bars with local food in Shinjuku.",
                    location="Shinjuku, Tokyo",
                    estimated_duration_minutes=90,
                ),
            ],
        ),
        DayPlan(
            day_number=3,
            date=date(2025, 6, 3),
            morning=[
                Activity(
                    name="Tsukiji Outer Market",
                    description="Fresh sushi breakfast and exploring local Japanese street food.",
                    location="Tsukiji, Tokyo",
                    estimated_duration_minutes=90,
                ),
            ],
            afternoon=[
                Activity(
                    name="teamLab Borderless",
                    description="Immersive digital art museum in Odaiba.",
                    location="Odaiba, Tokyo",
                    estimated_duration_minutes=180,
                ),
            ],
            evening=[
                Activity(
                    name="Odaiba waterfront dinner",
                    description="Seafood restaurant with Tokyo Bay views.",
                    location="Odaiba, Tokyo",
                    estimated_duration_minutes=90,
                ),
            ],
        ),
        DayPlan(
            day_number=4,
            date=date(2025, 6, 4),
            morning=[
                Activity(
                    name="Day trip to Nikko",
                    description="UNESCO World Heritage shrines and bridges in the mountains.",
                    location="Nikko, Tochigi",
                    estimated_duration_minutes=240,
                ),
            ],
            afternoon=[],
            evening=[
                Activity(
                    name="Return to Tokyo",
                    description="Shinkansen back to Tokyo, evening at leisure.",
                    location="Tokyo",
                    estimated_duration_minutes=120,
                ),
            ],
        ),
        DayPlan(
            day_number=5,
            date=date(2025, 6, 5),
            morning=[
                Activity(
                    name="Kyoto Morning Market",
                    description="Traditional market with local produce and crafts.",
                    location="Kyoto",
                    estimated_duration_minutes=120,
                ),
            ],
            afternoon=[
                Activity(
                    name="Fushimi Inari Shrine",
                    description="Thousands of vermilion torii gates winding up the mountain.",
                    location="Kyoto",
                    estimated_duration_minutes=180,
                ),
            ],
            evening=[
                Activity(
                    name="Tea ceremony experience",
                    description="Traditional matcha tea ceremony in a historic tea house.",
                    location="Kyoto",
                    estimated_duration_minutes=60,
                ),
            ],
        ),
    ],
    hotels=[
        HotelInfo(
            name="Park Hyatt Tokyo",
            check_in_date=date(2025, 6, 1),
            check_out_date=date(2025, 6, 6),
            price_per_night_min_hkd=3500.0,
            price_per_night_max_hkd=5000.0,
        ),
    ],
    flights=[
        FlightInfo(
            direction=FlightDirection.OUTBOUND,
            airline="ANA",
            flight_number="NH847",
            departure_airport="HKG",
            arrival_airport="NRT",
            departure_time=datetime(2025, 6, 1, 8, 30, 0),
            arrival_time=datetime(2025, 6, 1, 13, 0, 0),
            stops=[],
            booking_url="https://www.google.com/flights/NH847",
        ),
        FlightInfo(
            direction=FlightDirection.RETURN,
            airline="ANA",
            flight_number="NH846",
            departure_airport="NRT",
            arrival_airport="HKG",
            departure_time=datetime(2025, 6, 5, 15, 0, 0),
            arrival_time=datetime(2025, 6, 5, 18, 30, 0),
            stops=[],
            booking_url="https://www.google.com/flights/NH846",
        ),
    ],
    weather_summary="Mild spring weather, 18-26°C. Occasional light rain. Comfortable for walking.",
)
