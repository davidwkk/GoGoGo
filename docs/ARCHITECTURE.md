# GoGoGo — Architecture

## Overview

GoGoGo is a travel agent AI app. Users chat with an AI to plan trips, receiving structured itineraries with flights, hotels, attractions, and weather. Built with FastAPI + SQLAlchemy (backend) and React + Vite + shadcn/ui (frontend).

---

## Tech Stack

| Layer            | Technology                                                                        |
| ---------------- | --------------------------------------------------------------------------------- |
| Backend          | FastAPI + SQLAlchemy 2.0 + PostgreSQL 16                                          |
| ORM / Migrations | Alembic                                                                           |
| Auth             | JWT (python-jose) + passlib bcrypt                                                |
| Agent            | Google Gemini 3 Flash + Gemini 3.1 Flash-Lite                                     |
| Tools            | Tavily (search), SerpAPI (flights/hotels), OpenWeatherMap, Google Maps, Wikipedia |
| Frontend         | React 18 + Vite + React Router + Zustand                                          |
| UI               | shadcn/ui + Tailwind CSS                                                          |
| Voice            | Web Speech API (ASR + TTS)                                                        |

---

## Backend Architecture

```
backend/
├── main.py                     # FastAPI app, lifespan, router registration
├── core/
│   ├── config.py                # pydantic-settings (env vars)
│   ├── security.py             # JWT encode/decode, password hashing
│   ├── logging.py              # Loguru setup
│   └── middleware.py            # CORS
├── api/
│   ├── deps.py                  # get_db, get_current_user (JWT)
│   └── routes/
│       ├── auth.py              # POST /auth/register, POST /auth/login
│       ├── chat.py              # POST /chat/stream (SSE)
│       ├── chat_sessions.py     # GET /chat/sessions/{id}/messages
│       ├── health.py            # GET /health
│       ├── trips.py             # GET/POST/DELETE /trips
│       └── users.py             # GET/PATCH /users/me
├── db/
│   ├── base.py                  # SQLAlchemy Base
│   └── models/
│       ├── user.py              # User (id, username, email, hashed_password, created_at)
│       ├── chat_session.py       # ChatSession (id, user_id, created_at)
│       ├── message.py            # Message (id, session_id, role, content, created_at)
│       ├── trip.py               # Trip (id, user_id, session_id, itinerary_json, created_at)
│       └── preference.py         # UserPreference (id, user_id, preferences_json)
├── repositories/
│   ├── user_repo.py
│   ├── session_repo.py
│   ├── message_repo.py
│   ├── trip_repo.py
│   └── preference_repo.py
├── services/
│   ├── streaming_service.py     # SSE agent loop, stream_agent_response(), TOOL_MAP
│   ├── message_service.py       # Append user/agent/trip messages
│   ├── preference_service.py     # Extract preferences via Gemini Flash-Lite
│   ├── trip_service.py          # Save/list trips
│   └── user_service.py          # Get/update user profile
├── agent/
│   ├── __init__.py              # Empty shim with lazy-import comment
│   ├── schemas.py               # Lightweight Pydantic models for tool responses
│   ├── callbacks.py             # Logging helpers (defined but unused)
│   └── tools/
│       ├── __init__.py          # Tool registration, _make_sync wrapper, ALL_TOOLS, TOOL_MAP
│       ├── search.py            # Tavily + SerpAPI fallback
│       ├── flights.py           # SerpAPI Google Flights
│       ├── hotels.py            # SerpAPI Google Hotels
│       ├── weather.py           # OpenWeatherMap
│       ├── maps.py              # Google Maps URL builder
│       ├── transport.py         # SerpAPI Google Maps (route/transport)
│       └── attractions.py       # Wikipedia REST API
└── schemas/
    ├── chat.py                  # ChatStreamRequest, ChatMessage
    ├── user.py                  # UserCreate, UserUpdate, UserResponse, UserPreference
    ├── enums.py                 # All enums (TravelStyle, HotelTier, etc.)
    └── itinerary.py             # TripItinerary, DayPlan, FlightItem, HotelItem, etc.
```

### Database Schema

```
users
├── id (PK)
├── username
├── email (unique)
├── hashed_password
└── created_at

user_preferences
├── id (PK)
├── user_id (FK → users.id, unique)
├── preferences_json (JSONB)
└── updated_at

chat_sessions
├── id (PK)
├── user_id (FK → users.id)
└── created_at

messages
├── id (PK)
├── session_id (FK → chat_sessions.id)
├── role ("user" | "assistant")
├── content
└── created_at

trips
├── id (PK)
├── user_id (FK → users.id)
├── session_id (FK → chat_sessions.id)
├── itinerary_json (JSONB)
└── created_at
```

---

## Frontend Architecture

```
frontend/src/
├── App.tsx                     # Router — BrowserRouter + Routes
├── main.tsx                   # ReactDOM.createRoot
├── index.css                  # Tailwind + CSS variables (light/dark)
├── lib/utils.ts               # cn() utility
├── services/
│   ├── api.ts                 # Axios client with JWT interceptor
│   └── tripService.ts         # GET/DELETE /trips
├── store/
│   └── index.ts               # Zustand store (chat state + voice)
├── hooks/
│   ├── useChat.ts             # POST /chat/stream (SSE), handle response
│   ├── useASR.ts              # Web Speech API (mic → transcript)
│   └── useTTS.ts              # Web Speech Synthesis (text → speech)
├── components/
│   ├── layout/
│   │   └── Sidebar.tsx        # Left nav bar (fixed, 56px wide)
│   ├── chat/
│   │   └── InputBar.tsx       # Text input + voice + send + generate plan
│   ├── voice/
│   │   ├── VoiceButton.tsx    # Mic toggle
│   │   └── TTSPlayer.tsx      # Auto-play TTS on response
│   └── ui/                    # shadcn/ui components (button, card, input, etc.)
└── pages/
    ├── ChatPage.tsx           # Sidebar + chat UI (messages + InputBar)
    ├── LoginPage.tsx           # Full-screen login/register (no sidebar)
    ├── ProfilePage.tsx         # Sidebar + User profile + preferences
    └── TripPage.tsx           # Sidebar + Saved trips list + detail
```

