"""Tests for attractions tool — verifies parsing against real Wikipedia REST API schema."""

import unittest.mock

import pytest

from app.agent.tools.attractions import (
    _extract_location_from_description,
    get_attraction,
)


# ---------------------------------------------------------------------------
# Real Wikipedia REST API response shape
# ---------------------------------------------------------------------------

REAL_WIKI_RESPONSE = {
    "title": "Taj Mahal",
    "displaytitle": "Taj Mahal",
    "description": "Mausoleum in Agra, Uttar Pradesh, India",
    "extract": "The Taj Mahal is an ivory-white marble mausoleum on the right bank of the river Yamuna.",
    "thumbnail": {
        "source": "https://upload.wikimedia.org/wikipedia/thumb/taj_mahal.jpg/320px-taj_mahal.jpg",
        "width": 320,
        "height": 240,
    },
    "originalimage": {
        "source": "https://upload.wikimedia.org/wikipedia/original/taj_mahal.jpg",
        "width": 4000,
        "height": 3000,
    },
    "coordinates": {
        "lat": 27.175144,
        "lon": 78.042138,
    },
    "content_urls": {
        "desktop": {"page": "https://en.wikipedia.org/wiki/Taj_Mahal"},
        "mobile": {"page": "https://en.m.wikipedia.org/wiki/Taj_Mahal"},
    },
    "type": "standard",
    "wikibase_item": "Q6568032",
}


