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

- `GET /health` - Health check.
- `GET /.well-known/capability.json` - Capability metadata.
- `POST /synthesize` - Text-to-speech synthesis
  - Input (required): `{"text": "string"}`
  - Input (optional):
    - `engine`: `"piper" | "espeak"`
    - `voice`: Piper voice id returned by `GET /voices`
    - `language`: eSpeak NG language/voice code (varies by image)
    - `speaker`: integer speaker id for multi-speaker Piper models
  - Output: `audio/wav`
- `GET /voices` - List Piper voices/models discovered under `/models`.
- `GET /voices/espeak` - List eSpeak NG voices available in the container.

## Hardware Detection

The capability automatically detects:

- **Architecture**: x86_64, aarch64, armv7l, etc.
- **Available RAM**: Total system memory
- **CPU Cores**: Number of available CPU cores
- **GPU Type**: CUDA (NVIDIA), ROCm (AMD), OpenVINO (Intel), or none

### Resource Allocation

Resources are allocated based on detected hardware:

- **RAM**: 50% of available RAM, minimum 300MB, maximum 600MB
- **CPU**: 1-2 cores depending on system capacity
- **GPU**: Automatically detected and configured

### Manual Override

You can override auto-detected settings by editing the `.env` file or setting environment variables:

```bash
export TTS_CPU_LIMIT=2.0
export TTS_MEMORY_LIMIT=800M
podman-compose up -d
```

## Voice models

This container expects Piper voice model files under `/models`.

- Default single-voice path: `/models/voice.onnx` + `/models/voice.onnx.json`
- Multiple voices are supported: place additional `*.onnx` + `*.onnx.json` anywhere under `/models` and list them with:
  - `curl -s http://localhost:10200/voices | jq`

If you don't have a neural model yet (or want a lightweight fallback), you can use the built-in eSpeak NG engine:

```bash
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hallo, hoe gaan dit?","engine":"espeak","language":"af"}' \
  --output /tmp/af.wav
```

Language coverage depends on what voices are available in the container image. Zulu is not currently shipped by default in this project; it can be added later once an offline voice/model becomes available.

### Auto-download a default English Piper model (optional)

Similar to Ollama pulling a model on first use, this service can download a default English Piper voice into the `/models` volume at container startup.

By default, the container image will attempt to download `en_US-lessac-medium` on first start if `/models/voice.onnx` is missing (and will keep running in a degraded state if offline).

- To disable it: set `AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL=0`
- To override the default voice id: set `DEFAULT_PIPER_VOICE_ID`

Example (disable in `podman-compose.yml`):

```bash
podman-compose down
```

Add this under the service in `podman-compose.yml`:

```yaml
environment:
  - AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL=0
```

Then:

```bash
podman-compose up -d --build
```

## Supported Platforms

- Raspberry Pi 3/4/5 (armv7l, aarch64)
- x86_64 Linux systems
- ARM-based edge devices
- Systems with NVIDIA CUDA GPUs
- Systems with AMD ROCm GPUs
- Systems with Intel OpenVINO

## Documentation

- **[Cold Start Guide](COLD_START.md)** - Step-by-step installation from scratch
- **[Testing Guide](TESTING.md)** - Manual testing procedures and test suite
- [Architecture Decision Records](docs/adr/) - Documents key architectural decisions
  - [ADR-001: Hardware Detection and Dynamic Resource Configuration](docs/adr/001-hardware-detection-and-dynamic-resources.md)

## Testing

Run the automated test suite to verify the TTS capability:

```bash
./scripts/test-suite.sh
```

For detailed manual testing procedures, see [TESTING.md](TESTING.md).