### Layout Design Rule

All main app pages (Chat, Trips, Profile) share a **single fixed sidebar on the left**:

- Width: 56px
- Top: black `GG` logo button (navigates to /chat)
- Middle: icon nav (MessageSquare → /chat, Map → /trips, User → /profile)
- Active route: filled black background; inactive: muted with hover states

The remaining full-width area is the page's content. **LoginPage is full-screen with no sidebar.**

### Routing

| Path       | Component   | Layout         |
| ---------- | ----------- | -------------- |
| `/`        | → redirect  | —              |
| `/login`   | LoginPage   | Full-screen    |
| `/chat`    | ChatPage    | Sidebar layout |
| `/trips`   | TripPage    | Sidebar layout |
| `/profile` | ProfilePage | Sidebar layout |
| `*`        | → redirect  | —              |

### API Client

`apiClient` (Axios) sends requests directly to `VITE_API_URL || http://localhost:8000`. JWT token from `localStorage.getItem("token")` is attached via request interceptor as `Authorization: Bearer <token>`.

### State Management

Zustand store (`store/index.ts`) holds:

- `ChatState`: `sessionId`, `messages[]`, `isLoading`, `voiceAvailable`
- Actions: `setSessionId`, `addMessage`, `clearMessages`, `setLoading`

---

## API Endpoints

| Method | Path                           | Auth | Description                                    |
| ------ | ------------------------------ | ---- | ---------------------------------------------- |
| POST   | `/auth/register`               | —    | Register with email + username + password      |
| POST   | `/auth/login`                  | —    | Login with email + password                    |
| GET    | `/health`                      | —    | Health check                                   |
| POST   | `/chat/stream`                 | JWT  | SSE stream: text chunks, tool calls, itinerary |
| GET    | `/chat/sessions/{id}/messages` | JWT  | Get session message history                    |
| GET    | `/users/me`                    | JWT  | Get current user profile                       |
| PATCH  | `/users/me`                    | JWT  | Update username/preferences                    |
| GET    | `/trips`                       | JWT  | List user's saved trips                        |
| GET    | `/trips/{id}`                  | JWT  | Get single trip with full itinerary            |
| DELETE | `/trips/{id}`                  | JWT  | Delete a saved trip                            |

---

## Agent Loop

```
User message
    ↓
POST /chat/stream → SSE streaming endpoint
    ↓
stream_agent_response() in streaming_service.py
    ↓
[Loop up to MAX_TOOL_ROUNDS=20 or 120s timeout]
    ↓
Gemini 3 Flash with automatic_function_calling=DISABLED
    ↓
Gemini generates content → stream chunks to client as SSE {"chunk": text}
    ↓
Extract function_call parts from response
    ↓
    ├─ finalize_trip_plan called:
    │   → Intercept locally (NOT in TOOL_MAP)
    │   → Validate all 4 required tools were called
    │   → generate_content with response_json_schema=TripItinerary
    │   → Yield SSE {"message_type": "itinerary", "itinerary": ...}
    │   → Stream ends
    │
    └─ Regular tool (get_attraction, get_weather, search_web, etc.):
        → Look up in TOOL_MAP
        → await tool_fn(**args)
        → Yield SSE {"tool_result": tool_name, "result": {...}}
        → Append role="function" message to conversation
        → Continue loop
    ↓
No function calls → Stream ends with {"done": True}
```

### SSE Event Types

```
{"message_id": id}              # Assistant message ID on stream start
{"chunk": text}                 # Streamed text content
{"model_thought": thought}      # Gemini reasoning thoughts
{"tool_call": name, "args": {}} # Tool call initiated
{"tool_result": name, "result": {}}  # Tool execution result
{"message_type": "finalizing", "status": "generating_trip_plan"}
{"message_type": "itinerary", "itinerary": {...}}
{"message_type": "error", "error": "..."}
{"done": True}                  # Stream complete
```

---

## Key Design Decisions

1. **Dict over Pydantic for mid-loop tool responses**: Tool functions return `dict` (not Pydantic models). The agent SDK serializes both equally, but Pydantic mid-loop adds validation overhead with no benefit since the agent doesn't enforce schemas on tool responses.

2. **Module-level dict cache for transport**: `lru_cache` does NOT work on async functions. Use `_cache: dict[tuple, dict] = {}` pattern.

3. **No redirects for auth**: Pages show their content first without backend calls when unauthenticated. No React Router redirects — users see the page and a sign-in prompt if needed.

4. **Direct API calls over Vite proxy**: The `apiClient` points directly to the backend URL. The Vite proxy only handles `/auth` and `/health` (actual backend prefixes) — frontend routes like `/chat` are not proxied.

5. **Manual tool dispatch over AutomaticFunctionCalling**: `automatic_function_calling` is disabled in Gemini config. Tool calls are manually extracted from the stream and dispatched via `TOOL_MAP` for full control over execution and DB persistence.

6. **`finalize_trip_plan` interception**: The `finalize_trip_plan` function declaration is known to the model but is intercepted by name in the loop (not in `TOOL_MAP`). It triggers a separate `generate_content` call with `response_json_schema=TripItinerary` to produce structured output.
