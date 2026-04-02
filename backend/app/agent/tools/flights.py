"""SerpAPI Google Flights — search for flights.

API: GET https://serpapi.com/search.json
Params: engine=google_flights, departure_id=PEK, arrival_id=AUS,
        outbound_date=2026-03-31, return_date=2026-04-06, currency=HKD, hl=en

NOTE: google_flights engine does NOT support free-text "q" param.
      It requires structured params: departure_id, arrival_id, outbound_date.

--- SerpAPI Google Flights Full Response Schema ---
{
    "search_metadata": {...},
    "search_parameters": {...},
    "best_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"name": "Beijing Capital International Airport", "id": "PEK", "time": "2023-10-03 15:10"},
                    "arrival_airport":  {"name": "Haneda Airport",                       "id": "HND", "time": "2023-10-03 19:35"},
                    "duration": 205,
                    "airplane": "Boeing 787",
                    "airline": "ANA",
                    "airline_logo": "https://www.gstatic.com/flights/airline_logos/70px/NH.png",
                    "travel_class": "Economy",
                    "flight_number": "NH 962",
                    "legroom": "31 in",
                    "extensions": ["Average legroom (31 in)", "Wi-Fi for a fee", ...],
                    "overnight": true,
                    "often_delayed_by_over_30_min": true,
                    "ticket_also_sold_by": ["United"],
                },
                ...
            ],
            "layovers": [
                {"duration": 90,  "name": "Haneda Airport",                        "id": "HND"},
                {"duration": 231, "name": "Los Angeles International Airport",     "id": "LAX", "overnight": true},
            ],
            "total_duration": 1309,
            "carbon_emissions": {"this_flight": 1106000, "typical_for_this_route": 949000, "difference_percent": 17},
            "price": 2512,
            "type": "Round trip",
            "airline_logo": "https://www.gstatic.com/flights/airline_logos/70px/multi.png",
            "departure_token": "W1siUEVLIi...",
        }
    ],
    "other_flights": [
        # same structure as best_flights
    ],
}

--- Our Normalized Output Schema ---
{
    "flights": [
        {
            "airline": str,                     # e.g. "ANA"
            "flight_number": str,               # e.g. "NH 962"
            "departure_airport": str,           # IATA code, e.g. "PEK"
            "departure_airport_name": str,      # e.g. "Beijing Capital International Airport"
            "arrival_airport": str,             # IATA code, e.g. "HND"
            "arrival_airport_name": str,        # e.g. "Haneda Airport"
            "departure_time": str,              # ISO 8601 datetime, e.g. "2023-10-03T15:10:00"
            "arrival_time": str,                # ISO 8601 datetime, e.g. "2023-10-03T19:35:00"
            "duration_minutes": int,            # e.g. 205
            "airplane": str | None,            # e.g. "Boeing 787"
            "travel_class": str | None,        # e.g. "Economy"
            "legroom": str | None,             # e.g. "31 in"
            "layover_after": {                  # connection after this segment (between seg i and i+1)
                "airport_code": str,           # e.g. "HND"
                "airport_name": str,           # e.g. "Haneda Airport"
                "duration_minutes": int,        # e.g. 90
            } | None,
            "price": int | None,               # itinerary total price in HKD (same for all segs)
            "booking_url": str,                # Google Flights search URL pre-filled with route + date
        }
    ]
}
"""

from __future__ import annotations

import re
from datetime import date as _date, datetime

import httpx
from loguru import logger

from app.core.config import settings

