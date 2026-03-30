"""Simple tests for search tool (Tavily + SerpAPI)."""

import unittest.mock

import pytest

from app.agent.tools.search import _search_tavily, _search_serpapi


@pytest.mark.asyncio
async def test_search_tavily_returns_expected_results():
    """Tavily search returns correctly shaped results."""
    with unittest.mock.patch(
        "app.agent.tools.search.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "China Travel Guide",
                    "url": "https://example.com/china",
                    "raw_content": "A comprehensive guide to traveling in China.",
                }
            ]
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await _search_tavily("travel to China")

    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "China Travel Guide"
    assert result["results"][0]["url"] == "https://example.com/china"
    assert "comprehensive guide" in result["results"][0]["snippet"]


@pytest.mark.asyncio
async def test_search_tavily_handles_null_raw_content():
    """Tavily handles null raw_content (uses content or empty string)."""
    with unittest.mock.patch(
        "app.agent.tools.search.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test",
                    "url": "https://example.com",
                    "raw_content": None,
                    "content": "Fallback content here",
                }
            ]
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await _search_tavily("test")

    assert result["results"][0]["snippet"] == "Fallback content here"


@pytest.mark.asyncio
async def test_search_tavily_handles_timeout():
    """Tavily returns error dict on timeout."""
    with unittest.mock.patch(
        "app.agent.tools.search.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.post.side_effect = Exception("Timeout")
        mock_client_cls.return_value = mock_client

        result = await _search_tavily("test")

    assert "error" in result
    assert result["results"] == []


@pytest.mark.asyncio
async def test_search_serpapi_returns_expected_results():
    """SerpAPI fallback returns correctly shaped results."""
    with unittest.mock.patch(
        "app.agent.tools.search.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic_results": [
                {
                    "title": "Japan Travel",
                    "link": "https://example.com/japan",
                    "snippet": "Best places to visit in Japan.",
                }
            ]
        }
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await _search_serpapi("travel to Japan")

    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Japan Travel"
    assert result["results"][0]["url"] == "https://example.com/japan"


@pytest.mark.asyncio
async def test_search_serpapi_handles_error():
    """SerpAPI returns error dict on network failure."""
    with unittest.mock.patch(
        "app.agent.tools.search.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = Exception("Network error")
        mock_client_cls.return_value = mock_client

        result = await _search_serpapi("test")

    assert "error" in result
    assert result["results"] == []
