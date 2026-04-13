"""SerpAPI Google Flights — search for flights.

API: GET https://serpapi.com/search.json
Params: engine=google_flights, departure_id=PEK, arrival_id=AUS,
        outbound_date=2026-03-31, type=2 (one-way), currency=HKD, hl=en

NOTE: google_flights engine does NOT support free-text "q" param.
      It requires structured params: departure_id, arrival_id, outbound_date.

--- Round-trip strategy ---
For round-trips, we make exactly 2 API calls:
  1. Outbound: type=1, departure_id=<origin>, arrival_id=<dest>, outbound_date=<date>, return_date=<return_date>
     Returns departure_token(s) in the response.
  2. Return: type=1 with additional departure_token from step 1 to fetch linked return flights.

Fallback: If departure_token is unavailable or HTTP 400, falls back to reversed-airport one-way call.

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
            "direction": str,                     # "outbound" or "return"
            "airline": str | None,               # e.g. "ANA"
            "flight_number": str,                 # e.g. "NH 962"
            "departure_airport": str,             # IATA code, e.g. "PEK"
            "departure_airport_name": str,        # e.g. "Beijing Capital International Airport"
            "arrival_airport": str,               # IATA code, e.g. "HND"
            "arrival_airport_name": str,          # e.g. "Haneda Airport"
            "departure_time": str,                # ISO 8601 datetime, e.g. "2023-10-03T15:10:00"
            "arrival_time": str,                  # ISO 8601 datetime, e.g. "2023-10-03T19:35:00"
            "duration_minutes": int | None,       # e.g. 205
            "airplane": str | None,              # e.g. "Boeing 787"
            "travel_class": str | None,           # e.g. "Economy"
            "legroom": str | None,               # e.g. "31 in"
            "layover_after": {                   # connection after this segment (between seg i and i+1)
                "airport_code": str,             # e.g. "HND"
                "airport_name": str,             # e.g. "Haneda Airport"
                "duration_minutes": int | None,   # e.g. 90
            } | None,
            "price": int | None,                  # itinerary total price in HKD
            "booking_url": str,                   # Google Flights search URL
        }
    ]
}
"""

from __future__ import annotations

import re
from datetime import datetime

import httpx
from loguru import logger

from app.core.config import settings

