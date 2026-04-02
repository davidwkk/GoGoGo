"""Wikipedia REST API — enrich attractions with description, thumbnail, coordinates.

API: GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}
No API key required.

--- Wikipedia REST API Page Summary Full Response Schema ---
{
    "title": "Taj Mahal",
    "displaytitle": "Taj Mahal",
    "description": "Mausoleum in Agra, Uttar Pradesh, India",   # short description
    "extract": "The Taj Mahal is an ivory-white marble mausoleum...",
    "extract_html": "<p>The Taj Mahal is an ivory-white...</p>",
    "thumbnail": {
        "source": "https://upload.wikimedia.org/wikipedia/...",
        "width": 320,
        "height": 240
    },
    "originalimage": {
        "source": "https://upload.wikimedia.org/wikipedia/...",
        "width": 4000,
        "height": 3000
    },
    "coordinates": {
        "lat": 27.175144,
        "lon": 78.042138
    },
    "content_urls": {
        "desktop": {
            "page": "https://en.wikipedia.org/wiki/Taj_Mahal"
        },
        "mobile": {
            "page": "https://en.m.wikipedia.org/wiki/Taj_Mahal"
        }
    },
    "type": "standard",
    "wikibase_item": "Q6568032",
}

--- Our Normalized Output Schema ---
{
    "name": str,                    # e.g. "Taj Mahal"
    "description": str,             # full extract/description
    "location": str | None,        # textual location (city, country)
    "map_url": str | None,         # Google Maps embed URL built from coordinates
    "thumbnail_url": str | None,    # small image for cards
    "image_url": str | None,       # full original image URL
    "coordinates": {
        "lat": float,
        "lon": float,
    } | None,
    "category": str | None,        # e.g. "Mausoleum", "Museum", "Park"
    "wiki_url": str | None,        # desktop Wikipedia page URL
}
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings


async def get_attraction(attraction_name: str) -> dict:
    """Fetch attraction details from Wikipedia REST API."""
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="get_attraction",
        attraction_name=attraction_name,
    ).info(f"TOOL: get_attraction start — attraction={attraction_name}")

    title = attraction_name.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

    logger.bind(
        event="tool_api_call",
        layer="tool",
        tool="get_attraction",
        attraction_name=attraction_name,
        url=url,
    ).debug(f"TOOL: Calling Wikipedia API for {attraction_name}")

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent": "GoGoGo-Travel-Agent/1.0 (travel planning app; contact@example.com)",
                "Accept": "application/json",
            },
        ) as client:
            response = await client.get(url)
            if response.status_code == 404:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="get_attraction",
                    status_code=404,
                    attraction_name=attraction_name,
                ).error(f"TOOL: Attraction not found: {attraction_name}")
                return {
                    "error": f"Attraction not found: {attraction_name}",
                    "name": attraction_name,
                }
            response.raise_for_status()
            data = response.json()

        # Coordinates
        coords = None
        raw_coords = data.get("coordinates")
        if raw_coords and isinstance(raw_coords, dict):
            coords = {
                "lat": raw_coords.get("lat"),
                "lon": raw_coords.get("lon"),
            }

        # Build Google Maps embed URL from coordinates
        map_url = None
        if coords and settings.GOOGLE_MAPS_API_KEY:
            lat = coords.get("lat")
            lon = coords.get("lon")
            if lat is not None and lon is not None:
                map_url = (
                    f"https://www.google.com/maps/embed/v1/place"
                    f"?key={settings.GOOGLE_MAPS_API_KEY}"
                    f"&q=place/{lat},{lon}"
                )

        # Thumbnail vs full image
        thumbnail = data.get("thumbnail") or {}
        original = data.get("originalimage") or {}

        # Build textual location from description (best effort)
        # e.g. "Mausoleum in Agra, Uttar Pradesh, India" → "Agra, Uttar Pradesh, India"
        description = data.get("description", "")
        # Try to extract a location string from the description
        location = _extract_location_from_description(description)

        result = {
            "name": data.get("title", attraction_name),
            "description": data.get("extract", ""),
            "location": location,
            "map_url": map_url,
            "thumbnail_url": thumbnail.get("source"),
            "image_url": original.get("source"),
            "coordinates": coords,
            "category": description.split(" in ")[0] if " in " in description else None,
            "wiki_url": ((data.get("content_urls") or {}).get("desktop", {}) or {}).get(
                "page"
            ),
        }
        logger.bind(
            event="tool_done",
            layer="tool",
            tool="get_attraction",
            attraction_name=attraction_name,
            result_name=result["name"],
            has_coordinates=coords is not None,
            has_thumbnail=thumbnail.get("source") is not None,
        ).info(f"TOOL: get_attraction done — fetched: {result['name']}")
        return result
    except httpx.TimeoutException:
        logger.bind(
            event="tool_timeout",
            layer="tool",
            tool="get_attraction",
            attraction_name=attraction_name,
        ).error(f"TOOL: Timeout fetching attraction: {attraction_name}")
        return {
            "error": f"Timeout fetching attraction: {attraction_name}",
            "name": attraction_name,
        }
    except httpx.HTTPStatusError as e:
        logger.bind(
            event="tool_http_error",
            layer="tool",
            tool="get_attraction",
            status_code=e.response.status_code,
        ).error(f"TOOL: HTTP error fetching attraction: {e}")
        return {
            "error": f"HTTP error fetching attraction: {e}",
            "name": attraction_name,
        }
    except Exception as e:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="get_attraction",
            error=str(e),
        ).error(f"TOOL: Failed to fetch attraction: {e}")
        return {"error": f"Failed to fetch attraction: {e}", "name": attraction_name}


def _extract_location_from_description(description: str | None) -> str | None:
    """Extract a textual location from a Wikipedia short description.

    E.g. "Mausoleum in Agra, Uttar Pradesh, India" → "Agra, Uttar Pradesh, India"
    E.g. "Museum in London, England" → "London, England"
    """
    if not description:
        return None
    if " in " in description:
        return description.split(" in ", 1)[1].strip()
    return None
