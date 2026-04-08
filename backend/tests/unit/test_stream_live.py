"""Test chat streaming endpoint against running backend."""

import json

import httpx


def test_stream_endpoint_returns_sse():
    """Test that /api/v1/chat/stream returns SSE with real LLM."""
    with httpx.stream(
        "POST",
        "http://localhost:8000/api/v1/chat/stream",
        json={"message": "Hello", "session_id": None},
        timeout=60,
        headers={"accept": "text/event-stream"},
    ) as response:
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = []
        chunks_received = False
        done_received = False

        for line in response.iter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip():
                    event = json.loads(data_str)
                    events.append(event)
                    if "chunk" in event:
                        chunks_received = True
                    if "done" in event:
                        done_received = True

        assert len(events) > 0, "Should receive at least one SSE event"
        assert chunks_received, f"Should receive text chunks. Events: {events}"
        assert done_received, f"Should receive done signal. Events: {events}"

        chunk_texts = [e["chunk"] for e in events if "chunk" in e]
        full_text = "".join(chunk_texts)
        assert len(full_text) > 0, "Should have non-empty text chunks"
