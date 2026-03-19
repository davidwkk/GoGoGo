# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GoGoGo is a travel agent AI application with a React frontend and FastAPI backend. Users chat with an AI agent to plan trips, with structured itinerary output including flights, hotels, attractions, and weather.

**Stack:** FastAPI + SQLAlchemy (async) + PostgreSQL (backend) | React + Vite + shadcn/ui + Zustand (frontend) | LangChain + Gemini 3 Flash + Gemini 3.1 Flash Lite (agent)

## Quick Start

```bash
# Copy and configure environment
cp .env.example .env
# Fill in required API keys in .env

# Start all services
docker-compose up --build

# Stop services
docker-compose down

# Reset database
docker-compose down -v
```

**Service URLs:**
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Backend Commands

All backend commands run inside the Docker container:

```bash
# Run tests
docker-compose exec backend pytest

# Run tests with coverage
docker-compose exec backend pytest --cov=app --cov-report=term-missing

# Run a single test file
docker-compose exec backend pytest tests/unit/test_security.py

# Run a single test
docker-compose exec backend pytest tests/unit/test_security.py::test_jwt_encode_decode

# Generate database migration
docker-compose exec backend alembic revision --autogenerate -m "add trips table"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Open shell in backend container
docker-compose exec backend /bin/sh

# View backend logs
docker-compose logs -f backend
```

## Frontend Commands

All frontend commands run inside the Docker container:

```bash
# View frontend logs
docker-compose logs -f frontend

# Open shell in frontend container
docker-compose exec frontend /bin/sh
```

For local development outside Docker (optional):

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                    │
│  ├── Pages: LoginPage, ChatPage, TripPage                   │
│  ├── Chat: Voice input (Web Speech API), TTS playback       │
│  ├── State: Zustand store                                   │
│  └── API: Axios client with SSE streaming                   │
└─────────────────────────────────────────────────────────────┘
                           │ REST + SSE
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                          │
│  ├── /auth - JWT register/login                             │
│  ├── /chat/stream - SSE agent streaming                     │
│  ├── /trips - CRUD for saved itineraries                    │
│  ├── /users - User preferences                              │
│  └── /health - Docker healthcheck                           │
│                                                             │
│  LangChain Agent (Gemini 3 Flash)                          │
│  ├── Phase 1: agent.stream() → SSE → client shows thinking │
│  └── Phase 2: .with_structured_output() → TripItinerary    │
│                                                             │
│  Data Layer                                                 │
│  ├── SQLAlchemy async + Alembic migrations                  │
│  └── PostgreSQL 16                                          │
└─────────────────────────────────────────────────────────────┘
```

## Key Backend Files

| Path                           | Purpose                                       |
| ------------------------------ | --------------------------------------------- |
| `backend/app/main.py`          | FastAPI app entry, lifespan, router inclusion |
| `backend/app/core/config.py`   | pydantic-settings environment config          |
| `backend/app/core/security.py` | JWT encode/decode, password hashing           |
| `backend/app/db/models/`       | SQLAlchemy declarative models                 |
| `backend/app/repositories/`    | Database access layer                         |
| `backend/app/services/`        | Business logic                                |
| `backend/app/agent/agent.py`   | LangChain agent setup                         |
| `backend/app/agent/tools/`     | SerpAPI, OpenWeatherMap, Google Maps tools    |

## Key Frontend Files

| Path                              | Purpose                            |
| --------------------------------- | ---------------------------------- |
| `frontend/src/pages/ChatPage.tsx` | Main chat interface                |
| `frontend/src/hooks/useChat.ts`   | SSE streaming hook with auto-retry |
| `frontend/src/hooks/useASR.ts`    | Web Speech API voice input         |
| `frontend/src/hooks/useTTS.ts`    | Gemini TTS playback                |
| `frontend/src/store/`             | Zustand global state               |

## Environment Variables

Required in `.env`:
- `SECRET_KEY` - JWT signing key
- `GEMINI_API_KEY` - Google AI Studio
- `GEMINI_MODEL` - Gemini model for agent (default: gemini-3-flash-preview)
- `GEMINI_LITE_MODEL` - Lightweight model for preference extraction
- `GEMINI_TTS_MODEL` - TTS model (default: gemini-2.5-flash-preview-tts)
- `SERPAPI_KEY` - SerpAPI (web search, flights, hotels)
- `OPENWEATHER_API_KEY` - Weather data
- `GOOGLE_MAPS_API_KEY` - Map display
- `DATABASE_URL` - PostgreSQL connection (set by docker-compose)

## Database

PostgreSQL 16 with async SQLAlchemy. Alembic handles migrations. Key tables: `users`, `chat_sessions`, `messages`, `trips`, `user_preferences`.

## API Design

- REST + SSE streaming (Phase 1: agent reasoning stream)
- JWT Bearer token authentication
- Phase 2: `.with_structured_output()` → TripItinerary (Pydantic)
