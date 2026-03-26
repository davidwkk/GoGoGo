"""Simple tests for attractions tool."""

import unittest.mock

import pytest

from app.agent.tools.attractions import get_attraction


@pytest.mark.asyncio
async def test_get_attraction_returns_expected_keys():
    """Attraction returns name, description, thumbnail_url, coordinates."""
    with unittest.mock.patch(
        "app.agent.tools.attractions.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Tokyo Tower",
            "extract": "A famous observation tower in Tokyo.",
            "thumbnail": {"source": "https://example.com/tower.jpg"},
            "coordinates": [{"lat": 35.6586, "lon": 139.7454}],
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await get_attraction("Tokyo Tower")

    assert result["name"] == "Tokyo Tower"
    assert "description" in result
    assert "thumbnail_url" in result
    assert "coordinates" in result


@pytest.mark.asyncio
async def test_get_attraction_not_found():
    """Attraction returns error dict on 404."""
    with unittest.mock.patch(
        "app.agent.tools.attractions.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404")
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await get_attraction("Nonexistent Place")

    assert "error" in result


@pytest.mark.asyncio
async def test_get_attraction_handles_timeout():
    """Attraction returns error dict on timeout."""
    with unittest.mock.patch(
        "app.agent.tools.attractions.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = Exception("Timeout")
        mock_client_cls.return_value = mock_client

        result = await get_attraction("Tokyo Tower")

    assert "error" in result
