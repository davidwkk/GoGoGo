"""Wikipedia REST API — enrich attractions with description, thumbnail, coordinates.

API: GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}
No API key required.

Returns:
    {
        "name": "...",
        "description": "...",
        "thumbnail_url": "...",
        "coordinates": {"lat": ..., "lon": ...},
        "category": "..."
    }
"""

from __future__ import annotations

import httpx
from loguru import logger


async def get_attraction(attraction_name: str) -> dict:
    """Fetch attraction details from Wikipedia REST API."""
    title = attraction_name.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

    logger.info(f"[attractions] Fetching: {attraction_name}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning(f"[attractions] Not found: {attraction_name}")
                return {
                    "error": f"Attraction not found: {attraction_name}",
                    "name": attraction_name,
                }
            response.raise_for_status()
            data = response.json()

            coords = None
            if (
                "coordinates" in data
                and isinstance(data["coordinates"], list)
                and data["coordinates"]
            ):
                first = data["coordinates"][0]
                coords = {
                    "lat": first.get("lat"),
                    "lon": first.get("lon"),
                }

            result = {
                "name": data.get("title", attraction_name),
                "description": data.get("extract", ""),
                "thumbnail_url": data.get("thumbnail", {}).get("source"),
                "coordinates": coords,
                "category": None,
            }
            logger.info(f"[attractions] Fetched: {result['name']}")
            return result
    except httpx.TimeoutException:
        logger.warning(f"[attractions] Timeout: {attraction_name}")
        return {
            "error": f"Timeout fetching attraction: {attraction_name}",
            "name": attraction_name,
        }
    except httpx.HTTPStatusError as e:
        logger.warning(f"[attractions] HTTP error: {e}")
        return {
            "error": f"HTTP error fetching attraction: {e}",
            "name": attraction_name,
        }
    except Exception as e:
        logger.warning(f"[attractions] Failed: {e}")
        return {"error": f"Failed to fetch attraction: {e}", "name": attraction_name}
