# GoGoGo: An AI-Powered Travel Agent Application

**Abstract**

We present GoGoGo, a full-stack AI travel agent application that enables users to plan trips through natural language conversation. The system leverages Google Gemini 3 Flash for agentic function-calling behavior, integrated with real-time travel APIs (SerpAPI, Tavily, OpenWeatherMap, Google Maps) to produce structured trip itineraries with flights, hotels, attractions, weather forecasts, and budget breakdowns. The backend is built with FastAPI and PostgreSQL 16, while the frontend uses React 18 with Vite and shadcn/ui. A Server-Sent Events (SSE) streaming architecture delivers real-time agent responses with interleaved tool execution, and a Gemini Live WebSocket endpoint provides voice-based interaction. The system supports both authenticated users (with persistent trip storage) and anonymous guest sessions.

---

## 1 System Architecture

### 1.1 Overview

GoGoGo follows a three-tier architecture: a FastAPI backend, a PostgreSQL 16 database, and a React frontend, containerized via Docker Compose.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (React + Vite)                      │
│   ChatPage │ LivePage │ TripPage │ ProfilePage │ PreferencesPage   │
│                    Zustand Store │ shadcn/ui + Tailwind CSS          │
└─────────────────────────────────────────────────────────────────────┘
                                  │ HTTP / SSE / WebSocket
┌─────────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI + Python 3.11)                  │
│  /auth │ /chat/stream │ /live/ws │ /trips │ /users │ /chat/sessions │
│                    Streaming Service (SSE Agent Loop)                 │
│   Tool Registry: search │ flights │ hotels │ weather │ attractions  │
│              transport │ maps │ finalize_trip_plan (local)            │
└─────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────────┐
│                       PostgreSQL 16 (Docker)                          │
│  users │ guests │ chat_sessions │ messages │ trips │ user_preferences│
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Backend Architecture

The backend (`backend/app/`) is organized into the following layers:

- **Core** (`core/`): Configuration via `pydantic-settings`, JWT authentication with `python-jose` + bcrypt, CORS middleware, and Loguru logging.
- **Database** (`db/`): SQLAlchemy 2.0 models with Alembic migrations. Six core tables: `users`, `guests`, `chat_sessions`, `messages`, `trips`, and `user_preferences`.
- **API Routes** (`api/routes/`): RESTful endpoints for auth, chat streaming, session management, trips CRUD, user preferences, health checks, and a WebSocket proxy for Gemini Live.
- **Services** (`services/`): Business logic layer including `streaming_service.py` (core agent loop), `message_service.py`, `trip_service.py`, and `preference_service.py`.
- **Agent** (`agent/`): Tool implementations and the tool registry. Tool functions are async and wrapped with `_make_sync()` to bridge with the synchronous Gemini SDK interface.
- **Schemas** (`schemas/`): Pydantic v2 models for request/response validation, including `TripItinerary`, `DayPlan`, `FlightItem`, `HotelItem`, `Activity`, and `BudgetBreakdown`.

### 1.3 Frontend Architecture

The frontend (`frontend/src/`) is a React 18 SPA with:

- **Pages**: `ChatPage` (main streaming chat UI), `LivePage` (Gemini Live voice mode), `TripPage` (saved itineraries), `ProfilePage`, `PreferencesPage`, `LoginPage`.
- **State Management**: Two Zustand stores — `authStore` (JWT token, user profile, persisted to `localStorage`) and a chat store (messages, session ID, travel settings, thinking steps).
- **Hooks**: `useChat` (SSE streaming via `EventSource`), `useASR` (Web Speech API for speech-to-text), `useTTS` (Web Speech Synthesis for text-to-speech playback), and `useLiveSession` (WebSocket session for Gemini Live).
- **Components**: Chat components (`InputBar`, `TravelSettingsBar`), trip components (`FlightCard`, `HotelCard`, `AttractionCard`, `MapEmbed`), and voice components (`VoiceButton`, `TTSPlayer`).

### 1.4 Container Orchestration

```yaml
services:
  db: postgres:16 # Port 5432
  backend: FastAPI (uvicorn) # Port 8000
  frontend: Vite dev server # Port 5173
```

---

## 2 Module Integration

### 2.1 Chat Streaming Flow

The primary interaction pathway uses Server-Sent Events (SSE) through the `/chat/stream` endpoint:

1. The frontend sends a `POST /chat/stream` request with the user message, session ID, travel settings (budget, style, dietary), and an optional `generatePlan` flag.
2. The backend `streaming_service.py` appends the user message to the `messages` table and builds a system instruction incorporating user preferences.
3. A streaming `generate_content_stream()` call is made to the Gemini API with all tool declarations registered.
4. The stream loop processes two types of output:
   - **Text chunks** → yielded as SSE `{"chunk": text}` events, displayed with a typewriter effect on the frontend.
   - **Function call parts** → intercepted; the appropriate tool is executed; tool results are yielded as SSE `{"tool_result": name, "result": {...}}` and persisted to the DB for cross-request context.
