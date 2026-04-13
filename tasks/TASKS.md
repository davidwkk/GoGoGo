# 👥 `gogogo` — Task Assignment Document

> Deadline: Apr 16, 2026 | Team: 3 members

---

## 🙋 David

### 🎯 Goal

Build the intelligent core of the app: agent loop, all tools, structured output, preference extraction, voice I/O, auth, chat persistence, and trip display.

### ✅ Task Breakdown

#### Phase 1A — Voice UI First (Days 1–4)

> **⚠️ Feedback Loop Risk**: `useASR` must explicitly mute/pause `useTTS` when recording starts. Add a pulsing mic visual indicator so users can distinguish listening vs. speaking states.
> **⚠️ Text Fallback**: Every voice interaction must have a text fallback — if ASR fails or TTS is unavailable, fall back to on-screen text input/display.

- [x] `useASR.ts` — Web Speech API, start/stop recording, emit transcript ✅
  - Must emit partial transcripts in real-time
  - Must handle browser permission denial gracefully → fall back to text input
  - Export `isVoiceSupported(): boolean` — checks `window.SpeechRecognition ?? window.webkitSpeechRecognition` for browser support
- [x] `useTTS.ts` — Browser `window.speechSynthesis` ✅
  - Must fall back to text display if TTS unavailable
  - Export `isTTSAvailable(): boolean` — checks `window.speechSynthesis` support
- [x] `VoiceButton.tsx` — Mic toggle, pulsing recording indicator (only rendered if `isVoiceSupported()`) ✅
- [x] `TTSPlayer.tsx` — Auto-play TTS when new assistant message arrives; if TTS fails, show text instead ✅
- [x] `chatSlice.ts` — add `voiceAvailable: boolean` flag; initialize with `isVoiceSupported()` on app load; gate voice UI on this flag ✅ (as `store/index.ts`)
- [x] `useChat.ts` — wire VoiceButton → `chatService.ts` → `POST /chat`; handle `ChatResponse` (text + itinerary + message_type); needed for Phase 1A voice integration ✅

#### Phase 1B — Live Search Tools (Days 1–6)

> **⚠️ No Hallucination**: Every itinerary item must be fetched via live API — the agent MUST call at least one tool for every flight, hotel, attraction, transport, or weather data point. Pure LLM generation without tool calls is not acceptable.
> **⚠️ API Error Handling**: Each tool must catch exceptions and return `{"error": "..."}` dicts instead of raising — do not let external API failures become 500 errors.

- [x] Implement all 7 tools in `tools/` — each returns `dict` (NOT Pydantic models); keep them lightweight mid-loop ✅
  > **Why dict not Pydantic mid-loop**: SDK serializes both equally; Pydantic mid-loop adds validation overhead with no benefit since agent doesn't enforce schemas on tool responses; final output only = Pydantic TripItinerary
  > **⚠️ All tools must use `httpx.AsyncClient`** — do NOT use `requests` (sync, blocks event loop). Use `async with httpx.AsyncClient() as client: response = await client.get(url)`
  - `transport.py` 🟢 — SerpAPI Google Maps engine → transport options (MTR, bus, taxi, train) between cities/locations **[CORE — Route]** (small — same pattern as flights.py) | ⚠️ **Demo-grade cache**: use module-level `dict` — `lru_cache` does NOT work on async functions (caches coroutine object, not result). Pattern: `_cache: dict[tuple, dict] = {}`; check `if key in _cache` before fetching.
  - `attractions.py` 🟠 — Wikipedia REST API (`/page/summary/{title}`) → enrich attractions with description, thumbnail, coordinates **[CORE — Introduce]** (small — no API key, simple HTTP call)
  - `maps.py` — **URL builder only** (no API calls) — generates Google Maps Embed/Static URLs from coordinates/place names
  - `search.py` — Tavily primary, SerpAPI fallback (httpx.AsyncClient)
  - `flights.py` — SerpAPI Google Flights (httpx.AsyncClient)
  - `hotels.py` — SerpAPI Google Hotels (httpx.AsyncClient)
  - `weather.py` — OpenWeatherMap current weather (httpx.AsyncClient)
