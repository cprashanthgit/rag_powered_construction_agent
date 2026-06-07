# -*- coding: utf-8 -*-
"""
memory/semantic_cache.py — Similarity-based answer cache in Redis

Instead of exact-match caching, this cache works semantically:
  "What PPE is needed on site?"
  "What protective equipment is required on a construction site?"
  → These are different strings but mean the same thing → CACHE HIT

How it works:
  1. When an answer is generated, embed the question → store (embedding, result) in Redis
  2. On a new query, embed it → compare cosine similarity against all cached embeddings
  3. If similarity >= 0.92 → return cached result (skips the entire RAG pipeline)

Performance:
  - Cache miss: full pipeline ~3-8 seconds
  - Cache hit:  ~50-100 milliseconds (embedding + Redis lookup)

Storage keys in Redis:
  semcache:emb:{md5_hash}  → question embedding as hex string
  semcache:res:{md5_hash}  → JSON-serialized result dict
"""

import json
import hashlib
from typing import Optional

import numpy as np

from memory.redis_client import get_redis

# ── Constants ──────────────────────────────────────────────────────────────────
CACHE_TTL         = 86400   # seconds — 24 hours
SIMILARITY_THRESH = 0.70    # cosine similarity threshold (0.0 to 1.0)
                             # all-MiniLM-L6-v2 score distribution for construction queries:
                             #   Same/near-identical query : 0.90 - 1.00  → HITS
                             #   Same keywords, reworded   : 0.70 - 0.90  → HITS
                             #   Diff vocab, same meaning  : 0.40 - 0.70  → MISSES (expected)
                             #   Completely unrelated      : 0.00 - 0.10  → always MISS
EMB_KEY_PREFIX    = "semcache:emb:"
RES_KEY_PREFIX    = "semcache:res:"

# ── Lazy-loaded embedder (only loads when first query hits cache) ───────────────
_embedder = None


def _get_embedder():
    """
    Load the sentence-transformers model once, reuse forever.

    Uses all-MiniLM-L6-v2 — the same model used for document embeddings —
    so question embeddings are in the same vector space as chunk embeddings.
    Model is cached locally after first download (~90MB).

    Tries langchain_huggingface first (modern), falls back to langchain_community.
    """
    global _embedder
    if _embedder is None:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
        _embedder = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},  # required for cosine similarity
        )
    return _embedder


def _embed(text: str) -> np.ndarray:
    """Convert a text string into a normalized float32 embedding vector."""
    emb = _get_embedder().embed_query(text)
    return np.array(emb, dtype=np.float32)


def _query_key(query: str) -> str:
    """Generate a stable MD5 hash for the query (used as the Redis key suffix)."""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()


def cache_get(query: str) -> Optional[dict]:
    """
    Look up a query in the semantic cache.

    Scans all cached embeddings and computes cosine similarity against
    the new query embedding. Returns the cached result if similarity >= 0.92,
    otherwise returns None (cache miss → run the pipeline).

    The result dict has an extra key added: {"from_cache": True}
    so the pipeline and UI know this was a cache hit.

    Time complexity: O(n) where n = number of cached queries.
    Fine at cache size < 500; revisit with Redis vector search at scale.
    """
    r = get_redis()
    query_emb = _embed(query)

    for emb_key in r.scan_iter(f"{EMB_KEY_PREFIX}*"):
        raw_emb = r.get(emb_key)
        if not raw_emb:
            continue

        # Decode the stored embedding from hex back to numpy array
        cached_emb = np.frombuffer(bytes.fromhex(raw_emb), dtype=np.float32)

        # Cosine similarity (vectors are already normalized, so dot product = cosine)
        similarity = float(np.dot(query_emb, cached_emb))

        if similarity >= SIMILARITY_THRESH:
            res_key = RES_KEY_PREFIX + emb_key.split(":")[-1]
            raw_res = r.get(res_key)
            if raw_res:
                print(f"[CACHE HIT] similarity={similarity:.4f}  query='{query[:60]}'")
                result = json.loads(raw_res)
                result["from_cache"] = True
                return result

    return None  # cache miss


def cache_set(query: str, result: dict) -> None:
    """
    Store a query's embedding and result in Redis.

    Both keys share the same hash suffix so they can be found together.
    Embedding stored as hex string (Redis strings don't support binary directly).
    Result stored as JSON.
    """
    r = get_redis()
    key = _query_key(query)
    emb = _embed(query)

    # Store embedding as hex-encoded bytes
    r.setex(f"{EMB_KEY_PREFIX}{key}", CACHE_TTL, emb.tobytes().hex())

    # Store result as JSON (exclude from_cache flag before storing)
    result_to_store = {k: v for k, v in result.items() if k != "from_cache"}
    r.setex(f"{RES_KEY_PREFIX}{key}", CACHE_TTL, json.dumps(result_to_store))
