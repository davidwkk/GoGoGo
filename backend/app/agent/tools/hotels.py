"""SerpAPI Google Hotels — search for hotels.

API: GET https://serpapi.com/search.json
Params: q={query}, api_key={SERPAPI_KEY}, engine=google_hotels

Returns:
    {
        "hotels": [
            {
                "name": "...",
                "location": "...",
                "price_per_night": "...",
                "rating": "4.5/5",
                "amenities": [...],
                "booking_url": "..."
            },
            ...
        ]
    }
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings


async def search_hotels(
    destination: str,
    check_in: str | None = None,
    check_out: str | None = None,
) -> dict:
    """Search for hotels using SerpAPI Google Hotels."""
    if not settings.SERPAPI_KEY:
        return {"error": "SERPAPI_KEY not configured", "hotels": []}

    query = f"hotels in {destination}"
    if check_in:
        query += f" check-in {check_in}"
    if check_out:
        query += f" check-out {check_out}"

    logger.info(f"[hotels] Searching: {query}")

    params = {
        "q": query,
        "api_key": settings.SERPAPI_KEY,
        "engine": "google_hotels",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://serpapi.com/search.json",
                params=params,
            )
            if response.status_code == 401:
                logger.warning("[hotels] Invalid SerpAPI key")
                return {"error": "Invalid SerpAPI key", "hotels": []}
            if response.status_code == 404:
                logger.warning("[hotels] Hotels endpoint not found")
                return {"error": "SerpAPI hotels endpoint not found", "hotels": []}
            response.raise_for_status()
            data = response.json()

        hotels = []
        # SerpAPI returns hotels in "hotels" or "results"
        hotel_list = data.get("hotels", []) or data.get("results", [])

        for h in hotel_list[:10]:
            # Extract rating
            rating = None
            rating_data = h.get("rating")
            if rating_data:
                rating = f"{rating_data}/5"

            # Extract price
            price = h.get("price", "N/A")

            # Extract amenities
            amenities = []
            for ext in h.get("extensions", []):
                if isinstance(ext, str):
                    amenities.append(ext)
                elif isinstance(ext, list):
                    amenities.extend(ext)

            hotels.append(
                {
                    "name": h.get("name", "Unknown Hotel"),
                    "location": h.get("location", destination),
                    "price_per_night": price,
                    "rating": rating,
                    "amenities": amenities[:5],
                    "booking_url": h.get("link", ""),
                }
            )

        logger.info(f"[hotels] Found {len(hotels)} hotels in {destination}")
        return {"hotels": hotels}
    except httpx.TimeoutException:
        logger.warning(f"[hotels] Timeout for: {destination}")
        return {"error": f"Timeout searching hotels for: {destination}", "hotels": []}
    except httpx.HTTPStatusError as e:
        logger.warning(f"[hotels] HTTP error: {e}")
        return {"error": f"HTTP error searching hotels: {e}", "hotels": []}
    except Exception as e:
        logger.warning(f"[hotels] Failed: {e}")
        return {"error": f"Hotel search failed: {e}", "hotels": []}