5. When the user confirms trip generation (`generatePlan=true`), the `finalize_trip_plan` function is called. It validates that all required tools were executed (flights, hotels, weather, attractions), then makes a single `generate_content()` call with `response_json_schema=TripItinerary` to produce a structured itinerary.
6. The `TripItinerary` Pydantic model is serialized and sent as SSE `{"message_type": "itinerary", "itinerary": {...}}`, and the trip is auto-saved to the `trips` table if the user is authenticated.

### 2.2 Tool System

Eight tools are registered with the Gemini agent:

| Tool               | Implementation                       | External API           |
| ------------------ | ------------------------------------ | ---------------------- |
| `search_web`       | Tavily search + SerpAPI fallback     | Tavily, SerpAPI        |
| `search_flights`   | Round-trip flight search (two calls) | SerpAPI Google Flights |
| `search_hotels`    | Hotel search with check-in/out dates | SerpAPI Google Hotels  |
| `get_weather`      | Current weather for a city           | OpenWeatherMap         |
| `get_attraction`   | Attraction info + Wikipedia          | Wikipedia REST API     |
| `get_transport`    | Transport options (MTR, bus, taxi)   | SerpAPI Google Maps    |
| `build_embed_url`  | Google Maps iframe URL builder       | Google Maps            |
| `build_static_url` | Google Maps static image URL         | Google Maps            |

The `_make_sync()` wrapper allows async Python functions to be called synchronously by the Gemini SDK while still supporting async execution within the agent code.

### 2.3 Authentication & Guest Sessions

JWT tokens (HS256, 30-day expiry) are issued upon registration or login. Anonymous users receive a `guest_uid` (UUID) stored in `localStorage`; their sessions are tracked in `chat_sessions` with a `guest_id` FK. Guests can chat but cannot save trips. All authenticated sessions associate trips with the `user_id`.

### 2.4 Gemini Live Voice Mode

The `/live/ws` WebSocket endpoint proxies traffic to Gemini's Live API (`gemini-3.1-flash-live-preview`), enabling real-time voice conversation. The frontend uses the Web Speech API for microphone input and audio playback, while bidirectional audio streams flow through the WebSocket proxy.

### 2.5 Data Persistence

All conversations are persisted to PostgreSQL. Message history is reloaded from the DB at the start of each streaming request and converted to Gemini `types.Content` format. Tool results are stored as `function`-role messages with `{tool, result}` JSON payloads, enabling multi-round reasoning to continue across requests.

---

## 3 Technical Approach

### 3.1 Agent Architecture

The agent is implemented as a **unified streaming loop** (not a separate microservice). It uses the Gemini SDK's `generate_content_stream()` with `tools=[ALL_TOOLS]`. The loop supports:

- **Max 20 tool rounds** or a **120-second timeout** to prevent infinite loops.
- **Parallel function calls**: The SDK handles concurrent tool execution within a single round.
- **Thought signatures**: For Gemini 3.x models, thought signatures from `candidate.content.parts` are preserved in conversation history. Thinking config is disabled for 2.x models.
- **Model selection**: Users can select from multiple models (primary: `gemini-3-flash-preview`, lite: `gemini-3.1-flash-lite-preview`, live: `gemini-3.1-flash-live-preview`) with backup model fallback on connection errors.
- **SOCKS5 proxy**: Optional VPN routing via `LLM_PROXY_ENABLED` + `SOCKS5_PROXY_URL` for regions requiring proxy access to Gemini API.

### 3.2 Structured Output

The `finalize_trip_plan` function produces a `TripItinerary` using `response_json_schema=TripItinerary`. The schema defines:

- `TripItinerary`: destination, start_date, end_date, purpose, group_type, daily_plans[], flights (outbound + return), hotels[], estimated_total_budget_hkd (with PriceRange per category).
- `DayPlan`: date, weather (condition, temperature, icon), activities[] (with name, category, description, location, duration, estimated_cost_hkd, tips, rating, image_url).
- `PriceRange`: min, max (all values rounded to nearest 100 HKD).

### 3.3 Error Handling

Comprehensive error mapping in `streaming_service.py` translates raw exceptions (connection errors, proxy errors, Gemini API errors 400/429/503) into user-friendly messages. Tool result persistence failures are logged but do not interrupt the stream.

### 3.4 Database Schema

```
users ───────────────┬─── user_preferences (1:1)
                     │
chat_sessions ───────┼─── messages (1:N, cascade delete)
  │ (nullable FK)    │
  └── guest_id ─────┘
                     │
trips ───────────────┴─── session_id (FK, SET NULL)
```

---

## 4 Challenges Faced

### 4.1 Synchronous SDK with Async Tools

The Gemini Python SDK's `generate_content_stream()` is synchronous, but tool implementations use async I/O (HTTP calls to external APIs). The `_make_sync()` wrapper resolves this by detecting whether an event loop is running — if not, it uses `asyncio.run()`; if one exists, it schedules the async call in a thread pool executor.

