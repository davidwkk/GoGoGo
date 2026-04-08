"""Web search — Tavily primary, SerpAPI fallback.

Tavily API: POST https://api.tavily.com/search
SerpAPI fallback: GET https://serpapi.com/search.json?q={query}&api_key={SERPAPI_KEY}

--- Tavily Full Response Schema ---
{
    "query": str,                          # original search query
    "answer": str | None,                  # AI-generated answer (when include_answer=True)
    "results": [
        {
            "title": str,                  # page title
            "url": str,                    # website URL
            "content": str,                # short content snippet
            "score": float | None,         # relevance score (0.0 - 1.0)
            "raw_content": str | None,     # full raw content (when include_raw_content=True)
            "images": list[str] | None,    # image URLs
            "favicon": str | None,         # favicon URL
        },
        ...
    ],
    "images": list[str] | None,             # aggregated image URLs
    "usage": {"credits_used": int},         # API credits consumed
}

--- SerpAPI Full Response Schema (organic_results) ---
{
    "search_metadata": {...},
    "search_parameters": {...},
    "search_information": {...},
    "organic_results": [
        {
            "position": int,                         # result position in the list
            "title": str,                             # page title
            "link": str | None,                       # website URL (may be absent; use displayed_link)
            "redirect_link": str | None,              # full Google redirect URL
            "displayed_link": str,                    # human-readable displayed URL
            "thumbnail": str | None,                 # result thumbnail image
            "favicon": str | None,                    # favicon URL
            "snippet": str,                            # content snippet
            "snippet_highlighted_words": list[str],   # words highlighted in snippet
            "date": str | None,                       # date published (when available)
            "author": str | None,                     # author (for articles)
            "cited_by": int | None,                   # citation count
            "extracted_cited_by": str | None,
            "cached_page_link": str | None,
            "about_page_link": str | None,
            "about_page_serpapi_link": str | None,
            "related_pages_link": str | None,
            "about_this_result": {
                "source": {
                    "description": str | None,
                    "source_info_link": str | None,
                    "security": str,               # e.g., "secure"
                    "icon": str | None,
                }
            } | None,
            "source": str | None,                    # data source name (e.g., "Wikipedia")
            "sitelinks": {
                "inline": [
                    {"title": str, "link": str},
                    ...
                ],
                "expanded": [
                    {"title": str, "link": str},
                    ...
                ]
            } | None,
            "rich_snippet": {
                "top": {
                    "detected_extensions": {
                        "rating": float | None,      # e.g., 4 (stars)
                        "reviews": int | None,       # e.g., 2251
                        "price_range": str | None,   # e.g., "$$"
                    },
                    "extensions": list[str] | None,
                } | None,
                "bottom": {...} | None,
            } | None,
            "rich_snippet_table": {...} | None,
            "extensions": list[str] | None,
            "reviews": int | None,                    # review count
            "ratings": float | None,                 # star rating
            "answers": str | None,                   # direct answer
            "related_questions": [...],
            "carousel": [...],
        },
        ...
    ],
    "images": [...],
    "knowledge_graph": {...} | None,
    "top_stories": [...],
    "shopping_results": [...],
    "local_results": {...} | None,
    "recipes_results": [...] | None,
}

# Notes:
# - Minimum 3 results always returned. Total = 3 + start (if start parameter is used).
# - The "link" field may be absent; prefer "displayed_link" for display purposes.
# - rich_snippet.top.detected_extensions commonly contains rating, reviews, price_range.

--- Our Normalized Output Schema ---
{
    "results": [
        {
            "title": str,                  # page title
            "url": str,                    # website URL
            "snippet": str,                # content snippet (max 300 chars)
            "score": float | None,         # relevance score (Tavily only; None for SerpAPI)
        },
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
    logger.bind(
        event="tool_start",
        layer="tool",
        tool="search_web",
        query=query,
    ).info("TOOL: search_web start")

    if settings.TAVILY_API_KEY:
        result = await _search_tavily(query)
        if "error" not in result:
            result_count = len(result.get("results", []))
            logger.bind(
                event="tool_done",
                layer="tool",
                tool="search_web",
                provider="tavily",
                result_count=result_count,
            ).info(f"TOOL: search_web done — Tavily returned {result_count} results")
            return result

    # Fallback to SerpAPI
    result = await _search_serpapi(query)
    if "error" not in result:
        result_count = len(result.get("results", []))
        logger.bind(
            event="tool_done",
            layer="tool",
            tool="search_web",
            provider="serpapi",
            result_count=result_count,
        ).info(f"TOOL: search_web done — SerpAPI returned {result_count} results")
    else:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="search_web",
            error=result.get("error"),
        ).error(f"TOOL: search_web failed — {result.get('error')}")
    return result


async def _search_tavily(query: str) -> dict:
    """Primary search via Tavily AI."""
    logger.bind(
        event="tool_api_call",
        layer="tool",
        tool="search_web",
        provider="tavily",
        query=query,
    ).debug("TOOL: Calling Tavily API")

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
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_web",
                    provider="tavily",
                    status_code=401,
                ).error("TOOL: Invalid Tavily API key")
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
                        "score": r.get("score"),
                    }
                    for r in data.get("results", [])
                ]
            }
    except httpx.TimeoutException:
        logger.bind(
            event="tool_timeout",
            layer="tool",
            tool="search_web",
            provider="tavily",
            query=query,
        ).error(f"TOOL: Tavily timeout for query: {query}")
        return {"error": f"Timeout during Tavily search for: {query}", "results": []}
    except httpx.HTTPStatusError as e:
        logger.bind(
            event="tool_http_error",
            layer="tool",
            tool="search_web",
            provider="tavily",
            status_code=e.response.status_code,
        ).error(f"TOOL: Tavily HTTP error: {e}")
        return {"error": f"Tavily HTTP error: {e}", "results": []}
    except Exception as e:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="search_web",
            provider="tavily",
            error=str(e),
        ).error(f"TOOL: Tavily failed: {e}")
        return {"error": f"Tavily search failed: {e}", "results": []}


async def _search_serpapi(query: str) -> dict:
    """Fallback search via SerpAPI."""
    logger.bind(
        event="tool_api_call",
        layer="tool",
        tool="search_web",
        provider="serpapi",
        query=query,
    ).debug("TOOL: Calling SerpAPI")

    if not settings.SERPAPI_KEY:
        logger.bind(
            event="tool_no_api_key",
            layer="tool",
            tool="search_web",
            provider="serpapi",
        ).error("TOOL: No search API key configured (Tavily or SerpAPI)")
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
                logger.bind(
                    event="tool_api_error",
                    layer="tool",
                    tool="search_web",
                    provider="serpapi",
                    status_code=401,
                ).error("TOOL: Invalid SerpAPI key")
                return {"error": "Invalid SerpAPI key", "results": []}
            response.raise_for_status()
            data = response.json()

            results = []
            for r in data.get("organic_results", [])[:5]:
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("link") or r.get("displayed_link", ""),
                        "snippet": r.get("snippet", "")[:300],
                    }
                )

            return {"results": results}
    except httpx.TimeoutException:
        logger.bind(
            event="tool_timeout",
            layer="tool",
            tool="search_web",
            provider="serpapi",
            query=query,
        ).error(f"TOOL: SerpAPI timeout for query: {query}")
        return {"error": f"Timeout during SerpAPI search for: {query}", "results": []}
    except httpx.HTTPStatusError as e:
        logger.bind(
            event="tool_http_error",
            layer="tool",
            tool="search_web",
            provider="serpapi",
            status_code=e.response.status_code,
        ).error(f"TOOL: SerpAPI HTTP error: {e}")
        return {"error": f"SerpAPI HTTP error: {e}", "results": []}
    except Exception as e:
        logger.bind(
            event="tool_error",
            layer="tool",
            tool="search_web",
            provider="serpapi",
            error=str(e),
        ).error(f"TOOL: SerpAPI failed: {e}")
        return {"error": f"SerpAPI search failed: {e}", "results": []}