_IATA_RE = re.compile(r"^[A-Z]{3,4}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD

# City/metro codes that SerpAPI accepts but are NOT airport codes.
_CITY_TO_AIRPORT: dict[str, str] = {
    "BJS": "PEK",
    "SHA": "PVG",
    "NKG": "NKG",
    "CAN": "CAN",
}


async def search_flights(
    departure: str,
    arrival: str,
    date: str,
    return_date: str | None = None,
    passengers: int = 1,
) -> dict:
    """Search for flights using SerpAPI Google Flights.

    departure / arrival must be valid IATA airport codes (3-4 uppercase letters).
    SerpAPI google_flights engine does not support free-text queries.
    Pass return_date for round-trips (makes 2 API calls total).
    Omit return_date for one-way (single API call).
    """
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="search_flights",
        departure=departure,
        arrival=arrival,
        date=date,
        return_date=return_date,
    ).debug(
        f"TOOL: search_flights start — departure={departure} arrival={arrival} "
        f"date={date} return_date={return_date}"
    )

    if not settings.SERPAPI_KEY:
        logger.bind(
            event="tool_no_api_key",
            layer="tool",
            tool="search_flights",
        ).warning("TOOL: SERPAPI_KEY not configured")
        return {"error": "SERPAPI_KEY not configured", "flights": []}

    # ── Robust IATA code normalization ──────────────────────────────────────────
    raw_dep = (departure or "").strip()
    raw_arr = (arrival or "").strip()

    # Handle missing departure — default to HKG
    if not raw_dep:
        logger.bind(
            event="tool_param_fix",
            layer="tool",
            tool="search_flights",
            original=repr(departure),
            fix="defaulted to HKG",
        ).warning("TOOL: Missing departure, defaulting to HKG")
        raw_dep = "HKG"

    # Handle comma-separated codes like "HND,NRT" → take first
    if "," in raw_dep:
        raw_dep = raw_dep.split(",")[0].strip()
        logger.bind(
            event="tool_param_fix",
            layer="tool",
            tool="search_flights",
            original=departure,
            fix=f"took first code: {raw_dep}",
        ).warning(f"TOOL: Comma-separated departure code, took first: {raw_dep}")

    if "," in raw_arr:
        raw_arr = raw_arr.split(",")[0].strip()
        logger.bind(
            event="tool_param_fix",
            layer="tool",
            tool="search_flights",
            original=arrival,
            fix=f"took first code: {raw_arr}",
        ).warning(f"TOOL: Comma-separated arrival code, took first: {raw_arr}")

    # Uppercase
    dep_code = raw_dep.upper()
    arr_code = raw_arr.upper()

    # Resolve city/metro codes to airport codes
    if dep_code in _CITY_TO_AIRPORT and _CITY_TO_AIRPORT[dep_code] != dep_code:
        dep_code = _CITY_TO_AIRPORT[dep_code]
        logger.bind(
            event="tool_param_fix",
            layer="tool",
            tool="search_flights",
            original=raw_dep,
            fix=f"resolved to airport: {dep_code}",
        ).info(f"TOOL: City code {raw_dep} resolved to {dep_code}")

    if arr_code in _CITY_TO_AIRPORT and _CITY_TO_AIRPORT[arr_code] != arr_code:
        arr_code = _CITY_TO_AIRPORT[arr_code]
        logger.bind(
            event="tool_param_fix",
            layer="tool",
            tool="search_flights",
            original=raw_arr,
            fix=f"resolved to airport: {arr_code}",
        ).info(f"TOOL: City code {raw_arr} resolved to {arr_code}")

    # For Tokyo/NRT ambiguity, prefer HND over NRT
    if arr_code == "NRT":
        arr_code = "HND"
        logger.bind(
            event="tool_param_fix",
            layer="tool",
            tool="search_flights",
            original="NRT",
            fix="NRT→HND (prefer Haneda for central Tokyo proximity)",
        ).info("TOOL: NRT resolved to HND (prefer Haneda)")

    # Final IATA format validation
    if not _IATA_RE.match(dep_code) or not _IATA_RE.match(arr_code):
        logger.bind(
            event="tool_invalid_params",
            layer="tool",
            tool="search_flights",
            departure=departure,
            arrival=arrival,
            normalized=f"{dep_code} → {arr_code}",
        ).error(
            f"TOOL: Invalid airport codes after normalization: {dep_code!r} → {arr_code!r}"
        )
        return {
            "error": (
                f"Invalid airport code(s): {dep_code!r} → {arr_code!r}. "
                "Use 3-letter IATA codes (e.g., HKG, HND, PEK)."
            ),
            "flights": [],
        }

    # Validate date formats
    if not _DATE_RE.match(date):
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
    if return_date and not _DATE_RE.match(return_date):
        logger.bind(
            event="tool_invalid_params",
            layer="tool",
            tool="search_flights",
            return_date=return_date,
        ).error(f"TOOL: Invalid return_date format: {return_date!r}")
        return {
            "error": f"return_date must be YYYY-MM-DD format, got: {return_date!r}",
            "flights": [],
        }

    is_round_trip = return_date is not None

    if is_round_trip:
        return await _search_round_trip(
            dep_code, arr_code, date, return_date, passengers
        )

    result = await _search_single_leg(
        dep_code=dep_code,
        arr_code=arr_code,
        outbound_date=date,
        return_date=None,
        direction="outbound",
        trip_type="one_way",
        passengers=passengers,
    )
    return result


