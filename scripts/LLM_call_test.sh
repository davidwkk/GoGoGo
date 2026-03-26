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
from google.genai import Client, types
import os

api_key = os.environ.get('GEMINI_API_KEY')
lite_model = os.environ.get('GEMINI_LITE_MODEL', 'gemini-3.1-flash-lite-preview')
main_model = os.environ.get('GEMINI_MODEL', 'gemini-3.0-flash')

print(f'API key present: {bool(api_key)}')
print()

client = Client(api_key=api_key)

# Try GEMINI_LITE_MODEL first, fall back to GEMINI_MODEL on failure
models_to_try = [lite_model, main_model]

for model in models_to_try:
    try:
        print(f'Trying model: {model}')
        response = client.models.generate_content(
            model=model,
            contents=\"Say 'Hello, Gemini!' in exactly those words.\",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.MINIMAL
                ),
                max_output_tokens=50,
            ),
        )
        print(f'SUCCESS! Model: {model}')
        print(f'Response: {response.text}')
        break
    except Exception as e:
        print(f'FAILED: {e}')
        if model != models_to_try[-1]:
            print('Trying next model...\n')
        else:
            print('All models failed.')
"

echo ""
echo "==============================================="
echo "Test complete"
echo "==============================================="
