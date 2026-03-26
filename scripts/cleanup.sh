#!/bin/bash
set -e

cd "$(dirname "$0")/.."

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

echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║           GoGoGo Container Cleanup                  ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${RESET}\n"

# ── Detect containers from compose files ─────────────────────
# Get containers from both compose files if they exist
ALL_CONTAINERS=()

detect_containers() {
  local compose_file="$1"
  if [ -f "$compose_file" ]; then
    # Extract service names from compose file
    local services=$(docker compose -f "$compose_file" config --services 2>/dev/null || true)
    for svc in $services; do
      # Check if container is actually running or exists
      local container_id=$(docker compose -f "$compose_file" ps -q "$svc" 2>/dev/null | head -1 || true)
      if [ -n "$container_id" ]; then
        local container_name=$(docker inspect --format='{{.Name}}' "$container_id" 2>/dev/null | sed 's/^\///')
        local status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown")
        # Avoid duplicates
        if [[ ! " ${ALL_CONTAINERS[*]} " =~ " ${container_name}:${svc}:${compose_file} " ]]; then
          ALL_CONTAINERS+=("${container_name}:${svc}:${compose_file}")
        fi
      fi
    done
  fi
}

detect_containers "docker-compose.yml"
detect_containers "docker-compose.vpn.yml"

if [ ${#ALL_CONTAINERS[@]} -eq 0 ]; then
  warn "No containers found from docker-compose.yml or docker-compose.vpn.yml."
  exit 0
fi

# ── Define cleanup order (vpn-proxy first, then app services) ─
ORDER=("vpn-proxy" "db" "backend" "frontend")

# Sort containers by preferred order
sorted=()
for target in "${ORDER[@]}"; do
  for item in "${ALL_CONTAINERS[@]}"; do
    svc="${item%%:*}"
    if [[ "$item" == *":$target:"* ]] || [[ "$item" == *":$target"* ]]; then
      sorted+=("$item")
    fi
  done
done

# Add any remaining containers not in our order list
for item in "${ALL_CONTAINERS[@]}"; do
  if [[ ! " ${sorted[*]} " =~ " ${item} " ]]; then
    sorted+=("$item")
  fi
done

# ── Display menu ─────────────────────────────────────────────
echo -e "  ${BOLD}Detected containers:${RESET}\n"
idx=1
for item in "${sorted[@]}"; do
  container_name="${item%%:*}"
  svc="${item%%:*}"  # first field is container name
  # Extract service name (second field)
  rest="${item#*:}"
  compose_file="${rest##*:}"

  status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "unknown")
  printf "  ${CYAN}[%d]${RESET} %-30s %-15s (${YELLOW}%s${RESET})\n" "$idx" "$container_name" "${compose_file##*/}" "$status"
  idx=$((idx + 1))
done

echo ""
echo -e "  ${CYAN}[a]${RESET} All of the above"
echo -e "  ${CYAN}[q]${RESET} Quit"
echo ""

read -rn 1 -p "  Select container(s) to remove [e.g. 1,3 or a]: " SELECTION
echo ""
SELECTION="${SELECTION:-q}"

if [[ "$SELECTION" =~ ^[Qq]$ ]]; then
  log "Exiting. No containers removed."
  exit 0
fi

# ── Parse selection ──────────────────────────────────────────
containers_to_remove=()

if [[ "$SELECTION" =~ ^[Aa]$ ]]; then
  for item in "${sorted[@]}"; do
    containers_to_remove+=("$item")
  done
else
  # Parse comma-separated or space-separated numbers
  IFS=',' read -ra CHOSEN <<< "$SELECTION"
  for num in "${CHOSEN[@]}"; do
    num=$(echo "$num" | tr -d ' ')
    if [ "$num" -ge 1 ] && [ "$num" -le ${#sorted[@]} ]; then
      containers_to_remove+=("${sorted[$((num - 1))]}")
    else
      warn "Invalid selection: $num. Skipping."
    fi
  done
fi

if [ ${#containers_to_remove[@]} -eq 0 ]; then
  warn "No valid containers selected. Exiting."
  exit 0
fi

# ── Confirm removal ──────────────────────────────────────────
echo -e "\n  ${BOLD}Containers to remove:${RESET}"
for item in "${containers_to_remove[@]}"; do
  echo "    - ${item%%:*}"
done
echo ""
read -rn 1 -p "  Confirm removal? [y/N]: " CONFIRM
echo ""
CONFIRM="${CONFIRM:-N}"

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  warn "Aborted. No containers removed."
  exit 0
fi

# ── Remove containers ────────────────────────────────────────
echo ""
for item in "${containers_to_remove[@]}"; do
  container_name="${item%%:*}"
  rest="${item#*:}"
  compose_file="${rest##*:}"

  log "Removing $container_name..."
  if docker rm -f "$container_name" > /dev/null 2>&1; then
    success "Removed $container_name"
  else
    warn "Could not remove $container_name (may already be gone)"
  fi
done

echo ""
success "Cleanup complete."
