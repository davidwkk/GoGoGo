#!/bin/bash
# Startup script for backend - handles optional VPN proxy

set -e

# If LLM_PROXY_ENABLED=1, set HTTP_PROXY/HTTPS_PROXY for all HTTP calls
if [ "${LLM_PROXY_ENABLED:-0}" = "1" ]; then
    echo "VPN Proxy enabled: routing LLM calls through ${SOCKS5_PROXY_URL}"
    export HTTP_PROXY="${SOCKS5_PROXY_URL:-socks5://host.docker.internal:1080}"
    export HTTPS_PROXY="${SOCKS5_PROXY_URL:-socks5://host.docker.internal:1080}"
    export ALL_PROXY="${SOCKS5_PROXY_URL:-socks5://host.docker.internal:1080}"
else
    echo "VPN Proxy disabled"
fi

# Auto-apply any pending migrations
echo "Checking for database migrations..."
alembic upgrade head

# Start uvicorn
# IMPORTANT: In dev, avoid watching `.venv`/site-packages for reloads. Live WS connections
# will drop immediately if the server reloads due to dependency file timestamp churn.
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir app \
  --reload-exclude ".venv/*" \
  --reload-exclude "**/site-packages/*" \
  "$@"
