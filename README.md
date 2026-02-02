# ezansi-capability-tts-piper

Piper Text-to-Speech capability for eZansiEdgeAI with automatic hardware detection.

**Contract name:** `piper-tts`  
**Provides:** `text-to-speech`

## Features

- **Automatic Hardware Detection**: Detects system architecture, RAM, CPU cores, and GPU availability
- **Dynamic Resource Configuration**: Automatically configures resource limits based on detected hardware
- **Multiple Architecture Support**: Works on x86_64, aarch64, armv7l
- **GPU Acceleration Support**: Auto-detects CUDA, ROCm, and OpenVINO

## Quick start

### 1. Configure Hardware Resources

First, detect your system hardware and generate configuration:

```bash
./scripts/configure-hardware.sh
```

This will create a `.env` file with appropriate resource limits for your system.

### 2. Start the Service

```bash
podman-compose up -d
```

### 3. Verify Deployment

Check the health endpoint to see detected hardware:

```bash
curl http://localhost:10200/health | jq
```

### 4. Synthesize Speech

```bash
# Synthesize (writes WAV to file)
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from eZansiEdgeAI"}' \
  --output /tmp/tts.wav
file /tmp/tts.wav
```

## API

- `GET /health` - Health check with detected hardware information
- `GET /.well-known/capability.json` - Capability metadata with runtime-detected resources
- `POST /synthesize` - Text-to-speech synthesis
  - Input: `{"text": "string", "speaker": int (optional)}`
  - Output: `audio/wav`

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

This container expects a Piper voice model file mounted at `/models/voice.onnx` by default.
See `scripts/pull-voice.sh` (if available).

## Supported Platforms

- Raspberry Pi 3/4/5 (armv7l, aarch64)
- x86_64 Linux systems
- ARM-based edge devices
- Systems with NVIDIA CUDA GPUs
- Systems with AMD ROCm GPUs
- Systems with Intel OpenVINO
