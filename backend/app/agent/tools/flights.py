"""SerpAPI Google Flights — search for flights.

API: GET https://serpapi.com/search.json
Params: q={query}, api_key={SERPAPI_KEY}, engine=google_flights

Returns:
    {
        "flights": [
            {
                "airline": "...",
                "flight_number": "...",
                "departure": "...",
                "arrival": "...",
                "duration": "...",
                "price": "...",
                "booking_url": "..."  # constructed Google Flights search URL
            },
            ...
        ]
    }
"""

from __future__ import annotations

import httpx

from app.core.config import settings


async def search_flights(
    departure: str,
    arrival: str,
    date: str | None = None,
) -> dict:
    """Search for flights using SerpAPI Google Flights."""
    if not settings.SERPAPI_KEY:
        return {"error": "SERPAPI_KEY not configured", "flights": []}

    # Build query: "flights from JFK to NRT"
    query = f"flights from {departure} to {arrival}"
    if date:
        query += f" on {date}"

    params = {
        "q": query,
        "api_key": settings.SERPAPI_KEY,
        "engine": "google_flights",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://serpapi.com/search.json",
                params=params,
            )
            if response.status_code == 401:
                return {"error": "Invalid SerpAPI key", "flights": []}
            if response.status_code == 404:
                return {"error": "SerpAPI flights endpoint not found", "flights": []}
            response.raise_for_status()
            data = response.json()

        flights = []
        # SerpAPI returns flight results under "flights" or "best_flights" / "other_flights"
        flight_lists = data.get("flights") or data.get("best_flights", [])

        for f in flight_lists[:10]:
            # Build a Google Flights search URL for this route
            route_query = f"{departure}+to+{arrival}".replace(" ", "+")
            booking_url = (
                f"https://www.google.com/travel/flights/search?q={route_query}&hl=en"
            )

            flights.append(
                {
                    "airline": f.get("airline", "Unknown"),
                    "flight_number": f.get("flight_number", ""),
                    "departure": departure,
                    "arrival": arrival,
                    "duration": f.get("duration", ""),
                    "price": f.get("price", "N/A"),
                    "booking_url": booking_url,
                }
            )

        return {"flights": flights}
    except httpx.TimeoutException:
        return {"error": f"Timeout searching flights: {query}", "flights": []}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error searching flights: {e}", "flights": []}
    except Exception as e:
        return {"error": f"Flight search failed: {e}", "flights": []}
