# -*- coding: utf-8 -*-
"""
config.py — Central configuration module for the Construction Knowledge Assistant.

All constants are loaded from .env via python-dotenv.
Every other module imports from this file exclusively — no hardcoded values elsewhere.

# ─── BACKEND UPGRADE PATHS ────────────────────────────────────────────────────
#
# [MODE 1 — LOCAL, fully offline after first model download]
#   EMBEDDING_BACKEND=huggingface
#   EMBEDDING_MODEL=all-MiniLM-L6-v2
#   LLM_BACKEND=huggingface
#   LLM_MODEL=google/flan-t5-base
#   VECTOR_BACKEND=faiss
#
# [MODE 2 — PINECONE cloud VectorDB + local models (recommended dev mode)]
#   EMBEDDING_BACKEND=huggingface
#   VECTOR_BACKEND=pinecone
#   PINECONE_API_KEY=your_key
#   PINECONE_INDEX_NAME_LOCAL=cnst-local   ← 384-dim index
#
# [MODE 3 — DEMO DAY: full OpenAI + Pinecone, best quality]
#   EMBEDDING_BACKEND=openai
#   LLM_BACKEND=openai
#   LLM_MODEL=gpt-3.5-turbo
#   VECTOR_BACKEND=pinecone
#   PINECONE_INDEX_NAME_OPENAI=cnst-openai ← 1536-dim index
#   OPENAI_API_KEY=your_key
#
# ─────────────────────────────────────────────────────────────────────────────
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env file ─────────────────────────────────────────────────────────────
load_dotenv(override=True)

# ── LangSmith Observability ────────────────────────────────────────────────────
# Enables full trace-level visibility: retrieval, reranking, generation.
# Free tier: 5,000 traces/month at https://smith.langchain.com
# Set LANGCHAIN_TRACING_V2=true in .env to activate.
LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false").strip().lower()
LANGCHAIN_API_KEY:    str = os.getenv("LANGCHAIN_API_KEY",    "")
LANGCHAIN_PROJECT:    str = os.getenv("LANGCHAIN_PROJECT",    "cnst-rag-assistant")
LANGCHAIN_ENDPOINT:   str = os.getenv("LANGCHAIN_ENDPOINT",   "https://api.smith.langchain.com")

if LANGCHAIN_TRACING_V2 == "true" and LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]    = LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"]    = LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"]   = LANGCHAIN_ENDPOINT
    _langsmith_status = f"ENABLED  (project: {LANGCHAIN_PROJECT})"
elif LANGCHAIN_TRACING_V2 == "true" and not LANGCHAIN_API_KEY:
    _langsmith_status = "DISABLED (LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY not set)"
else:
    _langsmith_status = "DISABLED (set LANGCHAIN_TRACING_V2=true in .env to enable)"

# ── Valid option sets ──────────────────────────────────────────────────────────
VALID_LLM_BACKENDS    = ["huggingface", "openai", "ollama"]
VALID_EMB_BACKENDS    = ["huggingface", "openai"]
VALID_VECTOR_BACKENDS = ["faiss", "pinecone"]

# ── Embedding configuration ────────────────────────────────────────────────────
EMBEDDING_BACKEND: str = os.getenv("EMBEDDING_BACKEND", "huggingface").strip().lower()
EMBEDDING_MODEL:   str = os.getenv("EMBEDDING_MODEL",   "all-MiniLM-L6-v2")

# ── LLM configuration ─────────────────────────────────────────────────────────
LLM_BACKEND: str = os.getenv("LLM_BACKEND", "huggingface").strip().lower()
LLM_MODEL:   str = os.getenv("LLM_MODEL",   "google/flan-t5-base")

# ── Vector store backend ───────────────────────────────────────────────────────
VECTOR_BACKEND: str = os.getenv("VECTOR_BACKEND", "faiss").strip().lower()

# ── API keys & service URLs ────────────────────────────────────────────────────
OPENAI_API_KEY:   str = os.getenv("OPENAI_API_KEY",   "")
OLLAMA_BASE_URL:  str = os.getenv("OLLAMA_BASE_URL",  "http://localhost:11434")
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")

# ── Pinecone index names ───────────────────────────────────────────────────────
# Two indexes because dimension is locked at index creation time:
#   cnst-local  → 384-dim  (all-MiniLM-L6-v2, HuggingFace)
#   cnst-openai → 1536-dim (text-embedding-3-small, OpenAI)
PINECONE_INDEX_NAME_LOCAL:  str = os.getenv("PINECONE_INDEX_NAME_LOCAL",  "cnst-local")
PINECONE_INDEX_NAME_OPENAI: str = os.getenv("PINECONE_INDEX_NAME_OPENAI", "cnst-openai")

# ── File paths (always use pathlib.Path) ───────────────────────────────────────
DATA_DIR:         Path = Path(os.getenv("DATA_DIR",         "./data"))
VECTOR_STORE_DIR: Path = Path(os.getenv("VECTOR_STORE_DIR", "./vector_store"))

# ── Chunking parameters ────────────────────────────────────────────────────────
CHUNK_SIZE:    int = int(os.getenv("CHUNK_SIZE",    "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

# ── Retrieval parameters ───────────────────────────────────────────────────────
# TOP_K: number of candidates fetched from BM25 + dense before re-ranking.
# RERANKER_TOP_N: number of docs passed to the LLM after re-ranking (≤ TOP_K).
TOP_K:         int = int(os.getenv("TOP_K",          "5"))
RERANKER_TOP_N: int = int(os.getenv("RERANKER_TOP_N", "3"))

# ── Hybrid search (BM25 + dense) ──────────────────────────────────────────────
HYBRID_SEARCH_ENABLED: bool  = os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() == "true"
HYBRID_BM25_WEIGHT:    float = float(os.getenv("HYBRID_BM25_WEIGHT",  "0.4"))
HYBRID_DENSE_WEIGHT:   float = float(os.getenv("HYBRID_DENSE_WEIGHT", "0.6"))

# ── Cross-encoder re-ranking ───────────────────────────────────────────────────
RERANKER_ENABLED: bool = os.getenv("RERANKER_ENABLED", "true").lower() == "true"
RERANKER_MODEL:   str  = os.getenv(
    "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# ── Startup validation ─────────────────────────────────────────────────────────
# NOTE: data/ directory is only required for build_index.py (ingestion).
# The API server uses Pinecone for vector search — no PDFs needed at runtime.
if not DATA_DIR.exists():
    print(
        f"[config] WARNING: Data directory not found: {DATA_DIR.resolve()}. "
        "This is expected in cloud/API-only deployments (Pinecone handles vectors). "
        "Only needed if running build_index.py to re-ingest PDFs."
    )

if LLM_BACKEND not in VALID_LLM_BACKENDS:
    raise ValueError(
        f"Invalid LLM_BACKEND='{LLM_BACKEND}'. Valid options: {VALID_LLM_BACKENDS}"
    )

if EMBEDDING_BACKEND not in VALID_EMB_BACKENDS:
    raise ValueError(
        f"Invalid EMBEDDING_BACKEND='{EMBEDDING_BACKEND}'. "
        f"Valid options: {VALID_EMB_BACKENDS}"
    )

if VECTOR_BACKEND not in VALID_VECTOR_BACKENDS:
    raise ValueError(
        f"Invalid VECTOR_BACKEND='{VECTOR_BACKEND}'. "
        f"Valid options: {VALID_VECTOR_BACKENDS}"
    )

if LLM_BACKEND == "openai" and not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY is required when LLM_BACKEND=openai. Set it in .env."
    )

if EMBEDDING_BACKEND == "openai" and not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY is required when EMBEDDING_BACKEND=openai. Set it in .env."
    )

if VECTOR_BACKEND == "pinecone" and not PINECONE_API_KEY:
    raise ValueError(
        "PINECONE_API_KEY is required when VECTOR_BACKEND=pinecone. Set it in .env."
    )

if RERANKER_TOP_N > TOP_K:
    raise ValueError(
        f"RERANKER_TOP_N ({RERANKER_TOP_N}) cannot exceed TOP_K ({TOP_K}). "
        "The re-ranker can only select from the initial candidate pool."
    )

# ── Auto-create required directories ──────────────────────────────────────────
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)


def get_active_pinecone_index_name() -> str:
    """Return the Pinecone index name matching the active embedding model dimension."""
    return PINECONE_INDEX_NAME_OPENAI if EMBEDDING_BACKEND == "openai" else PINECONE_INDEX_NAME_LOCAL


def print_config_summary() -> None:
    """
    Print a human-readable summary of all active configuration settings.
    API keys are masked — only the first 4 characters are shown.
    """
    def _mask(key: str) -> str:
        if not key:
            return "(not set)"
        return key[:4] + "****" if len(key) > 4 else "****"

    print("=" * 65)
    print("  Construction Knowledge Assistant — Config Summary")
    print("=" * 65)
    print(f"  Embedding Backend : {EMBEDDING_BACKEND}")
    print(f"  Embedding Model   : {EMBEDDING_MODEL}")
    print(f"  LLM Backend       : {LLM_BACKEND}")
    print(f"  LLM Model         : {LLM_MODEL}")
    print(f"  Vector Backend    : {VECTOR_BACKEND}")
    if VECTOR_BACKEND == "pinecone":
        print(f"  Active Index      : {get_active_pinecone_index_name()}")
    print(f"  Hybrid Search     : {'ENABLED' if HYBRID_SEARCH_ENABLED else 'DISABLED'}"
          f"  (BM25 w={HYBRID_BM25_WEIGHT} + Dense w={HYBRID_DENSE_WEIGHT})")
    print(f"  Re-ranker         : {'ENABLED' if RERANKER_ENABLED else 'DISABLED'}"
          + (f"  ({RERANKER_MODEL})" if RERANKER_ENABLED else ""))
    print(f"  OpenAI API Key    : {_mask(OPENAI_API_KEY)}")
    print(f"  Pinecone API Key  : {_mask(PINECONE_API_KEY)}")
    print(f"  Data Directory    : {DATA_DIR.resolve()}")
    print(f"  Vector Store Dir  : {VECTOR_STORE_DIR.resolve()}")
    print(f"  Chunk Size        : {CHUNK_SIZE}")
    print(f"  Chunk Overlap     : {CHUNK_OVERLAP}")
    print(f"  Top-K (pool)      : {TOP_K}  (candidates from BM25 + dense)")
    print(f"  Reranker Top-N    : {RERANKER_TOP_N}  (final docs sent to LLM)")
    print(f"  LangSmith Tracing : {_langsmith_status}")
    print("=" * 65)


if __name__ == "__main__":
    print_config_summary()
