#!/bin/bash
set -e

cd "$(dirname "$0")"

# ── Constants ────────────────────────────────────────────────
HEALTH_TIMEOUT=60

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Logging ──────────────────────────────────────────────────
log()     { echo -e "${CYAN}[$(date +%H:%M:%S)]${RESET} $*";    }
success() { echo -e "${GREEN}[$(date +%H:%M:%S)] ✔ $*${RESET}"; }
warn()    { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠ $*${RESET}"; }
error()   { echo -e "${RED}[$(date +%H:%M:%S)] ✘ $*${RESET}";   }

# ── Trap ─────────────────────────────────────────────────────
cleanup() {
  echo ""
  warn "Interrupt received. Stopping all services..."
  docker compose down --remove-orphans
  success "All services stopped. Goodbye!"
  exit 0
}

trap 'error "Script failed on line $LINENO."' ERR
trap 'cleanup' INT TERM

# ── Setup ────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║           GoGoGo Service Launcher                ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${RESET}\n"
log "Starting GoGoGo services with DEBUG logging and hot reload..."

# ── 1. Check Docker is running ───────────────────────────────
if ! docker ps > /dev/null 2>&1; then
  error "Docker is not running or not accessible. Please start Docker Desktop and try again."
  exit 1
fi
success "Docker is running."

# ── 2. Check .env exists ─────────────────────────────────────
if [ ! -f ".env" ]; then
  error ".env file not found. Please create one before starting."
  exit 1
fi
success ".env file found."

export LOG_LEVEL=DEBUG

# ── 3. Build mode menu ───────────────────────────────────────
echo -e ""
echo -e "  ${BOLD}Select a build mode:${RESET}"
echo -e ""
echo -e "  ${CYAN}[1]${RESET} Quick restart       ${YELLOW}(down → up)${RESET} ${GREEN}[default]${RESET}"
echo -e "  ${CYAN}[2]${RESET} Build with cache    ${YELLOW}(up --build)${RESET}"
echo -e "  ${CYAN}[3]${RESET} Build without cache ${YELLOW}(build --no-cache → up)${RESET}"
echo -e "  ${CYAN}[4]${RESET} Build from scratch  ${YELLOW}(down -v → build --no-cache → up)${RESET}"
echo -e "  ${CYAN}[5]${RESET} Just start          ${YELLOW}(up, no build/down)${RESET}"
echo -e ""
read -rn 1 -p "  Enter choice [1-5] (default: 1): " BUILD_CHOICE
echo ""
BUILD_CHOICE="${BUILD_CHOICE:-1}"


# ── 4. Prune dangling images ──────────────────────────────────
log "Removing dangling images..."
docker image prune -f
success "Dangling images removed."

# ── 5. Execute build mode ─────────────────────────────────────
case "$BUILD_CHOICE" in
  1)
    log "Quick restart: bringing down existing containers..."
    docker compose down --remove-orphans
    success "Containers removed. Volumes kept."
    log "Starting services..."
    docker compose up --remove-orphans -d "$@"
    ;;
  2)
    log "Building with cache and starting services..."
    docker compose up --build --remove-orphans -d "$@"
    ;;
  3)
    log "Building without cache..."
    docker compose build --no-cache
    success "Build complete."
    log "Starting services..."
    docker compose up --remove-orphans -d "$@"
    ;;
  4)
    warn "Build from scratch will remove all volumes including the database!"
    read -rn 1 -p "  Are you sure? [y/N]: " CONFIRM
    echo ""
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
      log "Bringing down containers and volumes..."
      docker compose down --remove-orphans -v
      success "Containers and volumes removed."
      log "Building without cache..."
      docker compose build --no-cache
      success "Build complete."
      log "Starting services..."
      docker compose up --remove-orphans -d "$@"
    else
      warn "Aborted. Exiting."
      exit 0
    fi
    ;;
  5)
    log "Starting services without build..."
    docker compose up --remove-orphans -d "$@"
    ;;
  *)
    error "Invalid choice: '$BUILD_CHOICE'. Exiting."
    exit 1
    ;;
esac

success "Services started."

