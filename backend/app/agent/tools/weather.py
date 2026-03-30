"""OpenWeatherMap — current weather for a city.

API: GET https://api.openweathermap.org/data/2.5/weather
Params: q={city}, appid={API_KEY}, units=metric

Returns:
    {
        "city": "...",
        "temperature": "22°C",
        "condition": "Clear",
        "humidity": "65%",
        "icon": "01d"
    }
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings


async def get_weather(city: str) -> dict:
    """Fetch current weather for a city from OpenWeatherMap."""
    if not settings.OPENWEATHER_API_KEY:
        return {"error": "OPENWEATHER_API_KEY not configured", "city": city}

    logger.info(f"[weather] Fetching weather for: {city}")

    params = {
        "q": city,
        "appid": settings.OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params=params,
            )
            if response.status_code == 401:
                logger.warning("[weather] Invalid OpenWeatherMap API key")
                return {"error": "Invalid OpenWeatherMap API key", "city": city}
            if response.status_code == 404:
                logger.warning(f"[weather] City not found: {city}")
                return {"error": f"City not found: {city}", "city": city}
            response.raise_for_status()
            data = response.json()

            weather_list = data.get("weather") or []
            weather = weather_list[0] if weather_list else {}
            main = data.get("main", {})

            result = {
                "city": data.get("name", city),
                "temperature": f"{main.get('temp', '?')}°C",
                "condition": weather.get("main", "Unknown"),
                "humidity": f"{main.get('humidity', '?')}%",
                "icon": weather.get("icon", ""),
            }
            logger.info(
                f"[weather] {city}: {result.get('temperature')}, {result.get('condition')}"
            )
            return result
    except httpx.TimeoutException:
        logger.warning(f"[weather] Timeout for: {city}")
        return {"error": f"Timeout fetching weather for: {city}", "city": city}
    except httpx.HTTPStatusError as e:
        logger.warning(f"[weather] HTTP error: {e}")
        return {"error": f"HTTP error fetching weather: {e}", "city": city}
    except Exception as e:
        logger.warning(f"[weather] Failed: {e}")
        return {"error": f"Failed to fetch weather: {e}", "city": city}