# Strict IATA airport code pattern: 3 uppercase letters, sometimes 4 for regional codes
_IATA_RE = re.compile(r"^[A-Z]{3,4}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD


async def search_flights(
    departure: str,
    arrival: str,
    date: str | None = None,
) -> dict:
    """Search for flights using SerpAPI Google Flights.

    departure / arrival must be valid IATA airport codes (3-4 uppercase letters).
    SerpAPI google_flights engine does not support free-text queries.
    """
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="search_flights",
        departure=departure,
        arrival=arrival,
        date=date,
    ).info("TOOL: search_flights start")

    if not settings.SERPAPI_KEY:
        logger.bind(
            event="tool_no_api_key",
            layer="tool",
            tool="search_flights",
        ).warning("TOOL: SERPAPI_KEY not configured")
        return {"error": "SERPAPI_KEY not configured", "flights": []}

    # Strict IATA validation — must be 3-4 uppercase ASCII letters
    dep_code = departure.strip().upper() if departure else ""
    arr_code = arrival.strip().upper() if arrival else ""
    if not (_IATA_RE.match(dep_code) and _IATA_RE.match(arr_code)):
        logger.bind(
            event="tool_invalid_params",
            layer="tool",
            tool="search_flights",
            departure=departure,
            arrival=arrival,
        ).error(f"TOOL: Invalid airport codes: {departure!r} → {arrival!r}")
        return {
            "error": (
                "departure and arrival must be valid IATA airport codes (3-4 uppercase letters). "
                f"Got: {departure!r} → {arrival!r}"
            ),
            "flights": [],
        }

    # outbound_date is required — default to today if not supplied
    if date and not _DATE_RE.match(date):
        logger.bind(
            event="tool_invalid_params",
            layer="tool",
            tool="search_flights",
            date=date,
        ).error(f"TOOL: Invalid date format: {date!r}")
        return {
            "error": f"date must be YYYY-MM-DD format, got: {date!r}",
            "flights": [],
        }
    outbound_date = date or _date.today().isoformat()

    params: dict = {
        "api_key": settings.SERPAPI_KEY,
        "engine": "google_flights",
        "departure_id": dep_code,
        "arrival_id": arr_code,
        "outbound_date": outbound_date,
        "type": "1",  # 1 = one-way, 2 = round trip (default)
        "currency": "HKD",
        "hl": "en",
    }

    # Pre-build booking URL once (shared across all segments).
    # Note: outbound_date is NOT a valid param for google.com/travel — the date won't
    # be pre-filled; this is a best-effort fallback link.
    booking_url = (
        f"https://www.google.com/travel/flights/search?q={dep_code}+to+{arr_code}&hl=en"
    )

    logger.bind(
        event="tool_api_call",
        layer="tool",
        tool="search_flights",
        dep_code=dep_code,
        arr_code=arr_code,
        date=outbound_date,
    ).info(f"TOOL: Searching flights: {dep_code} → {arr_code} on {outbound_date}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://serpapi.com/search.json",
                params=params,
            )
            if response.status_code == 401:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_flights",
                    status_code=401,
                ).error("TOOL: Invalid SerpAPI key")
                return {"error": "Invalid SerpAPI key", "flights": []}
            if response.status_code == 404:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_flights",
                    status_code=404,
                ).error("TOOL: Flights endpoint not found")
                return {"error": "SerpAPI flights endpoint not found", "flights": []}
            if response.status_code == 429:
                logger.bind(
                    event="tool_rate_limit",
                    layer="tool",
                    tool="search_flights",
                    status_code=429,
                ).error("TOOL: SerpAPI rate limit exceeded")
                return {"error": "SerpAPI rate limit exceeded", "flights": []}
            if response.status_code == 400:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_flights",
                    status_code=400,
                    response_body=response.text[:500],
                ).error(f"TOOL: HTTP error searching flights: {response.text[:500]}")
                return {
                    "error": f"HTTP error searching flights: {response.text[:500]}",
                    "flights": [],
                }
            if response.status_code == 422:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_flights",
                    status_code=422,
                ).error(f"TOOL: Invalid SerpAPI params: {response.text}")
                return {
                    "error": f"Invalid SerpAPI params: {response.text}",
                    "flights": [],
                }
            response.raise_for_status()
            data = response.json()

        flights = []
        # SerpAPI returns up to ~10 itineraries; each has 1-4 flight segments
        raw_itineraries = data.get("best_flights", []) + data.get("other_flights", [])

        for itinerary in raw_itineraries:
            seg_flights = itinerary.get("flights", [])
            layovers = itinerary.get("layovers") or []
            price = itinerary.get("price")

            for i, f in enumerate(seg_flights):
                dep = f.get("departure_airport", {})
                arr = f.get("arrival_airport", {})

                # Layover that follows this segment — connects to the NEXT segment
                # layovers[0] is between seg[0] and seg[1], etc.
                layover_after = None
                if i < len(layovers):
                    lp = layovers[i]
                    layover_after = {
                        "airport_code": lp.get("id", ""),
                        "airport_name": lp.get("name", ""),
                        "duration_minutes": lp.get("duration"),
                    }

                flights.append(
                    {
                        "airline": f.get("airline"),  # None if missing
                        "flight_number": f.get("flight_number", ""),
                        "departure_airport": dep.get("id", ""),
                        "departure_airport_name": dep.get("name", ""),
                        "arrival_airport": arr.get("id", ""),
                        "arrival_airport_name": arr.get("name", ""),
                        "departure_time": _parse_iso_datetime(dep.get("time", "")),
                        "arrival_time": _parse_iso_datetime(arr.get("time", "")),
                        "duration_minutes": f.get("duration"),
                        "airplane": f.get("airplane"),
                        "travel_class": f.get("travel_class"),
                        "legroom": f.get("legroom"),
                        "layover_after": layover_after,
                        "price": price,
                        "booking_url": booking_url,
                    }
                )

        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_flights",
            dep_code=dep_code,
            arr_code=arr_code,
            flight_count=len(flights),
            itinerary_count=len(raw_itineraries),
        ).info(
            f"TOOL: search_flights done — found {len(flights)} segments "
            f"({len(raw_itineraries)} itineraries) for {dep_code} → {arr_code}"
        )
        return {"flights": flights}
    except httpx.TimeoutException:
        logger.bind(
            event="tool_timeout",
            layer="tool",
            tool="search_flights",
            dep_code=dep_code,
            arr_code=arr_code,
        ).error(f"TOOL: Timeout searching flights: {dep_code} → {arr_code}")
        return {
            "error": f"Timeout searching flights: {dep_code} → {arr_code}",
            "flights": [],
        }
    except httpx.HTTPStatusError as e:
        logger.bind(
            event="tool_http_error",
            layer="tool",
            tool="search_flights",
            status_code=e.response.status_code,
        ).error(f"TOOL: HTTP error searching flights: {e}")
        return {"error": f"HTTP error searching flights: {e}", "flights": []}
    except Exception as e:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="search_flights",
            error=str(e),
        ).error(f"TOOL: Flight search failed: {e}")
        return {"error": f"Flight search failed: {e}", "flights": []}


def _parse_iso_datetime(value: str) -> str:
    """Parse '2023-10-03 15:10' → '2023-10-03T15:10:00' ISO 8601."""
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M").isoformat()
    except ValueError:
        logger.bind(
            event="tool_parse_error",
            layer="tool",
            tool="search_flights",
            value=value,
        ).error(f"TOOL: Unexpected datetime format: {value!r}")
        return value
