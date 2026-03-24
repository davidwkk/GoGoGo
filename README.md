# GoGoGo
Final Project for CSCI3280 2025-26 Sem2 — AI-powered travel agent

## Quick Start

```bash
git clone git@github.com:davidwkk/GoGoGo.git
cd GoGoGo

# Check & install dependencies
./scripts/check-deps.sh --install

# Set up environment
cp .env.example .env   # Then fill in API keys (see below)

# Start all services
docker-compose up --build

# Verify it's working
curl http://localhost:8000/health
```

| Service  | URL                        |
| -------- | -------------------------- |
| Frontend | http://localhost:5173      |
| Backend  | http://localhost:8000      |
| API Docs | http://localhost:8000/docs |

**Stop:** `docker-compose down` | **Reset DB:** `docker-compose down -v`

---

## Required API Keys

Get free API keys and add them to your `.env`:

| Service | Purpose | Sign Up |
| ------- | ------- | ------- |
| `GEMINI_API_KEY` | AI agent + TTS | https://aistudio.google.com/ |
| `SERPAPI_KEY` | Flights, hotels, search | https://serpapi.com/ |
| `TAVILY_API_KEY` | Web search (primary) | https://tavily.com/ |
| `OPENWEATHER_API_KEY` | Weather data | https://openweathermap.org/ |
| `GOOGLE_MAPS_API_KEY` | Map display | https://console.cloud.google.com/ |

> **Demo cost:** $0 (all services have generous free tiers)

---

## Tech Stack

| Layer | Stack |
| ----- | ----- |
| Backend | FastAPI, SQLAlchemy, PostgreSQL 16, Alembic |
| Frontend | React, Vite, shadcn/ui, Zustand |
| AI | Gemini 3 Flash, Gemini 3.1 Flash-Lite |
| APIs | SerpAPI, Tavily, OpenWeatherMap, Google Maps |
| Tooling | Ruff, Docker, Docker Compose |

---

## Prerequisites

Tools checked by `./scripts/check-deps.sh`:

- **Docker** + Docker Compose
- **Git**
- **Node.js** + npm
- **Python 3.10+**
- **uv** — `pip install uv` or `brew install uv`
- **Ruff** — `pip install ruff` (optional, for linting)

Run without `--install` to just check:
```bash
./scripts/check-deps.sh
```

---

## Project Structure

```
gogogo/
├── backend/           # FastAPI + SQLAlchemy API
│   ├── app/
│   │   ├── api/      # Routes: auth, chat, trips, users, health
│   │   ├── agent/    # Gemini agent + tools
│   │   ├── db/       # Models, sessions, migrations
│   │   ├── schemas/  # Pydantic request/response models
│   │   └── services/ # Business logic
│   └── tests/
├── frontend/         # React + Vite frontend
│   ├── src/
│   │   ├── pages/    # LoginPage, ChatPage, TripPage
│   │   ├── hooks/    # useChat (SSE), useASR, useTTS
│   │   └── store/    # Zustand state
│   └── components/
├── scripts/          # Dev scripts (check-deps.sh)
└── docker-compose.yml
```

---

## Group Members

| Name | Student ID |
| ---- | ---------- |
| Wong Kwok Kam | 1155192018 |
| Peng Minqi | 1155191548 |
| Lim Xuan Qing | 1155264390 |

---

## Development

> **Recommended:** Use **everything claude code** (`/everything claude code`) in Claude Code for TDD enforcement, code review, and build error resolution. See `CLAUDE.md` for project conventions.

### Backend Commands (inside container)

```bash
docker-compose exec backend pytest                    # Run tests
docker-compose exec backend pytest --cov=app --cov-report=term-missing
docker-compose exec backend alembic revision --autogenerate -m "migration name"
docker-compose exec backend alembic upgrade head
docker-compose logs -f backend                       # Watch logs
```

### Backend IDE Setup (optional)

For local autocomplete in your IDE:
```bash
cd backend
uv venv
source .venv/bin/activate
uv sync
```

---

## Documentation

- **Architecture & API Design:** See [INFRA_PLAN.md](./INFRA_PLAN.md)
- **Development Conventions:** See [CLAUDE.md](./CLAUDE.md)
