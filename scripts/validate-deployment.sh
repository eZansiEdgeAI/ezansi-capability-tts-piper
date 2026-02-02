#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:10200}"

echo "Checking health at ${BASE_URL}/health"
code=$(curl -sS -o /tmp/tts_health.json -w '%{http_code}' "${BASE_URL}/health" || true)
if [[ "$code" != "200" ]]; then
  echo "Health check failed (HTTP ${code})"
  cat /tmp/tts_health.json || true
  exit 1
fi

echo "OK: health"

# Optional: ensure /voices endpoints exist
curl -sS "${BASE_URL}/voices" >/dev/null && echo "OK: voices" || echo "WARN: /voices unavailable"
curl -sS "${BASE_URL}/voices/espeak" >/dev/null && echo "OK: voices/espeak" || echo "WARN: /voices/espeak unavailable"

echo "Deployment validation complete."
