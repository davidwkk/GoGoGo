"""Tool registry for Gemini agent.

Gemini SDK accepts raw Python callables as tools — no manual
FunctionDeclaration needed. The SDK infers the schema from the
function signature and docstring.

All tool functions are async internally, but the SDK requires sync
callables when passed to GenerateContentConfig(tools=[...]).
We wrap them with asyncio.run() so they appear sync to the SDK.
"""

from __future__ import annotations

import asyncio
from functools import wraps

from app.agent.tools import (
    attractions,
    flights,
    hotels,
    maps,
    search,
    transport,
    weather,
)


def _make_sync(fn):
    """Wrap an async function so it appears sync to the Gemini SDK."""
    @wraps(fn)  # preserves __name__ so SDK sees unique declarations
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


# Sync wrappers for the SDK
get_attraction = _make_sync(attractions.get_attraction)
get_weather = _make_sync(weather.get_weather)
search_web = _make_sync(search.search_web)
search_flights = _make_sync(flights.search_flights)
search_hotels = _make_sync(hotels.search_hotels)
get_transport = _make_sync(transport.get_transport)
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
