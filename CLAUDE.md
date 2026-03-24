# CLAUDE.md

GoGoGo is a travel agent AI app. Users chat with an AI to plan trips, getting structured itineraries with flights, hotels, attractions, and weather.

## Stack

**Backend:** FastAPI + SQLAlchemy + PostgreSQL 16 + Alembic
**Agent:** google-genai + Gemini 3 Flash + Gemini 3.1 Flash-Lite (preferences)
**Tools:** Tavily (search) + SerpAPI (flights/hotels) + OpenWeatherMap + Google Maps
**Frontend:** React + Vite + shadcn/ui + Zustand
**ASR/TTS:** Web Speech API (browser) + Gemini TTS

## Quick Start

```bash
cp .env.example .env    # Fill in API keys
docker-compose up --build
docker-compose down -v # Reset database
```

**Services:** Frontend http://localhost:5173 | Backend http://localhost:8000/docs

## Backend Commands (run in container)

```bash
docker-compose exec backend pytest                              # All tests
docker-compose exec backend pytest tests/unit/test_security.py  # Single file
docker-compose exec backend pytest --cov=app --cov-report=term-missing
docker-compose exec backend alembic revision --autogenerate -m "migration name"
docker-compose exec backend alembic upgrade head
docker-compose logs -f backend
```

## Architecture

```
Frontend (React + Vite)
├── Pages: LoginPage, ChatPage, TripPage
├── Voice I/O: Web Speech API (STT) → text → LLM → text + Web Speech Synthesis (TTS)
└── State: Zustand store

Backend (FastAPI)
├── /auth - JWT register/login
├── /chat/stream - SSE streaming (Phase 1: agent reasoning)
├── /trips - CRUD itineraries
├── /users - preferences
├── /health - Docker healthcheck
└── Agent (google-genai direct)
    ├── Phase 1: Gemini 3 Flash → SSE stream (thinking, tool calls)
    └── Phase 2: .with_structured_output() → TripItinerary (Pydantic)
```

## Key Files

**Backend:**
- `backend/app/main.py` - FastAPI entry, lifespan, routers
- `backend/app/core/config.py` - pydantic-settings env config
- `backend/app/core/security.py` - JWT + password hashing
- `backend/app/agent/agent.py` - google-genai setup, two-phase streaming
- `backend/app/agent/tools/` - search, flights, hotels, weather, maps
- `backend/app/db/models/` - SQLAlchemy models
- `backend/app/repositories/` - DB access layer

**Frontend:**
- `frontend/src/pages/ChatPage.tsx` - Main chat UI
- `frontend/src/hooks/useChat.ts` - SSE streaming hook
- `frontend/src/hooks/useASR.ts` - Voice input
- `frontend/src/hooks/useTTS.ts` - TTS playback
- `frontend/src/store/` - Zustand state

## Environment Variables

```
DATABASE_URL, SECRET_KEY
GEMINI_API_KEY, GEMINI_MODEL, GEMINI_LITE_MODEL, GEMINI_TTS_MODEL
SERPAPI_KEY, TAVILY_API_KEY
OPENWEATHER_API_KEY, GOOGLE_MAPS_API_KEY
LOG_LEVEL=DEBUG
```

## Database

PostgreSQL 16 + SQLAlchemy + Alembic. Tables: `users`, `chat_sessions`, `messages`, `trips`, `user_preferences`.
