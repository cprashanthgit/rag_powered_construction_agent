# -*- coding: utf-8 -*-
"""
api.py — FastAPI Inference Layer (Phase 4 — Auth + Logging)

import uuid  # pre-generate query_id before background tasks

Exposes the RAG pipeline as a production-ready HTTP API with:
  - JWT authentication (POST /auth/token)
  - Role-based access control (RBAC) on all query endpoints
  - Query logging to PostgreSQL (non-blocking BackgroundTask)
  - Feedback collection (POST /feedback, GET /feedback/stats)
  - Streaming responses via Server-Sent Events (SSE)
  - Sync JSON responses for simple clients
  - Liveness + readiness health check
  - Auto-generated OpenAPI docs at /docs

Endpoints:
  POST /auth/token     → login with email/password, receive JWT
  GET  /health         → system status (vector store, backends, features)
  POST /query          → streaming SSE (text/event-stream)
  POST /query/sync     → full JSON response + logs to PostgreSQL
  POST /feedback       → submit thumbs up/down on an answer
  GET  /feedback/stats → satisfaction percentage and totals
  GET  /admin/queries  → recent query log (admin role only)
  GET  /docs           → FastAPI OpenAPI UI (built-in)

Run locally:
  uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Test auth:
  curl -X POST http://localhost:8000/auth/token \\
    -H "Content-Type: application/json" \\
    -d '{"email": "admin@cnst.com", "password": "yourpassword"}'

Test query (authenticated):
  curl -X POST http://localhost:8000/query/sync \\
    -H "Content-Type: application/json" \\
    -H "Authorization: Bearer <token>" \\
    -d '{"question": "What PPE is required on site?"}' | python -m json.tool
"""

import asyncio
import uuid
import time
from typing import AsyncIterator, List, Optional

import bcrypt
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

# ── Phase 5: Prometheus custom metrics ────────────────────────────────────────
from monitoring.metrics import (
    CACHE_HITS,
    CONFIDENCE_DIST,
    FEEDBACK_TOTAL,
    GENERATION_LATENCY,
    QUERY_TOTAL,
    REFUSED_QUERIES,
    RETRIEVAL_LATENCY,
    TOTAL_LATENCY,
)

# ── Auth imports ───────────────────────────────────────────────────────────────
from auth.jwt_handler import create_token
from auth.rbac import get_current_user

# ── DB imports ─────────────────────────────────────────────────────────────────
from db.postgres_client import (
    get_feedback_stats,
    get_recent_queries,
    get_user_by_email,
    log_query,
    record_feedback,
    update_last_login,
)

# ── App init ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Construction Safety RAG API",
    description=(
        "Retrieval-Augmented Generation API for construction safety documents. "
        "Supports JWT authentication, role-based access control, hybrid search "
        "(BM25 + dense), cross-encoder re-ranking, streaming token responses, "
        "query logging to PostgreSQL, user feedback collection, and "
        "Prometheus metrics at /metrics."
    ),
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Phase 5: Auto-expose /metrics for Prometheus scraping ────────────────────
# This adds standard HTTP metrics (request count, latency by endpoint, etc.)
# Our custom RAG metrics are recorded manually below in each endpoint.
Instrumentator().instrument(app).expose(app)


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic schemas
# ══════════════════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email:    str = Field(..., example="inspector@cnst.com")
    password: str = Field(..., example="yourpassword")


class LoginResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    role:         str
    email:        str


class QueryRequest(BaseModel):
    question:   str = Field(
        ..., min_length=3, max_length=1000,
        example="What PPE is required on a construction site?",
    )
    top_k:      int            = Field(default=5, ge=1, le=20)
    session_id: Optional[str]  = Field(default=None, description="Session ID for conversation memory")


class SourceRef(BaseModel):
    file: str = Field(..., example="osha_construction_safety_guide.pdf")
    page: int = Field(..., example=5)


class QueryResponse(BaseModel):
    answer:     str             = Field(..., example="Workers must wear hard hats...")
    sources:    List[SourceRef] = Field(default_factory=list)
    chunks:     List[str]       = Field(default_factory=list)
    from_cache: bool            = Field(default=False)
    query_id:   Optional[str]   = Field(default=None, description="UUID for submitting feedback")


class FeedbackRequest(BaseModel):
    query_id: str     = Field(..., description="UUID from the query response")
    rating:   int     = Field(..., ge=-1, le=1, description="+1 helpful, -1 not helpful")
    comment:  str     = Field(default="", description="Optional text comment")


class HealthResponse(BaseModel):
    status:                str
    vector_store_loaded:   bool
    llm_backend:           str
    embedding_backend:     str
    vector_backend:        str
    hybrid_search_enabled: bool
    reranker_enabled:      bool
    active_index:          str
    redis_connected:       bool
    postgres_connected:    bool


