"""Google Maps URL builder — no API calls.

Generates Google Maps Embed/Static URLs from coordinates or place names.

Returns:
    embed_url: "https://www.google.com/maps/embed?..."
    static_url: "https://maps.googleapis.com/maps/api/staticmap?..."
"""

from __future__ import annotations

from typing import Literal

from app.core.config import settings

TravelMode = Literal["driving", "walking", "bicycling", "transit"]


def build_embed_url(
    lat: float | None = None,
    lon: float | None = None,
    place: str | None = None,
    zoom: int = 14,
) -> str:
    """Build a Google Maps Embed API URL (place mode)."""
    if not settings.GOOGLE_MAPS_API_KEY:
        return ""

    if lat is not None and lon is not None:
        q = f"{lat},{lon}"
    elif place:
        q = place.replace(" ", "+")
    else:
        return ""

    return (
        "https://www.google.com/maps/embed/v1/place"
        f"?key={settings.GOOGLE_MAPS_API_KEY}"
        f"&q={q}"
        f"&zoom={zoom}"
    )


def build_static_url(
    lat: float,
    lon: float,
    zoom: int = 14,
    size: str = "600x300",
    marker_color: str = "red",
) -> str:
    """Build a Google Maps Static API URL."""
    if not settings.GOOGLE_MAPS_API_KEY:
        return ""

    return (
        "https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lon}"
        f"&zoom={zoom}"
        f"&size={size}"
        f"&markers=color:{marker_color}%7C{lat},{lon}"
        f"&key={settings.GOOGLE_MAPS_API_KEY}"
    )


def build_directions_url(
    from_place: str,
    to_place: str,
    mode: TravelMode = "driving",
) -> str:
    """Build a Google Maps directions URL (opens in browser/app)."""
    f = from_place.replace(" ", "+")
    t = to_place.replace(" ", "+")
    return (
        "https://www.google.com/maps/dir/"
        f"?api=1"
        f"&origin={f}"
        f"&destination={t}"
        f"&travelmode={mode}"
    )
