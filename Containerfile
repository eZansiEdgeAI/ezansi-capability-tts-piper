FROM docker.io/linuxserver/piper:latest

# piper image is optimized for inference; we add a tiny HTTP wrapper.
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip curl espeak-ng \
  && rm -rf /var/lib/apt/lists/*

# linuxserver/piper bundles piper as a python entrypoint under /lsiopy.
# Ensure runtime deps for that environment are present.
RUN /lsiopy/bin/pip install --no-cache-dir pathvalidate

# linuxserver's aarch64 piper-tts wheel can be missing the compiled espeakbridge extension.
# Provide a small pure-Python fallback that shells out to espeak-ng for IPA phonemes.
RUN cat > /lsiopy/lib/python3.12/site-packages/piper/espeakbridge.py <<'PY'
"""Pure-Python fallback for the piper.espeakbridge module.

The upstream piper-tts package normally provides a compiled espeakbridge extension.
On some platforms/images that extension may be missing.

This fallback shells out to espeak-ng to produce IPA phonemes.
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import List, Tuple

_data_dir: str | None = None
_voice: str = "en-us"


def initialize(data_dir: str) -> None:
  global _data_dir
  _data_dir = data_dir


def set_voice(voice: str) -> None:
  global _voice
  if voice:
    _voice = voice


def _espeak_env() -> dict:
  env = dict(os.environ)
  # espeak-ng commonly uses ESPEAK_DATA_PATH; keep it best-effort.
  if _data_dir:
    env.setdefault("ESPEAK_DATA_PATH", _data_dir)
  return env


def _phonemize_clause(text: str) -> str:
  text = text.strip()
  if not text:
    return ""
  # --ipa=3 gives a reasonably detailed IPA output.
  cmd = ["espeak-ng", "-q", "--ipa=3", "-v", _voice, text]
  result = subprocess.run(cmd, capture_output=True, text=True, env=_espeak_env())
  # Ignore stderr noise; only IPA phonemes are needed.
  return (result.stdout or "").strip()


def get_phonemes(text: str) -> List[Tuple[str, str, bool]]:
  # Split into clauses and preserve terminators.
  # Returns list of (phonemes, terminator, end_of_sentence)
  out: List[Tuple[str, str, bool]] = []

  s = (text or "").strip()
  if not s:
    return out

  parts = re.findall(r"[^.!?;:,]+[.!?;:,]?", s)
  if not parts:
    parts = [s]

  for part in parts:
    part = part.strip()
    if not part:
      continue

    terminator = part[-1] if part[-1] in ".!?;:," else ""
    clause_text = part[:-1].strip() if terminator else part
    phonemes = _phonemize_clause(clause_text)
    end_of_sentence = terminator in (".", "?", "!") or (terminator == "")
    out.append((phonemes, terminator, end_of_sentence))

  return out
PY

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY src /app/src

ENV PORT=10200 \
  PIPER_BIN=/lsiopy/bin/piper \
    PIPER_MODEL_PATH=/models/voice.onnx \
  PIPER_CONFIG_PATH=/models/voice.onnx.json \
  AUTO_DOWNLOAD_DEFAULT_PIPER_MODEL=1 \
  DEFAULT_PIPER_VOICE_ID=en_US-lessac-medium \
  PIPER_VOICES_INDEX_URL=https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json \
  PIPER_VOICES_BASE_URL=https://huggingface.co/rhasspy/piper-voices/resolve/main/

VOLUME ["/models"]
EXPOSE 10200

ENTRYPOINT []
CMD ["python3", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "10200"]
