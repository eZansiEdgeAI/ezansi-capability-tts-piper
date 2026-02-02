"""FastAPI application for the eZansi TTS capability.

This service provides text-to-speech synthesis using Piper (neural)
and an optional eSpeak NG fallback (classic) with dynamic hardware
configuration.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import threading
from dataclasses import dataclass
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .hardware_detection import get_hardware_info, get_recommended_resources


# Configuration from environment
PORT = int(os.getenv("PORT", "10200"))

# linuxserver/piper puts binaries under /lsiopy/bin. If PIPER_BIN isn't set,
# fall back to common locations.
_DEFAULT_PIPER_CANDIDATES = [
    "piper",
    "/lsiopy/bin/piper",
    "/usr/local/bin/piper",
    "/usr/bin/piper",
]
PIPER_BIN = os.getenv("PIPER_BIN") or next(
    (p for p in _DEFAULT_PIPER_CANDIDATES if Path(p).exists() or p == "piper"),
    "piper",
)

MODELS_DIR = Path(os.getenv("MODELS_DIR", "/models"))
PIPER_MODEL_PATH = Path(os.getenv("PIPER_MODEL_PATH", str(MODELS_DIR / "voice.onnx")))
PIPER_CONFIG_PATH = Path(os.getenv("PIPER_CONFIG_PATH", str(MODELS_DIR / "voice.onnx.json")))
ESPEAK_BIN = os.getenv("ESPEAK_BIN", "espeak-ng")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL = _env_bool("AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL", False)
DEFAULT_PIPER_VOICE_ID = os.getenv("DEFAULT_PIPER_VOICE_ID") or "en_US-lessac-medium"
PIPER_VOICES_INDEX_URL = os.getenv(
    "PIPER_VOICES_INDEX_URL",
    "https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json",
)
PIPER_VOICES_BASE_URL = os.getenv(
    "PIPER_VOICES_BASE_URL",
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/",
)


@dataclass
class DefaultModelDownloadStatus:
    enabled: bool
    voice_id: str
    state: Literal["disabled", "not_needed", "in_progress", "done", "failed"]
    error: Optional[str] = None


_default_model_status_lock = threading.Lock()
_default_model_status = DefaultModelDownloadStatus(
    enabled=AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL,
    voice_id=DEFAULT_PIPER_VOICE_ID,
    state="disabled" if not AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL else "in_progress",
    error=None,
)


def _download_to_path(url: str, dest: Path, expected_md5: Optional[str] = None, timeout_s: int = 300) -> None:
    """Download a URL to dest (atomic write) and optionally verify MD5."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        with tempfile.NamedTemporaryFile(prefix=dest.name + ".", suffix=".tmp", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            md5 = hashlib.md5()
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
                md5.update(chunk)
            tmp.flush()

    actual_md5 = md5.hexdigest()
    if expected_md5 and actual_md5.lower() != expected_md5.lower():
        tmp_path.unlink(missing_ok=True)
        raise ValueError(f"MD5 mismatch for {url}: expected {expected_md5} got {actual_md5}")

    shutil.move(str(tmp_path), str(dest))


