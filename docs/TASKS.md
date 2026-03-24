# 👥 `gogogo` — Task Assignment Document
> Deadline: 1 month | Team: 3 members | Infra: ✅ Already set up

---

## 🧭 Ownership Overview

| Area                                      | Owner                                         |
| ----------------------------------------- | --------------------------------------------- |
| Agent Core, Tools, Structured Output      | **David**                                     |
| Preference Extraction (Flash-Lite)        | **David**                                     |
| Voice — ASR + TTS                         | **David**                                     |
| SSE Streaming                             | **David** (Phase 2)                           |
| Auth — Register/Login, JWT, Login UI      | **Minqi**                                     |
| Chat — Session, Message History, Chat UI  | **Minqi**                                     |
| Trip — CRUD, Itinerary Display, Map Embed | **Xuan**                                      |
| DB Models + Migrations (all tables)       | **Shared** (each owns their feature's models) |

---

## 🙋 David — Agent Core + Voice

### 🎯 Goal
Build the intelligent core of the app: agent loop, all tools, structured output, preference extraction, and voice I/O.

### 📦 Files Owned
```
backend/app/agent/
├── agent.py                  # Gemini 3 Flash agent setup
├── callbacks.py              # Loguru logging callbacks
├── schemas.py                # TripItinerary + all Pydantic output models
└── tools/
    ├── search.py             # Tavily (primary) + SerpAPI fallback
    ├── flights.py            # SerpAPI Google Flights
    ├── hotels.py             # SerpAPI Google Hotels
    ├── weather.py            # OpenWeatherMap
    └── maps.py               # Google Maps Static/Embed URL builder

backend/app/services/
├── chat_service.py           # Invoke agent, return TripItinerary (David)
├── message_service.py        # Message persistence (Minqi)
└── preference_service.py     # Flash-Lite extraction + save preferences

backend/app/db/models/
└── preference.py             # user_preferences table

backend/app/repositories/
└── preference_repo.py        # Preference DB access (no expire_all!)

backend/app/schemas/
└── chat.py                   # ChatRequest / ChatResponse schemas

backend/app/api/routes/
└── chat.py                   # POST /chat (sync first, SSE later)

frontend/src/
├── hooks/
│   ├── useASR.ts             # Web Speech API hook
│   ├── useTTS.ts             # Web Speech Synthesis hook
│   └── useChat.ts            # Chat request hook (SSE in Phase 2)
├── components/voice/
│   ├── VoiceButton.tsx       # Mic toggle button
│   └── TTSPlayer.tsx         # Auto-play TTS on agent response
└── services/
    └── chatService.ts        # POST /chat API call
```

### ✅ Task Breakdown

#### Phase 1 — Agent Core (Week 1–2)
> **⚠️ Loop Bound**: Set `MAX_ITERATIONS = 5` in `agent.py` to prevent infinite loops if the LLM cycles.
> **⚠️ API Error Handling**: Each tool must catch exceptions and return `{"error": "..."}` dicts instead of raising — do not let external API failures become 500 errors.

- [ ] Implement all 5 tools in `tools/` — each returns typed dict
  - `search.py` — Tavily primary, SerpAPI fallback
  - `flights.py` — SerpAPI Google Flights
  - `hotels.py` — SerpAPI Google Hotels
  - `weather.py` — OpenWeatherMap current weather
  - `maps.py` — Build Google Maps Embed/Static URL
- [ ] Define all Pydantic output models in `agent/schemas.py`
  - `AttractionItem`, `HotelItem`, `FlightItem`, `DayPlan`, `TripItinerary`
- [ ] Set up Gemini 3 Flash agent in `agent.py`
  - Register all tools
  - Inject system prompt with user preferences placeholder
- [ ] Implement `callbacks.py` — Loguru logging for tool calls + agent finish
- [ ] Implement `chat_service.py`
  - Run agent loop → raw output
  - Call `generate_content` with response_schema → `TripItinerary`
  - Return structured result
- [ ] Expose `POST /chat` in `api/routes/chat.py`
  - Use **mocked auth** (`get_current_user` returns dummy user)
  - **Stub DB** (skip saving messages for now)
  - Accept `ChatRequest`, return `TripItinerary` JSON

#### Phase 2 — Preference Extraction (Week 2–3)
- [ ] Define `user_preferences` table in `db/models/preference.py`
- [ ] Write Alembic migration for `user_preferences`
- [ ] Implement `preference_repo.py` — upsert preferences
- [ ] Implement `preference_service.py`
  - Trigger extraction when session explicitly ended via `POST /chat/sessions/{id}/end`
  - Or trigger via `sendBeacon` on frontend `beforeunload` / logout
  - Call Gemini 3.1 Flash-Lite with full conversation history
  - Extract structured preferences from conversation
  - Save/update via `preference_repo`
- [ ] Inject saved preferences into agent system prompt in `agent.py`

#### Phase 3 — Voice UI (Week 3)
> **⚠️ Feedback Loop Risk**: `useASR` must explicitly mute/pause `useTTS` when recording starts. Add a pulsing mic visual indicator so users can distinguish listening vs. speaking states.

- [ ] `useASR.ts` — Web Speech API, start/stop recording, emit transcript
- [ ] `useTTS.ts` — Browser `window.speechSynthesis` (Phase 1); upgrade to Gemini TTS or Gemini Live later
- [ ] `VoiceButton.tsx` — Mic toggle, visual recording state
- [ ] `TTSPlayer.tsx` — Auto-play TTS when new assistant message arrives
- [ ] Wire voice into Chat UI (coordinate with Minqi's `ChatPage`)
- [ ] **Future upgrade:** Gemini Live API — single multimodal session replacing ASR + agent + TTS hooks

#### Phase 4 — SSE Streaming (Week 4)
> **⚠️ SSE + DB Session Risk**: Do not hold a DB transaction open during streaming. Save user message before stream starts, collect response in memory, and save assistant message via background task after stream finishes using a separate DB session.

- [ ] Upgrade `POST /chat` → `GET /chat/stream` SSE endpoint
- [ ] Stream agent thinking steps + tool calls to frontend
- [ ] Update `useChat.ts` — consume SSE, show intermediate steps in UI
- [ ] Add 3x auto-retry on SSE disconnect

### 🧪 Tests to Write
```
backend/tests/unit/
├── test_tools/
│   ├── test_search.py        # Returns expected shape
│   ├── test_flights.py
│   ├── test_hotels.py
│   ├── test_weather.py
│   └── test_maps.py
└── test_schemas/
    └── test_trip_itinerary.py  # TripItinerary validates correctly

backend/tests/integration/
└── test_chat/
    └── test_chat_endpoint.py   # POST /chat returns TripItinerary shape
```

### ⚠️ Mocking Strategy (Unblock yourself)
```python
# deps.py — temporary mock, swap when Minqi delivers auth
async def get_current_user():
    return User(id=1, username="dev", email="dev@test.com")
```
> Remove mock once Minqi's JWT middleware is ready.

---

## 🙋 Minqi — Auth + Chat

### 🎯 Goal
Own the full authentication flow and chat session/message persistence, end-to-end from DB to UI.

### 📦 Files Owned
```
backend/app/db/models/
├── user.py                   # users table
├── chat_session.py           # chat_sessions table
└── message.py                # messages table

backend/app/repositories/
├── user_repo.py              # User DB access
├── session_repo.py           # ChatSession DB access
└── message_repo.py           # Message DB access

backend/app/schemas/
├── auth.py                   # RegisterRequest, LoginRequest, TokenResponse
└── user.py                   # UserOut schema

backend/app/services/
├── auth_service.py           # Register, login, password verify
└── message_service.py        # Message persistence (append, get history)

backend/app/core/
└── security.py               # JWT encode/decode, password hashing

backend/app/api/
├── routes/
│   ├── auth.py               # POST /auth/register, POST /auth/login
│   └── users.py              # GET /users/me
└── deps.py                   # get_current_user, get_db

frontend/src/
├── pages/
│   └── LoginPage.tsx         # Login + Register form
├── hooks/
│   └── useAuth.ts            # Auth state, login/logout actions
├── store/                    # Zustand auth slice
└── services/
    └── authService.ts        # POST /auth/register, /auth/login
```

### ✅ Task Breakdown

#### Phase 1 — Auth Backend (Week 1–2)
- [ ] Define `users` table in `db/models/user.py`
- [ ] Write Alembic migration for `users`
- [ ] Implement `security.py`
  - `hash_password`, `verify_password` (passlib bcrypt)
  - `create_access_token`, `decode_access_token` (python-jose)
- [ ] Implement `auth_service.py` — register (check duplicate), login (verify + issue token)
- [ ] Implement `user_repo.py` — `get_by_email`, `get_by_id`, `create`
- [ ] Expose `POST /auth/register`, `POST /auth/login` in `api/routes/auth.py`
- [ ] Implement `deps.py`
  - `get_db` — async session dependency
  - `get_current_user` — decode JWT, return User
- [ ] Expose `GET /users/me` in `api/routes/users.py`

#### Phase 2 — Chat Persistence (Week 2–3)
- [ ] Define `chat_sessions` + `messages` tables
- [ ] Write Alembic migrations for both tables
- [ ] Implement `session_repo.py` — create session, get by user
- [ ] Implement `message_repo.py` — append message, get history by session
- [ ] Update `chat_service.py` (coordinate with David)
  - Save user message before agent call
  - Save assistant response after agent call
- [ ] Expose session history endpoint: `GET /chat/sessions/{session_id}/messages`

#### Phase 3 — Auth + Chat UI (Week 3)
- [ ] `LoginPage.tsx` — login + register tabs, form validation, error display
- [ ] `useAuth.ts` — login/logout, persist token in localStorage
- [ ] Zustand auth store — `user`, `token`, `isAuthenticated`
- [ ] `authService.ts` — API calls with Axios
- [ ] Protected route wrapper — redirect to login if unauthenticated
- [ ] `ChatPage.tsx` scaffold — message list, input bar (coordinate with David for voice wiring)
- [ ] `MessageBubble.tsx` — user vs assistant styling
- [ ] Display chat history on session load

### 🧪 Tests to Write
```
backend/tests/unit/
└── test_security/
    ├── test_jwt.py           # encode/decode roundtrip
    └── test_password.py      # hash + verify

backend/tests/integration/
└── test_auth/
    ├── test_register.py      # 201, duplicate 409
    └── test_login.py         # 200 + token, wrong password 401
```

### 🤝 Handoff to Team
> Once `deps.py` → `get_current_user` is ready, notify **David** to remove the mock.
> Once `message_repo.py` is ready, notify **David** to wire message saving in `chat_service.py`.

---

## 🙋 Xuan — Trip + Itinerary Display

### 🎯 Goal
Own the full trip persistence and display flow — saving structured itineraries, CRUD API, and the rich frontend itinerary/map UI.

### 📦 Files Owned
```
backend/app/db/models/
└── trip.py                   # trips table (itinerary_json as JSONB)

backend/app/repositories/
└── trip_repo.py              # Trip DB access

backend/app/schemas/
└── trip.py                   # TripOut, TripCreate, TripSummary schemas

backend/app/services/
└── trip_service.py           # Save trip, list trips, get trip by id

backend/app/api/routes/
└── trips.py                  # GET/POST/DELETE /trips

frontend/src/
├── pages/
│   └── TripPage.tsx          # Trip history list + detail view
├── components/
│   ├── trip/
│   │   ├── ItineraryCard.tsx  # Day-by-day plan display
│   │   ├── HotelCard.tsx      # Hotel info + booking link
│   │   ├── FlightCard.tsx     # Flight info + booking link
│   │   └── AttractionCard.tsx # Attraction info + photo
│   └── map/
│       └── MapEmbed.tsx       # Google Maps Embed iframe
└── services/
    └── tripService.ts         # GET/POST/DELETE /trips API calls
```

### ✅ Task Breakdown

#### Phase 1 — Trip Backend (Week 1–2)
- [ ] Define `trips` table in `db/models/trip.py`
  - `itinerary_json` as JSONB column
- [ ] Write Alembic migration for `trips`
- [ ] Implement `trip_repo.py`
  - `create`, `get_by_id`, `get_by_user`, `delete`
- [ ] Implement `trip_service.py`
  - `save_trip(user_id, session_id, itinerary: TripItinerary)` — serialize + store
  - `get_trips(user_id)` — list summaries
  - `get_trip(trip_id)` — full detail
- [ ] Expose CRUD in `api/routes/trips.py`
  - `POST /trips` — save trip (called by `chat_service` after agent finishes)
  - `GET /trips` — list user's trips
  - `GET /trips/{trip_id}` — full itinerary
  - `DELETE /trips/{trip_id}` — delete

#### Phase 2 — Coordinate with David (Week 2–3)
- [ ] **Only David** confirms the `TripItinerary` Pydantic schema (defined in `agent/schemas.py`) — no other team member approves schema changes
- [ ] `trip_service.save_trip()` accepts `TripItinerary` directly — no re-parsing
- [ ] Notify **David** when `trip_service.save_trip()` is ready to wire into `chat_service.py`

#### Phase 3 — Trip UI (Week 3)
- [ ] `TripPage.tsx` — list of saved trips, click to expand detail
- [ ] `ItineraryCard.tsx` — render `DayPlan[]`, day tabs or accordion
- [ ] `HotelCard.tsx` — name, price, rating, booking link button
- [ ] `FlightCard.tsx` — airline, departure/arrival, price, booking link
- [ ] `AttractionCard.tsx` — name, category badge, photo, rating
- [ ] `MapEmbed.tsx` — render Google Maps Embed iframe from `map_embed_url`
- [ ] `tripService.ts` — Axios calls for all trip endpoints
- [ ] Wire `TripPage` into app routing (coordinate with Minqi's auth guard)

### 🧪 Tests to Write
```
backend/tests/integration/
└── test_trips/
    ├── test_save_trip.py     # POST /trips saves correctly
    ├── test_list_trips.py    # GET /trips returns user's trips only
    └── test_get_trip.py      # GET /trips/{id} returns full itinerary
```

### 🤝 Handoff to Team
> Depends on **David** for `TripItinerary` schema — align in Week 1.
> Depends on **Minqi** for auth guard on trip routes — use mock `get_current_user` until ready.

---

## 🔗 Integration Points & Coordination

| When     | Who           | Action                                                                 |
| -------- | ------------- | ---------------------------------------------------------------------- |
| Week 1   | David + Xuan  | Finalize `TripItinerary` Pydantic schema together                      |
| Week 2   | Minqi → David | `deps.py` ready → David removes mock `get_current_user`                |
| Week 2–3 | Xuan → David  | `trip_service.save_trip()` ready → David wires into `chat_service.py`  |
| Week 2–3 | Minqi → David | `message_repo` ready → David wires message saving in `chat_service.py` |
| Week 3   | David → Minqi | Voice hooks ready → wire into `ChatPage.tsx`                           |
| Week 4   | All           | SSE upgrade — David upgrades endpoint, Minqi updates `useChat.ts`      |

## 📋 Follow-up Items (Post-SSE Loading UX)

| #   | Owner                | Task                                                                                                                                                                     |
| --- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Frontend (Minqi)** | Display fake loading steps ("Searching flights...", "Checking weather...") during sync POST request to keep user engaged before SSE is ready                             |
| 2   | **Minqi**            | Build `chat_history_service.py` with `append_user_message()` and `append_agent_message()` methods                                                                        |
| 3   | **David**            | Import and call `chat_history_service` methods inside `chat_service.py` workflow                                                                                         |
| 4   | **Xuan**             | `trip_repo`: Call `itinerary.model_dump(mode='json')` before saving to SQLAlchemy; validate back with `TripItinerary.model_validate(db_obj.itinerary_json)` on retrieval |
| 5   | **Frontend (Minqi)** | Add "Save & Finish Trip" button in UI that explicitly calls `POST /chat/sessions/{id}/end`                                                                               |

---

## 📅 Suggested Timeline

| Week  | David                                                 | Minqi                                             | Xuan                                              |
| ----- | ----------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- |
| **1** | Agent tools + Pydantic schemas + `agent.py`           | Auth backend (models, JWT, endpoints)             | Trip backend (model, repo, service, CRUD API)     |
| **2** | `chat_service.py` + `POST /chat` (mocked) + callbacks | Chat persistence (session + message models/repos) | Align schema with David, start trip UI components |
| **3** | Preference extraction + Voice UI (ASR/TTS)            | Auth + Chat UI (LoginPage, ChatPage scaffold)     | Trip UI (ItineraryCard, MapEmbed, TripPage)       |
| **4** | SSE streaming + wire real auth + DB                   | Wire message saving + polish Chat UI              | Polish trip UI + integration testing              |

---

## 🚦 Definition of Done

| Member    | Done When                                                                                                      |
| --------- | -------------------------------------------------------------------------------------------------------------- |
| **David** | Agent returns valid `TripItinerary` from real tools; voice input/output works; preferences saved after session |
| **Minqi** | Register/login works; JWT protected routes; chat history persists and loads                                    |
| **Xuan**  | Trips saved and listed; full itinerary renders with map; booking links work                                    |
| **All**   | `docker-compose up` → full flow works: login → chat → get itinerary → view trip                                |
