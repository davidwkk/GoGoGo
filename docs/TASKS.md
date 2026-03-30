# 👥 `gogogo` — Task Assignment Document

> Deadline: Apr 16, 2026 (~20 days) | Team: 3 members | Infra: ✅ Already set up (owned by David)

---

## 🧭 Ownership Overview

| Area                                      | Owner                                                              |
| ----------------------------------------- | ------------------------------------------------------------------ |
| Infra — Docker, FastAPI skeleton, setup   | **David**                                                          |
| Agent Core, Tools, Structured Output      | **David**                                                          |
| Preference Extraction (Flash-Lite)        | **David**                                                          |
| Voice — ASR + TTS                         | **David**                                                          |
| Auth — Register/Login, JWT, Login UI      | **David**                                                          |
| Chat — Session, Message History, Chat UI  | **David**                                                          |
| Trip — CRUD, Itinerary Display, Map Embed | **David**                                                          |
| DB Models + Migrations (all tables)       | **David** (owns all migrations and all models to remove conflicts) |

---

## 🙋 David

### 🎯 Goal

Build the intelligent core of the app: agent loop, all tools, structured output, preference extraction, voice I/O, auth, chat persistence, and trip display.

### 📦 Files Owned

```
backend/app/agent/
├── agent.py                  # Gemini 3 Flash agent setup (gemini-3-flash-preview)
├── callbacks.py              # Loguru logging callbacks
├── schemas.py                # TripItinerary + all Pydantic output models
└── tools/
    ├── search.py             # Tavily (primary) + SerpAPI fallback
    ├── flights.py            # SerpAPI Google Flights
    ├── hotels.py             # SerpAPI Google Hotels
    ├── weather.py            # OpenWeatherMap
    ├── maps.py               # Google Maps Static/Embed URL builder
    ├── transport.py           # SerpAPI Google Maps (route/transport options)
    └── attractions.py        # Wikipedia REST API (attraction details)

backend/app/services/
├── chat_service.py           # Invoke agent, return TripItinerary
├── preference_service.py      # Flash-Lite extraction (gemini-3.1-flash-lite-preview) + save preferences
├── auth_service.py           # Register, login, password verify
└── message_service.py        # Message persistence — create_session, get_session, append_message

backend/app/db/models/
├── user.py                   # users table
├── chat_session.py           # chat_sessions table
├── message.py                # messages table
└── preference.py             # user_preferences table

backend/app/repositories/
├── user_repo.py              # User DB access
├── session_repo.py           # ChatSession DB access
├── message_repo.py           # Message DB access
└── preference_repo.py        # Preference DB access (no expire_all!)

backend/app/schemas/
├── chat.py                   # ChatRequest / ChatResponse schemas
├── auth.py                   # RegisterRequest, LoginRequest, TokenResponse
└── user.py                   # UserOut schema

backend/app/api/routes/
├── chat.py                   # POST /chat
├── chat_sessions.py           # POST /chat/sessions/{id}/end, GET /chat/sessions/{id}/messages
├── auth.py                   # POST /auth/register, POST /auth/login
├── users.py                  # GET /users/me
└── health.py                 # /health

backend/app/core/
├── config.py                 # pydantic-settings env config
├── logging.py                # Loguru setup
├── security.py               # JWT encode/decode, password hashing
└── middleware.py             # CORS setup

backend/app/main.py            # FastAPI app entrypoint

backend/app/repositories/
└── trip_repo.py              # Trip DB access

backend/app/services/
└── trip_service.py           # Save trip, list trips, get trip by id

backend/app/api/routes/
└── trips.py                  # GET/DELETE /trips (POST /trips is internal — called by chat_service directly)

frontend/src/
├── pages/
│   ├── LoginPage.tsx         # Login + Register form
│   ├── ChatPage.tsx          # Message list, input bar
│   └── TripPage.tsx          # Trip history list + detail view
├── components/
│   ├── chat/
│   │   ├── ChatWindow.tsx    # Chat container
│   │   ├── MessageBubble.tsx # User vs assistant styling
│   │   └── InputBar.tsx      # Text input bar
│   ├── trip/
│   │   ├── ItineraryCard.tsx # Day-by-day plan display (as ActivityCard.tsx)
│   │   └── FlightCard.tsx    # Flight info + booking link
│   └── voice/
│       ├── VoiceButton.tsx   # Mic toggle button
│       └── TTSPlayer.tsx     # Auto-play TTS on agent response
├── hooks/
│   ├── useASR.ts             # Web Speech API hook
│   ├── useTTS.ts             # Web Speech Synthesis hook
│   ├── useChat.ts            # Chat request hook
│   └── useAuth.ts            # Auth state, login/logout actions
├── store/
│   ├── chatSlice.ts          # Chat state (session, messages)
│   └── tripSlice.ts          # Trip state (trip list, current trip)
└── services/
    ├── chatService.ts        # POST /chat API call
    ├── tripService.ts        # GET/DELETE /trips API calls
    └── authService.ts        # POST /auth/register, /auth/login
```

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