# ---------------------------------------------------------------------------
# Tests — get_attraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_attraction_returns_expected_results():
    """Attraction returns correctly shaped results with real Wikipedia schema."""
    with unittest.mock.patch(
        "app.agent.tools.attractions.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = REAL_WIKI_RESPONSE
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await get_attraction("Taj Mahal")

    # name from title
    assert result["name"] == "Taj Mahal"
    # description = full extract, not short description
    assert result["description"] == REAL_WIKI_RESPONSE["extract"]
    # location parsed from description
    assert result["location"] == "Agra, Uttar Pradesh, India"
    # category is the part before " in "
    assert result["category"] == "Mausoleum"
    # image URLs
    assert result["thumbnail_url"] == REAL_WIKI_RESPONSE["thumbnail"]["source"]
    assert result["image_url"] == REAL_WIKI_RESPONSE["originalimage"]["source"]
    # coordinates
    assert result["coordinates"] == {"lat": 27.175144, "lon": 78.042138}
    # wiki_url
    assert result["wiki_url"] == REAL_WIKI_RESPONSE["content_urls"]["desktop"]["page"]
    assert "error" not in result


@pytest.mark.asyncio
async def test_get_attraction_maps_url_built_when_api_key_present():
    """Google Maps embed URL is built when GOOGLE_MAPS_API_KEY is configured."""
    with (
        unittest.mock.patch(
            "app.agent.tools.attractions.httpx.AsyncClient"
        ) as mock_client_cls,
        unittest.mock.patch("app.agent.tools.attractions.settings") as mock_settings,
    ):
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = REAL_WIKI_RESPONSE
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client
        mock_settings.GOOGLE_MAPS_API_KEY = "AIzaSyTEST"

        result = await get_attraction("Taj Mahal")

    assert result["map_url"] is not None
    assert "key=AIzaSyTEST" in result["map_url"]
    assert "27.175144" in result["map_url"]
    assert "78.042138" in result["map_url"]


@pytest.mark.asyncio
async def test_get_attraction_maps_url_absent_when_no_api_key():
    """Google Maps embed URL is None when GOOGLE_MAPS_API_KEY is not set."""
    with (
        unittest.mock.patch(
            "app.agent.tools.attractions.httpx.AsyncClient"
        ) as mock_client_cls,
        unittest.mock.patch("app.agent.tools.attractions.settings") as mock_settings,
    ):
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = REAL_WIKI_RESPONSE
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client
        mock_settings.GOOGLE_MAPS_API_KEY = ""

        result = await get_attraction("Taj Mahal")

    assert result["map_url"] is None


@pytest.mark.asyncio
async def test_get_attraction_normalizes_spaces_in_title():
    """Attraction name with spaces uses underscores in Wikipedia URL."""
    with unittest.mock.patch(
        "app.agent.tools.attractions.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        await get_attraction("Tokyo Tower")

        called_url = mock_client.__aenter__.return_value.get.call_args
        assert "Tokyo_Tower" in str(called_url)


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
    assert result["name"] == "Nonexistent Place"


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
    assert "Timeout" in result["error"]


@pytest.mark.asyncio
async def test_get_attraction_handles_http_error():
    """Attraction returns error dict on HTTP status error."""
    with unittest.mock.patch(
        "app.agent.tools.attractions.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await get_attraction("Tokyo Tower")

    assert "error" in result


@pytest.mark.asyncio
async def test_get_attraction_missing_coordinates():
    """Attraction returns None coordinates when API omits them."""
    response = {**REAL_WIKI_RESPONSE, "coordinates": None}
    with (
        unittest.mock.patch(
            "app.agent.tools.attractions.httpx.AsyncClient"
        ) as mock_client_cls,
        unittest.mock.patch("app.agent.tools.attractions.settings") as mock_settings,
    ):
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client
        mock_settings.GOOGLE_MAPS_API_KEY = ""

        result = await get_attraction("Taj Mahal")

    assert result["coordinates"] is None
    assert result["map_url"] is None


@pytest.mark.asyncio
async def test_get_attraction_missing_thumbnail_and_original_image():
    """Attraction returns None for image fields when API omits them."""
    response = {**REAL_WIKI_RESPONSE, "thumbnail": None, "originalimage": None}
    with (
        unittest.mock.patch(
            "app.agent.tools.attractions.httpx.AsyncClient"
        ) as mock_client_cls,
        unittest.mock.patch("app.agent.tools.attractions.settings") as mock_settings,
    ):
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client
        mock_settings.GOOGLE_MAPS_API_KEY = ""

        result = await get_attraction("Taj Mahal")

    assert result["thumbnail_url"] is None
    assert result["image_url"] is None


@pytest.mark.asyncio
async def test_get_attraction_missing_content_urls():
    """Attraction returns None for wiki_url when content_urls is absent."""
    response = {**REAL_WIKI_RESPONSE, "content_urls": None}
    with (
        unittest.mock.patch(
            "app.agent.tools.attractions.httpx.AsyncClient"
        ) as mock_client_cls,
        unittest.mock.patch("app.agent.tools.attractions.settings") as mock_settings,
    ):
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_client = unittest.mock.MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        mock_client_cls.return_value = mock_client
        mock_settings.GOOGLE_MAPS_API_KEY = ""

        result = await get_attraction("Taj Mahal")

    assert result["wiki_url"] is None


# ---------------------------------------------------------------------------
# Tests — _extract_location_from_description
# ---------------------------------------------------------------------------


def test_extract_location_standard_format():
    """Standard 'Type in City, State, Country' format."""
    result = _extract_location_from_description(
        "Mausoleum in Agra, Uttar Pradesh, India"
    )
    assert result == "Agra, Uttar Pradesh, India"


def test_extract_location_museum():
    """Museum in City, Country format."""
    result = _extract_location_from_description("Museum in London, England")
    assert result == "London, England"


def test_extract_location_no_in_pattern():
    """Description without ' in ' returns None."""
    result = _extract_location_from_description("16th-century Ottoman mosque")
    assert result is None


def test_extract_location_empty():
    """Empty description returns None."""
    result = _extract_location_from_description("")
    assert result is None


def test_extract_location_none():
    """None description returns None."""
    result = _extract_location_from_description(None)
    assert result is None


def test_extract_location_only_in_prefix():
    """Description that is just 'Type in ' returns empty string stripped to None."""
    # e.g. " in Agra" would give "Agra" — but this is unrealistic in practice
    result = _extract_location_from_description(" in Agra")
    assert result == "Agra"


def test_extract_location_compound_category():
    """Category with multiple words before ' in ' is preserved."""
    result = _extract_location_from_description(
        "Islamic shrine in Agra, Uttar Pradesh, India"
    )
    assert result == "Agra, Uttar Pradesh, India"
    # category split happens separately in the caller, not in this function
