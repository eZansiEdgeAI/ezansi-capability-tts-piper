# Testing Guide

This guide provides step-by-step instructions to manually test the TTS capability and verify WAV output.

## Prerequisites

Before testing, ensure:
- The service is running (see [COLD_START.md](COLD_START.md) if needed)
- A voice model is loaded at `/models/voice.onnx`
- You have `curl` installed for API testing
- Optional: `file`, `ffplay`, `aplay`, or `sox` for audio playback

## Voice/Engine Selection

This service supports multiple synthesis engines:

- **Piper** (neural, higher quality) using `.onnx` + `.onnx.json` models under `/models`
- **eSpeak NG** (classic, lower quality but fast and multilingual)

List available Piper models discovered under `/models`:

```bash
curl -s http://localhost:10200/voices | jq
```

List available eSpeak NG voices (language codes) discovered at runtime:

```bash
curl -s http://localhost:10200/voices/espeak | jq
```

If you use eSpeak NG, you can list available language codes inside the container:

```bash
podman exec -it piper-tts-capability espeak-ng --voices | head
```

## Test 1: Service Health Check

Verify the service is running and hardware is detected correctly.

### Command

```bash
curl -s http://localhost:10200/health | jq
```

### Expected Output

```json
{
  "status": "healthy",
  "model_loaded": true,
  "hardware": {
    "architecture": "x86_64",
    "ram_mb": 14183,
    "cpu_cores": 4,
    "gpu_type": "none"
  },
  "default_model_download": {
    "enabled": true,
    "voice_id": "en_US-lessac-medium",
    "state": "done",
    "error": null
  },
  "engines": {
    "piper": {
      "available": true,
      "ready": true,
      "bin": "/lsiopy/bin/piper",
      "model_path": "/models/voice.onnx",
      "config_path": "/models/voice.onnx.json",
      "model_exists": true,
      "config_exists": true
    },
    "espeak": {
      "available": true,
      "ready": true,
      "bin": "espeak-ng"
    }
  },
  "voices": {
    "piper_total": 1,
    "piper_ready": 1
  }
}
```

### What to Check

- ✅ `status` should be `"healthy"` (if model is loaded) or `"degraded"` (if no model)
- ✅ `model_loaded` should be `true` if a voice model exists at `/models/voice.onnx`
- ✅ `hardware` section shows correct system information

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Check if service is running: `podman ps` |
| `status: "degraded"` | Download a voice model (see COLD_START.md step 3) |
| Wrong hardware values | Re-run `./scripts/configure-hardware.sh` |

---

## Test 2: Capability Metadata

Verify the capability exposes correct metadata with dynamic resource information.

### Command

```bash
curl -s http://localhost:10200/.well-known/capability.json | jq
```

### Expected Output

```json
{
  "name": "piper-tts",
  "version": "1.0.0",
  "type": "capability",
  "description": "Text-to-speech synthesis using Piper with dynamic hardware detection",
  "provides": [
    "text-to-speech"
  ],
  "resources": {
    "ram_mb": 600,
    "cpu_cores": 2,
    "accelerator": "none",
    "architecture": "x86_64"
  },
  "hardware": {
    "architecture": "x86_64",
    "ram_mb": 14183,
    "cpu_cores": 4,
    "gpu_type": "none"
  }
}
```

### What to Check

- ✅ `resources` shows recommended allocation based on your hardware
- ✅ `hardware` shows actual detected system capabilities
- ✅ Both sections should have consistent architecture values

---

## Test 3: Basic TTS Synthesis

Synthesize a simple phrase and save to WAV file.

### Command

```bash
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from eZansi TTS"}' \
  --output /tmp/test_output.wav
```

### Verify the Output

Check that a valid WAV file was created:

```bash
file /tmp/test_output.wav
```

**Expected Output:**
```
/tmp/test_output.wav: RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 22050 Hz
```

### What to Check

- ✅ File exists and is not empty: `ls -lh /tmp/test_output.wav`
- ✅ File type is `WAVE audio`
- ✅ Audio format: 16-bit PCM, mono, 22050 Hz (Piper default)

### Play the Audio

**Using `ffplay` (part of ffmpeg):**
```bash
ffplay -autoexit -nodisp /tmp/test_output.wav
```

**Using `aplay` (ALSA):**
```bash
aplay /tmp/test_output.wav
```

**Using `play` (SoX):**
```bash
play /tmp/test_output.wav
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| 503 Service Unavailable | Model not loaded - check health endpoint |
| 500 Internal Server Error | Check logs: `podman logs piper-tts-capability` |
| Empty or corrupt WAV | Verify model files exist in `/models/` |
| No audio playback | Check system audio settings or use different player |

---

## Test 3b: eSpeak NG Synthesis (Afrikaans example)

This works even when no Piper model is loaded.

```bash
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hallo, hoe gaan dit?","engine":"espeak","language":"af"}' \
  --output /tmp/af.wav
file /tmp/af.wav
```

If you get a 400 error about an unknown voice/language, run:

```bash
podman exec -it piper-tts-capability espeak-ng --voices
```

---

## Test 4: Long Text Synthesis

Test with longer text to verify performance and quality.

### Command

```bash
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "The eZansi Edge AI platform enables artificial intelligence capabilities on edge devices. This text-to-speech service uses Piper for high-quality synthesis with automatic hardware detection and dynamic resource allocation."
  }' \
  --output /tmp/long_text.wav