# ══════════════════════════════════════════════════════════════════════════════
# Startup — load pipeline singletons
# ══════════════════════════════════════════════════════════════════════════════

from pipeline import ask_question, _vector_store, _retriever


@app.on_event("startup")
async def startup_event():
    from config import (
        EMBEDDING_BACKEND, HYBRID_SEARCH_ENABLED, LLM_BACKEND,
        RERANKER_ENABLED, VECTOR_BACKEND, get_active_pinecone_index_name,
    )
    index = (
        get_active_pinecone_index_name() if VECTOR_BACKEND == "pinecone"
        else str(__import__("config").VECTOR_STORE_DIR)
    )
    status = "ok" if _vector_store is not None else "degraded (no vector store)"
    print(
        f"\n[API v5] Startup complete — status: {status}\n"
        f"  LLM: {LLM_BACKEND}  |  Embeddings: {EMBEDDING_BACKEND}  |  VectorDB: {VECTOR_BACKEND}\n"
        f"  Auth: JWT (HS256, 24hr)  |  Logging: PostgreSQL\n"
        f"  Metrics: http://localhost:8000/metrics\n"
        f"  Docs:    http://localhost:8000/docs\n"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Auth Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.post(
    "/auth/token",
    response_model=LoginResponse,
    summary="Login — get a JWT token",
    tags=["Auth"],
)
async def login(request: LoginRequest):
    """
    Authenticate with email + password. Returns a JWT token valid for 24 hours.

    Include the token in subsequent requests:
        Authorization: Bearer <token>

    To create a test user, connect to PostgreSQL and run:
        INSERT INTO users (email, password_hash, role)
        VALUES ('test@cnst.com', '<bcrypt_hash>', 'inspector');

    Generate a bcrypt hash in Python:
        import bcrypt
        print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())
    """
    # Fetch user from PostgreSQL
    user = await get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password against bcrypt hash
    password_matches = bcrypt.checkpw(
        request.password.encode("utf-8"),
        user["password_hash"].encode("utf-8"),
    )
    if not password_matches:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last_login timestamp (fire-and-forget)
    await update_last_login(str(user["id"]))

    # Create and return JWT token
    token = create_token(
        user_id=str(user["id"]),
        email=request.email,
        role=user["role"],
    )
    return LoginResponse(
        access_token=token,
        role=user["role"],
        email=request.email,
    )


# ══════════════════════════════════════════════════════════════════════════════
# System Health
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness & readiness check",
    tags=["System"],
)
async def health():
    """Returns system status including which backends are active."""
    from config import (
        EMBEDDING_BACKEND, HYBRID_SEARCH_ENABLED, LLM_BACKEND,
        RERANKER_ENABLED, VECTOR_BACKEND, get_active_pinecone_index_name,
    )
    from memory.redis_client import redis_available

    active_index = (
        get_active_pinecone_index_name() if VECTOR_BACKEND == "pinecone"
        else "faiss (local)"
    )

    # Quick PostgreSQL check
    postgres_ok = False
    try:
        from db.postgres_client import get_pool
        pool = await get_pool()
        await pool.fetchval("SELECT 1")
        postgres_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok" if _vector_store is not None else "degraded",
        vector_store_loaded=(_vector_store is not None),
        llm_backend=LLM_BACKEND,
        embedding_backend=EMBEDDING_BACKEND,
        vector_backend=VECTOR_BACKEND,
        hybrid_search_enabled=HYBRID_SEARCH_ENABLED,
        reranker_enabled=RERANKER_ENABLED,
        active_index=active_index,
        redis_connected=redis_available(),
        postgres_connected=postgres_ok,
    )


# ══════════════════════════════════════════════════════════════════════════════
# RAG Query Endpoints
# ══════════════════════════════════════════════════════════════════════════════

async def _sse_stream(question: str) -> AsyncIterator[str]:
    """Internal SSE stream — unchanged from v2."""
    from config import RERANKER_TOP_N
    from generator import generate_answer_stream
    from hybrid_retriever import retrieve
    from reranker import rerank

    if _retriever is None or _vector_store is None:
        yield "data: [ERROR] Vector store not loaded. Run build_index.py first.\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        candidate_docs = retrieve(question, _retriever)
        final_docs     = rerank(question, candidate_docs, top_n=RERANKER_TOP_N)
        async for token in generate_answer_stream(question, final_docs):
            yield f"data: {token.replace(chr(10), ' ')}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as exc:
        yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"


