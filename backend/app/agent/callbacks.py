"""Loguru logging callbacks for agent tool calls and finish events."""

from __future__ import annotations

from loguru import logger


def log_tool_call(tool_name: str, args: dict) -> None:
    """Called when the agent makes a tool call."""
    logger.info(f"[AGENT] Tool call: {tool_name} | args={args}")


def log_tool_response(tool_name: str, result: dict) -> None:
    """Called after a tool returns a response."""
    if "error" in result:
        logger.warning(f"[AGENT] Tool error: {tool_name} | {result['error']}")
    else:
        # Truncate long results for logging
        preview = str(result)[:200]
        logger.info(f"[AGENT] Tool response: {tool_name} | {preview}...")


def log_agent_finish(response_preview: str) -> None:
    """Called when the agent loop finishes with a final response."""
    logger.info(f"[AGENT] Finished | response={response_preview[:300]}...")
