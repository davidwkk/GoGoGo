"""Loguru structured logging callbacks for agent tool calls and finish events."""

from __future__ import annotations

from loguru import logger


def log_tool_call(tool_name: str, args: dict) -> None:
    """Called when the agent makes a tool call."""
    logger.bind(
        event="tool_call",
        tool=tool_name,
        tool_args=args,
    ).info("Agent tool call")


def log_tool_response(tool_name: str, result: dict) -> None:
    """Called after a tool returns a response."""
    if "error" in result:
        logger.bind(
            event="tool_response",
            tool=tool_name,
            error=result["error"],
        ).warning("Agent tool error")
    else:
        # Truncate long results for logging
        preview = str(result)[:500]
        logger.bind(
            event="tool_response",
            tool=tool_name,
            result_preview=preview,
        ).info("Agent tool response")


def log_agent_finish(response_preview: str, token_usage: dict | None = None) -> None:
    """Called when the agent loop finishes with a final response."""
    logger.bind(
        event="agent_finish",
        response_preview=response_preview[:500],
        token_usage=token_usage,
    ).info("Agent finished")
