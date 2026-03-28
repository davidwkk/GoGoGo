#!/usr/bin/env python3
"""Seed the database with sample users and demo trip for local development."""

from __future__ import annotations

import os
import sys
from uuid import uuid4

# Ensure app module is importable (works both locally and inside container)
# When run from backend/: __file__ = backend/scripts/seed_db.py
# When run from container: __file__ = /app/scripts/seed_db.py
_script_dir = os.path.dirname(__file__)
_backend_dir = os.path.dirname(_script_dir)  # .../backend/scripts -> .../backend
_root_dir = os.path.dirname(_backend_dir)  # .../backend -> repo root

sys.path.insert(0, _backend_dir)

# Try loading .env for local dev (outside container)
_env_path = os.path.join(_root_dir, ".env")
if os.path.exists(_env_path):
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_path)
    except ImportError:
        pass  # dotenv not installed, rely on environment variables

from app.core.security import get_password_hash  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.models.trip import Trip  # noqa: E402
from app.db.session import session_factory  # noqa: E402


SEED_USERS = [
    {"username": "testuser", "email": "user@gmail.com", "password": "user"},
]

DEMO_ITINERARY = {
    "destination": "Tokyo, Japan",
    "duration_days": 5,
    "summary": (
        "5-day cultural immersion through Tokyo — from ancient temples and electric "
        "districts to Mount Fuji views and sushi breakfasts. A perfect blend of "
        "tradition and modernity."
    ),
    "weather_summary": (
        "Pleasant spring weather (15-22°C). Light jacket recommended for evenings. "
        "Cherry blossoms in full bloom — bring a camera!"
    ),
    "map_embed_url": "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d206884.11874974792!2d139.491206!3d35.686725!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x60188bfbd89f700b:0x277c49ba34ed38!2sTokyo!5e0!3m2!1sen!2sjp!4v1700000000000!5m2!1sen!2sjp",
    "flights": [
        {
            "direction": "outbound",
            "airline": "Japan Airlines",
            "flight_number": "JL 123",
            "departure_airport": "HKG",
            "arrival_airport": "NRT",
            "departure_time": "2026-04-15T08:00:00",
            "arrival_time": "2026-04-15T13:00:00",
            "stops": [],
            "booking_url": "https://www.jal.co.jp/en/us/",
        },
        {
            "direction": "return",
            "airline": "Japan Airlines",
            "flight_number": "JL 456",
            "departure_airport": "NRT",
            "arrival_airport": "HKG",
            "departure_time": "2026-04-20T18:00:00",
            "arrival_time": "2026-04-20T21:30:00",
            "stops": [],
            "booking_url": "https://www.jal.co.jp/en/us/",
        },
    ],
    "hotels": [
        {
            "name": "Park Hyatt Tokyo",
            "check_in_date": "2026-04-15",
            "check_out_date": "2026-04-20",
            "price_per_night_min_hkd": 2800,
            "price_per_night_max_hkd": 4500,
        },
    ],
    "days": [
        {
            "day_number": 1,
            "date": "2026-04-15",
            "morning": [
                {
                    "name": "Senso-ji Temple",
                    "description": (
                        "Tokyo's oldest temple in Asakusa. Arrive early to beat the crowds "
                        "and explore the Thunder Gate, Five-Story Pagoda, and the shopping "
                        "street Nakamise-dori."
                    ),
                    "location": "Asakusa, Tokyo",
                    "map_url": "https://maps.google.com/?q=Senso-ji",
                    "estimated_duration_minutes": 120,
                },
            ],
            "afternoon": [
                {
                    "name": "Tokyo Skytree",
                    "description": (
                        "The tallest tower in Japan. Head to the Tembo Galleria observation "
                        "deck for panoramic views of the entire city and on clear days, "
                        "Mount Fuji."
                    ),
                    "location": "Sumida, Tokyo",
                    "map_url": "https://maps.google.com/?q=Tokyo+Skytree",
                    "estimated_duration_minutes": 180,
                },
            ],
            "evening": [
                {
                    "name": "Ramen Dinner in Shinjuku",
                    "description": (
                        "End the day with a steaming bowl of tonkotsu ramen at a local "
                        "favorite. The rich pork broth and hand-pulled noodles are the "
                        "perfect comfort food after a day of exploring."
                    ),
                    "location": "Shinjuku, Tokyo",
                    "map_url": None,
                    "estimated_duration_minutes": 60,
                },
            ],
        },
        {
            "day_number": 2,
            "date": "2026-04-16",
            "morning": [
                {
                    "name": "Tsukiji Outer Market",
                    "description": (
                        "Explore the bustling outer market lanes. Fresh sushi breakfast, "
                        "grilled seafood skewers, and Japanese produce. The best time to "
                        "visit is before 10am."
                    ),
                    "location": "Tsukiji, Tokyo",
                    "map_url": "https://maps.google.com/?q=Tsukiji+Market",
                    "estimated_duration_minutes": 120,
                },
            ],
            "afternoon": [
                {
                    "name": "teamLab Planets Tokyo",
                    "description": (
                        "Immersive digital art installation. Walk through knee-deep water "
                        "as projected flowers bloom around you. Book tickets in advance — "
                        "this is one of Tokyo's most popular attractions."
                    ),
                    "location": "Toyosu, Tokyo",
                    "map_url": "https://maps.google.com/?q=teamLab+Planets",
                    "estimated_duration_minutes": 150,
                },
            ],
            "evening": [
                {
                    "name": "Odaiba Seaside Dinner",
                    "description": (
                        "Dine with a view of Rainbow Bridge and Tokyo Bay. The waterfront "
                        "area offers dozens of restaurants spanning Japanese izakaya to "
                        "international cuisine."
                    ),
                    "location": "Odaiba, Tokyo",
                    "map_url": None,
                    "estimated_duration_minutes": 90,
                },
            ],
        },
        {
            "day_number": 3,
            "date": "2026-04-17",
            "morning": [
                {
                    "name": "Meiji Shrine & Harajuku",
                    "description": (
                        "Start with a tranquil walk through the forested Meiji Shrine, then "
                        "cross over to the eclectic Harajuku district for Takeshita Street "
                        "and people-watching at Yoyogi Park."
                    ),
                    "location": "Shibuya, Tokyo",
                    "map_url": "https://maps.google.com/?q=Meiji+Jingu",
                    "estimated_duration_minutes": 150,
                },
            ],
            "afternoon": [
                {
                    "name": "Shibuya Crossing & Hachiko",
                    "description": (
                        "Experience the world's busiest pedestrian scramble. Stand at the "
                        "corner and watch the organized chaos of 3,000 people crossing at "
                        "once. Don't forget the iconic Hachiko statue photo."
                    ),
                    "location": "Shibuya, Tokyo",
                    "map_url": "https://maps.google.com/?q=Shibuya+Crossing",
                    "estimated_duration_minutes": 60,
                },
            ],
            "evening": [
                {
                    "name": "Shinjuku Golden Gai",
                    "description": (
                        "Navigate the narrow alleys of Tokyo's most atmospheric nightlife "
                        "district. Tiny bars with just 5-6 seats, each with unique "
                        "character. Perfect for craft cocktails or Japanese whisky."
                    ),
                    "location": "Shinjuku, Tokyo",
                    "map_url": None,
                    "estimated_duration_minutes": 120,
                },
            ],
        },
        {
            "day_number": 4,
            "date": "2026-04-18",
            "morning": [
                {
                    "name": "Day Trip to Mount Fuji",
                    "description": (
                        "Full-day excursion to Chureito Pagoda and Lake Kawaguchi. The "
                        "5-story pagoda offers the classic Fuji photo shot, especially "
                        "stunning during cherry blossom season."
                    ),
                    "location": "Fujiyoshida, Yamanashi",
                    "map_url": "https://maps.google.com/?q=Chureito+Pagoda",
                    "estimated_duration_minutes": 240,
                },
            ],
            "afternoon": [
                {
                    "name": "Lake Kawaguchi",
                    "description": (
                        "Take the cable car up for unbeatable Fuji views, then stroll the "
                        "lakefront. Try local hoto noodles and grab a Fuji-shaped pancake "
                        "as a souvenir."
                    ),
                    "location": "Fujikawaguchiko, Yamanashi",
                    "map_url": None,
                    "estimated_duration_minutes": 120,
                },
            ],
            "evening": [
                {
                    "name": "Return to Tokyo + Akihabara",
                    "description": (
                        "Head back to Tokyo and explore the electric town of Akihabara. "
                        "Neon-lit arcades, anime shops, and the latest gadgets. Great for "
                        "evening exploration."
                    ),
                    "location": "Akihabara, Tokyo",
                    "map_url": None,
                    "estimated_duration_minutes": 120,
                },
            ],
        },
        {
            "day_number": 5,
            "date": "2026-04-19",
            "morning": [
                {
                    "name": "Ueno Park & Museums",
                    "description": (
                        "Tokyo National Museum houses one of the world's finest collections "
                        "of Japanese art. The park itself is beautiful during cherry "
                        "blossom season with rivers of pink petals."
                    ),
                    "location": "Ueno, Tokyo",
                    "map_url": "https://maps.google.com/?q=Ueno+Park",
                    "estimated_duration_minutes": 150,
                },
            ],
            "afternoon": [
                {
                    "name": "Ameyoko Shopping Street",
                    "description": (
                        "Busy market street with everything from fresh produce to designer "
                        "knockoffs. Great for last-minute souvenirs, snacks, and "
                        "experiencing authentic Tokyo street life."
                    ),
                    "location": "Ueno, Tokyo",
                    "map_url": None,
                    "estimated_duration_minutes": 90,
                },
            ],
            "evening": [
                {
                    "name": "Farewell Omakase Dinner",
                    "description": (
                        "End your trip with an omakase experience at a Michelin-starred "
                        "sushi restaurant in Ginza. A 20-course journey through the finest "
                        "seasonal fish — the perfect finale."
                    ),
                    "location": "Ginza, Tokyo",
                    "map_url": None,
                    "estimated_duration_minutes": 120,
                },
            ],
        },
    ],
}


