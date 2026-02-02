#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:10200}"
OUT_DIR="${OUT_DIR:-/tmp}"

mkdir -p "$OUT_DIR"

./scripts/validate-deployment.sh

echo "Testing eSpeak synthesis (should work even without Piper model)"
curl -sS -X POST "${BASE_URL}/synthesize" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from eSpeak","engine":"espeak","language":"en"}' \
  --output "${OUT_DIR}/espeak.wav"
file "${OUT_DIR}/espeak.wav"

echo "Testing Piper synthesis (may require model or auto-download)"
code=$(curl -sS -o "${OUT_DIR}/piper.wav" -w '%{http_code}' -X POST "${BASE_URL}/synthesize" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from Piper","engine":"piper"}')

if [[ "$code" != "200" ]]; then
  echo "WARN: Piper synthesis returned HTTP ${code}. This is expected if no model is present yet."
else
  file "${OUT_DIR}/piper.wav"
fi

echo "Test suite complete. Output in ${OUT_DIR}" 
