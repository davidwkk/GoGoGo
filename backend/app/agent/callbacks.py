"""Loguru structured logging callbacks for agent tool calls and finish events."""

from __future__ import annotations

from loguru import logger


def log_tool_call(
    tool_name: str,
    args: dict,
    trace_id: str | None = None,
    service: str = "agent",
    model: str | None = None,
) -> None:
    """Called when the agent makes a tool call."""
    logger.bind(
        event="tool_call",
        service=service,
        trace_id=trace_id,
        model=model,
        tool=tool_name,
        tool_args=args,
    ).info("Agent tool call")


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
        logger.bind(
            event="tool_response",
            service=service,
            trace_id=trace_id,
            model=model,
            tool=tool_name,
            tool_error=result["error"],
            tool_duration_ms=duration_ms,
        ).warning("Agent tool error")
    else:
        # Truncate long results for logging
        preview = str(result)[:500]
        logger.bind(
            event="tool_response",
            service=service,
            trace_id=trace_id,
            model=model,
            tool=tool_name,
            tool_result_preview=preview,
            tool_duration_ms=duration_ms,
        ).info("Agent tool response")


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
        response_preview=response_preview[:500] if response_preview else None,
        token_usage=token_usage,
        latency_ms=latency_ms,
    ).info("Agent finished")
