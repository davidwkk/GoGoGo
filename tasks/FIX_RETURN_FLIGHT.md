# Plan: Fix Return Flight — Limit to 1 Return Flight

## Context

In `_search_round_trip` (`flights.py:206-256`), the current implementation:

1. Makes 2 API calls: one for outbound, one for return (reversed airports, `type=2`)
2. Returns up to `_MAX_FLIGHTS_PER_LEG` (10) flights for **each** leg
3. Does NOT use the `departure_token` from the outbound response

The task requires fetching **just 1 return flight** (not 10).

> **Note**: The comments in the code explain why `departure_token`-based return booking was not used — tokens were either all identical for the route, or returned HTTP 400. The reversed-airport approach is more reliable. The plan below keeps the reversed-airport return leg approach but limits to exactly 1 return flight result.

## Changes

MUST USE departure_token to fetch the return flight for the round-trip flight fetched in the first API call!!!

This optional parameter is used to select the flight and get returning flights (for Round trip) or flights for the next leg of itinerary (for Multi-city). Find this token in the departure flight results.

It cannot be used together with booking_token.

### `backend/app/agent/tools/flights.py`

**Line 231-232** — change return flights limit from 10 to 1:

```python
# Before:
return_flights = return_result.get("flights", [])[:_MAX_FLIGHTS_PER_LEG]

# After:
return_flights = return_result.get("flights", [])[:1]
```

This means for round-trips:

- Outbound: up to 10 flights (unchanged)
- Return: **1 flight only** (changed)

**Line 101** — reduce the cap since we only need 1 return flight:

```python
# Before:
_MAX_FLIGHTS_PER_LEG = 10

# After:
_MAX_FLIGHTS_PER_LEG = 3
```

## Verification

1. Run existing tests: `docker-compose exec backend pytest`
2. Manually trigger a round-trip flight search and verify only 1 return flight is returned