- [x] Define all Pydantic output models in `agent/schemas.py` ✅
  > **⚠️ Pydantic type rules**: ✅ `str`, `int`, `float`, `bool`, `list[str]`, `enum`, nested `BaseModel` | ⚠️ `dict[str, int]` — not well supported, avoid | ❌ Raw `dict` types not supported by Gemini schema
  - `AttractionItem` (with `description`, `thumbnail_url`, `coordinates` from Wikipedia) **[CORE — Introduce]**
  - `HotelItem`, `FlightItem`, `TransportOption` (with `from_location`, `to_location`, `transport_type`, `duration`, `cost`) **[CORE — Route]**
  - `DayPlan` (includes `TransportOption[]` for between-location routing), `TripItinerary` **[CORE — Plan]**
- [x] **Day 3 — Commit `MOCK_ITINERARY` fixture** (hardcoded `TripItinerary` instance in `tests/fixtures/`) to unblock Minqi and Xuan ✅
- [x] Set up Gemini 3 Flash agent in `agent.py` ✅
  - Register all tools
  - System prompt: `prefs_section = f"User preferences: {preferences}" if preferences else ""` then `f"You are a travel planning assistant. {prefs_section}..."` — **never** use `{preferences or ""}` or direct None interpolation (it literally injects the word "None")
  - System prompt enforces: **every response item must come from a tool call** — no pure LLM text for facts/prices/times

#### Phase 1C — Agent Loop + Structured Output (Days 4–9)

> **⚠️ Loop Bound**: Set `MAX_ITERATIONS = 10` in `agent.py` to prevent infinite loops if the LLM cycles.
> **⚠️ Function call iteration**: Iterate ALL parts — `function_calls = [p.function_call for p in response.candidates[0].content.parts if p.function_call]`. Do NOT assume `parts[0]` is the only function call — Gemini 3 Flash supports parallel calls in one turn.
> **⚠️ Loop termination**: If `function_calls` is non-empty, execute tools and continue; if empty (plain text), the loop is done.
> **⚠️ Preserve thought_signature**: Append `response.candidates[0].content` as-is to the messages list — do NOT reconstruct `types.Content(role="model", parts=[...])` manually. This strips the `thought_signature` and breaks multi-turn context. The SDK preserves it when you append the raw content object.
> **⚠️ response_schema**: Only enforce `response_json_schema` on the **final** `generate_content` call that returns `TripItinerary` — mid-loop tool calls must **not** use `response_schema` or the model will try to end the loop prematurely.
> **⚠️ History management**: You must manually append both model turns and tool responses to the `messages` list between iterations — Gemini does not auto-manage conversation history.
> **⚠️ Pydantic bridging**: Use `response_json_schema=TripItinerary.model_json_schema()` (pass the raw dict, NOT a string) with `response_mime_type="application/json"`. Validate response with `TripItinerary.model_validate_json(response.text)`. Union types are supported — see the ModerationResult example in the codebase.

