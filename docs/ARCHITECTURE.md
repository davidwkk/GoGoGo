# GoGoGo — Architecture

## Overview

GoGoGo is a travel agent AI app. Users chat with an AI to plan trips, receiving structured itineraries with flights, hotels, attractions, and weather. Built with FastAPI + SQLAlchemy (backend) and React + Vite + shadcn/ui (frontend).

---

## Tech Stack

| Layer            | Technology                                                             |
| ---------------- | ---------------------------------------------------------------------- |
| Backend          | FastAPI + SQLAlchemy 2.0 + PostgreSQL 16                               |
| ORM / Migrations | Alembic                                                                |
| Auth             | JWT (python-jose) + bcrypt (direct)                                    |
| Agent            | Google Gemini 3 Flash + Gemini 3.1 Flash-Lite + Gemini Live            |
| Tools            | Tavily (search), SerpAPI (flights/hotels), OpenWeatherMap, Google Maps |
| Frontend         | React 18 + Vite + React Router + Zustand                               |
| UI               | shadcn/ui + Tailwind CSS                                               |
| Voice I/O        | Web Speech API (ASR + TTS) + Gemini Live (WebSocket)                   |
| Proxy            | SOCKS5 proxy support for LLM calls (optional VPN routing)              |

---

## Backend Architecture

```
backend/
├── main.py                       # FastAPI app, lifespan, router registration
├── core/
│   ├── config.py                 # pydantic-settings (env vars, backup models, proxy)
│   ├── security.py               # JWT encode/decode, bcrypt password hashing
│   ├── logging.py                # Loguru setup
│   └── middleware.py              # CORS
├── api/
│   ├── deps.py                   # get_db, get_current_user, get_current_user_optional
│   └── routes/
│       ├── auth.py               # POST /auth/register, POST /auth/login
│       ├── chat.py               # POST /chat/stream (SSE)
│       ├── chat_sessions.py      # GET /chat/sessions/{id}/messages
│       ├── live.py                # WebSocket /live/ws (Gemini Live proxy)
│       ├── health.py             # GET /health
│       ├── trips.py              # GET/POST/DELETE /trips
│       └── users.py              # GET/PATCH /users/me
├── db/
│   ├── base.py                   # SQLAlchemy Base
│   ├── session.py                # get_db dependency
│   └── models/
│       ├── user.py               # User (id, username, email, hashed_password, created_at)
│       ├── guest.py              # Guest (id, created_at) — anonymous sessions
│       ├── chat_session.py       # ChatSession (id, user_id, guest_id, created_at)
│       ├── message.py            # Message (id, session_id, role, content, message_type)
│       ├── trip.py               # Trip (id, user_id, session_id, itinerary_json)
│       └── preference.py         # UserPreference (id, user_id, preferences_json, updated_at)
├── repositories/
│   ├── user_repo.py
│   ├── session_repo.py
│   ├── message_repo.py
│   ├── trip_repo.py
│   └── preference_repo.py
├── services/
│   ├── streaming_service.py      # SSE agent loop, stream_agent_response()
│   ├── message_service.py        # Append user/assistant/trip messages
│   ├── preference_service.py     # Extract preferences via Gemini Flash-Lite
│   ├── trip_service.py           # Save/list trips
│   └── user_service.py           # Get/update user profile
├── agent/
│   ├── schemas.py                # Lightweight Pydantic models for tool responses
│   ├── callbacks.py              # Logging helpers
│   └── tools/
│       ├── __init__.py           # Tool registry, _make_sync wrapper, ALL_TOOLS, TOOL_MAP
│       ├── search.py             # Tavily + SerpAPI fallback
│       ├── flights.py            # SerpAPI Google Flights (round-trip with departure_token)
│       ├── hotels.py             # SerpAPI Google Hotels
│       ├── weather.py            # OpenWeatherMap
│       ├── maps.py               # Google Maps URL builder (embed + static)
│       ├── transport.py          # SerpAPI Google Maps (route/transport)
│       └── attractions.py        # Wikipedia REST API
├── schemas/
│   ├── auth.py                   # RegisterRequest, LoginRequest, TokenResponse
│   ├── chat.py                   # ChatRequest, ChatStreamRequest
│   ├── user.py                   # UserCreate, UserUpdate, UserResponse
│   ├── enums.py                 # All enums (TravelStyle, HotelTier, etc.)
│   └── itinerary.py             # TripItinerary, DayPlan, FlightItem, HotelItem, etc.
└── utils/
    └── stream_utils.py           # Proxy reachability checks
```

