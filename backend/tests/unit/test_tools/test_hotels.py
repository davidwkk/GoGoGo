"""Tests for hotels tool — verifies parsing against real SerpAPI schema."""

import unittest.mock

import pytest

from app.agent.tools.hotels import search_hotels


# ---------------------------------------------------------------------------
# Real SerpAPI google_hotels response shape (simplified)
# ---------------------------------------------------------------------------

REAL_HOTELS_RESPONSE = {
    "properties": [
        {
            "type": "hotel",
            "name": "The Ritz-Carlton, Bali",
            "description": "Zen-like quarters in an upscale property.",
            "link": "https://www.ritzcarlton.com/bal",
            "gps_coordinates": {"latitude": -8.83067, "longitude": 115.21533},
            "check_in_time": "3:00 PM",
            "check_out_time": "12:00 PM",
            "rate_per_night": {
                "lowest": "$347",
                "extracted_lowest": 347,
                "before_taxes_fees": "$287",
                "extracted_before_taxes_fees": 287,
            },
            "total_rate": {
                "lowest": "$1,733",
                "extracted_lowest": 1733,
            },
            "deal": "27% less than usual",
            "deal_description": "Great Deal",
            "hotel_class": "5-star hotel",
            "extracted_hotel_class": 5,
            "images": [
                {
                    "thumbnail": "https://lh3.googleusercontent.com/proxy/thumb.jpg",
                    "original_image": "https://d2hyz2bfif3cr8.cloudfront.net/image.jpg",
                }
            ],
            "overall_rating": 4.6,
            "reviews": 3614,
            "location_rating": 2.8,
            "amenities": [
                "Free Wi-Fi",
                "Free parking",
                "Pools",
                "Spa",
                "Bar",
                "Restaurant",
            ],
            "nearby_places": [
                {
                    "name": "I Gusti Ngurah Rai International Airport",
                    "transportations": [
                        {"type": "Taxi", "duration": "29 min"},
                        {"type": "Walking", "duration": "5 min"},
                    ],
                }
            ],
            "eco_certified": True,
        }
    ],
    "non_matching_properties": [],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_hotels_returns_expected_results():
    """Hotels search returns correctly shaped results."""
    with unittest.mock.patch(
        "app.agent.tools.hotels.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = REAL_HOTELS_RESPONSE
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_hotels(
            "Bali", check_in="2026-03-31", check_out="2026-04-06"
        )

    assert "hotels" in result
    assert len(result["hotels"]) == 1

    hotel = result["hotels"][0]
    assert hotel["name"] == "The Ritz-Carlton, Bali"
    assert hotel["location"] == "Bali"
    assert hotel["check_in_date"] == "2026-03-31"
    assert hotel["check_out_date"] == "2026-04-06"
    assert hotel["check_in_time"] == "3:00 PM"
    assert hotel["check_out_time"] == "12:00 PM"
    # Price: already in HKD from SerpAPI
    assert hotel["price_per_night_min_hkd"] == 347
    assert hotel["total_price_hkd"] == 1733
    assert hotel["hotel_class"] == "5-star hotel"
    assert hotel["hotel_class_int"] == 5
    assert hotel["rating"] == 4.6
    assert hotel["reviews"] == 3614
    assert hotel["location_rating"] == 2.8
    assert "Free Wi-Fi" in hotel["amenities"]
    assert hotel["image_url"] == "https://d2hyz2bfif3cr8.cloudfront.net/image.jpg"
    assert hotel["thumbnail_url"] == "https://lh3.googleusercontent.com/proxy/thumb.jpg"
    assert "eco_certified" not in hotel
    assert "deal" not in hotel
    assert "deal_description" not in hotel
    # Nearby places
    assert len(hotel["nearby_places"]) == 1
    assert (
        hotel["nearby_places"][0]["name"] == "I Gusti Ngurah Rai International Airport"
    )
    assert hotel["nearby_places"][0]["transportations"][0]["type"] == "Taxi"
    assert hotel["nearby_places"][0]["transportations"][0]["duration"] == "29 min"


@pytest.mark.asyncio
async def test_search_hotels_non_matching_fallback():
    """non_matching_properties is used when properties is empty."""
    with unittest.mock.patch(
        "app.agent.tools.hotels.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": [],
            "non_matching_properties": [
                {
                    "name": "Fallback Hotel",
                    "description": "A fallback option.",
                    "rate_per_night": {"extracted_lowest": 100},
                    "images": [],
                    "amenities": [],
                }
            ],
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_hotels("UnknownPlace", check_in="2026-05-01")

    assert len(result["hotels"]) == 1
    assert result["hotels"][0]["name"] == "Fallback Hotel"


@pytest.mark.asyncio
async def test_search_hotels_handles_missing_api_key():
    """Hotels returns error when API key not configured."""
    with unittest.mock.patch("app.agent.tools.hotels.settings") as mock_settings:
        mock_settings.SERPAPI_KEY = ""

        result = await search_hotels("Bali", check_in="2026-05-01")

    assert "error" in result
    assert "not configured" in result["error"]


@pytest.mark.asyncio
async def test_search_hotels_handles_network_error():
    """Hotels returns error dict on network failure."""
    with unittest.mock.patch(
        "app.agent.tools.hotels.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = Exception(
            "Connection refused"
        )
        mock_client_cls.return_value = mock_client

        result = await search_hotels("Bali", check_in="2026-05-01")

    assert "error" in result
    assert result["hotels"] == []


@pytest.mark.asyncio
async def test_search_hotels_handles_401():
    """Hotels returns clear error on 401."""
    with unittest.mock.patch(
        "app.agent.tools.hotels.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 401
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_hotels("Bali", check_in="2026-05-01")

    assert "error" in result
    assert "Invalid SerpAPI key" in result["error"]


@pytest.mark.asyncio
async def test_search_hotels_handles_429():
    """Hotels returns clear error on rate limit."""
    with unittest.mock.patch(
        "app.agent.tools.hotels.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 429
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_hotels("Bali", check_in="2026-05-01")

    assert "error" in result
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_search_hotels_missing_price_returns_none():
    """Hotels with no rate_per_night returns None prices."""
    with unittest.mock.patch(
        "app.agent.tools.hotels.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": [
                {
                    "name": "Free Hotel",
                    "description": "A mystery.",
                    "rate_per_night": {},
                    "images": [],
                    "amenities": [],
                }
            ],
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_hotels("Somewhere", check_in="2026-05-01")

    assert result["hotels"][0]["price_per_night_min_hkd"] is None
    assert result["hotels"][0]["price_per_night_max_hkd"] is None
