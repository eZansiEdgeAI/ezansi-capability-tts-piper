# Cold Start Guide

This guide helps you get the Piper TTS capability running from scratch on a fresh system.

## Prerequisites

- **Container Runtime**: Podman or Docker
- **Operating System**: Linux (tested on Ubuntu, Debian, Fedora, Raspberry Pi OS)
- **Minimum Resources**:
  - 300 MB RAM
  - 1 CPU core
  - 1.5 GB storage
- **Network**: Internet access for initial setup (to pull base image and voice models)
- **Tools**: `curl`, `jq` (optional, for testing)

## Step-by-Step Installation

### 1. Clone the Repository

```bash
git clone https://github.com/eZansiEdgeAI/ezansi-capability-tts-piper.git
cd ezansi-capability-tts-piper
```

### 2. Detect and Configure Hardware

Run the hardware configuration script to automatically detect your system capabilities:

```bash
./scripts/configure-hardware.sh
```

If you get a permissions error, run:

```bash
chmod +x ./scripts/configure-hardware.sh
./scripts/configure-hardware.sh
```

**Expected Output:**
```
Detecting system hardware...
Architecture: x86_64
Total RAM: 15994 MB
CPU Cores: 4
GPU Type: none

Recommended Configuration:
  CPU Limit: 2.0
  Memory Limit: 600M
  CPU Reservation: 0.5
  Memory Reservation: 300M

Configuration saved to .env
You can now run: podman-compose up -d
```

This creates a `.env` file with optimal settings for your hardware.

### 3. Start the Service (Build + Run)

```bash
podman-compose up -d --build
```

By default, the container will attempt to auto-download a default English Piper model on first start (downloads into the `/models` volume). This means you do not need to manually download a voice model for a first-run test.

If you're offline on first start, the service will still come up and eSpeak NG will still work, but Piper will remain unavailable until a model exists under `/models`.

To disable auto-download, set `AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL=0` (in `.env` or in `podman-compose.yml`). To change which voice is downloaded, set `DEFAULT_PIPER_VOICE_ID`.

### 4. Verify the Service is Running

Check container status:

```bash
podman ps
```

You should see the `piper-tts-capability` container running.

Check logs:

```bash
podman logs piper-tts-capability
```

**Expected Output:**
```
[+] Building ...
=> [1/5] FROM docker.io/linuxserver/piper:latest
=> [2/5] RUN apt-get update && apt-get install -y ...
=> [3/5] WORKDIR /app
=> [4/5] COPY requirements.txt /app/requirements.txt
=> [5/5] RUN pip3 install --no-cache-dir -r /app/requirements.txt
...
Successfully built localhost/ezansi-capability-tts-piper:1.0.0
```

**Build Time**: Approximately 2-5 minutes depending on your internet connection and system performance.

### 5. Test the Health Endpoint

```bash
curl http://localhost:10200/health | jq
```

**Expected Output (shape):**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "hardware": {"architecture": "...", "ram_mb": 0, "cpu_cores": 0, "gpu_type": "..."},
  "default_model_download": {"enabled": true, "voice_id": "en_US-lessac-medium", "state": "done", "error": null},
  "engines": {"piper": {"available": true, "ready": true}, "espeak": {"available": true, "ready": true}},
  "voices": {"piper_total": 1, "piper_ready": 1}
}
```

**Notes:**

- `status` is `healthy` if either Piper or eSpeak is ready.
- If this is your first run, `default_model_download.state` may be `in_progress` for a few minutes while the voice downloads.
- If you are offline, `default_model_download.state` may be `failed` and Piper synthesis will return `503` until a model exists under `/models`.

### 6. List Voices

Piper models discovered under `/models`:

```bash
curl -s http://localhost:10200/voices | jq
```

eSpeak NG voices available in the image:

```bash
curl -s http://localhost:10200/voices/espeak | jq
```

### 7. Synthesize Speech (Write WAV to File)

Test eSpeak first (works even if Piper is still downloading):

```bash
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from eSpeak","engine":"espeak","language":"en"}' \
  --output /tmp/espeak.wav
file /tmp/espeak.wav
```

Then test Piper (once `default_model_download.state` is `done`, or if you provided your own model under `/models`):

```bash
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from Piper"}' \
  --output /tmp/piper.wav
file /tmp/piper.wav
```

If you downloaded the default model, you can optionally force it explicitly as `voice: "voice"` (because it’s stored as `/models/voice.onnx`):

```bash
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello","engine":"piper","voice":"voice"}' \
  --output /tmp/piper-voice.wav
```

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
podman logs piper-tts-capability
```

**Common issues:**
- Port 10200 already in use: Change the port in `podman-compose.yml`
- Insufficient resources: Adjust limits in `.env` file

### Service Returns 503 on Synthesis

**Cause**: Piper model isn’t ready yet.

**Solutions:**

- Use eSpeak while waiting: set `{"engine":"espeak"}` in your request.
- Wait for the auto-download to complete and check `default_model_download.state` via `/health`.
- If you’re offline, provide a Piper model under `/models` (and ensure both `voice.onnx` and `voice.onnx.json` exist).

Restart after adding a model:

```bash
podman-compose restart
```

### “Unsupported WAV format” or `file` doesn’t show RIFF/WAVE

This usually means you saved an HTTP error response body as a `.wav`.

Re-run with `-i` to see the HTTP status and content-type:

```bash
curl -i -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello"}'
```

### Permission Issues with Scripts

Make scripts executable:
```bash
chmod +x scripts/configure-hardware.sh
```

## Next Steps

Once the service is running:

1. Proceed to the [Testing Guide](TESTING.md) to verify TTS functionality
2. Review the [README](README.md) for API documentation
3. Check the [ADR documentation](docs/adr/) for architectural decisions

## Quick Reference

| Command | Purpose |
|---------|---------|
| `./scripts/configure-hardware.sh` | Detect hardware and generate `.env` |
| `podman-compose build` | Build the container image |
| `podman-compose up -d` | Start the service |
| `podman-compose up -d --build` | Build + start in one command |
| `podman-compose down` | Stop the service |
| `podman-compose restart` | Restart the service |
| `podman logs piper-tts-capability` | View service logs |
| `curl http://localhost:10200/health` | Check service health |

## Reset to a True “First Run” (Optional)

If you want to repeat a cold start from scratch (including re-downloading the default voice), remove the models volume:

```bash
podman-compose down

# Find the volume name and remove it
podman volume ls | grep -E 'piper-models|piper_models|piper-model'
podman volume rm ezansi-capability-tts-piper_piper-models
```