async def _search_round_trip(
    dep_code: str,
    arr_code: str,
    outbound_date: str,
    return_date: str,
    passengers: int = 1,
) -> dict:
    """Search round-trip with automatic return flight fetching.

    Makes two API calls:
      1. Outbound: type=1 with return_date → get flights + departure_token
      2. Return:  type=1 with departure_token → get return flights for selected outbound

    If ANY step fails, returns the error and lets the LLM decide how to proceed.
    No fallback to reversed-airport approach.
    """
    # Step 1: Get outbound flights
    outbound_result = await _search_single_leg(
        dep_code=dep_code,
        arr_code=arr_code,
        outbound_date=outbound_date,
        return_date=return_date,
        direction="outbound",
        trip_type="round_trip_outbound",
        passengers=passengers,
    )

    # Check if outbound call succeeded
    if outbound_result.get("error"):
        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_flights",
            is_round_trip=True,
            step="outbound_failed",
            error=outbound_result["error"],
        ).warning(f"TOOL: Round-trip outbound call failed: {outbound_result['error']}")
        return {
            "flights": [],
            "error": f"Outbound flight search failed: {outbound_result['error']}",
        }

    outbound_flights = outbound_result.get("flights", [])
    if not outbound_flights:
        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_flights",
            is_round_trip=True,
            step="no_outbound_flights",
        ).warning("TOOL: No outbound flights found")
        return {
            "flights": [],
            "error": "No outbound flights found for the selected route and dates.",
        }

    # Extract departure_token from outbound result
    departure_token = outbound_result.get("departure_token")
    if not departure_token:
        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_flights",
            is_round_trip=True,
            step="no_departure_token",
        ).warning("TOOL: No departure_token in outbound response")
        return {
            "flights": [],
            "error": "No departure_token returned. Cannot fetch return flights automatically.",
        }

    # Step 2: Fetch return flights using departure_token
    # IMPORTANT: Same airport codes, same dates, type=1 (round trip)
    return_result = await _search_return_by_token(
        dep_code=dep_code,
        arr_code=arr_code,
        outbound_date=outbound_date,
        return_date=return_date,
        departure_token=departure_token,
        passengers=passengers,
    )

    # Check if return call succeeded
    if return_result.get("error"):
        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_flights",
            is_round_trip=True,
            step="return_failed",
            error=return_result["error"],
        ).warning(f"TOOL: Return flight fetch failed: {return_result['error']}")
        return {
            "flights": [],
            "error": f"Return flight fetch failed: {return_result['error']}. Please try again.",
        }

    return_flights = return_result.get("flights", [])
    if not return_flights:
        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_flights",
            is_round_trip=True,
            step="no_return_flights",
        ).warning("TOOL: No return flights found via departure_token")
        return {
            "flights": [],
            "error": "No return flights found for the selected outbound flight. Please try different dates or route.",
        }

    # Combine: 1 outbound + up to 3 return flights
    all_flights = outbound_flights[:1] + return_flights[:3]

    # Use only the first outbound flight's booking URL for all flights (round-trip)
    if all_flights:
        primary_booking_url = all_flights[0].get("booking_url")
        for flight in all_flights[1:]:
            flight["booking_url"] = primary_booking_url

    logger.bind(
        event="tool_done",
        layer="tool",
        tool="search_flights",
        is_round_trip=True,
        outbound_count=len(outbound_flights[:1]),
        return_count=len(return_flights[:1]),
        total_count=len(all_flights),
    ).debug(
        f"TOOL: search_flights done — round-trip | "
        f"outbound={dep_code}→{arr_code} ({len(outbound_flights[:1])} flight) "
        f"return={arr_code}→{dep_code} ({len(return_flights[:1])} flight) | "
        f"error=None"
    )
    return {"flights": all_flights, "error": None}


async def _search_return_by_token(
    dep_code: str,
    arr_code: str,
    outbound_date: str,
    return_date: str,
    departure_token: str,
    passengers: int = 1,
) -> dict:
    """Fetch return flights using departure_token from the outbound flight.

    Per SerpAPI docs, departure_token links an outbound flight to its return options.
    Uses type=1 (round trip) with SAME airport codes and dates as the outbound search,
    plus the departure_token, to get return flights for the selected outbound leg.
    """
    params: dict = {
        "api_key": settings.SERPAPI_KEY,
        "engine": "google_flights",
        "departure_id": dep_code,
        "arrival_id": arr_code,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "type": "1",  # round trip (required for departure_token to work)
        "currency": "HKD",
        "hl": "en",
        "departure_token": departure_token,
    }

    logger.bind(
        event="tool_api_call",
        layer="tool",
        tool="search_flights",
        dep_code=dep_code,
        arr_code=arr_code,
        date=outbound_date,
        direction="return",
        trip_type="return_via_token",
        engine="google_flights",
        has_departure_token=True,
    ).debug(
        f"TOOL: Searching return flights via departure_token: {dep_code} → {arr_code} on {outbound_date}"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://serpapi.com/search.json",
                params=params,
            )
            if response.status_code == 400:
                error_body = response.text
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_flights",
                    status_code=400,
                    direction="return",
                    response_body=error_body[:200],
                ).error(f"TOOL: HTTP 400 with departure_token: {error_body[:200]}")
                return {"flights": [], "error": f"HTTP 400: {error_body[:200]}"}
            response.raise_for_status()
            data = response.json()

        raw_itineraries = data.get("best_flights", []) + data.get("other_flights", [])
        flights, _ = _parse_itineraries(
            raw_itineraries, "return", outbound_date, return_date, passengers
        )

        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_flights",
            dep_code=dep_code,
            arr_code=arr_code,
            flight_count=len(flights),
            direction="return",
            trip_type="return_via_token",
        ).debug(
            f"TOOL: search_flights (return via token) done — {len(flights)} segments for {dep_code} → {arr_code}"
        )
        return {"flights": flights}
    except Exception as e:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="search_flights",
            direction="return",
            error=str(e),
        ).error(f"TOOL: Return flight search failed: {e}")
        return {"flights": [], "error": f"Return flight search failed: {e}"}


