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

from app.core.config import settings


async def get_weather(city: str) -> dict:
    """Fetch current weather for a city from OpenWeatherMap."""
    if not settings.OPENWEATHER_API_KEY:
        return {"error": "OPENWEATHER_API_KEY not configured", "city": city}

    params = {
        "q": city,
        "appid": settings.OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params=params,
            )
            if response.status_code == 401:
                return {"error": "Invalid OpenWeatherMap API key", "city": city}
            if response.status_code == 404:
                return {"error": f"City not found: {city}", "city": city}
            response.raise_for_status()
            data = response.json()

            weather = data.get("weather", [{}])[0]
            main = data.get("main", {})

            return {
                "city": data.get("name", city),
                "temperature": f"{main.get('temp', '?')}°C",
                "condition": weather.get("main", "Unknown"),
                "humidity": f"{main.get('humidity', '?')}%",
                "icon": weather.get("icon", ""),
            }
    except httpx.TimeoutException:
        return {"error": f"Timeout fetching weather for: {city}", "city": city}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error fetching weather: {e}", "city": city}
    except Exception as e:
        return {"error": f"Failed to fetch weather: {e}", "city": city}
