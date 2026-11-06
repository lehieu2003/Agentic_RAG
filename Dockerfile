# Backend API container: FastAPI + local embedding/reranker/OCR models.
# First start downloads the models into the mounted HF cache (~4 GB) — see
# docker-compose.yml for the volume wiring.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/data/hf-cache

# libgomp1:  required by onnxruntime (RapidOCR) and torch CPU wheels.
# libgl1 + libglib2.0-0: required by opencv-python (RapidOCR dependency).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Torch CPU wheel first: avoids pulling the ~2 GB CUDA stack that the plain
# PyPI wheel would bring, which the API never uses.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Application data: uploads, Qdrant storage, session DB, HF model cache.
RUN useradd --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data
USER appuser

EXPOSE 8000

# start-period is long because the first boot downloads the embedding and
# reranker models before the app can answer probes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# Single worker: the embedded (local-path) Qdrant client takes an exclusive
# file lock; scale by pointing QDRANT_URL at a Qdrant server instead.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