### Database Schema

```
users
├── id (PK, UUID)
├── username
├── email (unique)
├── hashed_password
└── created_at

guests
├── id (PK, UUID)
└── created_at

user_preferences
├── id (PK)
├── user_id (FK → users.id, unique)
├── preferences_json (JSONB)
└── updated_at

chat_sessions
├── id (PK)
├── user_id (FK → users.id, nullable)
├── guest_id (FK → guests.id, nullable)
└── created_at

messages
├── id (PK)
├── session_id (FK → chat_sessions.id)
├── role ("user" | "assistant" | "function")
├── content
├── message_type ("text" | "itinerary" | "tool_result", nullable)
└── created_at

trips
├── id (PK, UUID)
├── user_id (FK → users.id)
├── session_id (FK → chat_sessions.id)
├── itinerary_json (JSONB)
└── created_at
```

---

## Frontend Architecture

```
frontend/src/
├── App.tsx                      # Router — BrowserRouter + Routes
├── main.tsx                    # ReactDOM.createRoot
├── index.css                   # Tailwind + CSS variables (light/dark)
├── lib/utils.ts                # cn() utility
├── services/
│   ├── api.ts                  # Axios client with JWT interceptor
│   ├── authService.ts          # Login/register
│   └── tripService.ts          # GET/DELETE /trips
├── store/
│   ├── index.ts                # Zustand store (chat state + voice)
│   └── authStore.ts            # Zustand auth store (token, user)
├── hooks/
│   ├── useChat.ts              # POST /chat/stream (SSE)
│   ├── useASR.ts               # Web Speech API (mic → transcript)
│   ├── useTTS.ts               # Web Speech Synthesis (text → speech)
│   └── useLiveSession.ts       # WebSocket session for Gemini Live voice
├── components/
│   ├── layout/
│   │   ├── AppLayout.tsx       # Page wrapper with sidebar
│   │   └── Sidebar.tsx         # Left nav (56px, icon-based)
│   ├── chat/
│   │   ├── InputBar.tsx        # Text input + voice + send + generate plan
│   │   └── TravelSettingsBar.tsx # Travel type selection bar
│   ├── voice/
│   │   ├── VoiceButton.tsx     # Mic toggle
│   │   └── TTSPlayer.tsx       # Auto-play TTS on response
│   ├── trip/
│   │   ├── FlightCard.tsx      # Flight details card
│   │   ├── HotelCard.tsx        # Hotel details card
│   │   ├── AttractionCard.tsx  # Attraction details card
│   │   └── MapEmbed.tsx        # Google Maps embed iframe
│   └── ui/                     # shadcn/ui components
└── pages/
    ├── ChatPage.tsx            # Sidebar + chat UI
    ├── LivePage.tsx            # Gemini Live voice chat
    ├── TripPage.tsx            # Sidebar + saved trips list + detail
    ├── ProfilePage.tsx         # Sidebar + user profile + preferences
    ├── PreferencesPage.tsx     # User preferences editor
    └── LoginPage.tsx           # Full-screen login/register
```

### Routing

| Path           | Component       | Layout         |
| -------------- | --------------- | -------------- |
| `/`            | → redirect      | —              |
| `/login`       | LoginPage       | Full-screen    |
| `/chat`        | ChatPage        | Sidebar layout |
| `/live`        | LivePage        | Sidebar layout |
| `/trips`       | TripPage        | Sidebar layout |
| `/profile`     | ProfilePage     | Sidebar layout |
| `/preferences` | PreferencesPage | Sidebar layout |
| `*`            | → redirect      | —              |

---

## API Endpoints