# ── 6. Per-service health check ───────────────────────────────
check_service_health() {
  local SERVICE="$1"
  local LABEL="$2"
  local ELAPSED=0

  log "Checking ${LABEL}..."

  while true; do
    local CONTAINER_ID
    CONTAINER_ID=$(docker compose ps -q "$SERVICE" 2>/dev/null | head -1)

    STATUS=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
      "$CONTAINER_ID" 2>/dev/null || echo "unknown")

    case "$STATUS" in
      healthy)
        success "${LABEL} is healthy."
        return 0
        ;;
      unhealthy)
        error "${LABEL} is unhealthy. Run: docker compose logs ${SERVICE}"
        return 1
        ;;
      none)
        RUNNING=$(docker inspect --format='{{.State.Running}}' \
          "$CONTAINER_ID" 2>/dev/null || echo "false")
        if [ "$RUNNING" = "true" ]; then
          warn "${LABEL} has no healthcheck — container is running."
          return 0
        fi
        ;;
      *)
        ;;
    esac

    if [ "$ELAPSED" -ge "$HEALTH_TIMEOUT" ]; then
      error "${LABEL} did not become healthy within ${HEALTH_TIMEOUT}s."
      return 1
    fi

    if (( ELAPSED % 10 == 0 && ELAPSED > 0 )); then
      warn "${LABEL} still starting... (${ELAPSED}s elapsed)"
    fi

    sleep 2
    ELAPSED=$((ELAPSED + 2))
  done
}

log "Waiting for all services to become healthy (timeout: ${HEALTH_TIMEOUT}s each)..."
echo ""

FAILED=0
check_service_health "frontend" "Frontend (fn)" || FAILED=1
check_service_health "backend"  "Backend  (bn)" || FAILED=1
check_service_health "db"       "Database (db)" || FAILED=1

echo ""
if [ "$FAILED" -eq 1 ]; then
  error "One or more services failed. Bringing down all containers..."
  docker compose down --remove-orphans
  exit 1
fi

# ── 7. Access URLs ────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║              Services are running!               ║${RESET}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════╣${RESET}"
echo -e "${BOLD}${GREEN}║  🌐 Frontend  →  http://localhost:5173           ║${RESET}"
echo -e "${BOLD}${GREEN}║  ⚙️  Backend   →  http://localhost:8000           ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════╝${RESET}\n"

# ── 8. Seed DB ───────────────────────────────────────────────
echo -e "${YELLOW}Seed the database with sample users?${RESET}"
echo -e "  ${CYAN}[1]${RESET} Yes, seed sample users  ${YELLOW}(alice, bob, charlie / password123)${RESET} ${GREEN}[default]${RESET}"
echo -e "  ${CYAN}[2]${RESET} No, skip seeding"
echo -e "${YELLOW}Enter choice (1-2): ${RESET}\c"
read -r -n 1 SEED_CHOICE
echo ""
SEED_CHOICE="${SEED_CHOICE:-1}"

case "$SEED_CHOICE" in
  1)
    log "Seeding database..."
    docker compose exec backend python /app/scripts/seed_db.py
    success "Database seeded."
    ;;
  2)
    log "Skipping database seed."
    ;;
  *)
    warn "Invalid choice. Skipping seed."
    ;;
esac

# ── 9. Log viewer ─────────────────────────────────────────────
echo -e "${YELLOW}View service logs?${RESET}"
echo -e "  ${CYAN}[1]${RESET} All          ${GREEN}[default]${RESET}"
echo -e "  ${CYAN}[2]${RESET} Frontend (fn)"
echo -e "  ${CYAN}[3]${RESET} Backend  (bn)"
echo -e "  ${CYAN}[4]${RESET} Database (db)"
echo -e "  ${CYAN}[5]${RESET} None / Skip"
echo -e "${YELLOW}Enter choice (1-5): ${RESET}\c"
read -r -n 1 LOG_CHOICE
echo ""
LOG_CHOICE="${LOG_CHOICE:-1}"


case "$LOG_CHOICE" in
  1) log "Showing all logs (Ctrl+C to exit)...";       docker compose logs -f           ;;
  2) log "Showing Frontend logs (Ctrl+C to exit)...";  docker compose logs -f frontend  ;;
  3) log "Showing Backend logs (Ctrl+C to exit)...";   docker compose logs -f backend   ;;
  4) log "Showing Database logs (Ctrl+C to exit)...";  docker compose logs -f db        ;;
  5) log "Skipping log view. All done!" ;;
  *) log "Invalid choice. Skipping log view." ;;
esac
