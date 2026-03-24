"""Chat service — David owns agent invocation only."""

from app.schemas.chat import TripItinerary


def invoke_agent(
    user_message: str,
    user_id: int,
    session_id: int | None = None,
) -> TripItinerary:
    """
    Invoke the Gemini agent with the user's message.

    Phase 1 (sync): Runs agent loop, returns structured TripItinerary.
    Phase 2 (SSE): Streams agent thinking + tool calls, then returns structured output.
    """
    # TODO: Integrate google-genai agent here
    # This is a placeholder that returns a mock response
    # Replace with real agent invocation:
    #   1. Build messages list with system prompt + conversation history
    #   2. Run agent loop via google-genai generate_content
    #   3. Call structured output endpoint → TripItinerary
    #   4. Return structured result
    return TripItinerary(
        destination="Tokyo, Japan",
        duration_days=5,
        summary="A 5-day trip to Tokyo exploring culture, food, and landmarks.",
        days=[],
        hotels=[],
        flights=[],
        weather_summary="Mild spring weather, 15-22°C",
        map_embed_url=None,
    )
