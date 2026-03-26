#!/bin/bash
# Test script for Gemini 3.1 Flash-Lite API call
# Usage: ./LLM_call_test.sh

set -e

# Load env from project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"

if [ -f "$ENV_FILE" ]; then
  export $(grep -v '^#' "$ENV_FILE" | xargs)
else
  echo "Error: .env file not found at $ENV_FILE"
  exit 1
fi

# Fallback to default model name
MODEL="${GEMINI_LITE_MODEL:-gemini-3.1-flash-lite-preview}"

echo "==============================================="
echo "Testing Gemini LLM Call"
echo "==============================================="
echo "Model: $MODEL"
echo "API Key present: ${#GEMINI_API_KEY} chars"
echo ""

cd "$PROJECT_ROOT/backend"

uv run python -c "
from google.genai import Client
import os

api_key = os.environ.get('GEMINI_API_KEY')
model = os.environ.get('GEMINI_LITE_MODEL', 'gemini-3.1-flash-lite-preview')

print(f'Testing model: {model}')
print(f'API key present: {bool(api_key)}')
print()

client = Client(api_key=api_key)

response = client.models.generate_content(
    model=model,
    contents=\"Say 'Hello, Gemini 3.1 Flash-Lite!' in exactly those words.\",
)

print(f'Response: {response.text}')
"

echo ""
echo "==============================================="
echo "Test complete"
echo "==============================================="