- [x] Implement `callbacks.py` — Loguru logging for tool calls + agent finish ✅
- [x] Implement `chat_service.py` ✅
  - Run agent loop → structured `TripItinerary` via `generate_content` with `response_json_schema`
  - Wrap entire agent loop in `asyncio.wait_for(..., timeout=25.0)` — abort and return error text if wall-clock exceeds 25s
    > ⚠️ **Demo-grade**: acceptable for low-concurrency demo use. All `httpx.AsyncClient` calls use `async with` so connections clean up on cancel. Add comment: `# Demo-grade: acceptable for low-concurrency demo use`
  - Return `ChatResponse` (not bare `TripItinerary`): `ChatResponse(text=str, itinerary=TripItinerary|None, message_type=Literal["chat","itinerary","error"])`
  - **Text fallback**: if TTS fails, return text response as well
    > **References:** [Gemini Function Calling](https://ai.google.dev/gemini-api/docs/function-calling?example=meeting) · [Gemini Structured Outputs](https://blog.google/innovation/google-ai/gemini-api-structured-outputs/)
    > **Correct pattern for structured output** (confirmed working):

```python
from google import genai
client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config={
        "response_mime_type": "application/json",
        "response_json_schema": TripItinerary.model_json_schema(),  # pass raw dict
    },
)
result = TripItinerary.model_validate_json(response.text)  # validate response
```

- [x] Expose `POST /chat` in `api/routes/chat.py` ✅
  - Use **mocked auth** (`get_current_user` returns dummy user)
  - Accept optional `session_id` in request — if absent, create a new session
  - **Stub DB** (skip saving messages for now)
  - Accept `ChatRequest`, return `ChatResponse` (`text`, `itinerary | None`, `message_type`)
  - `itinerary` is only populated when `generate_plan=True` (user clicks "Generate Trip Plan" button); otherwise returns `text` only
  - `generate_plan: bool = False` gate in `ChatRequest` — if False, skip full agent loop (cheap chat); if True, run full loop + structured output
- [x] Add `ChatResponse` schema in `schemas/chat.py`: `text: str`, `itinerary: TripItinerary | None`, `message_type: Literal["chat", "itinerary", "error"]` ✅
- [x] Frontend: add "Generate Trip Plan" button in `ChatPage.tsx` / `InputBar.tsx` — pressing it sends `POST /chat` with a flag indicating full itinerary generation is requested ✅ (as `InputBar.tsx` in `components/chat/`)
- [x] **Empty preferences fallback**: If `user_preferences` is empty/null (first chat), proceed without preferences — do NOT block or error; inject empty preferences dict into system prompt ✅

#### Phase 2 — Preference Extraction (Days 9–13)

- [x] Define `user_preferences` table in `db/models/preference.py` ✅
- [x] Write Alembic migration for `user_preferences` ✅
- [x] Implement `preference_repo.py` — upsert preferences ✅
- [x] Implement `preference_service.py` ✅
  - Trigger: `POST /chat/sessions/{id}/end` — user explicitly ends session, requests trip plan
  - Call Gemini 3.1 Flash-Lite with full conversation history
  - Extract structured preferences from conversation
  - Save/update via `preference_repo`
- [x] Inject saved preferences into agent system prompt in `agent.py` ✅

#### Phase 3 — Auth Wiring + Integration (Days 13–20)

##### Auth Backend

- [x] Define `users` table in `db/models/user.py` ✅
- [x] Write Alembic migration for `users` ✅
- [x] Implement `security.py` ✅
  - `hash_password`, `verify_password` (passlib bcrypt)
  - `create_access_token`, `decode_access_token` (python-jose)
  - Use `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")` in `deps.py`
- [x] Implement `auth_service.py` — register (check duplicate), login (verify + issue token) ✅
- [x] Implement `user_repo.py` — `get_by_email`, `get_by_id`, `create` ✅
- [x] Expose `POST /auth/register`, `POST /auth/login` in `api/routes/auth.py` ✅
- [x] Implement `deps.py` ✅
  - `get_db` — async session dependency
  - `get_current_user` — decode JWT via `oauth2_scheme: OAuth2PasswordBearer` (David's mock uses the same signature); must return `User(id, username, email)` — do NOT change return type or field names
- [x] Expose `GET /users/me` in `api/routes/users.py` ✅

##### Chat Persistence

- [x] Define `chat_sessions` + `messages` tables ✅
- [x] Write Alembic migrations for both tables ✅
- [x] Implement `message_service.py` — `create_session`, `get_session`, `append_message`, `get_session_messages`, `get_or_create_guest` ✅
- [x] Build `chat_history_service.py` with `append_user_message()` and `append_agent_message()` methods ✅ (in `message_service.py`)
- [x] Update `chat_service.py` ✅
  - Save user message before agent call ✅
  - Save assistant response after agent call ✅
- [x] Expose session history endpoint: `GET /chat/sessions/{session_id}/messages` ✅

##### Trip Backend

- [x] Define `trips` table in `db/models/trip.py` ✅
  - `itinerary_json` as JSONB column
- [x] Write Alembic migration for `trips` ✅
- [x] Implement `trip_repo.py` ✅
  - `create`, `get_by_id`, `get_by_user`, `delete`
  - Call `itinerary.model_dump(mode='json')` before saving to SQLAlchemy
  - Validate back with `TripItinerary.model_validate(db_obj.itinerary_json)` on retrieval
- [x] Implement `trip_service.py` ✅
  - `save_trip(user_id, session_id, itinerary: TripItinerary)` — serialize + store
  - `get_trips(user_id)` — list summaries
  - `get_trip(trip_id)` — full detail
- [x] Expose CRUD in `api/routes/trips.py` ✅
  - `POST /trips` — save trip (called by `chat_service` after agent finishes)
  - `GET /trips` — list user's trips
  - `GET /trips/{trip_id}` — full itinerary
  - `DELETE /trips/{trip_id}` — delete

##### Auth + Chat Wiring

- [x] Remove mock `get_current_user` — deps.py now uses real JWT decode, returns `user_id` int from token ✅
- [x] Wire message saving — chat.py calls `append_message` before/after `invoke_agent` ✅
- [x] Wire `save_trip` — `chat_service.invoke_agent` calls `trip_service.save_trip` when `generate_plan=True` ✅
- [x] Wire voice into Chat UI — ChatPage/InputBar already integrate VoiceButton + useASR/useTTS ✅

##### Frontend UI

- [x] `LoginPage.tsx` — login + register tabs, form validation, error display; full-screen centered card, no sidebar ✅
- [x] "Continue as Guest" button — bypasses auth, stores `guest_uid` in localStorage, navigates to chat; `useChat.ts` sends guest_uid as session_id; backend resolves guest sessions ✅
- [x] `useAuth.ts` — login/logout, persist token in localStorage ✅
- [x] `ChatPage.tsx` — basic scaffold exists with message list + InputBar; MessageBubble rendered inline ✅
- [x] `MessageBubble.tsx` — user vs assistant styling ✅
- [x] **Trip UI** ✅ — `TripPage.tsx`, `ItineraryCard.tsx` (as `ActivityCard.tsx`), `FlightCard.tsx`, `tripService.ts`, wire TripPage into routing

#### Phase 4 — Streaming UI + Observability (Post-Phase 3)

- [x] **Typewriter effects in frontend** (casual chat) ✅ — Stream LLM response tokens to frontend for casual chat; update `useChat.ts` to handle SSE token streaming; render tokens as they arrive in `MessageBubble.tsx`
- [x] **Add log to track LLM full cycle** ✅ — Instrument `chat_service.py` and `agent.py` with structured logging (Loguru → JSON format); add metrics for: LLM call latency, tool call counts, token usage, end-to-end response time
- [x] **Stream agent tool calls to frontend** (casual setting) ✅ — Thinking bubbles display when agent is actively calling tools (e.g., "Searching flights...", "Checking weather..."); show intermediate steps in UI during agent loop
- [x] **SSE Streaming** ✅ — Upgrade `POST /chat` → `GET /chat/stream` SSE endpoint ✅ (`POST /chat/stream` in `chat.py`)
- [x] **Stream agent tool calls to frontend** (casual setting) ✅ — Thinking bubbles show intermediate steps in UI
- [x] **Render LLM responses in Markdown** ✅ — Use `react-markdown` to render assistant message text with proper formatting; headers render after full response received (improvement possible later)

### 🔲 Remaining Tasks

- [x] **Verify the return schema from tools** — Confirm the return schemas and write API testcases to test the tools.
- [x] **Verify the map URL building method** — Audit `tools/maps.py` URL builder; confirm generated Google Maps Embed/Static URLs are correctly formatted with coordinates and place names; add unit tests for edge cases (special characters, empty values, coordinate bounds).
- [x] **Fix thinking bubble display** when LLM calls tools ✅ — Thinking bubbles are now collapsible per message using `expandedBubbles` state; shown persistently for every user message.
- [x] **Agent decides when to generate trip plan** — Remove the explicit "Generate Trip Plan" button; let the agent autonomously decide when to produce a structured `TripItinerary` based on conversation context (e.g., user expresses intent to travel, provides destinations/dates). The agent should detect trip-planning intent and invoke `generate_content` with `response_json_schema` accordingly. Frontend no longer sends a `generate_plan` flag — the agent loop handles this internally.
- [x] **Migrate trip planning to streaming** — Travel planning agent NOT yet refactored to streaming; requires migrating from waiting for full output to using SSE stream; requires adding a tool to fetch the current time/day for date-aware planning. Depends on: "Agent decides when to generate" (the streaming refactor builds on the unified agent loop).
- [x] **Add 3x auto-retry on SSE disconnect** ✅ — Up to 3 retries with exponential backoff (500ms base) on SSE disconnect or fetch error; yields reconnecting status to UI on retry attempts
- [x] **Explicit 'yes' confirmation** ✅ — Agent prompt updated to require explicit "yes" from user before calling `finalize_trip_plan`; presents summary and asks for confirmation first.
- [x] **Enrichment fields in agent output** ✅ — Agent system prompt updated to instruct population of all enrichment fields: `opening_hours`, `admission_fee_hkd`, `rating`, `review_count`, `tips`, `image_url`, `thumbnail_url`, `booking_url`, `address` (Activity); `star_rating`, `guest_rating`, `image_url`, `embed_map_url` (Hotel); `duration_minutes`, `cabin_class` (Flight); `estimated_total_budget_hkd` (TripItinerary); `theme`, `notes`, `estimated_daily_budget_hkd` (DayPlan).
- [x] **Demo trip data enrichment** ✅ — All enrichment fields populated in `seed_db.py` DEMO_ITINERARY: flights have `duration_minutes`, `cabin_class`; hotels have `image_url`, `embed_map_url`, `star_rating`, `guest_rating`; activities have all enrichment fields; day plans have `theme`, `notes`, `estimated_daily_budget_hkd`; `estimated_total_budget_hkd` with breakdown.
- [x] **Schema misalignment fixes** ✅ — `TripSummary.created_at` changed to `DateTime | str`; `/demo` endpoint now validates itinerary via `TripItinerary.model_validate` with graceful degradation.
- [x] **ItineraryDisplay matches TripPage** ✅ — `ItineraryDisplay` in ChatPage now includes: budget section with flights/hotels/activities breakdown, day headers with theme and daily budget badge, `HotelCard` component (with MapEmbed, ImageLightbox), icons (`Banknote`, `Bed`, `Plane`, `Ticket`).
- [x] **Auto-save trip on itinerary generation** — After `finalize_trip_plan` returns a valid `TripItinerary` (no `"error"` key), the streaming loop should automatically call `trip_service.save_trip()` to persist it before yielding `done: true`. Changes required:
  - **Backend** (`streaming_service.py`): In the `finalize_trip_plan` success path (after the itinerary SSE event is yielded), call `trip_service.save_trip(user_id, session_id, itinerary)` before yielding `done: true`. The `user_id` comes from the request context passed into `stream_agent_response`.
  - **Frontend** (`ChatPage.tsx`): Remove the "Save & Finish Trip" button and its associated `POST /chat/sessions/{id}/end` call from the UI. No manual save needed — the backend auto-saves.
  - **UX**: After the trip is auto-saved, show a brief toast/snackbar "Trip saved!" in the chat UI so the user knows it was persisted.
- [x] **Delete trip plan** ✅ — `DELETE /trips/{trip_id}` already existed. TripPage already had the delete button fully wired with confirmation dialog. Added `sonner` toast library, replaced `alert()` with `toast.success('Trip deleted')` on success and `toast.error('Failed to delete this trip. Please try again.')` on failure. Added `Toaster` to `App.tsx`.
- [x] **Auth error UX for all user-gated buttons** — Many buttons (new chat, save trip, etc.) silently fail when the user's token is invalid/expired. Audit every button that requires an active user (e.g., "New Chat", "Save & Finish Trip" — to be removed, itinerary auto-save). For each:
  - Catch 401/403 responses from the API.
  - Show a **prominent error toast** (not just a console log): "Your session has expired. Please log in again." with a link/button to navigate to `/login`.
  - If the user is a guest (no token), show a toast: "Please log in to save your trip." instead of silently failing.
  - Apply this globally in the `apiClient` Axios interceptor — if any response returns 401 or 403, trigger a shared auth-error handler that shows the toast and optionally clears the stored token.
- [x] **Change password feature** — Implement backend endpoint `PUT /users/me/password` (or `POST /users/change-password`) that accepts `current_password` and `new_password`, verifies the current password, hashes and stores the new one. Wire into `ProfilePage.tsx` with form validation (min 8 chars, require uppercase + digit).
- [x] **Clear chat history feature** — Implement `DELETE /chat/sessions/{session_id}/messages` endpoint to clear all messages in a single chat session. Add a "Clear chat" button in ChatPage UI for the current session (clears local state + calls backend). Also add `DELETE /chat/sessions` endpoint to clear all sessions/history for the current user. Show confirmation toast on success.
- [x] **Custom trip planning commands/rules** — Allow users to input custom commands or rules in ProfilePage (e.g., "Prioritize commercial activities", "Always suggest budget options") that are saved as part of `user_preferences`. These commands should be sent to the LLM alongside existing preference extraction in the agent system prompt (e.g., inject as `"User instructions: {commands}"` in the agent prompt). Add a text area in ProfilePage for "Trip Planning Preferences / Custom Commands" with save button. Commands are stored in `user_preferences` table and injected into the agent prompt on every trip-planning chat.
- [x] Zustand auth store — `user`, `token`, `isAuthenticated`
- [x] `authService.ts` — API calls with Axios (uses `apiClient` directly in `LoginPage.tsx` instead)
- [x] Protected route wrapper — tell the user to login if unauthenticated (no auto-redirect, but show a button to the login page)
- [x] **Guest access**: the chat history bar must be visible to guest users too; guest users can create new chat sessions, but cannot save trips.
- [x] **Chat history bar alignment** — Fix the style of the chat history bar; specifically, the border/line below it should be at the same vertical level as the main chat page when the history bar is collapsed (alignment is correct when expanded).
- [ ] **Save the image for attractions** - Attraction images should be saved to db instead of fetching it every time.
- [x] **Fix the null fields in trip plan** - There are many null values in the generated trip plan which can be optimized.
- [x] **Fix return flight** — Round-trip now uses `departure_token` from first API call to automatically fetch return flights in a second API call (same airports + dates, `type=1`). Returns 1 outbound + up to 3 return flights. No fallback to reversed-airport approach — errors are returned to LLM to retry.
- [x] **Limit the number of hotels returned from API** - Reduce the results to at most 3 hotels.

## 🙋 Minqi

### ✅ Task Breakdown

#### Phase 3 — Auth + Chat UI

- [x] Verify STT working properly
- [x] Increase STT duration to at least 30s (now supports up to 60s, auto-stops after 20s silence, and supports manual stop)
- [x] **Fix chat history for sessions** — Chat is currently memoryless; each session/conversation must load and display previous messages from the database so users can resume conversations. Backend: implement `get_active_session_by_user(user_id)` in `message_service`; wire into `chat.py` on session resume. Frontend: load previous messages when user opens an existing session.
- [x] **Guest access**: the chat history bar must be visible to guest users too; guest users can create new chat sessions, but cannot save trips.
- [x] **Chat history bar alignment** — Fix the style of the chat history bar; specifically, the border/line below it should be at the same vertical level as the main chat page when the history bar is collapsed (alignment is correct when expanded).

#### Phase 4 — TTS Upgrades (Minqi)

> Implement TTS module in 2 phases, with a possible third phase:

- [x] **Phase 1 — Browser native TTS** ✅ (implemented with per-assistant-message Play/Stop button using `window.speechSynthesis`)
- [x] **Phase 2 — Gemini Live API** — Single multimodal session replacing ASR + agent + TTS hooks entirely

### 🔲 Remaining Tasks

- [x] **Favorite Chat History** - Allow user to mark some chat history sessions as favorite, showing on the top of the history bar. ✅ (`is_favorite` + star in sidebar; API `PATCH` with `is_favorite`; list ordered favorites-first)
- [x] **Fix bug** - User should be able to read other chat sessions when an active LLM call is in progress ✅ (abort + clear loading state on session switch; cancelable `generate_plan` POST via `AbortSignal`)

---

## 🙋 Xuan

### ✅ Task Breakdown

#### Phase 3 — Trip UI

- [x] **Implement frontend display in My Trip Page and display of Trip Itinerary** ✅
- [x] **Fix frontend display for trips and other components** — Audit and fix any display issues in TripPage, HotelCard, AttractionCard, and other trip-related components
- [x] `HotelCard.tsx` — name, price, rating, booking link button
- [x] `AttractionCard.tsx` — name, category badge, photo, rating
- [x] `MapEmbed.tsx` — render Google Maps Embed iframe from `map_embed_url` (inline in TripPage instead)

### 🔲 Remaining Tasks

- [x] **Image popup dialog** — Make images in trip cards clickable; show full-size image in a popup dialog when clicked (e.g., lightbox modal)
- [x] **Typewriter Effect** — Add typewriter effect to ChatPage for LLM's response; stream tokens as they arrive for a more natural chat feel
- [x] **Fix the display bug** - '✨ Your trip plan is ready below' only appears when the user refresh the page, but not when the trip is done. It should appear directly when the trip plan is generated and rendered.

#### Frontend E2E Tests

> ⚠️ **Label backend dependencies as TODO** — if a test requires a backend API that doesn't exist yet, add a `# TODO: needs backend <feature>` comment so it can be implemented later without blocking

- [x] **Login flow** — `LoginPage.tsx` → register → redirect to chat
- [x] **Guest mode flow** — Continue as Guest → redirect to chat
- [x] **Chat → generate plan → view trip** — Send message → click "Generate Trip Plan" → wait for itinerary → navigate to TripPage → verify itinerary renders
- [x] **Trip detail view** — Click a saved trip → verify all sections (flights, hotels, attractions) render with images
- [x] **Voice input toggle** — Verify mic button appears, toggles recording state (if browser supports Web Speech API)

#### Frontend Polishing & Robustness

- [x] **Skeleton/loading states** — Add skeleton loaders for trip cards, chat messages, and itinerary sections while data loads
- [x] **Error handling UI** — Timeout displays for failed API calls, retry buttons where applicable
- [x] **API error envelope standardization** — Standardize `APIError { detail: string; code?: string }` in `api.ts` ✅ (already implemented in `api.ts` with interceptor; used in `LoginPage.tsx`)
- [x] **Mobile responsive layout audit** — Verify all pages (Login, Chat, Trip) render correctly on narrow viewports; fix any overflow or truncation issues
- [ ] Add FAKE loading sentences when LLM takes a long time to respond (e.g. >5: LLM is thinking hard >10: Current load is high, may need to wait longer time, etc.)
- [x] Fix the display issue in TripCard, FlightCard, AttractionCard (embed map), etc.
