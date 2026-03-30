"""Simple tests for flights tool."""

import unittest.mock

import pytest

from app.agent.tools.flights import search_flights


@pytest.mark.asyncio
async def test_search_flights_returns_expected_results():
    """Flights search returns correctly shaped results."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "flights": [
                {
                    "airline": "Cathay Pacific",
                    "flight_number": "CX123",
                    "duration": "4h 30m",
                    "price": "HKD 2,500",
                }
            ]
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_flights("Hong Kong", "Tokyo")

    assert "flights" in result
    assert len(result["flights"]) == 1
    assert result["flights"][0]["airline"] == "Cathay Pacific"
    assert result["flights"][0]["flight_number"] == "CX123"
    assert result["flights"][0]["departure"] == "Hong Kong"
    assert result["flights"][0]["arrival"] == "Tokyo"


@pytest.mark.asyncio
async def test_search_flights_uses_best_flights():
    """Flights uses best_flights when flights key is absent."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "best_flights": [
                {
                    "airline": "Japan Airlines",
                    "flight_number": "JL456",
                    "duration": "5h",
                    "price": "HKD 3,000",
                }
            ]
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_flights("Hong Kong", "Osaka")

    assert len(result["flights"]) == 1
    assert result["flights"][0]["airline"] == "Japan Airlines"


@pytest.mark.asyncio
async def test_search_flights_missing_api_key():
    """Flights returns error when API key not configured."""
    with unittest.mock.patch("app.agent.tools.flights.settings") as mock_settings:
        mock_settings.SERPAPI_KEY = ""

        result = await search_flights("Hong Kong", "Tokyo")

    assert "error" in result
    assert "not configured" in result["error"]


@pytest.mark.asyncio
async def test_search_flights_handles_error():
    """Flights returns error dict on network failure."""
    with unittest.mock.patch(
        "app.agent.tools.flights.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = Exception("Network error")
        mock_client_cls.return_value = mock_client

        result = await search_flights("Hong Kong", "Tokyo")

    assert "error" in result
    assert result["flights"] == []