def _maybe_auto_download_default_piper_model() -> None:
    """Optionally download a default Piper model into the /models volume.

    This mimics the 'first run pulls a default model' behavior: if the configured
    model/config files are missing and AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL is enabled,
    download DEFAULT_PIPER_VOICE_ID from the Piper voices index.
    """
    with _default_model_status_lock:
        _default_model_status.enabled = AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL
        _default_model_status.voice_id = DEFAULT_PIPER_VOICE_ID

        if not AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL:
            _default_model_status.state = "disabled"
            _default_model_status.error = None
            return

        if PIPER_MODEL_PATH.exists() and PIPER_CONFIG_PATH.exists():
            _default_model_status.state = "not_needed"
            _default_model_status.error = None
            return

        _default_model_status.state = "in_progress"
        _default_model_status.error = None

    try:
        with urllib.request.urlopen(PIPER_VOICES_INDEX_URL, timeout=30) as resp:
            voices = json.loads(resp.read().decode("utf-8", errors="ignore"))

        voice_entry = voices.get(DEFAULT_PIPER_VOICE_ID)
        if not voice_entry:
            with _default_model_status_lock:
                _default_model_status.state = "failed"
                _default_model_status.error = (
                    f"Default Piper voice id '{DEFAULT_PIPER_VOICE_ID}' not found in voices index"
                )
            print(
                f"WARN: Default Piper voice id '{DEFAULT_PIPER_VOICE_ID}' not found in voices index; "
                "skipping auto-download"
            )
            return

        files = voice_entry.get("files") or {}
        onnx_rel = next((p for p in files.keys() if p.endswith(".onnx")), None)
        json_rel = next((p for p in files.keys() if p.endswith(".onnx.json")), None)
        if not onnx_rel or not json_rel:
            with _default_model_status_lock:
                _default_model_status.state = "failed"
                _default_model_status.error = (
                    f"voices index entry '{DEFAULT_PIPER_VOICE_ID}' missing .onnx/.onnx.json paths"
                )
            print(
                f"WARN: voices index entry '{DEFAULT_PIPER_VOICE_ID}' missing .onnx/.onnx.json paths; "
                "skipping auto-download"
            )
            return

        onnx_md5 = (files.get(onnx_rel) or {}).get("md5_digest")
        json_md5 = (files.get(json_rel) or {}).get("md5_digest")

        onnx_url = PIPER_VOICES_BASE_URL.rstrip("/") + "/" + onnx_rel
        json_url = PIPER_VOICES_BASE_URL.rstrip("/") + "/" + json_rel

        print(
            f"No Piper model found at {PIPER_MODEL_PATH}. "
            f"Auto-downloading default voice '{DEFAULT_PIPER_VOICE_ID}'..."
        )
        _download_to_path(onnx_url, PIPER_MODEL_PATH, expected_md5=onnx_md5)
        _download_to_path(json_url, PIPER_CONFIG_PATH, expected_md5=json_md5)
        print(f"Default Piper voice downloaded to {PIPER_MODEL_PATH}")
        with _default_model_status_lock:
            _default_model_status.state = "done"
            _default_model_status.error = None

    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        # Do not fail container startup; remain degraded until a model is provided.
        with _default_model_status_lock:
            _default_model_status.state = "failed"
            _default_model_status.error = str(e)
        print(f"WARN: Failed to auto-download default Piper voice: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Downloading a default model can take a while on first run.
    # Do it in the background so the service can come up (and still serve eSpeak).
    threading.Thread(target=_maybe_auto_download_default_piper_model, daemon=True).start()
    # Startup: Log hardware information
    hw_info = get_hardware_info()
    recommended = get_recommended_resources()
    
    print("=" * 60)
    print("Piper TTS Capability Starting")
    print("=" * 60)
    print(f"Detected Hardware:")
    print(f"  Architecture: {hw_info['architecture']}")
    print(f"  RAM: {hw_info['ram_mb']} MB")
    print(f"  CPU Cores: {hw_info['cpu_cores']}")
    print(f"  GPU: {hw_info['gpu_type']}")
    print(f"\nRecommended Resources:")
    print(f"  RAM: {recommended['ram_mb']} MB")
    print(f"  CPU Cores: {recommended['cpu_cores']}")
    print(f"  Accelerator: {recommended['accelerator']}")
    print("=" * 60)
    
    yield
    
    # Shutdown: cleanup if needed
    print("Piper TTS Capability shutting down")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Piper TTS Capability",
    description="Text-to-speech synthesis using Piper (and optional eSpeak NG) with dynamic hardware detection",
    version="1.0.0",
    lifespan=lifespan
)