```

### Verify

```bash
# Check file size (should be larger than test 3)
ls -lh /tmp/long_text.wav

# Verify format
file /tmp/long_text.wav

# Play audio
ffplay -autoexit -nodisp /tmp/long_text.wav
```

### What to Check

- ✅ File size is proportional to text length
- ✅ Synthesis completes in reasonable time (< 30 seconds)
- ✅ Audio quality is consistent throughout

---

## Test 5: Multi-Speaker Model (If Available)

If your voice model supports multiple speakers, test speaker selection.

### Command

```bash
# Try speaker 0
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"This is speaker zero", "speaker":0}' \
  --output /tmp/speaker_0.wav

# Try speaker 1
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"This is speaker one", "speaker":1}' \
  --output /tmp/speaker_1.wav
```

### Verify

Compare the two outputs:
```bash
ffplay -autoexit -nodisp /tmp/speaker_0.wav
ffplay -autoexit -nodisp /tmp/speaker_1.wav
```

**Note**: Single-speaker models ignore the `speaker` parameter.

---

## Test 6: Error Handling

Verify the API handles errors correctly.

### Test 6a: Empty Text

```bash
curl -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":""}'
```

**Expected:** HTTP 422 Validation Error

### Test 6b: Invalid JSON

```bash
curl -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d 'invalid json'
```

**Expected:** HTTP 422 Validation Error

### Test 6c: Missing Content-Type

```bash
curl -X POST http://localhost:10200/synthesize \
  -d '{"text":"test"}'
```

**Expected:** HTTP 422 Validation Error

---

## Test 7: Hardware Detection Accuracy

Verify detected hardware matches your system.

### Command

```bash
# Get detected hardware from service
curl -s http://localhost:10200/health | jq .hardware

# Compare with actual system specs
echo "System Info:"
uname -m  # Architecture
nproc     # CPU cores
free -m | grep Mem: | awk '{print $2 " MB total RAM"}'
```

### What to Check

- ✅ Architecture matches `uname -m`
- ✅ CPU cores matches `nproc`
- ✅ RAM is approximately correct (within 10%)

---

## Test 8: Resource Limits

Verify the container respects configured resource limits.

### Check Container Stats

```bash
podman stats --no-stream piper-tts-capability
```

### Expected Output

```
CONTAINER ID   NAME                   CPU %   MEM USAGE / LIMIT   MEM %   NET IO       BLOCK IO   PIDS
abc123def456   piper-tts-capability   0.5%    250MB / 600MB       41.67%  1.2kB / 0B   0B / 0B    3
```

### What to Check

- ✅ Memory usage stays within configured limit (600MB default)
- ✅ CPU usage is reasonable (varies during synthesis)

---

## Test 9: Stress Test

Test service stability under load.

### Command

```bash
# Synthesize 10 different phrases rapidly
for i in {1..10}; do
  echo "Synthesis $i..."
  curl -s -X POST http://localhost:10200/synthesize \
    -H 'Content-Type: application/json' \
    -d "{\"text\":\"This is test number $i\"}" \
    --output /tmp/stress_test_$i.wav
done

echo "All files created:"
ls -lh /tmp/stress_test_*.wav
```

### What to Check

- ✅ All 10 files created successfully
- ✅ All files are valid WAV format
- ✅ Service remains responsive after test
- ✅ No memory leaks (check `podman stats`)

---

## Test 10: API Documentation

Verify the auto-generated API documentation is accessible.

### Command

```bash
# Open in browser or use curl
curl -s http://localhost:10200/docs
```

**In Browser**: Navigate to `http://localhost:10200/docs`

### What to Check

- ✅ Swagger UI loads correctly
- ✅ All endpoints are documented (`/health`, `/.well-known/capability.json`, `/synthesize`)
- ✅ Interactive API testing works

---

## Complete Test Suite Script

Run all tests automatically:

```bash
#!/bin/bash
# Complete TTS capability test suite

echo "=========================================="
echo "TTS Capability Test Suite"
echo "=========================================="

# Test 1: Health Check
echo -e "\nTest 1: Health Check"
curl -s http://localhost:10200/health | jq .status

# Test 2: Capability Metadata
echo -e "\nTest 2: Capability Metadata"
curl -s http://localhost:10200/.well-known/capability.json | jq .name

# Test 3: Basic Synthesis
echo -e "\nTest 3: Basic Synthesis"
curl -s -X POST http://localhost:10200/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test successful"}' \
  --output /tmp/test.wav
file /tmp/test.wav

# Test 4: Hardware Detection
echo -e "\nTest 4: Hardware Detection"
curl -s http://localhost:10200/health | jq .hardware

echo -e "\n=========================================="
echo "Test Suite Complete"
echo "=========================================="
```

Save this as `scripts/test-suite.sh`, make it executable (`chmod +x scripts/test-suite.sh`), and run it.

---

## Success Criteria

All tests pass when:

1. ✅ Health endpoint returns `"healthy"` status
2. ✅ Capability metadata shows correct resource allocation
3. ✅ Synthesis generates valid WAV files
4. ✅ Audio playback works correctly
5. ✅ Hardware detection is accurate
6. ✅ Resource limits are respected
7. ✅ Error handling works correctly
8. ✅ Service remains stable under load

## Next Steps

- Review [README.md](README.md) for more API details
- Check [docs/adr/](docs/adr/) for architecture decisions
- Explore different voice models from [Piper releases](https://github.com/rhasspy/piper/releases)