> **⚠️ Loop Bound**: Set `MAX_ITERATIONS = 5` in `agent.py` to prevent infinite loops if the LLM cycles.
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

### 🔲 Remaining Tasks

- [ ] **Verify the map URL building method** — Audit `tools/maps.py` URL builder; confirm generated Google Maps Embed/Static URLs are correctly formatted with coordinates and place names; add unit tests for edge cases (special characters, empty values, coordinate bounds)
- [ ] **Migrate trip planning to streaming** — Travel planning agent NOT yet refactored to streaming; requires migrating from waiting for full output to using SSE stream; requires adding a tool to fetch the current time/day for date-aware planning
- [ ] **Fix chat history for sessions** — Chat is currently memoryless; each session/conversation must load and display previous messages from the database so users can resume conversations
- [ ] **Update `useChat.ts` for trip planning** — consume SSE, show intermediate steps in UI during trip generation
- [ ] **Add 3x auto-retry on SSE disconnect** — currently 2 retries with exponential backoff in `_stream_chat`
- [ ] **Upgrade `useTTS.ts` from `window.speechSynthesis` → Gemini TTS**
- [ ] **Gemini Live API** — single multimodal session replacing ASR + agent + TTS hooks entirely

### 🧪 Tests to Write

```
backend/tests/unit/
├── test_tools/
│   ├── test_search.py        # Returns expected shape
│   ├── test_flights.py
│   ├── test_hotels.py
│   ├── test_weather.py       ✅ (3 tests)
│   ├── test_maps.py          ✅ (5 tests)
│   ├── test_transport.py     # SerpAPI Google Maps returns transport options
│   └── test_attractions.py   ✅ (3 tests)
└── test_schemas/
    └── test_trip_itinerary.py  ✅ DONE — 9 tests covering roundtrip, validation, constraints

backend/tests/unit/
└── test_security/
    ├── test_jwt.py           # encode/decode roundtrip
    └── test_password.py      # hash + verify

backend/tests/integration/
├── test_auth/
│   ├── test_register.py      # 201, duplicate 409
│   └── test_login.py         # 200 + token, wrong password 401
└── test_trips/
    ├── test_save_trip.py     # POST /trips saves correctly
    ├── test_list_trips.py    # GET /trips returns user's trips only
    └── test_get_trip.py      # GET /trips/{id} returns full itinerary

backend/tests/integration/
└── test_chat/
└── test_chat_endpoint.py # POST /chat returns TripItinerary shape
```

### ⚠️ Mocking Strategy (Unblock yourself)

```python
# deps.py — temporary mock, swap when Minqi's JWT middleware is ready
DEV_USER_ID = 1  # use named constant, NOT inline magic number

async def get_current_user(
    token: str = Depends(oauth2Scheme),  # real version uses JWT Bearer token
):
    return User(id=DEV_USER_ID, username="dev", email="dev@test.com")
# ⚠️ Swap the body only — keep the function signature identical when removing mock.
# Minqi: your real get_current_user MUST return User(id, username, email) shape.
# Do NOT change the return type or field names or David's routes break silently.
```

---

## 🙋 Minqi

### ✅ Task Breakdown

#### Phase 3 — Auth + Chat UI

- [x] Verify STT working properly
- [ ] Increase STT duration to at least 30s
- [ ] Zustand auth store — `user`, `token`, `isAuthenticated`
- [ ] `authService.ts` — API calls with Axios (uses `apiClient` directly in `LoginPage.tsx` instead)
- [ ] Protected route wrapper — redirect to login if unauthenticated
- [ ] Display fake loading steps ("Searching flights...", "Checking weather...") during POST /chat request
- [ ] Add "Save & Finish Trip" button that calls `POST /chat/sessions/{id}/end`
- [ ] Display chat history on session load

---

## 🙋 Xuan

### ✅ Task Breakdown

#### Phase 3 — Trip UI

- [x] **Implement frontend display in My Trip Page and display of Trip Itinerary** ✅

### 🔲 Remaining Tasks

- [ ] **Fix frontend display for trips and other components** — Audit and fix any display issues in TripPage, HotelCard, AttractionCard, and other trip-related components
- [ ] `HotelCard.tsx` — name, price, rating, booking link button
- [ ] `AttractionCard.tsx` — name, category badge, photo, rating
- [ ] `MapEmbed.tsx` — render Google Maps Embed iframe from `map_embed_url` (inline in TripPage instead)

---

## 🚨 Open Issues

