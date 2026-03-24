#!/bin/bash
# =============================================================================
# gogogo — Dependency Checker & Setup
# =============================================================================
# Detects required tools and optionally installs missing ones.
# Usage: ./scripts/check-deps.sh [--install]
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

INSTALL=false
if [[ "$1" == "--install" ]]; then
    INSTALL=true
fi

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)  echo "macos" ;;
        Linux*)   echo "linux" ;;
        *)        echo "unknown" ;;
    esac
}

OS=$(detect_os)

# =============================================================================
# Tool Checks
# =============================================================================

check_command() {
    local cmd="$1"
    local name="$2"
    local install_hint="$3"

    if command -v "$cmd" &> /dev/null; then
        version=$(command -v "$cmd" | xargs --no-run-if-empty "$cmd" --version 2>/dev/null | head -n1 || echo "installed")
        echo -e "${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "${RED}✗${NC} $name (not found)"
        if [[ -n "$install_hint" ]]; then
            echo "  → $install_hint"
        fi
        return 1
    fi
}

# =============================================================================
# Install Functions
# =============================================================================

install_homebrew() {
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}Installing Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
}

install_docker() {
    case "$OS" in
        macos)
            if ! command -v docker &> /dev/null; then
                echo -e "${YELLOW}Installing Docker Desktop for Mac...${NC}"
                echo "  Download from: https://www.docker.com/products/docker-desktop/"
                echo "  Or run: brew install --cask docker"
                return 1
            fi
            ;;
        linux)
            if ! command -v docker &> /dev/null; then
                echo -e "${YELLOW}Installing Docker...${NC}"
                curl -fsSL https://get.docker.com | sh
                sudo usermod -aG docker "$USER"
                return 1
            fi
            ;;
    esac
}

install_git() {
    case "$OS" in
        macos)
            if ! command -v git &> /dev/null; then
                echo -e "${YELLOW}Installing Git...${NC}"
                if command -v brew &> /dev/null; then
                    brew install git
                else
                    echo "  Install Xcode Command Line Tools or Homebrew first"
                    return 1
                fi
            fi
            ;;
        linux)
            sudo apt-get update && sudo apt-get install -y git
            ;;
    esac
}

install_uv() {
    case "$OS" in
        macos)
            if ! command -v uv &> /dev/null; then
                echo -e "${YELLOW}Installing uv...${NC}"
                if command -v brew &> /dev/null; then
                    brew install uv
                else
                    curl -LsSf https://astral.sh/uv/install.sh | sh
                fi
            fi
            ;;
        linux)
            curl -LsSf https://astral.sh/uv/install.sh | sh
            ;;
    esac
}

install_npm() {
    case "$OS" in
        macos)
            if ! command -v npm &> /dev/null; then
                echo -e "${YELLOW}Installing Node.js & npm...${NC}"
                if command -v brew &> /dev/null; then
                    brew install node
                else
                    echo "  Install Node.js from: https://nodejs.org/"
                    return 1
                fi
            fi
            ;;
        linux)
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt-get install -y nodejs
            ;;
    esac
}

install_ruff() {
    if command -v uv &> /dev/null; then
        uv tool install ruff
    elif command -v pip &> /dev/null; then
        pip install ruff
    fi
}

# =============================================================================
# Main
# =============================================================================

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  gogogo — Dependency Checker${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

missing=0

# Required tools
echo -e "${BLUE}--- Required ---${NC}"
check_command docker "Docker" || missing=$((missing + 1))
check_command git "Git" || missing=$((missing + 1))
check_command npm "npm" || missing=$((missing + 1))
check_command python3 "Python 3" || missing=$((missing + 1))
echo ""

# Optional but recommended
echo -e "${BLUE}--- Recommended ---${NC}"
check_command uv "uv (Python package manager)" "pip install uv" || missing=$((missing + 1))
check_command ruff "Ruff (Python linter)" "pip install ruff" || missing=$((missing + 1))
echo ""

# Docker Compose (usually comes with Docker Desktop)
if command -v docker &> /dev/null; then
    if docker compose version &> /dev/null || docker-compose version &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker Compose"
    else
        echo -e "${RED}✗${NC} Docker Compose (should be included with Docker Desktop)"
    fi
fi
echo ""

# =============================================================================
# Install Mode
# =============================================================================

if [[ "$INSTALL" == "true" && "$missing" -gt 0 ]]; then
    echo -e "${YELLOW}Installing missing dependencies...${NC}"
    echo ""

    # Git
    if ! command -v git &> /dev/null; then
        install_git || true
    fi

    # npm
    if ! command -v npm &> /dev/null; then
        install_npm || true
    fi

    # uv
    if ! command -v uv &> /dev/null; then
        install_uv || true
    fi

    # ruff
    if ! command -v ruff &> /dev/null; then
        install_ruff || true
    fi

    # Docker needs manual install on macOS
    if ! command -v docker &> /dev/null; then
        install_docker || true
    fi

    echo ""
    echo -e "${YELLOW}Please restart your terminal and run this script again to verify.${NC}"
fi

# =============================================================================
# Summary & Next Steps
# =============================================================================

echo ""
echo -e "${BLUE}========================================${NC}"
if [[ "$missing" -eq 0 ]]; then
    echo -e "${GREEN}✓ All dependencies satisfied!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. cp .env.example .env"
    echo "  2. Fill in your API keys in .env"
    echo "  3. docker-compose up --build"
    echo "  4. Visit http://localhost:5173"
    echo ""
    echo -e "For full documentation, see ${BLUE}INFRA_PLAN.md${NC}"
else
    echo -e "${YELLOW}⚠ $missing tool(s) missing${NC}"
    echo ""
    echo "Run with ${GREEN}--install${NC} to attempt automatic installation:"
    echo "  ./scripts/check-deps.sh --install"
    echo ""
    echo "Or install manually:"
    echo "  • Docker: https://docker.com/get-started"
    echo "  • Git: https://git-scm.com/downloads"
    echo "  • Node.js: https://nodejs.org/"
    echo "  • uv: https://github.com/astral-sh/uv"
    echo "  • Ruff: https://docs.astral.sh/ruff/"
fi
echo ""
