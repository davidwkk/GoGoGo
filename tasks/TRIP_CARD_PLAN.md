# TRIP_CARD Implementation Plan

## Context

The TRIP_CARD.md specifies 9 fixes for trip card components (Flight, Hotel, Attraction). The fixes involve: adding missing fields to TypeScript interfaces, updating frontend components to display new data, and modifying backend prompts to prevent hallucination and improve data quality.

**Priority Order:** Fix 3,4,5,6,7 first (enrichment), then 8,1,2 (structural/price fixes)

---

## Fix 3: Flight Card - Add duration_minutes, airplane, travel_class

### Files to Modify

1. **`frontend/src/types/trip.ts`** - Add `airplane` and `travel_class` fields to `Flight` interface
2. **`frontend/src/components/trip/FlightCard.tsx`** - Display formatted duration, airplane, travel_class

### Changes

- Add `airplane?: string | null` to Flight interface
- Add `travel_class?: string | null` to Flight interface (maps from tool's `travel_class`)
- In FlightCard.tsx:
  - Add a utility function to format `duration_minutes` → "3hrs 20mins"
  - Display airplane model (e.g., "Boeing 787")
  - Display travel class (e.g., "Economy")

---

## Fix 4: Hotel Card - Add hotel_class_int, rating, reviews, location_rating, amenities, description

### Files to Modify

1. **`frontend/src/types/trip.ts`** - Add missing fields to `Hotel` interface
2. **`frontend/src/components/trip/HotelCard.tsx`** - Display new fields with expandable amenities

### Changes

- Add `hotel_class_int?: number | null` to Hotel interface
- Add `reviews?: number | null` to Hotel interface
- Add `location_rating?: number | null` to Hotel interface
- Add `amenities?: string[] | null` to Hotel interface
- Add `description?: string | null` to Hotel interface
- In HotelCard.tsx:
  - Display star class (e.g., "5-star hotel" or just 5 stars)
  - Display rating and review count
  - Display location_rating
  - Display description
  - Make amenities expandable/collapsible list
  - Keep image loading from `image_url` (already tries image_url first)

---

## Fix 5: Attraction Card - Add collapsible description, wiki link, embed map

### Files to Modify

1. **`frontend/src/types/trip.ts`** - Add `wiki_url` to `Activity` interface
2. **`frontend/src/components/trip/AttractionCard.tsx`** - Add collapsible description, wiki link, map embed

### Changes

- Add `wiki_url?: string | null` to Activity interface
- In AttractionCard.tsx:
  - Make description collapsible (click to expand/collapse)
  - Add "Wiki" link button if wiki_url exists
  - Add "Map" button that shows embedded map when clicked (using map_url)

---

## Fix 6: Prompt - Prevent hallucination of prices

### Files to Modify

1. **`backend/app/services/streaming_service.py`** - Update `_build_system_instruction()`

### Changes

In the "Rules" section or create new "Price Hallucination Prevention" section:

- Add: "CRITICAL: Do NOT invent, estimate, or make up ANY prices, including admission_fee_hkd for attractions. Only include prices that appear in the tool results. If a price is not available, do not include it."
- Add: "Only use data explicitly provided in tool results. Do not add information not present in the fetched data."

---

## Fix 7: Prompt - Improve tips and thumbnail_url usage

### Files to Modify

1. **`backend/app/services/streaming_service.py`** - Update `_build_system_instruction()`

### Changes

In the "Enrichment Fields" section for Activity, strengthen the tips instruction:

- Add: "Generate practical tips for each attraction based on the information available. Tips should include useful reminders like best time to visit, optimal duration, photography spots, or insider knowledge."
- Ensure thumbnail_url uses API-fetched image directly when available (already mentioned but clarify)

---

## Fix 8: Tool Schemas - Ensure data flows correctly to LLM

### Files to Modify

1. **`frontend/src/types/trip.ts`** - Update interfaces to match tool outputs
2. **`backend/app/agent/schemas.py`** (if exists) - Check if backend schemas need alignment
3. **`backend/app/agent/tools/attractions.py`** - Verify wiki_url is being returned

### Changes

- Ensure Activity interface includes all fields from attraction tool (wiki_url, map_url, etc.)
- Ensure Hotel interface includes all fields from hotel tool (hotel_class_int, reviews, location_rating, amenities, description)
- Ensure Flight interface includes airplane, travel_class
- Verify attractions.py returns wiki_url in result (it does at line 148-150)

---

## Fix 1: Flight Card - Show only 1 uniform price for round-trip

### Files to Modify

1. **`frontend/src/components/trip/FlightCard.tsx`** - Only show price on outbound flight

### Changes

- Only show price_hkd when `flight.direction === 'outbound'`
- This prevents showing the price twice (once on outbound, once on return)

---

## Fix 2: Flight Card - Uniform booking URL for round-trip

### Files to Modify

1. **`backend/app/agent/tools/flights.py`** - Only use first flight's booking_url for round-trip
2. **`frontend/src/types/trip.ts`** - Ensure interface supports single booking_url

### Changes

In `_parse_itineraries()` or `_search_round_trip()`:

- When combining outbound and return flights, set `booking_url` only from the first outbound flight's result
- All flights in the round-trip should share the same booking_url

In flights.py `_search_round_trip()` around line 313:

```python
# Use only the first outbound flight's booking URL for all return flights
all_flights = outbound_flights[:1] + return_flights[:3]
if all_flights and len(all_flights) > 1:
    primary_booking_url = all_flights[0].get("booking_url")
    for flight in all_flights[1:]:
        flight["booking_url"] = primary_booking_url
```

---

## Verification

1. Run `uv run pyright backend/app/agent/tools/` to check type correctness
2. Run `npx tsc --noEmit` in frontend to check TypeScript
3. Test round-trip flight search to verify single price and URL
4. Test hotel card renders all new fields
5. Test attraction card collapsible description and wiki link

---

## File Summary

| File                                              | Changes                                                                                                                                |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/types/trip.ts`                      | Add airplane, travel_class to Flight; hotel_class_int, reviews, location_rating, amenities, description to Hotel; wiki_url to Activity |
| `frontend/src/components/trip/FlightCard.tsx`     | Show duration, airplane, travel_class; hide price on return                                                                            |
| `frontend/src/components/trip/HotelCard.tsx`      | Show hotel_class_int, reviews, location_rating, amenities (expandable), description                                                    |
| `frontend/src/components/trip/AttractionCard.tsx` | Collapsible description, wiki link, embed map                                                                                          |
| `backend/app/services/streaming_service.py`       | Add anti-hallucination rules for prices, improve tips instruction                                                                      |
| `backend/app/agent/tools/flights.py`              | Set uniform booking_url for round-trip                                                                                                 |

---

## Implementation Status

### Completed ✅
- Fix 3: Flight interface updated with `airplane`; FlightCard displays airplane, cabin_class, duration
- Fix 1: FlightCard shows price only on outbound; "Round Trip" badge added; "Round Trip Total" label
- Fix 4: Hotel interface updated with `hotel_class_int`, `reviews`, `location_rating`, `amenities`, `description`
- Fix 5: Activity interface updated with `wiki_url`
- Fix 8: TypeScript interfaces aligned with tool outputs

### Not Yet Implemented
- HotelCard.tsx - display new fields (hotel_class_int, reviews, location_rating, amenities expandable, description)
- AttractionCard.tsx - collapsible description, wiki link, embed map
- Backend prompts (Fix 6: prevent price hallucination, Fix 7: improve tips)
- Fix 2: Uniform booking URL for round-trip in flights.py
