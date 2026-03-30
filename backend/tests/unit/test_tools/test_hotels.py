"""Simple tests for hotels tool."""

import unittest.mock

import pytest

from app.agent.tools.hotels import search_hotels


@pytest.mark.asyncio
async def test_search_hotels_returns_expected_results():
    """Hotels search returns correctly shaped results."""
    with unittest.mock.patch(
        "app.agent.tools.hotels.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hotels": [
                {
                    "name": "Grand Hotel Tokyo",
                    "location": "Tokyo, Japan",
                    "price": "HKD 1,200",
                    "rating": 4.5,
                    "extensions": ["Free WiFi", "Pool", "Gym"],
                    "link": "https://example.com/hotel",
                }
            ]
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await search_hotels("Tokyo")

    assert "hotels" in result
    assert len(result["hotels"]) == 1
    assert result["hotels"][0]["name"] == "Grand Hotel Tokyo"
    assert result["hotels"][0]["location"] == "Tokyo, Japan"
    assert result["hotels"][0]["rating"] == "4.5/5"


@pytest.mark.asyncio
async def test_search_hotels_handles_missing_api_key():
    """Hotels returns error when API key not configured."""
    with unittest.mock.patch("app.agent.tools.hotels.settings") as mock_settings:
        mock_settings.SERPAPI_KEY = ""

        result = await search_hotels("Tokyo")

    assert "error" in result
    assert "not configured" in result["error"]


@pytest.mark.asyncio
async def test_search_hotels_handles_error():
    """Hotels returns error dict on network failure."""
    with unittest.mock.patch(
        "app.agent.tools.hotels.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = Exception("Network error")
        mock_client_cls.return_value = mock_client

        result = await search_hotels("Tokyo")

    assert "error" in result
    assert result["hotels"] == []
