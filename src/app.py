"""
FastAPI application for Piper TTS capability.

This service provides text-to-speech synthesis using Piper
with dynamic hardware configuration.
"""

import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .hardware_detection import get_hardware_info, get_recommended_resources


# Configuration from environment
PORT = int(os.getenv("PORT", "10200"))
PIPER_BIN = os.getenv("PIPER_BIN", "piper")
PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "/models/voice.onnx")
PIPER_CONFIG_PATH = os.getenv("PIPER_CONFIG_PATH", "/models/voice.onnx.json")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
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
    description="Text-to-speech synthesis using Piper with dynamic hardware detection",
    version="1.0.0",
    lifespan=lifespan
)


class SynthesizeRequest(BaseModel):
    """Request model for TTS synthesis."""
    text: str = Field(..., description="Text to synthesize", min_length=1)
    speaker: Optional[int] = Field(None, description="Speaker ID for multi-speaker models")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    hardware: dict


class CapabilityResponse(BaseModel):
    """Capability metadata response."""
    name: str
    version: str
    type: str
    description: str
    provides: list
    resources: dict
    hardware: dict


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and hardware information.
    """
    model_exists = Path(PIPER_MODEL_PATH).exists()
    hw_info = get_hardware_info()
    
    return HealthResponse(
        status="healthy" if model_exists else "degraded",
        model_loaded=model_exists,
        hardware=hw_info
    )


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
        description="Text-to-speech synthesis using Piper with dynamic hardware detection",
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
    # Check if model exists
    if not Path(PIPER_MODEL_PATH).exists():
        raise HTTPException(
            status_code=503,
            detail=f"Model not found at {PIPER_MODEL_PATH}"
        )
    
    # Build piper command
    cmd = [
        PIPER_BIN,
        "--model", PIPER_MODEL_PATH,
        "--output-raw"
    ]
    
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