@app.post(
    "/query",
    summary="Streaming RAG query (SSE)",
    tags=["RAG"],
)
async def query_stream(request: QueryRequest, user: dict = Depends(get_current_user)):
    """Stream the RAG answer token-by-token via Server-Sent Events."""
    if _vector_store is None:
        raise HTTPException(503, "Vector store not loaded. Run build_index.py first.")
    return StreamingResponse(
        _sse_stream(request.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/query/sync",
    response_model=QueryResponse,
    summary="Synchronous RAG query (JSON) — logs to PostgreSQL",
    tags=["RAG"],
)
async def query_sync(
    request:          QueryRequest,
    background_tasks: BackgroundTasks,
    user:             dict = Depends(get_current_user),
):
    """
    Return the full RAG answer as JSON and log the query to PostgreSQL.

    The JWT token is optional — anonymous users (no token) get public access.
    Include Authorization: Bearer <token> to identify yourself and your role.

    The response includes a query_id UUID — use it to submit feedback.
    """
    if _vector_store is None:
        raise HTTPException(503, "Vector store not loaded. Run build_index.py first.")

    from config import LLM_BACKEND, LLM_MODEL

    # ── Run the full RAG pipeline ──────────────────────────────────────────────
    t_total_start = time.time()

    t_retrieval_start = time.time()
    result = ask_question(
        query=request.question,
        session_id=request.session_id or user.get("sub", "api"),
    )
    retrieval_ms = int((time.time() - t_retrieval_start) * 1000)
    total_ms     = int((time.time() - t_total_start) * 1000)

    if result["answer"].startswith("Error:"):
        REFUSED_QUERIES.labels(reason="error").inc()
        raise HTTPException(status_code=500, detail=result["answer"])

    # ── Phase 5: Record Prometheus metrics ────────────────────────────────────
    from_cache   = result.get("from_cache", False)
    user_role    = user.get("role", "public")

    QUERY_TOTAL.labels(
        llm_backend=LLM_BACKEND,
        cache_hit=str(from_cache),
        user_role=user_role,
    ).inc()

    TOTAL_LATENCY.observe(total_ms / 1000)          # convert ms → seconds
    RETRIEVAL_LATENCY.observe(retrieval_ms / 1000)

    if from_cache:
        CACHE_HITS.inc()

    # Confidence proxy: use the retrieval speed as a rough indicator until
    # the reranker exposes its score directly (Phase 5.1 improvement).
    # For now we record 0.0 so the histogram populates without errors.
    CONFIDENCE_DIST.observe(0.0)

    # ── Pre-generate query_id so we can return it immediately ─────────────────
    query_id = str(uuid.uuid4())

    # ── Log to PostgreSQL in background (user gets answer immediately) ─────────
    try:
        background_tasks.add_task(
            log_query,
            query_id      = query_id,
            session_id    = request.session_id or user.get("sub", "api"),
            user_id       = user.get("sub"),
            user_role     = user_role,
            query         = request.question,
            answer        = result["answer"],
            sources       = result["sources"],
            confidence    = 0.0,
            retrieval_ms  = retrieval_ms,
            generation_ms = 0,
            total_ms      = total_ms,
            cache_hit     = from_cache,
            llm_backend   = LLM_BACKEND,
            llm_model     = LLM_MODEL,
        )
    except Exception:
        pass  # never let logging failures break the response

    return QueryResponse(
        answer     = result["answer"],
        sources    = [SourceRef(**s) for s in result["sources"]],
        chunks     = result["chunks"],
        from_cache = from_cache,
        query_id   = query_id,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Feedback Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.post(
    "/feedback",
    summary="Submit thumbs up/down on an answer",
    tags=["Feedback"],
)
async def submit_feedback(
    req:  FeedbackRequest,
    user: dict = Depends(get_current_user),
):
    """
    Rate an answer as helpful (+1) or not helpful (-1).
    Use the query_id returned by /query/sync.
    """
    await record_feedback(req.query_id, req.rating, req.comment)

    # ── Phase 5: Record feedback metric ───────────────────────────────────────
    label = "positive" if req.rating == 1 else "negative"
    FEEDBACK_TOTAL.labels(rating=label).inc()

    return {"status": "recorded", "query_id": req.query_id}


@app.get(
    "/feedback/stats",
    summary="Get aggregate feedback satisfaction stats",
    tags=["Feedback"],
)
async def feedback_stats():
    """Returns total ratings, positive count, and satisfaction percentage."""
    return await get_feedback_stats()


# ══════════════════════════════════════════════════════════════════════════════
# Admin Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/admin/queries",
    summary="Recent query log (admin only)",
    tags=["Admin"],
)
async def recent_queries(
    limit: int  = 20,
    user:  dict = Depends(get_current_user),
):
    """
    Returns the most recent queries from the query_log table.
    Restricted to admin role.
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    rows = await get_recent_queries(limit=limit)
    # Convert datetime objects to strings for JSON serialisation
    for row in rows:
        if "created_at" in row and row["created_at"]:
            row["created_at"] = str(row["created_at"])
    return {"queries": rows, "count": len(rows)}


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
