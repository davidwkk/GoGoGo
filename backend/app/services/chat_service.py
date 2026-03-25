"""Chat service — David owns agent invocation only."""

from app.schemas.chat import ChatResponse, TripItinerary


async def invoke_agent(
    user_message: str,
    user_id: int,
    session_id: int | None = None,
    generate_plan: bool = False,
) -> ChatResponse:
    """
    Invoke the Gemini agent with the user's message.

    Phase 1 (sync): If generate_plan=False, simple generate_content (no tools, no structured output).
                    If generate_plan=True, runs full agent loop + structured TripItinerary.
    Phase 2 (SSE): Streams agent thinking + tool calls, then returns structured output.
    """
    # TODO: Integrate google-genai agent here
    # This is a placeholder that returns a mock response
    #
    # Two-phase pattern when implementing:
    #   Phase 1: Tool-calling loop (NO response_schema) — gather data via tools
    #   Phase 2: Separate generate_content call WITH response_json_schema → TripItinerary
    #
    # Demo-grade timeout: acceptable for low-concurrency demo use
    # try:
    #     result = await asyncio.wait_for(run_agent_loop(...), timeout=25.0)
    # except asyncio.TimeoutError:
    #     return ChatResponse(session_id="", text="Request timed out.", itinerary=None, message_type="error")
    #
    # Simple dict cache for transport (no lru_cache on async):
    # _transport_cache: dict[tuple, dict] = {}
    # key = (from_loc, to_loc, mode)
    # if key not in _transport_cache:
    #     _transport_cache[key] = await _fetch_from_serpapi(...)
    # return _transport_cache[key]

    mock_itinerary = TripItinerary(
        destination="Tokyo, Japan",
        duration_days=5,
        summary="A 5-day trip to Tokyo exploring culture, food, and landmarks.",
        days=[],
        hotels=[],
        flights=[],
        weather_summary="Mild spring weather, 15-22°C",
    )

    if generate_plan:
        return ChatResponse(
            session_id=str(session_id) if session_id else "",
            text="",
            itinerary=mock_itinerary,
            message_type="itinerary",
        )
    return ChatResponse(
        session_id=str(session_id) if session_id else "",
        text="Hello! How can I help you plan your trip?",
        itinerary=None,
        message_type="chat",
    )
