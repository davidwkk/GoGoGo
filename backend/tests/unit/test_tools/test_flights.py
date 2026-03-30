"""Tests for flights tool — verifies parsing against real SerpAPI schema."""

import unittest.mock

import pytest

from app.agent.tools.flights import search_flights


# ---------------------------------------------------------------------------
# Real SerpAPI google_flights response shape (simplified)
# ---------------------------------------------------------------------------

REAL_FLIGHT_RESPONSE = {
    "best_flights": [
        {
            "flights": [
                {
                    "departure_airport": {
                        "name": "Beijing Capital International Airport",
                        "id": "PEK",
                        "time": "2023-10-03 15:10",
                    },
                    "arrival_airport": {
                        "name": "Haneda Airport",
                        "id": "HND",
                        "time": "2023-10-03 19:35",
                    },
                    "duration": 205,
                    "airplane": "Boeing 787",
                    "airline": "ANA",
                    "airline_logo": "https://www.gstatic.com/flights/airline_logos/70px/NH.png",
                    "travel_class": "Economy",
                    "flight_number": "NH 962",
                    "legroom": "31 in",
                },
                {
                    "departure_airport": {
                        "name": "Haneda Airport",
                        "id": "HND",
                        "time": "2023-10-03 21:05",
                    },
                    "arrival_airport": {
                        "name": "Los Angeles International Airport",
                        "id": "LAX",
                        "time": "2023-10-03 15:10",
                    },
                    "duration": 605,
                    "airplane": "Boeing 787",
                    "airline": "ANA",
                    "flight_number": "NH 126",
                    "legroom": "32 in",
                },
            ],
            "layovers": [
                {"duration": 90, "name": "Haneda Airport", "id": "HND"},
            ],
            "total_duration": 1309,
            "price": 2512,
            "type": "Round trip",
        }
    ],
    "other_flights": [],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_flights_returns_expected_results():
    """Flights search returns correctly shaped results with real SerpAPI schema."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = REAL_FLIGHT_RESPONSE
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_flights("PEK", "LAX")

    assert "flights" in result
    # Two flight segments from one itinerary
    assert len(result["flights"]) == 2

    # First segment
    seg1 = result["flights"][0]
    assert seg1["airline"] == "ANA"
    assert seg1["flight_number"] == "NH 962"
    assert seg1["departure_airport"] == "PEK"
    assert seg1["arrival_airport"] == "HND"
    assert seg1["departure_time"] == "2023-10-03T15:10:00"
    assert seg1["arrival_time"] == "2023-10-03T19:35:00"
    assert seg1["duration_minutes"] == 205
    assert seg1["layover_after"]["airport_code"] == "HND"
    assert seg1["layover_after"]["duration_minutes"] == 90
    assert seg1["price"] == 2512

    # Second segment — no further connections after it
    seg2 = result["flights"][1]
    assert seg2["airline"] == "ANA"
    assert seg2["flight_number"] == "NH 126"
    assert seg2["departure_airport"] == "HND"
    assert seg2["arrival_airport"] == "LAX"
    assert seg2["layover_after"] is None  # last segment, no connection after


@pytest.mark.asyncio
async def test_search_flights_validates_iata_codes():
    """Flights returns error for invalid airport codes."""
    result = await search_flights("tokyo", "hong kong")  # city names, not IATA

    assert "error" in result
    assert "IATA airport codes" in result["error"]
    assert result["flights"] == []


@pytest.mark.asyncio
async def test_search_flights_missing_api_key():
    """Flights returns error when API key not configured."""
    with unittest.mock.patch("app.agent.tools.flights.settings") as mock_settings:
        mock_settings.SERPAPI_KEY = ""

        result = await search_flights("PEK", "LAX")

    assert "error" in result
    assert "not configured" in result["error"]


@pytest.mark.asyncio
async def test_search_flights_handles_network_error():
    """Flights returns error dict on network failure."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = Exception(
            "Connection refused"
        )
        mock_client_cls.return_value = mock_client

        result = await search_flights("PEK", "LAX")

    assert "error" in result
    assert result["flights"] == []


@pytest.mark.asyncio
async def test_search_flights_handles_401():
    """Flights returns clear error on 401."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 401
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_flights("PEK", "LAX")

    assert "error" in result
    assert "Invalid SerpAPI key" in result["error"]
    assert result["flights"] == []


@pytest.mark.asyncio
async def test_search_flights_handles_429():
    """Flights returns clear error on rate limit."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 429
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_flights("PEK", "LAX")

    assert "error" in result
    assert "rate limit" in result["error"].lower()
    assert result["flights"] == []


@pytest.mark.asyncio
async def test_search_flights_other_flights_fallback():
    """other_flights is used when best_flights is absent."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "best_flights": [],
            "other_flights": [
                {
                    "flights": [
                        {
                            "departure_airport": {
                                "name": "HND",
                                "id": "HND",
                                "time": "2023-10-03 21:05",
                            },
                            "arrival_airport": {
                                "name": "LAX",
                                "id": "LAX",
                                "time": "2023-10-03 15:10",
                            },
                            "duration": 605,
                            "airline": "United",
                            "flight_number": "UA 1",
                        }
                    ],
                    "layovers": [],
                    "price": 3000,
                }
            ],
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_flights("HND", "LAX")

    assert len(result["flights"]) == 1
    assert result["flights"][0]["airline"] == "United"


@pytest.mark.asyncio
async def test_search_flights_default_date_format():
    """date param is validated as YYYY-MM-DD."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"best_flights": [], "other_flights": []}
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_flights("PEK", "LAX", date="31-03-2026")

    assert "error" in result
    assert "YYYY-MM-DD" in result["error"]
