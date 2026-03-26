#!/bin/bash
# NordVPN OpenVPN Setup Helper
# Usage: ./scripts/nordvpn-setup.sh /path/to/sg475.ovpn
#
# This script helps you set up the VPN proxy for LLM calls.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
VPN_DIR="$PROJECT_ROOT/vpn"

echo "==============================================="
echo "NordVPN OpenVPN Setup"
echo "==============================================="
echo ""

# Check for OpenVPN config file as argument
OVPN_FILE="$1"
if [ -z "$OVPN_FILE" ]; then
    echo "Usage: $0 /path/to/sg475.ovpn"
    echo ""
    echo "Steps:"
    echo "1. Download OpenVPN config from NordVPN dashboard"
    echo "2. Run: $0 /path/to/downloaded.ovpn"
    echo ""
    echo "Or manually:"
    echo "1. Go to: https://dashboard.nordvpn.com/"
    echo "2. Account → Manual setup → Service credentials"
    echo "3. Get your OVPN_USERNAME and OVPN_PASSWORD"
    echo "4. Download OpenVPN config for your server"
    exit 1
fi

if [ ! -f "$OVPN_FILE" ]; then
    echo "Error: File not found: $OVPN_FILE"
    exit 1
fi

echo "✓ OpenVPN config found: $OVPN_FILE"

# Create vpn directory
mkdir -p "$VPN_DIR"
cp "$OVPN_FILE" "$VPN_DIR/custom.ovpn"
echo "✓ Copied to: $VPN_DIR/custom.ovpn"

# Extract server address from config
SERVER=$(grep "^remote " "$OVPN_FILE" | head -1 | awk '{print $2}')
PORT=$(grep "^remote " "$OVPN_FILE" | head -1 | awk '{print $3}')
PROTO=$(grep "^proto " "$OVPN_FILE" | awk '{print $2}')

echo ""
echo "Extracted from config:"
echo "  Server: $SERVER"
echo "  Port: $PORT"
echo "  Protocol: $PROTO"

echo ""
echo "==============================================="
echo "Next Steps:"
echo "==============================================="
echo ""
echo "1. Get NordVPN Service Credentials:"
echo "   Go to: https://dashboard.nordvpn.com/"
echo "   Account → Manual setup → Service credentials"
echo "   Copy your username (looks like: okjgt5@example.com)"
echo ""
echo "2. Add these to your .env file:"
echo ""
echo "   OVPN_USERNAME=<your-service-username>"
echo "   OVPN_PASSWORD=<your-service-password>"
echo "   OVPN_SERVER=$SERVER"
echo "   OVPN_PROTO=$PROTO"
echo "   LLM_PROXY_ENABLED=1"
echo ""
echo "3. Start VPN proxy:"
echo "   docker compose -f docker-compose.vpn.yml up -d"
echo ""
echo "4. Test:"
echo "   curl -x socks5://localhost:1080 https://generativelanguage.googleapis.com"
echo ""
echo "5. Restart backend:"
echo "   docker compose restart backend"
echo ""

# Optionally update .env if it exists
if [ -f "$ENV_FILE" ]; then
    echo "==============================================="
    echo "I can update .env automatically if you provide"
    echo "OVPN_USERNAME and OVPN_PASSWORD now."
    echo "==============================================="
fi
