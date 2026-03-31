"""Google Maps URL builder — no API calls.

Generates Google Maps Embed/Static URLs from coordinates or place names.

Returns:
    embed_url: "https://www.google.com/maps/embed?..."
    static_url: "https://maps.googleapis.com/maps/api/staticmap?..."
"""

from __future__ import annotations

from typing import Literal

from loguru import logger

from app.core.config import settings

TravelMode = Literal["driving", "walking", "bicycling", "transit"]


def build_embed_url(
    lat: float | None = None,
    lon: float | None = None,
    place: str | None = None,
    zoom: int = 14,
) -> str:
    """Build a Google Maps Embed API URL (place mode)."""
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="build_embed_url",
        lat=lat,
        lon=lon,
        place=place,
        zoom=zoom,
    ).debug("TOOL: build_embed_url called")

    if not settings.GOOGLE_MAPS_API_KEY:
        logger.bind(
            event="tool_no_api_key",
            layer="tool",
            tool="build_embed_url",
        ).warning("TOOL: GOOGLE_MAPS_API_KEY not configured")
        return ""

    if lat is not None and lon is not None:
        q = f"{lat},{lon}"
    elif place:
        q = place.replace(" ", "+")
    else:
        logger.bind(
            event="tool_invalid_params",
            layer="tool",
            tool="build_embed_url",
            lat=lat,
            lon=lon,
            place=place,
        ).warning("TOOL: build_embed_url — no coordinates or place provided")
        return ""

    url = (
        "https://www.google.com/maps/embed/v1/place"
        f"?key={settings.GOOGLE_MAPS_API_KEY}"
        f"&q={q}"
        f"&zoom={zoom}"
    )

    logger.bind(
        event="tool_done",
        layer="tool",
        tool="build_embed_url",
        url_preview=url[:80] + "..." if len(url) > 80 else url,
    ).debug("TOOL: build_embed_url done")

    return url


def build_static_url(
    lat: float,
    lon: float,
    zoom: int = 14,
    size: str = "600x300",
    marker_color: str = "red",
) -> str:
    """Build a Google Maps Static API URL."""
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="build_static_url",
        lat=lat,
        lon=lon,
        zoom=zoom,
        size=size,
        marker_color=marker_color,
    ).debug("TOOL: build_static_url called")

    if not settings.GOOGLE_MAPS_API_KEY:
        logger.bind(
            event="tool_no_api_key",
            layer="tool",
            tool="build_static_url",
        ).warning("TOOL: GOOGLE_MAPS_API_KEY not configured")
        return ""

    url = (
        "https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lon}"
        f"&zoom={zoom}"
        f"&size={size}"
        f"&markers=color:{marker_color}%7C{lat},{lon}"
        f"&key={settings.GOOGLE_MAPS_API_KEY}"
    )

    logger.bind(
        event="tool_done",
        layer="tool",
        tool="build_static_url",
        url_preview=url[:80] + "..." if len(url) > 80 else url,
    ).debug("TOOL: build_static_url done")

    return url


def build_directions_url(
    from_place: str,
    to_place: str,
    mode: TravelMode = "driving",
) -> str:
    """Build a Google Maps directions URL (opens in browser/app)."""
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="build_directions_url",
        from_place=from_place,
        to_place=to_place,
        mode=mode,
    ).debug("TOOL: build_directions_url called")

    f = from_place.replace(" ", "+")
    t = to_place.replace(" ", "+")
    url = (
        "https://www.google.com/maps/dir/"
        f"?api=1"
        f"&origin={f}"
        f"&destination={t}"
        f"&travelmode={mode}"
    )

    logger.bind(
        event="tool_done",
        layer="tool",
        tool="build_directions_url",
        url_preview=url[:80] + "..." if len(url) > 80 else url,
    ).debug("TOOL: build_directions_url done")

    return url
