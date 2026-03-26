"""Simple tests for maps URL builder."""

from unittest.mock import patch

from app.agent.tools.maps import build_embed_url, build_static_url, build_directions_url


def test_build_embed_url_with_coords():
    """build_embed_url returns a maps embed URL with coordinates."""
    with patch("app.agent.tools.maps.settings") as mock_settings:
        mock_settings.GOOGLE_MAPS_API_KEY = "test_key"

        url = build_embed_url(lat=35.6586, lon=139.7454, zoom=15)
        assert "google.com/maps/embed" in url
        assert "test_key" in url
        assert "35.6586" in url
        assert "139.7454" in url


def test_build_embed_url_with_place():
    """build_embed_url returns a maps embed URL with place name."""
    with patch("app.agent.tools.maps.settings") as mock_settings:
        mock_settings.GOOGLE_MAPS_API_KEY = "test_key"

        url = build_embed_url(place="Tokyo Tower", zoom=14)
        assert "google.com/maps/embed" in url
        assert "test_key" in url


def test_build_embed_url_no_api_key():
    """build_embed_url returns empty string when no API key."""
    with patch("app.agent.tools.maps.settings") as mock_settings:
        mock_settings.GOOGLE_MAPS_API_KEY = ""

        url = build_embed_url(lat=35.6586, lon=139.7454)
        assert url == ""


def test_build_static_url():
    """build_static_url returns a static map URL."""
    with patch("app.agent.tools.maps.settings") as mock_settings:
        mock_settings.GOOGLE_MAPS_API_KEY = "test_key"

        url = build_static_url(lat=35.6586, lon=139.7454, zoom=14, size="600x300")
        assert "maps.googleapis.com/maps/api/staticmap" in url
        assert "35.6586" in url
        assert "600x300" in url


def test_build_directions_url():
    """build_directions_url returns a directions URL."""
    url = build_directions_url(from_place="Tokyo", to_place="Kyoto", mode="driving")
    assert "google.com/maps/dir" in url
    assert "Tokyo" in url
    assert "Kyoto" in url
