"""Tool registry for Gemini agent.

Gemini SDK accepts raw Python callables as tools — no manual
FunctionDeclaration needed. The SDK infers the schema from the
function signature and docstring.
"""
from __future__ import annotations

from app.agent.tools import attractions, flights, hotels, maps, search, transport, weather

# Raw callables — SDK handles schema inference
get_attraction = attractions.get_attraction
get_weather = weather.get_weather
search_web = search.search_web
search_flights = flights.search_flights
search_hotels = hotels.search_hotels
get_transport = transport.get_transport
build_embed_url = maps.build_embed_url
build_static_url = maps.build_static_url

# All tools as a list for passing to GenerateContentConfig(tools=[...])
ALL_TOOLS = [
    get_attraction,
    get_weather,
    search_web,
    search_flights,
    search_hotels,
    get_transport,
    build_embed_url,
]

__all__ = [
    "get_attraction",
    "get_weather",
    "search_web",
    "search_flights",
    "search_hotels",
    "get_transport",
    "build_embed_url",
    "build_static_url",
    "ALL_TOOLS",
]
