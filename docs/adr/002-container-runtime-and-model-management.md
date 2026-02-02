# ADR-002: Container Runtime, Engine Fallbacks, and Default Model Bootstrapping

## Status

Accepted

## Date

2026-02-02

## Context

The capability must run reliably on edge devices (including aarch64 / Raspberry Pi) under Podman/podman-compose.

During initial bring-up we encountered several practical issues:

1. **Image pull failures / short-name resolution**: The original base image reference (`rhasspy/piper:latest`) was not reliably pullable in Podman environments without additional registry configuration.
2. **Wrong entrypoint semantics**: Some upstream images (notably `linuxserver/piper`) use an init/s6 entrypoint designed for their own services, which can conflict with our FastAPI/uvicorn command.
3. **Model bootstrapping friction**: Requiring every user to manually download and mount a voice model creates a poor cold-start experience.
4. **Language/model variability**: Not all desired languages are available in Piper voice packs; we need a pragmatic fallback for basic multilingual speech.
5. **Runtime dependency gaps on aarch64**: The `linuxserver/piper` base image can include a `piper-tts` Python package lacking the compiled `espeakbridge` extension on aarch64, causing Piper synthesis to fail at runtime.
6. **Operational observability**: Users need clear visibility into what engines are usable, whether models are present/downloading, and which voices are discoverable.

## Decision

We standardize on the following runtime architecture and bootstrapping approach:

### 1. Base Image

- Use `docker.io/linuxserver/piper:latest` as the container base image because it is pullable in typical Podman environments and includes a working Piper binary path under `/lsiopy/bin/piper`.

### 2. Entrypoint Control

- Override upstream entrypoints to ensure the container starts the capability server:
  - `ENTRYPOINT []`
  - `CMD ["python3", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "10200"]`

### 3. Engine Strategy (Piper + Fallback)

- Provide two synthesis engines:
  - **Piper**: neural TTS via Piper CLI using `*.onnx` + `*.onnx.json` voice assets under `/models`.
  - **eSpeak NG**: classic TTS fallback (`espeak-ng`) that works without neural model downloads.

### 4. Voice Discovery Endpoints

- Add endpoints to expose what is available at runtime:
  - `GET /voices` lists discovered Piper models under `/models`.
  - `GET /voices/espeak` lists available eSpeak NG voices (language codes) from the container.

### 5. Default Model Bootstrapping (Cold Start)

- On first container start, if `/models/voice.onnx` and `/models/voice.onnx.json` are missing, automatically download a default English Piper voice (`en_US-lessac-medium`) into the `/models` volume.
- The download is performed in the background so the API can come up immediately.
- The download location is the shared `/models` volume so it persists across restarts.
- Download sources are driven by the Piper voices index:
  - Index: `https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json`
  - Base: `https://huggingface.co/rhasspy/piper-voices/resolve/main/`
- The implementation verifies file integrity using MD5 digests from the index.

### 6. Make Piper Work on aarch64

- Ensure Piper runtime dependencies exist in the base image’s `/lsiopy` Python environment:
  - Install `pathvalidate`.
- Provide a pure-Python fallback for `piper.espeakbridge` when the compiled extension is missing by shelling out to `espeak-ng` for IPA phonemes.

### 7. Health and Observability

- Improve `GET /health` to include:
  - Engine availability/readiness (Piper and eSpeak)
  - Piper model/config file presence
  - Piper voice discovery counts
  - Default model download status (`disabled|not_needed|in_progress|done|failed`)

## Consequences

### Positive

- **Reliable Podman bring-up**: Avoids short-name registry issues and improves compatibility with common Podman defaults.
- **Deterministic startup**: `ENTRYPOINT []` ensures our FastAPI server runs consistently.
- **Better cold start UX**: Default English voice is available automatically for immediate TTS testing.
- **Resilience**: eSpeak NG provides a usable fallback even when no neural models are present or the device is offline.
- **Better observability**: `/health`, `/voices`, and `/voices/espeak` reduce guesswork and support blueprint automation.
- **aarch64 correctness**: Fixes Piper runtime failures caused by missing `espeakbridge`.

### Negative

- **Network at first run**: Default model download requires outbound internet access on first start (unless a model is pre-seeded into the volume).
- **Longer first-start latency**: The first download can take time (mitigated by background download and eSpeak fallback).
- **More moving parts**: Extra endpoints and download logic increase complexity.
- **Fallback phonemization quality**: The pure-Python `espeakbridge` fallback uses `espeak-ng` CLI, which may not match the upstream compiled bridge perfectly.

## Alternatives Considered

### 1. Keep `rhasspy/piper:latest` as base

**Rejected**: Not reliably pullable in Podman environments; short-name resolution and registry issues blocked cold start.

### 2. Download the model at image build time

**Rejected**:
- Makes builds slow and network-dependent.
- Bloats the image and prevents reusing a shared `/models` volume across upgrades.

### 3. Bundle model files in the repository

**Rejected**: Large binaries are not suitable for the repo and complicate licensing and distribution.

### 4. Use only eSpeak NG

**Rejected**: Voice quality is substantially lower; neural TTS is a core requirement.

### 5. Switch to another TTS runtime (e.g., Kokoro ONNX)

**Deferred**: Not adopted in this ADR; language availability (e.g., Zulu) and operational fit require additional evaluation.

## Notes

- This ADR intentionally avoids claiming specific language availability beyond what is bundled or discoverable at runtime.
- Adding a new language is expected to be a **model provisioning** problem (drop a compatible model into `/models`), not a code change.