def seed_users() -> None:
    """Insert seed users into the database, skipping those that already exist."""
    session = session_factory()
    try:
        for user_data in SEED_USERS:
            existing = (
                session.query(User).filter(User.email == user_data["email"]).first()
            )
            if existing:
                print(f"  Skipping {user_data['username']} (already exists)")
                continue

            hashed = get_password_hash(user_data["password"])
            user = User(
                id=uuid4(),
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=hashed,
            )
            session.add(user)
            print(f"  Created {user_data['username']} ({user_data['email']})")
        session.commit()
        print("Seed complete.")
    finally:
        session.close()


def seed_demo_trip() -> None:
    """Insert or update the demo trip for the test user."""
    session = session_factory()
    try:
        user = session.query(User).filter(User.email == "user@gmail.com").first()
        if not user:
            print("  Skipping demo trip (testuser not found — run users seed first)")
            return

        existing = (
            session.query(Trip)
            .filter(Trip.user_id == user.id, Trip.title.like("%Tokyo Spring%"))
            .first()
        )
        if existing:
            print(f"  Skipping demo trip (already exists: {existing.title})")
            return

        # Generate title from destination and first/last date
        dates = [d["date"] for d in DEMO_ITINERARY["days"]]
        title = f"Tokyo Spring Adventure ({dates[0]} – {dates[-1]})"

        trip = Trip(
            user_id=user.id,
            session_id=None,
            title=title,
            destination=DEMO_ITINERARY["destination"],
            itinerary_json=DEMO_ITINERARY,
        )
        session.add(trip)
        session.commit()
        print(f"  Created demo trip: {title}")
    finally:
        session.close()


if __name__ == "__main__":
    print("Seeding database with sample users and demo trip...")
    db_url = os.getenv("DATABASE_URL", "(not set - using container env)")
    print(
        f"  DATABASE_URL: {db_url[:50]}..."
        if db_url and len(db_url) > 50
        else f"  DATABASE_URL: {db_url}"
    )
    seed_users()
    seed_demo_trip()