| Method | Path                           | Auth | Description                               |
| ------ | ------------------------------ | ---- | ----------------------------------------- |
| POST   | `/auth/register`               | —    | Register with email + username + password |
| POST   | `/auth/login`                  | —    | Login with email + password               |
| GET    | `/health`                      | —    | Health check                              |
| POST   | `/chat/stream`                 | JWT  | SSE stream: text, tool calls, itinerary   |
| GET    | `/chat/sessions/{id}/messages` | JWT  | Get session message history               |
| WS     | `/live/ws`                     | JWT  | Gemini Live voice (WebSocket proxy)       |
| GET    | `/users/me`                    | JWT  | Get current user profile                  |
| PATCH  | `/users/me`                    | JWT  | Update username/preferences               |
| GET    | `/trips`                       | JWT  | List user's saved trips                   |
| GET    | `/trips/{id}`                  | JWT  | Get single trip with full itinerary       |
| DELETE | `/trips/{id}`                  | JWT  | Delete a saved trip                       |

---

## Agent Loop

```
User message → POST /chat/stream
    ↓
stream_agent_response() — up to MAX_TOOL_ROUNDS=20 or 120s timeout
    ↓
Gemini 3 Flash (default) or user-selected model
    ↓
[Loop]
    ├─ Stream text chunks → SSE {"chunk": text}
    ├─ Extract function_call parts
    └─ If tool call:
        ├─ finalize_trip_plan (intercepted locally):
        │   → Validate all required tools called
        │   → generate_content with response_json_schema=TripItinerary
        │   → Yield SSE {"message_type": "itinerary", ...}
        │   → Auto-save trip to DB if authenticated
        │
        └─ Regular tool (TOOL_MAP):
            → await tool_fn(**args)
            → Yield SSE {"tool_result": tool_name, "result": {...}}
            → Persist to DB for cross-request context
            → Continue loop
    ↓
No function calls → SSE {"done": True}
```

### Tool Map

| Tool               | Function                       |
| ------------------ | ------------------------------ |
| `get_attraction`   | Wikipedia REST API             |
| `get_weather`      | OpenWeatherMap                 |
| `search_web`       | Tavily + SerpAPI fallback      |
| `search_flights`   | SerpAPI Google Flights         |
| `search_hotels`    | SerpAPI Google Hotels          |
| `get_transport`    | SerpAPI Google Maps transport  |
| `build_embed_url`  | Google Maps embed URL builder  |
| `build_static_url` | Google Maps static URL builder |

### SSE Event Types

```
{"message_id": id}                    # Assistant message ID on stream start
{"chunk": text}                       # Streamed text content
{"model_thought": thought}            # Gemini reasoning thoughts
{"tool_call": name, "args": {}}       # Tool call initiated
{"tool_result": name, "result": {}}  # Tool execution result
{"message_type": "finalizing"}        # Trip plan generation started
{"message_type": "itinerary", ...}    # Structured TripItinerary payload
{"message_type": "error", "error": "..."}
{"trip_saved": true}                  # Trip auto-saved to DB
{"done": True}                        # Stream complete
```

---

## Key Design Decisions

1. **Dict over Pydantic for mid-loop tool responses**: Tool functions return `dict`. The agent SDK serializes both equally, but Pydantic mid-loop adds validation overhead with no benefit.

2. **Module-level dict cache for transport**: `lru_cache` does NOT work on async functions. Use `_cache: dict[tuple, dict] = {}` pattern.

3. **finalize_trip_plan interception**: The `finalize_trip_plan` function is declared as a Gemini tool but intercepted locally (not in `TOOL_MAP`). It triggers a separate `generate_content` call with `response_json_schema=TripItinerary`.

4. **Thinking config**: Only enabled for 3.x model series. Disabled for 2.x (gemini-2.5-flash).

5. **Guest sessions**: Anonymous users can chat but cannot save trips. Guest ID stored in `chat_sessions.guest_id`.

6. **SOCKS5 proxy**: Optional VPN routing for LLM calls via `LLM_PROXY_ENABLED` + `SOCKS5_PROXY_URL` config.
