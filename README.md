# ezansi-capability-tts-piper

Piper Text-to-Speech capability for eZansiEdgeAI.

**Contract name:** `piper-tts`  
**Provides:** `text-to-speech`

## Quick start

```bash
podman-compose up -d
./scripts/validate-deployment.sh

# Synthesize (writes WAV to file)
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from eZansiEdgeAI"}' \
  --output /tmp/tts.wav
file /tmp/tts.wav
```

## API

- `GET /health`
- `GET /.well-known/capability.json`
- `POST /synthesize` → `audio/wav`

## Voice models

This container expects a Piper voice model file mounted at `/models/voice.onnx` by default.
See `scripts/pull-voice.sh`.
