"""SerpAPI Google Maps — transport options between locations.

API: GET https://serpapi.com/search.json
Params: q={query}, api_key={SERPAPI_KEY}, engine=google_maps

⚠️ Demo-grade cache: module-level dict (NOT lru_cache on async).
lru_cache does NOT work on async functions — it caches the coroutine
object, not the result.

Returns:
    {
        "options": [
            {
                "type": "MTR",
                "duration": "45 min",
                "cost": "HKD 50",
                "details": "..."
            },
            ...
        ]
    }
"""

from __future__ import annotations

import httpx

from app.core.config import settings

# Demo-grade cache: dict[tuple[str, str], dict]
_cache: dict[tuple[str, str], dict] = {}


async def get_transport(
    from_location: str,
    to_location: str,
    mode: str | None = None,
) -> dict:
    """
    Get transport options between two locations.

    mode: preferred transport type (e.g. "MTR", "bus", "taxi", "train")
          If None, returns all available options.
    """
    cache_key = (from_location.strip().lower(), to_location.strip().lower())
    if cache_key in _cache:
        result = _cache[cache_key]
        if mode:
            result = {
                "options": [
                    o
                    for o in result.get("options", [])
                    if mode.lower() in o.get("type", "").lower()
                ]
            }
        return result

    if not settings.SERPAPI_KEY:
        return {"error": "SERPAPI_KEY not configured", "options": []}

    query = f"transport from {from_location} to {to_location}"
    params = {
        "q": query,
        "api_key": settings.SERPAPI_KEY,
        "engine": "google_maps",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://serpapi.com/search.json",
                params=params,
            )
            if response.status_code == 401:
                return {"error": "Invalid SerpAPI key", "options": []}
            response.raise_for_status()
            data = response.json()

        options = []
        # Parse transport results — SerpAPI Google Maps returns "transport_results"
        # or "routes" depending on query type
        transport_list = (
            data.get("transport_results", [])
            or data.get("routes", [])
            or data.get("results", [])
        )

        for t in transport_list[:10]:
            transport_type = t.get("type", "Unknown")
            options.append(
                {
                    "type": transport_type,
                    "duration": t.get("duration", "N/A"),
                    "cost": t.get("price", t.get("fare", "N/A")),
                    "details": t.get("description", ""),
                }
            )

        result = {"options": options}
        _cache[cache_key] = result

        if mode:
            result = {
                "options": [
                    o for o in options if mode.lower() in o.get("type", "").lower()
                ]
            }
        return result

    except httpx.TimeoutException:
        return {
            "error": f"Timeout fetching transport: {from_location} → {to_location}",
            "options": [],
        }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error fetching transport: {e}", "options": []}
    except Exception as e:
        return {"error": f"Transport search failed: {e}", "options": []}
