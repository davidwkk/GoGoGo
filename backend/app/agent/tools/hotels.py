"""SerpAPI Google Hotels — search for hotels.

API: GET https://serpapi.com/search.json
Params: engine=google_hotels, q=Bali, check_in_date=2026-03-31,
        check_out_date=2026-04-01, adults=2, currency=HKD, gl=us, hl=en

--- SerpAPI Google Hotels Full Response Schema ---
{
    "properties": [
        {
            "type": "hotel",
            "name": "The Ritz-Carlton, Bali",
            "description": "Zen-like quarters...",
            "link": "https://www.ritzcarlton.com/...",
            "logo": "https://www.gstatic.com/travel-hotels/branding/...",
            "sponsored": true,
            "eco_certified": true,
            "gps_coordinates": {"latitude": -8.830..., "longitude": 115.215...},
            "check_in_time": "3:00 PM",
            "check_out_time": "12:00 PM",
            "rate_per_night": {
                "lowest": "$347",
                "extracted_lowest": 347,
                "before_taxes_fees": "$287",
                "extracted_before_taxes_fees": 287,
            },
            "total_rate": {
                "lowest": "$1,733",
                "extracted_lowest": 1733,
                "before_taxes_fees": "$1,434",
                "extracted_before_taxes_fees": 1434,
            },
            "deal": "27% less than usual",
            "deal_description": "Great Deal",
            "prices": [
                {
                    "source": "The Ritz-Carlton, Bali",
                    "logo": "...",
                    "rate_per_night": {...},
                }
            ],
            "nearby_places": [
                {
                    "name": "I Gusti Ngurah Rai International Airport",
                    "transportations": [
                        {"type": "Taxi", "duration": "29 min"}
                    ]
                }
            ],
            "hotel_class": "5-star hotel",       # string, e.g. "5-star hotel"
            "extracted_hotel_class": 5,           # integer 1-5
            "images": [
                {
                    "thumbnail": "https://lh3.googleusercontent.com/...",
                    "original_image": "https://d2hyz2bfif3cr8.cloudfront.net/...",
                }
            ],
            "overall_rating": 4.6,               # float
            "reviews": 3614,                      # int
            "location_rating": 2.8,              # float
            "ratings": [                          # star breakdown
                {"stars": 5, "count": 1613},
                {"stars": 4, "count": 350},
                ...
            ],
            "reviews_breakdown": [
                {
                    "name": "Property",
                    "description": "Property",
                    "total_mentioned": 605,
                    "positive": 534,
                    "negative": 44,
                    "neutral": 27,
                    "category_token": "...",
                    "serpapi_link": "https://serpapi.com/...",
                }
            ],
            "amenities": ["Free Wi-Fi", "Free parking", "Pools", "Spa", ...],
            "excluded_amenities": ["No air conditioning", ...],
            "health_and_safety": {
                "groups": [
                    {
                        "title": "Physical distancing",
                        "list": [{"title": "Contactless check-in", "available": true}, ...],
                    }
                ],
                "details_link": "https://serpapi.com/...",
            },
            "essential_info": ["Entire villa", "Sleeps 4", "9 bedrooms", ...],
            "property_token": "ChcIyo2FjdjsrkZ8xGgsvZy8xdGYyMTV2aBAB",
            "serpapi_property_details_link": "https://serpapi.com/search.json?...",
            "serpapi_google_hotels_reviews_link": "https://serpapi.com/search.json?...",
            "serpapi_google_hotels_photos_link": "https://serpapi.com/search.json?...",
        }
    ],
    "non_matching_properties": [...],   # same schema as properties
}

--- Our Normalized Output Schema ---
{
    "hotels": [
        {
            "name": str,                           # e.g. "The Ritz-Carlton, Bali"
            "location": str,                        # search destination (set to caller destination)
            "check_in_time": str | None,           # e.g. "3:00 PM"
            "check_out_time": str | None,          # e.g. "12:00 PM"
            "check_in_date": str | None,            # from request param (not in response)
            "check_out_date": str | None,          # from request param (not in response)
            "price_per_night_min_hkd": float | None,  # rate_per_night.extracted_lowest
            "price_per_night_max_hkd": float | None,  # same (range not available in this schema)
            "total_price_hkd": float | None,       # total_rate.extracted_lowest
            "hotel_class": str | None,            # e.g. "5-star hotel"
            "hotel_class_int": int | None,        # e.g. 5
            "rating": float | None,               # overall_rating
            "reviews": int | None,                 # total review count
            "location_rating": float | None,      # location_rating
            "amenities": list[str],                # top amenities
            "description": str,                   # property description
            "image_url": str | None,             # first original image URL
            "thumbnail_url": str | None,          # first thumbnail URL
            "embed_map_url": str | None,           # Google Maps embed URL from GPS
            "nearby_places": [                    # nearby landmarks / transport
                {
                    "name": str,
                    "transportations": [
                        {"type": str, "duration": str},
                        ...
                    ]
                },
                ...
            ],
            "booking_url": str | None,            # Google Hotels booking link from property_token
            "eco_certified": bool | None,         # eco_certified flag
            "deal": str | None,                 # e.g. "27% less than usual"
            "deal_description": str | None,     # e.g. "Great Deal"
        }
    ]
}
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings


async def search_hotels(
    destination: str,
    check_in: str,
    check_out: str | None = None,
    adults: int = 2,
) -> dict:
    """Search for hotels using SerpAPI Google Hotels."""
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="search_hotels",
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        currency="HKD",
    ).debug(
        f"TOOL: search_hotels start — destination={destination} | "
        f"check_in={check_in} check_out={check_out} adults={adults}"
    )

    if not settings.SERPAPI_KEY:
        logger.bind(
            event="tool_no_api_key",
            layer="tool",
            tool="search_hotels",
        ).warning("TOOL: SERPAPI_KEY not configured")
        return {"error": "SERPAPI_KEY not configured", "hotels": []}

    params = {
        "q": destination,
        "api_key": settings.SERPAPI_KEY,
        "engine": "google_hotels",
        "currency": "HKD",
        "hl": "en",
        "adults": adults,
    }
    if check_in:
        params["check_in_date"] = check_in
    if check_out:
        params["check_out_date"] = check_out

    logger.bind(
        event="tool_api_call",
        layer="tool",
        tool="search_hotels",
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        engine="google_hotels",
    ).debug(
        f"TOOL: Calling SerpAPI for hotels — destination={destination} | "
        f"check_in={check_in} check_out={check_out} adults={adults} | engine=google_hotels"
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
                    tool="search_hotels",
                    status_code=401,
                ).error("TOOL: Invalid SerpAPI key")
                return {"error": "Invalid SerpAPI key", "hotels": []}
            if response.status_code == 404:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_hotels",
                    status_code=404,
                ).error("TOOL: Hotels endpoint not found")
                return {"error": "SerpAPI hotels endpoint not found", "hotels": []}
            if response.status_code == 429:
                logger.bind(
                    event="tool_rate_limit",
                    layer="tool",
                    tool="search_hotels",
                    status_code=429,
                ).error("TOOL: SerpAPI rate limit exceeded")
                return {"error": "SerpAPI rate limit exceeded", "hotels": []}
            response.raise_for_status()
            data = response.json()

        hotels = []
        # Only use non_matching_properties as fallback when main properties is empty
        properties = data.get("properties", [])
        if not properties:
            properties = data.get("non_matching_properties", [])
            logger.bind(
                event="tool_fallback",
                layer="tool",
                tool="search_hotels",
            ).warning(
                "TOOL: No matching properties; falling back to non_matching_properties"
            )

        for h in properties[:1]:
            # Price — round to nearest 100 (floor for min, ceil for max)
            rate_per_night = h.get("rate_per_night") or {}
            raw_price = rate_per_night.get("extracted_lowest")
            if raw_price is not None:
                price_min_hkd = int(raw_price // 100 * 100)
                price_max_hkd = int((raw_price + 99) // 100 * 100)
            else:
                price_min_hkd = None
                price_max_hkd = None

            # Total price for the stay (already in HKD)
            total_rate = h.get("total_rate") or {}
            total_price_hkd = total_rate.get("extracted_lowest")

            # Build embed map URL — use hotel name search (no API key required for embed)
            embed_map_url: str | None = None
            hotel_name = h.get("name", "")
            if hotel_name:
                encoded_name = hotel_name.replace(" ", "+")
                embed_map_url = (
                    f"https://www.google.com/maps?q={encoded_name}&output=embed"
                )

            # Build booking URL from property_token (Chk/I/Cgo prefix → Google Hotels entity)
            # Include check-in, check-out, adults for direct booking page
            booking_url: str | None = None
            property_token = h.get("property_token")
            if property_token:
                booking_url = (
                    f"https://www.google.com/travel/hotels/entity/{property_token}"
                    f"?check_in={check_in}&check_out={check_out}&adults={adults}&hl=en&curr=HKD"
                )

            # First image
            images = h.get("images") or []
            first_image = images[0] if images else {}
            thumbnail_url = first_image.get("thumbnail")
            image_url = first_image.get("original_image")

            # Nearby places — first 3 for brevity
            nearby = []
            for place in (h.get("nearby_places") or [])[:3]:
                transports = [
                    {"type": t.get("type"), "duration": t.get("duration")}
                    for t in (place.get("transportations") or [])
                ]
                nearby.append(
                    {"name": place.get("name"), "transportations": transports}
                )

            hotels.append(
                {
                    "name": h.get("name", "Unknown Hotel"),
                    "location": destination,
                    "check_in_time": h.get("check_in_time"),
                    "check_out_time": h.get("check_out_time"),
                    "check_in_date": check_in,
                    "check_out_date": check_out,
                    "price_per_night_min_hkd": price_min_hkd,
                    "price_per_night_max_hkd": price_max_hkd,
                    "total_price_hkd": total_price_hkd,
                    "hotel_class": h.get("hotel_class"),  # e.g. "5-star hotel"
                    "hotel_class_int": h.get("extracted_hotel_class"),  # e.g. 5
                    "rating": h.get("overall_rating"),
                    "reviews": h.get("reviews"),
                    "location_rating": h.get("location_rating"),
                    "amenities": (h.get("amenities") or [])[:3],  # top 3 for display
                    "description": h.get("description", ""),
                    "image_url": image_url,
                    "thumbnail_url": thumbnail_url,
                    "embed_map_url": embed_map_url,
                    "nearby_places": nearby,
                    "booking_url": booking_url,
                }
            )

        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_hotels",
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            hotel_count=len(hotels),
        ).debug(
            f"TOOL: search_hotels done — found {len(hotels)} hotels for {destination} | "
            f"check_in={check_in} check_out={check_out}"
        )
        return {"hotels": hotels}
    except httpx.TimeoutException:
        logger.bind(
            event="tool_timeout",
            layer="tool",
            tool="search_hotels",
            destination=destination,
        ).error(f"TOOL: Timeout searching hotels for: {destination}")
        return {"error": f"Timeout searching hotels for: {destination}", "hotels": []}
    except httpx.HTTPStatusError as e:
        logger.bind(
            event="tool_http_error",
            layer="tool",
            tool="search_hotels",
            status_code=e.response.status_code,
        ).error(f"TOOL: HTTP error searching hotels: {e}")
        return {"error": f"HTTP error searching hotels: {e}", "hotels": []}
    except Exception as e:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="search_hotels",
            error=str(e),
        ).error(f"TOOL: Hotel search failed: {e}")
        return {"error": f"Hotel search failed: {e}", "hotels": []}
