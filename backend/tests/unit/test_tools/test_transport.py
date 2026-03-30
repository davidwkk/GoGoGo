"""Simple tests for transport tool."""

import unittest.mock

import pytest

from app.agent.tools.transport import get_transport


@pytest.fixture(autouse=True)
def clear_transport_cache():
    """Clear the module-level transport cache before each test."""
    from app.agent.tools import transport

    transport._cache.clear()
    yield
    transport._cache.clear()


@pytest.mark.asyncio
async def test_get_transport_returns_expected_results():
    """Transport returns correctly shaped results."""
    with unittest.mock.patch(
        "app.agent.tools.transport.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transport_results": [
                {
                    "type": "MTR",
                    "duration": "45 min",
                    "price": "HKD 50",
                    "description": "Direct MTR train",
                }
            ]
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await get_transport("Hong Kong Station", "Kowloon Station")

    assert "options" in result
    assert len(result["options"]) == 1
    assert result["options"][0]["type"] == "MTR"
    assert result["options"][0]["duration"] == "45 min"
    assert result["options"][0]["cost"] == "HKD 50"


@pytest.mark.asyncio
async def test_get_transport_filters_by_mode():
    """Transport filters results by mode when specified."""
    with unittest.mock.patch(
        "app.agent.tools.transport.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transport_results": [
                {"type": "MTR", "duration": "45 min", "price": "HKD 50"},
                {"type": "Bus", "duration": "90 min", "price": "HKD 25"},
            ]
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await get_transport("HK Station Unique", "Kowloon Unique", mode="MTR")

    assert len(result["options"]) == 1
    assert result["options"][0]["type"] == "MTR"


@pytest.mark.asyncio
async def test_get_transport_missing_api_key():
    """Transport returns error when API key not configured."""
    with unittest.mock.patch("app.agent.tools.transport.settings") as mock_settings:
        mock_settings.SERPAPI_KEY = ""

        result = await get_transport("HK Station Test", "Kowloon Test")

    assert "error" in result
    assert "not configured" in result["error"]


@pytest.mark.asyncio
async def test_get_transport_handles_error():
    """Transport returns error dict on network failure."""
    with unittest.mock.patch(
        "app.agent.tools.transport.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = Exception("Network error")
        mock_client_cls.return_value = mock_client

        result = await get_transport("HK Station Error", "Kowloon Error")

    assert "error" in result
    assert result["options"] == []