async def _search_single_leg(
    dep_code: str,
    arr_code: str,
    outbound_date: str,
    return_date: str | None,
    direction: str,
    trip_type: str,  # "one_way" | "round_trip_outbound"
    passengers: int = 1,
) -> dict:
    """Make a single-leg API call to SerpAPI and return parsed results."""
    type_value = "2" if trip_type == "one_way" else "1"

    params: dict = {
        "api_key": settings.SERPAPI_KEY,
        "engine": "google_flights",
        "departure_id": dep_code,
        "arrival_id": arr_code,
        "outbound_date": outbound_date,
        "type": type_value,
        "currency": "HKD",
        "hl": "en",
    }
    if return_date:
        params["return_date"] = return_date

    logger.bind(
        event="tool_api_call",
        layer="tool",
        tool="search_flights",
        dep_code=dep_code,
        arr_code=arr_code,
        date=outbound_date,
        return_date=return_date,
        direction=direction,
        trip_type=trip_type,
        engine="google_flights",
    ).debug(
        f"TOOL: Searching flights: {dep_code} → {arr_code} on {outbound_date} "
        f"| direction={direction} trip_type={trip_type} engine=google_flights"
    )

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
                    direction=direction,
                ).error("TOOL: Invalid SerpAPI key")
                return {"flights": [], "error": "Invalid SerpAPI key"}
            if response.status_code == 404:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_flights",
                    status_code=404,
                    direction=direction,
                ).error("TOOL: Flights endpoint not found")
                return {"flights": [], "error": "SerpAPI flights endpoint not found"}
            if response.status_code == 429:
                logger.bind(
                    event="tool_rate_limit",
                    layer="tool",
                    tool="search_flights",
                    status_code=429,
                    direction=direction,
                ).error("TOOL: SerpAPI rate limit exceeded")
                return {"flights": [], "error": "SerpAPI rate limit exceeded"}
            if response.status_code == 400:
                error_body = response.text
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_flights",
                    status_code=400,
                    response_body=error_body,
                    direction=direction,
                ).error(f"TOOL: HTTP 400 searching flights: {error_body[:200]}")
                return {"flights": [], "error": f"HTTP 400: {error_body[:200]}"}
            if response.status_code == 422:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_flights",
                    status_code=422,
                    direction=direction,
                ).error(f"TOOL: Invalid SerpAPI params: {response.text[:200]}")
                return {
                    "flights": [],
                    "error": f"Invalid SerpAPI params: {response.text[:200]}",
                }
            response.raise_for_status()
            data = response.json()

        raw_itineraries = data.get("best_flights", []) + data.get("other_flights", [])
        flights, departure_tokens = _parse_itineraries(
            raw_itineraries, direction, outbound_date, return_date, passengers
        )
        # Get the first valid departure_token for use in return flight lookup
        first_departure_token = next((t for t in departure_tokens if t), None)

        # Retry with correct airport code if 0 results and code is a known city code
        if not flights:
            retry_dep = _CITY_TO_AIRPORT.get(dep_code)
            retry_arr = _CITY_TO_AIRPORT.get(arr_code)
            if retry_dep and retry_dep != dep_code:
                logger.bind(
                    event="tool_retry",
                    layer="tool",
                    tool="search_flights",
                    reason="0 results, city code resolved",
                    old_dep=dep_code,
                    new_dep=retry_dep,
                    arr=arr_code,
                    direction=direction,
                ).info(
                    f"TOOL: 0 results for {dep_code}→{arr_code}, retrying with airport code {retry_dep}"
                )
                return await _search_single_leg(
                    dep_code=retry_dep,
                    arr_code=arr_code,
                    outbound_date=outbound_date,
                    return_date=return_date,
                    direction=direction,
                    trip_type=trip_type,
                )
            if retry_arr and retry_arr != arr_code:
                logger.bind(
                    event="tool_retry",
                    layer="tool",
                    tool="search_flights",
                    reason="0 results, city code resolved",
                    dep=dep_code,
                    old_arr=arr_code,
                    new_arr=retry_arr,
                    direction=direction,
                ).info(
                    f"TOOL: 0 results for {dep_code}→{arr_code}, retrying with airport code {retry_arr}"
                )
                return await _search_single_leg(
                    dep_code=dep_code,
                    arr_code=retry_arr,
                    outbound_date=outbound_date,
                    return_date=return_date,
                    direction=direction,
                    trip_type=trip_type,
                )

        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_flights",
            dep_code=dep_code,
            arr_code=arr_code,
            flight_count=len(flights),
            itinerary_count=len(raw_itineraries),
            direction=direction,
            trip_type=trip_type,
        ).debug(
            f"TOOL: search_flights ({direction}/{trip_type}) done — {len(flights)} segments "
            f"({len(raw_itineraries)} itineraries) for {dep_code} → {arr_code} on {outbound_date}"
        )
        return {"flights": flights, "departure_token": first_departure_token}
    except httpx.TimeoutException:
        logger.bind(
            event="tool_timeout",
            layer="tool",
            tool="search_flights",
            dep_code=dep_code,
            arr_code=arr_code,
            direction=direction,
        ).error(f"TOOL: Timeout searching flights: {dep_code} → {arr_code}")
        return {"flights": [], "error": f"Timeout: {dep_code} → {arr_code}"}
    except httpx.HTTPStatusError as e:
        logger.bind(
            event="tool_http_error",
            layer="tool",
            tool="search_flights",
            status_code=e.response.status_code,
            direction=direction,
        ).error(f"TOOL: HTTP error searching flights: {e}")
        return {"flights": [], "error": f"HTTP error: {e}"}
    except Exception as e:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="search_flights",
            direction=direction,
            error=str(e),
        ).error(f"TOOL: Flight search failed: {e}")
        return {"flights": [], "error": f"Flight search failed: {e}"}


