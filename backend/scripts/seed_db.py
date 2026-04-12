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
    {"username": "user", "email": "user@gmail.com", "password": "user"},
    {"username": "user1", "email": "user1@gmail.com", "password": "user"},
    {"username": "user2", "email": "user2@gmail.com", "password": "user"},
    {"username": "user3", "email": "user3@gmail.com", "password": "user"},
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
    "estimated_total_budget_hkd": {
        "flights_hkd": {"min": 4200, "max": 4800},
        "hotels_hkd": {"min": 14000, "max": 22600},
        "activities_hkd": {"min": 1200, "max": 2500},
        "total_hkd": {"min": 19400, "max": 29900},
    },
    "flights": [
        {
            "direction": "outbound",
            "airline": "Japan Airlines",
            "flight_number": "JL 123",
            "departure_airport": "HKG",
            "arrival_airport": "NRT",
            "departure_airport_name": "Hong Kong International Airport",
            "arrival_airport_name": "Narita International Airport",
            "departure_time": "2026-04-15T08:00:00",
            "arrival_time": "2026-04-15T13:00:00",
            "stops": [],
            "duration_minutes": 300,
            "airplane": "Boeing 787-9",
            "travel_class": "economy",
            "booking_url": "https://www.google.com/travel/flights/search?q=HKG+to+NRT%2C+2026-04-15+to+2026-04-19&hl=en&curr=HKD",
            "price_hkd": 4200.0,
        },
        {
            "direction": "return",
            "airline": "Japan Airlines",
            "flight_number": "JL 456",
            "departure_airport": "NRT",
            "arrival_airport": "HKG",
            "departure_airport_name": "Narita International Airport",
            "arrival_airport_name": "Hong Kong International Airport",
            "departure_time": "2026-04-19T18:00:00",
            "arrival_time": "2026-04-19T21:30:00",
            "stops": [],
            "duration_minutes": 210,
            "airplane": "Boeing 787-8",
            "travel_class": "economy",
            "booking_url": "https://www.google.com/travel/flights/search?q=NRT+to+HKG%2C+2026-04-15+to+2026-04-19&hl=en&curr=HKD",
            "price_hkd": 4800.0,
        },
    ],
    "hotels": [
        {
            "name": "Park Hyatt Tokyo",
            "check_in_date": "2026-04-15",
            "check_out_date": "2026-04-19",
            "price_per_night_hkd": {"min": 2800, "max": 4500},
            "star_rating": 5,
            "guest_rating": 9.2,
            "hotel_class_int": 5,
            "reviews": 8743,
            "location_rating": 9.4,
            "amenities": [
                "Infinity pool",
                "Spa",
                "Fitness centre",
                "3 restaurants",
                "Bar",
                "Concierge",
                "Room service",
                "Laundry service",
                "Valet parking",
                "Free WiFi",
            ],
            "description": (
                "Luxury five-star hotel in Shinjuku with stunning Tokyo views. "
                "Famous from 'Lost in Translation', featuring contemporary Japanese art, "
                "a renowned spa, and award-winning dining including the New York Grill."
            ),
            "booking_url": "https://www.google.com/travel/hotels?q=Park+Hyatt+Tokyo&check_in=2026-04-15&check_out=2026-04-19&hl=en&curr=HKD",
            "address": "3-7-1-2 Nishi Shinjuku, Shinjuku City, Tokyo 163-1055",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Park_Hyatt_Tokyo.jpg/1280px-Park_Hyatt_Tokyo.jpg",
            "embed_map_url": "https://www.google.com/maps?q=Park+Hyatt+Tokyo&output=embed",
        },
    ],
    "days": [
        {
            "day_number": 1,
            "date": "2026-04-15",
            "theme": "Arrival & Traditional Tokyo",
            "notes": "Arrival day. Take it easy and adjust to the timezone. Evening ramen recommended.",
            "estimated_daily_budget_hkd": {"min": 400, "max": 800},
            "morning": [
                {
                    "name": "Senso-ji Temple",
                    "description": (
                        "Tokyo's oldest temple in Asakusa. Arrive early to beat the crowds "
                        "and explore the Thunder Gate, Five-Story Pagoda, and the shopping "
                        "street Nakamise-dori."
                    ),
                    "location": "Asakusa, Tokyo",
                    "category": "culture",
                    "estimated_duration_minutes": 120,
                    "address": "2-3-1 Asakusa, Taito City, Tokyo 111-0032",
                    "map_url": "https://maps.google.com/maps?q=35.7148,139.7967&output=embed",
                    "opening_hours": "6:00 AM - 5:00 PM",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.7,
                    "review_count": 89234,
                    "tips": [
                        "Arrive before 8 AM to avoid crowds",
                        "Try the fortune slips (omikuji)",
                        "Nakamise-dori shopping street opens at 9 AM",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Senso-ji_Temple_aside_Kaminarimon_croped.jpg/1280px-Senso-ji_Temple_aside_Kaminarimon_croped.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Senso-ji_Temple_aside_Kaminarimon_croped.jpg/320px-Senso-ji_Temple_aside_Kaminarimon_croped.jpg",
                    "coordinates": {"lat": 35.7148, "lon": 139.7967},
                    "wiki_url": "https://en.wikipedia.org/wiki/Sens%C5%8D-ji",
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
                    "category": "sightseeing",
                    "estimated_duration_minutes": 180,
                    "address": "1-1-2 Oshiage, Sumida City, Tokyo 131-0045",
                    "map_url": "https://maps.google.com/maps?q=35.7101,139.8107&output=embed",
                    "opening_hours": "10:00 AM - 9:00 PM",
                    "admission_fee_hkd": 210.0,
                    "rating": 4.5,
                    "review_count": 45123,
                    "tips": [
                        "Book tickets online to skip the queue",
                        "Tembo Galleria offers the best views",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Tokyo_Skytree_2013_July.JPG/1280px-Tokyo_Skytree_2013_July.JPG",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Tokyo_Skytree_2013_July.JPG/320px-Tokyo_Skytree_2013_July.JPG",
                    "booking_url": "https://www.tokyo-skytree.jp/ticket/",
                    "coordinates": {"lat": 35.7101, "lon": 139.8107},
                    "wiki_url": "https://en.wikipedia.org/wiki/Tokyo_Skytree",
                },
            ],
            "evening": [
                {
                    "name": "Ramen Dinner in Shinjuku",
                    "description": (
                        "Ramen is a Japanese noodle dish consisting of Chinese-style alkaline "
                        "wheat noodles served in a meat or fish-based broth, often flavored with "
                        "soy sauce or miso. Toppings range from sliced pork (chashu) and "
                        "soft-boiled eggs to nori and scallions. Tonkotsu ramen features a "
                        "rich, creamy pork bone broth simmered for hours until deeply savory. "
                        "Shinjuku's Kabukicho district is home to some of Tokyo's finest ramen "
                        "shops, each with their own house specialty. Slurping is not only "
                        "acceptable — it is encouraged, as it cools the noodles and aerates the "
                        "aromatics for maximum flavor. A perfect, soul-warming end to a day "
                        "of temple visits and sightseeing."
                    ),
                    "location": "Shinjuku, Tokyo",
                    "category": "food",
                    "estimated_duration_minutes": 60,
                    "address": "1-1-1 Kabukicho, Shinjuku City, Tokyo 160-0021",
                    "opening_hours": "11:00 AM - 4:00 AM",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.4,
                    "review_count": 3210,
                    "tips": [
                        "Golden Gai nearby has great bars for after-dinner drinks"
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/71/Ramen_Tonkotsu_by_Hiroshi_Niiyama.jpg/1280px-Ramen_Tonkotsu_by_Hiroshi_Niiyama.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/71/Ramen_Tonkotsu_by_Hiroshi_Niiyama.jpg/320px-Ramen_Tonkotsu_by_Hiroshi_Niiyama.jpg",
                    "coordinates": {"lat": 35.6938, "lon": 139.7034},
                    "wiki_url": "https://en.wikipedia.org/wiki/Ramen",
                },
            ],
        },
        {
            "day_number": 2,
            "date": "2026-04-16",
            "theme": "Food & Digital Art",
            "notes": "Food-focused day with a digital art experience. Book teamLab in advance.",
            "estimated_daily_budget_hkd": {"min": 800, "max": 1500},
            "morning": [
                {
                    "name": "Tsukiji Outer Market",
                    "description": (
                        "Explore the bustling outer market lanes. Fresh sushi breakfast, "
                        "grilled seafood skewers, and Japanese produce. The best time to "
                        "visit is before 10am."
                    ),
                    "location": "Tsukiji, Tokyo",
                    "category": "food",
                    "estimated_duration_minutes": 120,
                    "address": "4-16-2 Tsukiji, Chuo City, Tokyo 104-0045",
                    "map_url": "https://maps.google.com/maps?q=35.6654,139.7707&output=embed",
                    "opening_hours": "5:00 AM - 2:00 PM",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.6,
                    "review_count": 23456,
                    "tips": [
                        "Come before 8 AM for the freshest sushi breakfast",
                        "Bring cash",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Tsukiji_outer_market.jpg/1280px-Tsukiji_outer_market.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Tsukiji_outer_market.jpg/320px-Tsukiji_outer_market.jpg",
                    "coordinates": {"lat": 35.6654, "lon": 139.7707},
                    "wiki_url": "https://en.wikipedia.org/wiki/Tsukiji_Market",
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
                    "category": "culture",
                    "estimated_duration_minutes": 150,
                    "address": "6-1-16 Toyosu, Koto City, Tokyo 135-0061",
                    "map_url": "https://maps.google.com/maps?q=35.6498,139.7875&output=embed",
                    "opening_hours": "9:00 AM - 10:00 PM",
                    "admission_fee_hkd": 320.0,
                    "rating": 4.8,
                    "review_count": 67890,
                    "tips": [
                        "Book online at least 2 weeks in advance",
                        "Wear shorts or easily removable pants for the water room",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/TeamLab_Planets_-_Infinite_Mirror_Room.jpg/1280px-TeamLab_Planets_-_Infinite_Mirror_Room.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/TeamLab_Planets_-_Infinite_Mirror_Room.jpg/320px-TeamLab_Planets_-_Infinite_Mirror_Room.jpg",
                    "booking_url": "https://teamlab.art/planets/",
                    "coordinates": {"lat": 35.6498, "lon": 139.7875},
                    "wiki_url": "https://en.wikipedia.org/wiki/TeamLab_Planets_Tokyo",
                },
            ],
            "evening": [
                {
                    "name": "Odaiba Seaside Dinner",
                    "description": (
                        "Odaiba is a large artificial island in Tokyo Bay, connected to "
                        "central Tokyo by the Rainbow Bridge. Originally built for defensive "
                        "purposes in the 1960s and then redeveloped in the 1990s into a "
                        "futuristic shopping and entertainment district, Odaiba offers "
                        "breathtaking views of the Tokyo skyline across the bay. Dine "
                        "waterside as the Rainbow Bridge lights up at sunset, with options "
                        "ranging from Japanese izakaya and sushi bars to international "
                        "cuisine. The Gundam statue, teamLab Borderless museum, and a "
                        "full-scale replica of the Liberty Bell are all within walking "
                        "distance — making Odaiba one of Tokyo's most exciting evening "
                        "destinations."
                    ),
                    "location": "Odaiba, Tokyo",
                    "category": "food",
                    "estimated_duration_minutes": 90,
                    "address": "1-1-10 Aomi, Koto City, Tokyo 135-0064",
                    "map_url": "https://maps.google.com/maps?q=35.5544,139.7742&output=embed",
                    "opening_hours": "11:00 AM - 11:00 PM",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.3,
                    "review_count": 8765,
                    "tips": [
                        "Rainbow Bridge lights up at sunset",
                        "Gundam statue is nearby",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Odaiba_and_Rainbow_Bridge_from_Tokyo_Tower.jpg/1280px-Odaiba_and_Rainbow_Bridge_from_Tokyo_Tower.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Odaiba_and_Rainbow_Bridge_from_Tokyo_Tower.jpg/320px-Odaiba_and_Rainbow_Bridge_from_Tokyo_Tower.jpg",
                    "coordinates": {"lat": 35.5544, "lon": 139.7742},
                    "wiki_url": "https://en.wikipedia.org/wiki/Odaiba",
                },
            ],
        },
        {
            "day_number": 3,
            "date": "2026-04-17",
            "theme": "Shibuya & Nightlife",
            "notes": "Explore the energy of Shibuya and end with Golden Gai's unique bars.",
            "estimated_daily_budget_hkd": {"min": 500, "max": 1200},
            "morning": [
                {
                    "name": "Meiji Shrine & Harajuku",
                    "description": (
                        "Start with a tranquil walk through the forested Meiji Shrine, then "
                        "cross over to the eclectic Harajuku district for Takeshita Street "
                        "and people-watching at Yoyogi Park."
                    ),
                    "location": "Shibuya, Tokyo",
                    "category": "culture",
                    "estimated_duration_minutes": 150,
                    "address": "1-1 Yoyogikamizonocho, Shibuya City, Tokyo 151-8557",
                    "map_url": "https://maps.google.com/maps?q=35.6764,139.6993&output=embed",
                    "opening_hours": "Sunrise - Sunset",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.7,
                    "review_count": 54321,
                    "tips": [
                        "The shrine is most peaceful early morning",
                        "Takeshita Street gets very crowded on weekends",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Meiji_Jingu_01.jpg/1280px-Meiji_Jingu_01.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Meiji_Jingu_01.jpg/320px-Meiji_Jingu_01.jpg",
                    "coordinates": {"lat": 35.6764, "lon": 139.6993},
                    "wiki_url": "https://en.wikipedia.org/wiki/Meiji_Shrine",
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
                    "category": "sightseeing",
                    "estimated_duration_minutes": 60,
                    "address": "Shibuya Station, Shibuya City, Tokyo 150-0043",
                    "map_url": "https://maps.google.com/maps?q=35.6595,139.7004&output=embed",
                    "opening_hours": "24 hours",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.6,
                    "review_count": 98765,
                    "tips": [
                        "Starbucks overlooking the crossing offers great views",
                        "Hachiko statue is at the west exit",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Shibuya_Crossing_2013.jpg/1280px-Shibuya_Crossing_2013.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Shibuya_Crossing_2013.jpg/320px-Shibuya_Crossing_2013.jpg",
                    "coordinates": {"lat": 35.6595, "lon": 139.7004},
                    "wiki_url": "https://en.wikipedia.org/wiki/Shibuya_crossing",
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
                    "category": "food",
                    "estimated_duration_minutes": 120,
                    "address": "164164 Kabukicho, Shinjuku City, Tokyo 160-0021",
                    "map_url": "https://maps.google.com/maps?q=35.6942,139.7034&output=embed",
                    "opening_hours": "6:00 PM - 4:00 AM",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.5,
                    "review_count": 4567,
                    "tips": [
                        "Each bar has a different theme and atmosphere",
                        "Look for English menus or ask for recommendations",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Shinjuku_Golden_Gai.jpg/1280px-Shinjuku_Golden_Gai.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Shinjuku_Golden_Gai.jpg/320px-Shinjuku_Golden_Gai.jpg",
                    "coordinates": {"lat": 35.6942, "lon": 139.7034},
                    "wiki_url": "https://en.wikipedia.org/wiki/Golden_Gai",
                },
            ],
        },
        {
            "day_number": 4,
            "date": "2026-04-18",
            "theme": "Mount Fuji Day Trip",
            "notes": "Early start required for the best Fuji views. Wear comfortable walking shoes.",
            "estimated_daily_budget_hkd": {"min": 600, "max": 1200},
            "morning": [
                {
                    "name": "Day Trip to Mount Fuji",
                    "description": (
                        "A full-day excursion to Mount Fuji's most iconic viewpoints. "
                        "Start at Chureito Pagoda, a five-story Buddhist pagoda in "
                        "Fujiyoshida that has become one of Japan's most photographed "
                        "spots — the 400-step staircase frames Mount Fuji perfectly, "
                        "especially stunning during cherry blossom season and in autumn "
                        "when the maple leaves turn red. Continue to Lake Kawaguchi, "
                        "the second-largest of Fuji's Five Lakes, where you can take "
                        "the cable car up to Tenjo Height for unbeatable panoramic Fuji "
                        "views. The lakefront promenade is perfect for a leisurely "
                        "stroll, and local shops sell hoto noodles and Fuji-shaped "
                        "souvenirs. On clear mornings, Fuji's reflection on the mirror-"
                        "like lake surface creates a scene straight out of a woodblock "
                        "print — one of Japan's most iconic natural vistas."
                    ),
                    "location": "Fujiyoshida, Yamanashi",
                    "category": "nature",
                    "estimated_duration_minutes": 240,
                    "address": "2-4 Chureito Pagoda, Fujiyoshida, Yamanashi 403-0015",
                    "map_url": "https://maps.google.com/maps?q=35.3945,138.7764&output=embed",
                    "opening_hours": "24 hours (viewpoint)",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.8,
                    "review_count": 34567,
                    "tips": [
                        "Climb the 400 steps for the classic Fuji shot",
                        "Best time is early morning for clear skies",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Chureito_Pagoda_and_Mount_Fuji_croped.jpg/1280px-Chureito_Pagoda_and_Mount_Fuji_croped.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Chureito_Pagoda_and_Mount_Fuji_croped.jpg/320px-Chureito_Pagoda_and_Mount_Fuji_croped.jpg",
                    "coordinates": {"lat": 35.3945, "lon": 138.7764},
                    "wiki_url": "https://en.wikipedia.org/wiki/Chureito_Pagoda",
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
                    "category": "nature",
                    "estimated_duration_minutes": 120,
                    "address": "湖1 Kawaguchiko, Minamitsuru District, Yamanashi 401-0301",
                    "map_url": "https://maps.google.com/maps?q=35.5163,138.7513&output=embed",
                    "opening_hours": "9:00 AM - 5:30 PM",
                    "admission_fee_hkd": 250.0,
                    "rating": 4.6,
                    "review_count": 28901,
                    "tips": [
                        "Kawaguchiko Station has lockers for luggage",
                        "Nissan Star Pit has great Fuji views",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Lake_Kawaguchi_and_Mount_Fuji.jpg/1280px-Lake_Kawaguchi_and_Mount_Fuji.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Lake_Kawaguchi_and_Mount_Fuji.jpg/320px-Lake_Kawaguchi_and_Mount_Fuji.jpg",
                    "coordinates": {"lat": 35.5163, "lon": 138.7513},
                    "wiki_url": "https://en.wikipedia.org/wiki/Lake_Kawaguchi",
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
                    "category": "shopping",
                    "estimated_duration_minutes": 120,
                    "address": "Sotokanda, Chiyoda City, Tokyo 101-0021",
                    "map_url": "https://maps.google.com/maps?q=35.7023,139.7745&output=embed",
                    "opening_hours": "10:00 AM - 10:00 PM",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.4,
                    "review_count": 19283,
                    "tips": [
                        "Yodobashi Camera is the largest electronics store",
                        "Anime shops are concentrated on Chuo-dori",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Akihabara_201312.jpg/1280px-Akihabara_201312.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Akihabara_201312.jpg/320px-Akihabara_201312.jpg",
                    "coordinates": {"lat": 35.7023, "lon": 139.7745},
                    "wiki_url": "https://en.wikipedia.org/wiki/Akihabara",
                },
            ],
        },
        {
            "day_number": 5,
            "date": "2026-04-19",
            "theme": "Culture & Farewell",
            "notes": "Last day. Morning culture and shopping, evening omakase farewell dinner.",
            "estimated_daily_budget_hkd": {"min": 800, "max": 2000},
            "morning": [
                {
                    "name": "Ueno Park & Museums",
                    "description": (
                        "Tokyo National Museum houses one of the world's finest collections "
                        "of Japanese art. The park itself is beautiful during cherry "
                        "blossom season with rivers of pink petals."
                    ),
                    "location": "Ueno, Tokyo",
                    "category": "culture",
                    "estimated_duration_minutes": 150,
                    "address": "13-9 Uenokoen, Taito City, Tokyo 110-8712",
                    "map_url": "https://maps.google.com/maps?q=35.7146,139.7733&output=embed",
                    "opening_hours": "9:30 AM - 5:00 PM",
                    "admission_fee_hkd": 100.0,
                    "rating": 4.7,
                    "review_count": 28765,
                    "tips": [
                        "Tokyo National Museum is free on some days",
                        "The park is beautiful for hanami during cherry blossom season",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Ueno_Park_Sakura_2013.jpg/1280px-Ueno_Park_Sakura_2013.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Ueno_Park_Sakura_2013.jpg/320px-Ueno_Park_Sakura_2013.jpg",
                    "coordinates": {"lat": 35.7146, "lon": 139.7733},
                    "wiki_url": "https://en.wikipedia.org/wiki/Ueno_Park",
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
                    "category": "shopping",
                    "estimated_duration_minutes": 90,
                    "address": "4 Ueno, Taito City, Tokyo 110-0005",
                    "map_url": "https://maps.google.com/maps?q=35.7099,139.7742&output=embed",
                    "opening_hours": "10:00 AM - 8:00 PM",
                    "admission_fee_hkd": 0.0,
                    "rating": 4.3,
                    "review_count": 12345,
                    "tips": [
                        "Great for cheap souvenirs and snacks",
                        "Cash is recommended for bargaining",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Ameyoko_croped.jpg/1280px-Ameyoko_croped.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Ameyoko_croped.jpg/320px-Ameyoko_croped.jpg",
                    "coordinates": {"lat": 35.7099, "lon": 139.7742},
                    "wiki_url": "https://en.wikipedia.org/wiki/Ameyoko",
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
                    "category": "food",
                    "estimated_duration_minutes": 120,
                    "address": "6-10-1 Ginza, Chuo City, Tokyo 104-0061",
                    "map_url": "https://maps.google.com/maps?q=35.6715,139.7649&output=embed",
                    "opening_hours": "5:00 PM - 10:00 PM",
                    "admission_fee_hkd": 1500.0,
                    "rating": 4.9,
                    "review_count": 5432,
                    "tips": [
                        "Reservation required at least 2 weeks ahead",
                        "Dress code is smart casual",
                    ],
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Sushi_%285676123442%29.jpg/1280px-Sushi_%285676123442%29.jpg",
                    "thumbnail_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Sushi_%285676123442%29.jpg/320px-Sushi_%285676123442%29.jpg",
                    "booking_url": "https://www.tablecheck.com/en/reserve/",
                    "coordinates": {"lat": 35.6715, "lon": 139.7649},
                    "wiki_url": "https://en.wikipedia.org/wiki/Omakase",
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
