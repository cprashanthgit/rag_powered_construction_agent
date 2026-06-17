# -*- coding: utf-8 -*-
"""
monitoring/metrics.py — Prometheus Metrics Registry (Phase 5)

Defines all custom RAG metrics.  Import and use these anywhere in api.py.

Metric naming convention:  rag_<what>_<unit>
  Counters   → rag_*_total
  Histograms → rag_*_seconds  (latency)  or rag_*_score  (distribution)
  Gauges     → rag_*          (instantaneous value)

All objects are module-level singletons — created once at import time.
prometheus_fastapi_instrumentator adds the generic HTTP metrics automatically
(/metrics endpoint).  These are *additional*, RAG-specific metrics.
"""

from prometheus_client import Counter, Gauge, Histogram

# ── Query throughput ───────────────────────────────────────────────────────────
QUERY_TOTAL = Counter(
    "rag_queries_total",
    "Total number of RAG queries processed",
    ["llm_backend", "cache_hit", "user_role"],   # label dimensions
)

# ── Latency histograms ─────────────────────────────────────────────────────────
RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_duration_seconds",
    "Time spent on vector retrieval + cross-encoder reranking",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

GENERATION_LATENCY = Histogram(
    "rag_generation_duration_seconds",
    "Time spent waiting for the LLM to generate the final answer",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

TOTAL_LATENCY = Histogram(
    "rag_total_duration_seconds",
    "End-to-end wall-clock time for a /query/sync request",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

# ── Cache performance ──────────────────────────────────────────────────────────
CACHE_HITS = Counter(
    "rag_cache_hits_total",
    "Number of queries served from the Redis semantic cache",
)

# ── Answer quality (confidence proxy) ─────────────────────────────────────────
CONFIDENCE_DIST = Histogram(
    "rag_confidence_score",
    "Distribution of cross-encoder confidence scores (0–1)",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── Refusals / low-quality responses ──────────────────────────────────────────
REFUSED_QUERIES = Counter(
    "rag_refused_queries_total",
    "Queries refused or answered with low confidence",
    ["reason"],   # e.g. low_confidence, empty_retrieval, error
)

# ── Active sessions ────────────────────────────────────────────────────────────
ACTIVE_SESSIONS = Gauge(
    "rag_active_sessions",
    "Approximate number of Redis sessions currently active",
)

# ── Feedback ───────────────────────────────────────────────────────────────────
FEEDBACK_TOTAL = Counter(
    "rag_feedback_total",
    "Total feedback submissions",
    ["rating"],   # "positive" or "negative"
)