class SynthesizeRequest(BaseModel):
    """Request model for TTS synthesis."""
    text: str = Field(..., description="Text to synthesize", min_length=1)
    speaker: Optional[int] = Field(None, description="Speaker ID for multi-speaker models")
    engine: Optional[Literal["piper", "espeak"]] = Field(
        None,
        description="TTS engine to use. Defaults to piper when available.",
    )
    voice: Optional[str] = Field(
        None,
        description=(
            "Voice/model id. For Piper, this is a model id returned by GET /voices. "
            "If omitted, uses PIPER_MODEL_PATH."
        ),
    )
    language: Optional[str] = Field(
        None,
        description="Language/voice code for espeak-ng (e.g., 'en', 'en-us', 'af').",
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    hardware: dict
    default_model_download: dict
    engines: dict
    voices: dict


class CapabilityResponse(BaseModel):
    """Capability metadata response."""
    name: str
    version: str
    type: str
    description: str
    provides: list
    resources: dict
    hardware: dict


class VoiceInfo(BaseModel):
    """Information about an available voice/model on disk."""

    id: str
    engine: Literal["piper", "espeak"]
    # Piper fields
    model_path: Optional[str] = None
    config_path: Optional[str] = None
    ready: Optional[bool] = None
    # eSpeak fields
    language: Optional[str] = None
    voice_name: Optional[str] = None
    gender_age: Optional[str] = None
    file: Optional[str] = None
    other_languages: Optional[str] = None


def _discover_espeak_voices() -> list[VoiceInfo]:
    """Discover voices available in espeak-ng.

    This parses the output of `espeak-ng --voices` into a structured list.
    """
    try:
        result = subprocess.run(
            [ESPEAK_BIN, "--voices"],
            capture_output=True,
            check=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return []

    text = result.stdout.decode("utf-8", errors="ignore")
    voices: list[VoiceInfo] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("pty"):
            continue

        # Typical columns (whitespace-delimited):
        # Pty  Language  Age/Gender  VoiceName  File  Other Languages
        parts = line.split()
        if len(parts) < 5:
            continue

        language = parts[1]
        gender_age = parts[2]
        voice_name = parts[3]
        file = parts[4]
        other = " ".join(parts[5:]) if len(parts) > 5 else None

        voices.append(
            VoiceInfo(
                id=f"{language}:{voice_name}",
                engine="espeak",
                language=language,
                voice_name=voice_name,
                gender_age=gender_age,
                file=file,
                other_languages=other,
            )
        )

    return voices


def _discover_piper_voices(models_dir: Path = MODELS_DIR) -> list[VoiceInfo]:
    """Discover Piper voices under /models.

    We treat every *.onnx file as a voice and expect a matching *.onnx.json next to it.
    Voice id is the relative path (without suffix) from models_dir.
    """
    voices: list[VoiceInfo] = []
    if not models_dir.exists():
        return voices

    for model_path in sorted(models_dir.rglob("*.onnx")):
        try:
            rel = model_path.relative_to(models_dir)
        except ValueError:
            continue

        voice_id = str(rel.with_suffix(""))
        config_path = model_path.with_suffix(model_path.suffix + ".json")  # .onnx.json
        ready = model_path.exists() and config_path.exists()

        voices.append(
            VoiceInfo(
                id=voice_id,
                engine="piper",
                model_path=str(model_path),
                config_path=str(config_path),
                ready=ready,
            )
        )

    return voices


def _resolve_piper_voice(voice_id: Optional[str]) -> tuple[Path, Path]:
    """Resolve the model/config paths for a Piper voice.

    If voice_id is None, uses configured PIPER_MODEL_PATH/PIPER_CONFIG_PATH.
    Otherwise voice_id must match a discovered voice id.
    """
    if not voice_id:
        return PIPER_MODEL_PATH, PIPER_CONFIG_PATH

    for voice in _discover_piper_voices():
        if voice.id == voice_id:
            return Path(voice.model_path), Path(voice.config_path)

    raise HTTPException(status_code=404, detail=f"Unknown voice '{voice_id}'. See GET /voices")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and hardware information.
    """
    piper_bin_exists = bool(shutil.which(PIPER_BIN) or Path(PIPER_BIN).exists())
    piper_model_exists = PIPER_MODEL_PATH.exists()
    piper_config_exists = PIPER_CONFIG_PATH.exists()
    piper_ready = piper_bin_exists and piper_model_exists and piper_config_exists

    espeak_bin_exists = bool(shutil.which(ESPEAK_BIN) or Path(ESPEAK_BIN).exists())
    espeak_ready = espeak_bin_exists

    hw_info = get_hardware_info()

    with _default_model_status_lock:
        download_status = {
            "enabled": _default_model_status.enabled,
            "voice_id": _default_model_status.voice_id,
            "state": _default_model_status.state,
            "error": _default_model_status.error,
        }

    piper_voices = _discover_piper_voices()
    piper_ready_count = sum(1 for v in piper_voices if v.ready)

    engines = {
        "piper": {
            "available": piper_bin_exists,
            "ready": piper_ready,
            "bin": PIPER_BIN,
            "model_path": str(PIPER_MODEL_PATH),
            "config_path": str(PIPER_CONFIG_PATH),
            "model_exists": piper_model_exists,
            "config_exists": piper_config_exists,
        },
        "espeak": {
            "available": espeak_bin_exists,
            "ready": espeak_ready,
            "bin": ESPEAK_BIN,
        },
    }

    voices_summary = {
        "piper_total": len(piper_voices),
        "piper_ready": piper_ready_count,
    }

    overall_ok = piper_ready or espeak_ready
    
    return HealthResponse(
        status="healthy" if overall_ok else "degraded",
        model_loaded=piper_ready,
        hardware=hw_info,
        default_model_download=download_status,
        engines=engines,
        voices=voices_summary,
    )


@app.get("/voices", response_model=list[VoiceInfo])
async def list_voices():
    """List available voices/models under /models.

    For now this only lists Piper voices (onnx + onnx.json).
    """
    return _discover_piper_voices()


@app.get("/voices/espeak", response_model=list[VoiceInfo])
async def list_espeak_voices():
    """List eSpeak NG voices available in the container."""
    return _discover_espeak_voices()


@app.get("/.well-known/capability.json", response_model=CapabilityResponse)
async def get_capability():
    """
    Capability metadata endpoint.
    
    Returns dynamic capability information based on detected hardware.
    """
    recommended = get_recommended_resources()
    hw_info = get_hardware_info()
    
    return CapabilityResponse(
        name="piper-tts",
        version="1.0.0",
        type="capability",
        description="Text-to-speech synthesis using Piper (and optional eSpeak NG) with dynamic hardware detection",
        provides=["text-to-speech"],
        resources=recommended,
        hardware=hw_info
    )


@app.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """
    Synthesize speech from text.
    
    Args:
        request: SynthesizeRequest with text and optional speaker ID
        
    Returns:
        WAV audio file
    """
    # Decide engine
    engine = request.engine
    if engine is None:
        engine = "piper"

    if engine == "espeak":
        # espeak-ng writes WAV directly
        lang = request.language or "en"
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            cmd = [ESPEAK_BIN, "-v", lang, "-w", tmp.name, request.text]
            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=30)
                wav_data = Path(tmp.name).read_bytes()
                return Response(
                    content=wav_data,
                    media_type="audio/wav",
                    headers={"Content-Disposition": "attachment; filename=speech.wav"},
                )
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=504, detail="TTS synthesis timed out")
            except subprocess.CalledProcessError as e:
                stderr = (e.stderr or b"").decode("utf-8", errors="ignore")
                if "voice does not exist" in stderr.lower():
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Unknown espeak-ng voice/language '{lang}'. "
                            "List available codes inside the container with: espeak-ng --voices"
                        ),
                    )
                raise HTTPException(status_code=500, detail=f"eSpeak synthesis failed: {stderr}")

    # Piper
    model_path, config_path = _resolve_piper_voice(request.voice)

    if not model_path.exists() or not config_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Piper model not ready. Missing {model_path} or {config_path}",
        )

    cmd = [PIPER_BIN, "--model", str(model_path), "--config", str(config_path), "--output-raw"]
    if request.speaker is not None:
        cmd.extend(["--speaker", str(request.speaker)])
    
    try:
        # Run piper with text input
        result = subprocess.run(
            cmd,
            input=request.text.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=30
        )
        
        # Return raw PCM audio as WAV
        # Piper outputs raw 16-bit PCM at 22050 Hz mono by default
        # We need to add WAV header
        audio_data = result.stdout
        wav_data = _create_wav_header(len(audio_data)) + audio_data
        
        return Response(
            content=wav_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav"
            }
        )
        
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="TTS synthesis timed out"
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"TTS synthesis failed: {e.stderr.decode('utf-8', errors='ignore')}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


def _create_wav_header(data_size: int, sample_rate: int = 22050, 
                       bits_per_sample: int = 16, channels: int = 1) -> bytes:
    """
    Create a WAV file header.
    
    Args:
        data_size: Size of audio data in bytes
        sample_rate: Audio sample rate (default: 22050 Hz)
        bits_per_sample: Bits per sample (default: 16)
        channels: Number of channels (default: 1 for mono)
        
    Returns:
        WAV header as bytes
    """
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    
    header = bytearray()
    
    # RIFF header
    header.extend(b'RIFF')
    header.extend((data_size + 36).to_bytes(4, 'little'))  # File size - 8
    header.extend(b'WAVE')
    
    # fmt subchunk
    header.extend(b'fmt ')
    header.extend((16).to_bytes(4, 'little'))  # Subchunk size
    header.extend((1).to_bytes(2, 'little'))   # Audio format (1 = PCM)
    header.extend(channels.to_bytes(2, 'little'))
    header.extend(sample_rate.to_bytes(4, 'little'))
    header.extend(byte_rate.to_bytes(4, 'little'))
    header.extend(block_align.to_bytes(2, 'little'))
    header.extend(bits_per_sample.to_bytes(2, 'little'))
    
    # data subchunk
    header.extend(b'data')
    header.extend(data_size.to_bytes(4, 'little'))
    
    return bytes(header)
