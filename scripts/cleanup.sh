#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36e'
BOLD='\033[1m'
RESET='\033[0m'

log()     { echo -e "${CYAN}[$(date +%H:%M:%S)]${RESET} $*";    }
success() { echo -e "${GREEN}[$(date +%H:%M:%S)] ✔ $*${RESET}"; }
warn()    { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠ $*${RESET}"; }
error()   { echo -e "${RED}[$(date +%H:%M:%S)] ✘ $*${RESET}";   }

# ── Discover all compose-managed containers ──────────────────
# Returns lines of: "container_name|project|service|status"
get_compose_containers() {
  docker ps -a \
    --filter "label=com.docker.compose.project" \
    --format '{{.Names}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}|{{.Status}}'
}

# ── Get config files for a project (from any of its containers) ──
get_config_files() {
  local project="$1"
  docker ps -a \
    --filter "label=com.docker.compose.project=$project" \
    --format '{{.Label "com.docker.compose.project.config_files"}}' \
    | head -1
}

# ── Build compose command from config files string ───────────
# Input: "/path/a.yml,/path/b.yml"  Output: "docker compose -f /path/a.yml -f /path/b.yml"
build_compose_cmd() {
  local config_files="$1"
  local project="$2"
  local cmd="docker compose"
  IFS=',' read -ra files <<< "$config_files"
  for f in "${files[@]}"; do
    cmd+=" -f $f"
  done
  cmd+=" -p $project"
  echo "$cmd"
}

# ── Main ─────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║           GoGoGo Container Cleanup               ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${RESET}\n"

# ── Collect containers ────────────────────────────────────────
readarray -t RAW < <(get_compose_containers)

if [ ${#RAW[@]} -eq 0 ]; then
  warn "No compose-managed containers found."
  exit 0
fi

# ── Sort by preferred cleanup order ──────────────────────────
ORDER=("vpn-proxy" "db" "backend" "frontend")
sorted=()
for target in "${ORDER[@]}"; do
  for item in "${RAW[@]}"; do
    svc=$(echo "$item" | cut -d'|' -f3)
    [[ "$svc" == "$target" ]] && sorted+=("$item")
  done
done
for item in "${RAW[@]}"; do
  [[ ! " ${sorted[*]} " =~ " ${item} " ]] && sorted+=("$item")
done

# ── Display menu ──────────────────────────────────────────────
echo -e "  ${BOLD}Detected containers:${RESET}\n"
idx=1
for item in "${sorted[@]}"; do
  name=$(echo   "$item" | cut -d'|' -f1)
  project=$(echo "$item" | cut -d'|' -f2)
  svc=$(echo    "$item" | cut -d'|' -f3)
  status=$(echo "$item" | cut -d'|' -f4)
  printf "  ${CYAN}[%d]${RESET} %-35s %-20s (${YELLOW}%s${RESET})\n" \
    "$idx" "$name" "[$project/$svc]" "$status"
  idx=$((idx + 1))
done

echo ""
echo -e "  ${CYAN}[a]${RESET} All of the above"
echo -e "  ${CYAN}[q]${RESET} Quit"
echo ""
read -rp "  Select container(s) to remove [e.g. 1,3 or a]: " SELECTION
SELECTION="${SELECTION:-q}"
echo ""

[[ "$SELECTION" =~ ^[Qq]$ ]] && { log "Exiting. No containers removed."; exit 0; }

# ── Parse selection ───────────────────────────────────────────
to_remove=()
if [[ "$SELECTION" =~ ^[Aa]$ ]]; then
  to_remove=("${sorted[@]}")
else
  IFS=',' read -ra CHOSEN <<< "$SELECTION"
  for num in "${CHOSEN[@]}"; do
    num=$(echo "$num" | tr -d ' ')
    if [[ "$num" =~ ^[0-9]+$ ]] && [ "$num" -ge 1 ] && [ "$num" -le "${#sorted[@]}" ]; then
      to_remove+=("${sorted[$((num - 1))]}")
    else
      warn "Invalid selection: $num — skipping."
    fi
  done
fi

[ ${#to_remove[@]} -eq 0 ] && { warn "No valid containers selected."; exit 0; }

# ── Confirm ───────────────────────────────────────────────────
echo -e "  ${BOLD}Containers to remove:${RESET}"
for item in "${to_remove[@]}"; do
  echo "    - $(echo "$item" | cut -d'|' -f1)"
done
echo ""

# ── Group by project → run compose down per project ──────────
# Prefer compose down (cleans networks/volumes) when ALL containers
# in a project are selected; otherwise fall back to docker rm -f.
echo ""

declare -A project_total   # project → total container count
declare -A project_selected # project → selected count

for item in "${sorted[@]}"; do
  p=$(echo "$item" | cut -d'|' -f2)
  project_total[$p]=$(( ${project_total[$p]:-0} + 1 ))
done
for item in "${to_remove[@]}"; do
  p=$(echo "$item" | cut -d'|' -f2)
  project_selected[$p]=$(( ${project_selected[$p]:-0} + 1 ))
done

# Collect projects where ALL containers are selected → use compose down
full_down_projects=()
partial_remove=()
for item in "${to_remove[@]}"; do
  p=$(echo "$item" | cut -d'|' -f2)
  if [ "${project_selected[$p]}" -eq "${project_total[$p]}" ]; then
    # Mark project for full down (deduplicate)
    [[ ! " ${full_down_projects[*]} " =~ " $p " ]] && full_down_projects+=("$p")
  else
    partial_remove+=("$item")
  fi
done

# Full project teardown
for project in "${full_down_projects[@]}"; do
  config_files=$(get_config_files "$project")
  cmd=$(build_compose_cmd "$config_files" "$project")
  log "Running compose down for project: $project"
  $cmd down && success "Project $project torn down." || error "Failed to tear down $project."
done

# Partial removal (individual containers)
for item in "${partial_remove[@]}"; do
  name=$(echo "$item" | cut -d'|' -f1)
  log "Removing $name..."
  docker rm -f "$name" > /dev/null && success "Removed $name." || warn "Could not remove $name."
done

echo ""
success "Cleanup complete."
