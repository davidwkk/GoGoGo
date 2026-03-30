"""Web search — Tavily primary, SerpAPI fallback.

Tavily API: POST https://api.tavily.com/search
SerpAPI fallback: GET https://serpapi.com/search.json?q={query}&api_key={SERPAPI_KEY}

Returns:
    {
        "results": [
            {"title": "...", "url": "...", "snippet": "..."},
            ...
        ]
    }
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings


async def search_web(query: str) -> dict:
    """Search the web using Tavily with SerpAPI fallback."""
    logger.info(f"[search] Query: {query}")

    if settings.TAVILY_API_KEY:
        result = await _search_tavily(query)
        if "error" not in result:
            logger.info(
                f"[search] Tavily returned {len(result.get('results', []))} results"
            )
            return result

    # Fallback to SerpAPI
    result = await _search_serpapi(query)
    if "error" not in result:
        logger.info(
            f"[search] SerpAPI returned {len(result.get('results', []))} results"
        )
    return result


async def _search_tavily(query: str) -> dict:
    """Primary search via Tavily AI."""
    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
    }
    headers = {
        "Authorization": f"Bearer {settings.TAVILY_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json=payload,
                headers=headers,
            )
            if response.status_code == 401:
                logger.warning("[search] Invalid Tavily API key")
                return {"error": "Invalid Tavily API key", "results": []}
            response.raise_for_status()
            data = response.json()

            return {
                "results": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": (r.get("raw_content") or r.get("content") or "")[
                            :300
                        ],
                    }
                    for r in data.get("results", [])
                ]
            }
    except httpx.TimeoutException:
        logger.warning(f"[search] Tavily timeout for: {query}")
        return {"error": f"Timeout during Tavily search for: {query}", "results": []}
    except httpx.HTTPStatusError as e:
        logger.warning(f"[search] Tavily HTTP error: {e}")
        return {"error": f"Tavily HTTP error: {e}", "results": []}
    except Exception as e:
        logger.warning(f"[search] Tavily failed: {e}")
        return {"error": f"Tavily search failed: {e}", "results": []}


async def _search_serpapi(query: str) -> dict:
    """Fallback search via SerpAPI."""
    if not settings.SERPAPI_KEY:
        logger.warning("[search] No search API key configured")
        return {
            "error": "No search API key configured (Tavily or SerpAPI)",
            "results": [],
        }

    params = {
        "q": query,
        "api_key": settings.SERPAPI_KEY,
        "num": 5,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://serpapi.com/search.json",
                params=params,
            )
            if response.status_code == 401:
                logger.warning("[search] Invalid SerpAPI key")
                return {"error": "Invalid SerpAPI key", "results": []}
            response.raise_for_status()
            data = response.json()

            results = []
            for r in data.get("organic_results", [])[:5]:
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("link", ""),
                        "snippet": r.get("snippet", "")[:300],
                    }
                )

            return {"results": results}
    except httpx.TimeoutException:
        logger.warning(f"[search] SerpAPI timeout for: {query}")
        return {"error": f"Timeout during SerpAPI search for: {query}", "results": []}
    except httpx.HTTPStatusError as e:
        logger.warning(f"[search] SerpAPI HTTP error: {e}")
        return {"error": f"SerpAPI HTTP error: {e}", "results": []}
    except Exception as e:
        logger.warning(f"[search] SerpAPI failed: {e}")
        return {"error": f"SerpAPI search failed: {e}", "results": []}