def _parse_itineraries(
    raw_itineraries: list[dict],
    direction: str,
    outbound_date: str | None,
    return_date: str | None = None,
    passengers: int = 1,
) -> tuple[list[dict], list[str | None]]:
    """Parse raw SerpAPI itineraries into our normalized flight dicts.

    Returns:
        Tuple of (flights list, departure_tokens list)
    """
    flights = []
    departure_tokens = []

    for itinerary in raw_itineraries:
        seg_flights = itinerary.get("flights", [])
        layovers = itinerary.get("layovers") or []
        price = itinerary.get("price")
        departure_token = itinerary.get("departure_token")
        trip_type = itinerary.get("type", "")  # e.g. "Round trip" or "One way"
        is_round_trip = "round" in trip_type.lower()

        seg_outbound_date: str | None = None
        if seg_flights:
            first_dep = seg_flights[0].get("departure_airport", {}).get("time", "")
            seg_outbound_date = (
                _parse_iso_datetime(first_dep)[:10] if first_dep else None
            )

        for i, f in enumerate(seg_flights):
            dep = f.get("departure_airport", {})
            arr = f.get("arrival_airport", {})

            layover_after = None
            if i < len(layovers):
                lp = layovers[i]
                layover_after = {
                    "airport_code": lp.get("id", ""),
                    "airport_name": lp.get("name", ""),
                    "duration_minutes": lp.get("duration"),
                }

            seg_dep_code = dep.get("id", "")
            seg_arr_code = arr.get("id", "")

            seg_date = seg_outbound_date or outbound_date
            seat_text = f"{passengers}+seats" if passengers > 1 else "1+seat"
            if is_round_trip and return_date:
                # Round trip: natural language with both dates
                query = f"flights+to+{seg_arr_code}+from+{seg_dep_code}+on+{seg_date}+through+{return_date}+{seat_text}"
            elif direction == "return":
                # Not round trip, return leg: one-way on return date
                query = f"flights+to+{seg_arr_code}+from+{seg_dep_code}+on+{seg_date}+{seat_text}"
            else:
                # Not round trip, outbound leg: one-way on departure date
                query = f"flights+to+{seg_arr_code}+from+{seg_dep_code}+on+{seg_date}+{seat_text}"

            booking_url = (
                f"https://www.google.com/travel/flights/search?q={query}&hl=en&curr=HKD"
            )

            flights.append(
                {
                    "direction": direction,
                    "airline": f.get("airline"),
                    "flight_number": f.get("flight_number", ""),
                    "departure_airport": seg_dep_code,
                    "departure_airport_name": dep.get("name", ""),
                    "arrival_airport": seg_arr_code,
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
            departure_tokens.append(departure_token)
    return flights, departure_tokens


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
