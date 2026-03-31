"""Loguru structured logging callbacks for agent tool calls and finish events."""

from __future__ import annotations

from loguru import logger


def _summarize_tool_result(tool_name: str, result: dict) -> dict:
    """Extract useful summary info from tool results for logging."""
    summary: dict = {"result_count": 0, "has_error": "error" in result}

    if "error" in result:
        summary["error"] = result["error"]
        return summary

    if "flights" in result:
        flights = result.get("flights", [])
        summary["result_count"] = len(flights)
        summary["items"] = [
            {"airline": f.get("airline"), "price": f.get("price")} for f in flights[:3]
        ]
    elif "hotels" in result:
        hotels = result.get("hotels", [])
        summary["result_count"] = len(hotels)
        summary["items"] = [
            {"name": h.get("name"), "price": h.get("price_per_night")}
            for h in hotels[:3]
        ]
    elif "weather" in result:
        summary["weather"] = result.get("weather")
    elif "options" in result:
        options = result.get("options", [])
        summary["result_count"] = len(options)
        summary["items"] = [
            {
                "type": o.get("type"),
                "duration": o.get("duration"),
                "cost": o.get("cost"),
            }
            for o in options[:3]
        ]
    elif "results" in result:
        results = result.get("results", [])
        summary["result_count"] = len(results)
        summary["items"] = [
            {"title": r.get("title", "")[:50], "url": r.get("url", "")}
            for r in results[:3]
        ]
    elif "attractions" in result:
        attractions = result.get("attractions", [])
        summary["result_count"] = len(attractions)
        summary["items"] = [
            {"name": a.get("name"), "category": a.get("category")}
            for a in attractions[:3]
        ]
    elif isinstance(result, dict) and not result:
        summary["empty"] = True

    return summary


def log_tool_call(
    tool_name: str,
    args: dict,
    trace_id: str | None = None,
    service: str = "agent",
    model: str | None = None,
) -> None:
    """Called when the agent makes a tool call."""
    # Build readable args string
    args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
    logger.bind(
        event="tool_call",
        service=service,
        trace_id=trace_id,
        model=model,
        tool=tool_name,
        tool_args=args,
    ).info(f"[TOOL CALL] {tool_name}({args_str})")


def log_tool_response(
    tool_name: str,
    result: dict,
    duration_ms: float | None = None,
    trace_id: str | None = None,
    service: str = "agent",
    model: str | None = None,
) -> None:
    """Called after a tool returns a response."""
    if "error" in result:
        # Extract error details - error dict may contain context beyond the message
        error_msg = result["error"]
        error_details = {k: v for k, v in result.items() if k != "error"}
        logger.bind(
            event="tool_response",
            service=service,
            trace_id=trace_id,
            model=model,
            tool=tool_name,
            tool_error=error_msg,
            tool_error_details=error_details if error_details else None,
            tool_duration_ms=duration_ms,
        ).warning(f"Agent tool error: {error_msg}")
    else:
        # Extract meaningful summary from result
        summary = _summarize_tool_result(tool_name, result)
        logger.bind(
            event="tool_response",
            service=service,
            trace_id=trace_id,
            model=model,
            tool=tool_name,
            tool_result_summary=summary,
            tool_duration_ms=duration_ms,
        ).info(f"Agent tool response — {summary.get('result_count', 0)} results")


def log_agent_finish(
    response_preview: str,
    token_usage: dict | None = None,
    latency_ms: float | None = None,
    trace_id: str | None = None,
    service: str = "agent",
    model: str | None = None,
    agent_mode: str | None = None,
    iterations: int | None = None,
    max_iterations: int | None = None,
) -> None:
    """Called when the agent loop finishes with a final response."""
    logger.bind(
        event="agent_finish",
        service=service,
        trace_id=trace_id,
        model=model,
        agent_mode=agent_mode,
        iterations=iterations,
        max_iterations=max_iterations,
        response_preview=response_preview if response_preview else None,
        token_usage=token_usage,
        latency_ms=latency_ms,
    ).info("Agent finished")