| #   | Severity | Area     | Issue                                                                                                                                                    |
| --- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 17  | 🟡       | Backend  | ⚠️ Open — `message_service` needs `get_active_session_by_user(user_id)` for page refresh resumption (chat history load on session resume)                |
| 21  | 🟡       | Frontend | ⚠️ Open — `AttractionCard.tsx` not yet created (Xuan)                                                                                                    |
| 24  | 🟡       | Frontend | ⚠️ Partial — `HotelCard.tsx`, `AttractionCard.tsx`, `MapEmbed.tsx` still missing (Xuan); TripPage and FlightCard implemented ✅                          |
| 26  | 🟡       | Frontend | ⚠️ Partial — Minqi Phase 3: auth store, authService, protected route, fake loading steps, "Save & Finish Trip" button, chat history on reload still open |
| —   | 🟡       | Frontend | Standardize API error envelope: `APIError { detail: string; code?: string }` in `api.ts` (nice to have)                                                  |
| —   | 🟡       | Frontend | ⚠️ Open — Increase STT duration to at least 30s (Minqi)                                                                                                  |

---

## 🔗 Integration Points & Coordination

| When       | Who           | Action                                                                                             |
| ---------- | ------------- | -------------------------------------------------------------------------------------------------- |
| Day 1      | David + Xuan  | ✅ Finalize `TripItinerary` Pydantic schema together                                               |
| Day 1      | David + Minqi | ✅ Session ID creation flow — `chat.py` creates session on first message when `session_id` is null |
| Day 3      | David → All   | ✅ Commit `MOCK_ITINERARY` fixture — unblocks Minqi and Xuan immediately                           |
| Days 4–6   | Minqi → David | ✅ `deps.py` uses real JWT decode with `user_id` in token payload                                  |
| Days 4–9   | David         | ✅ `trip_service` + `trip_repo` created; wired into `chat_service.py`                              |
| Days 4–9   | Minqi → David | ✅ `message_service` wired into `chat.py` for message persistence                                  |
| Day 4      | David → Minqi | ✅ Voice hooks (useASR, useTTS, VoiceButton) integrated into ChatPage/InputBar                     |
| Days 13–20 | All           | 🔄 Integration week — full flow testing, bug fixes, demo polish                                    |

---

## 📅 Revised Timeline (20 Days)

| Days      | David                                                                                 | Minqi                                             | Xuan                                              |
| --------- | ------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- |
| **1–4**   | **Voice UI first** (useASR, useTTS, VoiceButton, TTSPlayer, text fallback)            | Auth backend (models, JWT, endpoints)             | Trip backend (model, repo, service, CRUD API)     |
| **1–6**   | **Live tools first** (transport, attractions, maps, flights, hotels, weather, search) | —                                                 | —                                                 |
| **4–9**   | Agent loop + `chat_service.py` + callbacks + `POST /chat`                             | Chat persistence (session + message models/repos) | Align schema with David, start trip UI components |
| **9–13**  | Preference extraction + auth wiring                                                   | Auth + Chat UI (LoginPage, ChatPage scaffold)     | Trip UI (ItineraryCard, MapEmbed, TripPage)       |
| **13–17** | Wire real auth + DB into chat, import chat_history_service                            | Wire message saving + polish Chat UI              | Polish trip UI + wire into routing                |
| **18–20** | 🔴 Buffer — integration bugs, demo prep                                               | 🔴 Buffer — integration bugs, demo prep           | 🔴 Buffer — integration bugs, demo prep           |

---

## 🚦 Definition of Done

| Member    | Done When                                                                                                      |
| --------- | -------------------------------------------------------------------------------------------------------------- |
| **David** | Agent returns valid `TripItinerary` from real tools; voice input/output works; preferences saved after session |
| **Minqi** | Register/login works; JWT protected routes; chat history persists and loads                                    |
| **Xuan**  | Trips saved and listed; full itinerary renders with map; booking links work                                    |
| **All**   | `docker-compose up` → full flow works: login → chat → get itinerary → view trip                                |

---

## 🔮 Future Considerations (Post-Deadline / v2)

> These features are **descoped** from the Apr 16 deadline. Revisit only if all core features are done before Day 15.

### SSE Streaming

> **⚠️ SSE + DB Session Risk**: Do not hold a DB transaction open during streaming. Save user message before stream starts, collect response in memory, and save assistant message via background task after stream finishes using a separate DB session.

- [x] Upgrade `POST /chat` → `GET /chat/stream` SSE endpoint ✅ (`POST /chat/stream` in `chat.py`)
- [x] Stream agent tool calls to frontend (casual setting) ✅ — Thinking bubbles show intermediate steps in UI
- [ ] **Trip planning NOT yet migrated to streaming** — Travel planning agent still uses full output waiting; needs refactor to SSE streaming
- [ ] Update `useChat.ts` for trip planning — consume SSE, show intermediate steps in UI during trip generation
- [ ] Add 3x auto-retry on SSE disconnect (currently 2 retries with exponential backoff in `_stream_chat`)

### Voice Upgrade

- [ ] Upgrade `useTTS.ts` from `window.speechSynthesis` → Gemini TTS
- [ ] **Gemini Live API** — single multimodal session replacing ASR + agent + TTS hooks entirely
