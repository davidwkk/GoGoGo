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
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="get_weather",
        city=city,
    ).info(f"TOOL: get_weather start — city={city}")

    if not settings.OPENWEATHER_API_KEY:
        logger.bind(
            event="tool_no_api_key",
            layer="tool",
            tool="get_weather",
        ).warning("TOOL: OPENWEATHER_API_KEY not configured")
        return {"error": "OPENWEATHER_API_KEY not configured", "city": city}

    params = {
        "q": city,
        "appid": settings.OPENWEATHER_API_KEY,
        "units": "metric",
    }

    logger.bind(
        event="tool_api_call",
        layer="tool",
        tool="get_weather",
        city=city,
    ).debug(f"TOOL: Calling OpenWeatherMap API for {city}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params=params,
            )
            if response.status_code == 401:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="get_weather",
                    status_code=401,
                ).warning("TOOL: Invalid OpenWeatherMap API key")
                return {"error": "Invalid OpenWeatherMap API key", "city": city}
            if response.status_code == 404:
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="get_weather",
                    status_code=404,
                    city=city,
                ).warning(f"TOOL: City not found: {city}")
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
            logger.bind(
                event="tool_done",
                layer="tool",
                tool="get_weather",
                city=city,
                temperature=result.get("temperature"),
                condition=result.get("condition"),
            ).info(
                f"TOOL: get_weather done — {city}: {result.get('temperature')}, {result.get('condition')}"
            )
            return result
    except httpx.TimeoutException:
        logger.bind(
            event="tool_timeout",
            layer="tool",
            tool="get_weather",
            city=city,
        ).warning(f"TOOL: Timeout fetching weather for: {city}")
        return {"error": f"Timeout fetching weather for: {city}", "city": city}
    except httpx.HTTPStatusError as e:
        logger.bind(
            event="tool_http_error",
            layer="tool",
            tool="get_weather",
            status_code=e.response.status_code,
        ).warning(f"TOOL: HTTP error fetching weather: {e}")
        return {"error": f"HTTP error fetching weather: {e}", "city": city}
    except Exception as e:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="get_weather",
            error=str(e),
        ).warning(f"TOOL: Failed to fetch weather: {e}")
        return {"error": f"Failed to fetch weather: {e}", "city": city}
