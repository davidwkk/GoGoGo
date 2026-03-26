"""Simple tests for weather tool."""

import unittest.mock

import pytest

from app.agent.tools.weather import get_weather


@pytest.mark.asyncio
async def test_get_weather_returns_expected_keys():
    """Weather returns city, temperature, condition, humidity, icon."""
    # Mock the entire tool function to verify correct dict shape
    with unittest.mock.patch(
        "app.agent.tools.weather.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        # json() is synchronous in httpx.Response
        mock_response.json.return_value = {
            "name": "Tokyo",
            "weather": [{"main": "Clear", "icon": "01d"}],
            "main": {"temp": 22.5, "humidity": 65},
        }
        mock_client = unittest.mock.MagicMock()
        # client.get() returns the mock_response directly (not a coroutine chain)
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await get_weather("Tokyo")

    assert result["city"] == "Tokyo"
    assert "temperature" in result
    assert result["condition"] == "Clear"


@pytest.mark.asyncio
async def test_get_weather_handles_error():
    """Weather returns error dict on network failure."""
    with unittest.mock.patch(
        "app.agent.tools.weather.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = Exception("Network error")
        mock_client_cls.return_value = mock_client

        result = await get_weather("Tokyo")

    assert "error" in result


@pytest.mark.asyncio
async def test_get_weather_missing_api_key():
    """Weather returns error when API key not configured."""
    with unittest.mock.patch("app.agent.tools.weather.settings") as mock_settings:
        mock_settings.OPENWEATHER_API_KEY = ""

        result = await get_weather("Tokyo")

    assert "error" in result
    assert "not configured" in result["error"]