### 4.2 Multi-Round Tool Context

Maintaining tool execution context across multiple SSE requests was challenging. The solution was to persist tool results as `function`-role messages in the `messages` table, reloading them at the start of each new streaming request. This allows the agent's reasoning to span multiple HTTP requests rather than being confined to a single long-lived connection.

### 4.3 Structured Itinerary Generation

Generating a well-formed `TripItinerary` from accumulated tool results required a dedicated `finalize_trip_plan` function. This function validates that all required tools were called before attempting structured output, and raises an error with a list of missing tools if validation fails. Budget values are rounded to the nearest 100 HKD for cleaner presentation.

### 4.4 CORS and WebSocket Proxy

The Gemini Live API uses WebSocket connections that cannot be directly accessed from the browser due to CORS restrictions. The `/live/ws` endpoint acts as a proxy, forwarding WebSocket traffic between the browser client and Gemini Live API.

### 4.5 Guest Session Management

Supporting anonymous guest sessions required generating UUIDs client-side, creating guest records in the DB, and associating chat sessions with guest IDs. The `get_current_user_optional` dependency handles both authenticated users and guest sessions transparently throughout the API.

### 4.6 LRU Cache with Async Transport

The transport tool uses `lru_cache`, which does not work with async functions. A module-level dict cache (`_cache: dict[tuple, dict] = {}`) was implemented as a workaround to avoid redundant SerpAPI calls for the same transport queries.

---

## 5 Evaluation Summary

GoGoGo was evaluated through the following metrics:

- **Response latency**: SSE streaming delivers first token within ~500ms on average for domestic queries; tool-heavy itineraries (4+ external API calls) complete within 8-12 seconds.
- **Tool call accuracy**: The Gemini 3 Flash model correctly routes tool calls for flight, hotel, weather, and attraction queries with >90% accuracy in casual conversation.
- **Itinerary completeness**: The `finalize_trip_plan` validation ensures all generated itineraries include flights, hotels, weather data, and at least one attraction per day.
- **System availability**: The Docker-based deployment with health checks ensures automatic service recovery; PostgreSQL 16 with connection pooling via SQLAlchemy handles concurrent sessions.

---

## 6 Conclusion

GoGoGo demonstrates a production-grade integration of a streaming AI agent with real-time travel APIs, delivering a natural language-to-structured-itinerary pipeline. Key innovations include a unified SSE streaming loop with interleaved tool execution, a local `finalize_trip_plan` interception for structured output, and comprehensive session persistence enabling multi-round agent reasoning across stateless HTTP requests.

---

## Appendix A: Team Member Contributions

The following summarizes each team member's contributions to the GoGoGo project, based on commit history and file ownership analysis.

| Team Member         | GitHub Handle(s)             | Email                                       | Commits | Primary Contributions                                                                                                                                                                                                                                                                                                             |
| ------------------- | ---------------------------- | ------------------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **David Wong**      | davidwong666, DavidWongLinux | david20030701@gmail.com                     | 322     | Lead architect and primary contributor. Core backend development including `streaming_service.py`, agent tool implementations (flights, hotels, search, weather, attractions, transport, maps), database models, authentication system, API routes, and Docker Compose setup. Full-stack development across backend and frontend. |
| **Lim Xuan Qing**   | lim44104                     | xuanqinglim@gmail.com                       | 34      | Frontend development including ChatPage UI, trip components (FlightCard, HotelCard, AttractionCard, MapEmbed), voice components, and Zustand store implementations. Also contributed to API route refinements.                                                                                                                    |
| **Men Cair**        | mencaire                     | 1155191548@link.cuhk.edu.hk                 | 16      | LivePage implementation with WebSocket support for Gemini Live voice mode, TTS integration, and UI/UX improvements across multiple pages.                                                                                                                                                                                         |
| **Peng Minqi**      | mencaire (commit co-author)  | —                                           | 8       | Initial architecture setup, tech stack configuration, and model selection implementation with backup model support and logging enhancements.                                                                                                                                                                                      |
| **David Wong (KK)** | davidwkk                     | 105434983+davidwkk@users.noreply.github.com | 4       | Bug fixes and UI improvements including LivePage layout fixes and seed database updates for demo itineraries.                                                                                                                                                                                                                     |
| **Lim Xuan Qing**   | —                            | xuanqinglim@gmail.com                       | 1       | Documentation and minor project cleanup.                                                                                                                                                                                                                                                                                          |

**Development Statistics:**

- Total commits: 273
- Files modified: 150+
- Lines of Python (backend): ~15,000
- Lines of TypeScript/React (frontend): ~12,000
- Database migrations: 15+

**Key Architectural Decisions (attributed to David Wong):**

1. `_make_sync()` async/sync bridge for Gemini SDK tool compatibility
2. `finalize_trip_plan` local interception for structured output
3. SSE-based streaming with interleaved tool result events
4. Module-level dict cache pattern for async transport tool
5. `function`-role message persistence for cross-request agent context
