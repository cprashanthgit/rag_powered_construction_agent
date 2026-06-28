# ══════════════════════════════════════════════════════════════════════
# deploy/Dockerfile — Construction RAG Assistant (FastAPI backend)
#
# Build context is the PROJECT ROOT (one level up from this file).
# The docker-compose.cloud.yml handles that automatically:
#   build:
#     context: ..
#     dockerfile: deploy/Dockerfile
#
# Never bake secrets into the image — pass them via .env.prod at runtime.
# ══════════════════════════════════════════════════════════════════════

FROM python:3.11-slim

# System dependencies required by PyTorch / sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer is cached if requirements-api.txt unchanged)
COPY requirements-api.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements-api.txt

# Copy application source files
COPY api.py              ./api.py
COPY pipeline.py         ./pipeline.py
COPY config.py           ./config.py
COPY generator.py        ./generator.py
COPY embedder.py         ./embedder.py
COPY retriever.py        ./retriever.py
COPY hybrid_retriever.py ./hybrid_retriever.py
COPY reranker.py         ./reranker.py

# Copy package directories
COPY auth/       ./auth/
COPY db/         ./db/
COPY memory/     ./memory/
COPY monitoring/ ./monitoring/

# vector_store/ is NOT baked in — it is mounted as a read-only volume
# at runtime via docker-compose.cloud.yml

EXPOSE 8000

# Single worker — the pipeline is CPU-bound; multiple workers would
# duplicate the cross-encoder model (~350MB) in RAM unnecessarily.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
