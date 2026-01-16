FROM rhasspy/piper:latest

# piper image is optimized for inference; we add a tiny HTTP wrapper.
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY src /app/src

ENV PORT=10200 \
    PIPER_BIN=piper \
    PIPER_MODEL_PATH=/models/voice.onnx \
    PIPER_CONFIG_PATH=/models/voice.onnx.json

VOLUME ["/models"]
EXPOSE 10200

CMD ["python3", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "10200"]
