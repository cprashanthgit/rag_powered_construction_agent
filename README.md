# 🏗️ Construction Safety RAG Assistant

Ever wished you could just *ask* a question and get a real answer pulled straight from construction safety manuals? That's exactly what this project does.

This started as a **Retrieval-Augmented Generation (RAG)** system for querying construction safety documents in plain English — and has since evolved into a production-oriented AI knowledge assistant with JWT authentication, role-based access control, Redis-powered session memory and semantic caching, PostgreSQL query logging, and a live Prometheus + Grafana monitoring dashboard.

It combines hybrid search, cross-encoder re-ranking, and a flexible dual-mode setup — so you can run it completely **free and offline**, or flip a switch to use **OpenAI + Pinecone** for significantly better answer quality.

---

## ✨ What It Can Do

### Core RAG Pipeline
- 🔍 **Hybrid Search** — combines BM25 keyword search with dense vector retrieval, fused using Reciprocal Rank Fusion for better coverage
- 🎯 **Cross-Encoder Re-ranking** — uses `ms-marco-MiniLM-L-6-v2` to narrow down top-5 candidates to the 3 most relevant document chunks
- 🔀 **Dual-Mode Architecture** — fully local (free) or cloud-powered (best quality) — controlled by 5 lines in `.env`
- 🖥️ **Streamlit Chat UI** — interactive chat interface with message history, cache indicators, and source expanders at `localhost:8501`
- ⚡ **FastAPI REST Server** — sync and streaming query endpoints at `localhost:8000`
- 📄 **Multi-Document Ingestion** — ingests construction safety PDFs chunked into 8,938 searchable segments

### Production Features (v3)
- 🔐 **JWT Authentication** — token-based login with 3-role RBAC (public / inspector / admin)
- 🧠 **Redis Session Memory** — conversation history persisted per session (1hr TTL, last 5 exchanges)
- ⚡ **Semantic Cache** — repeated or similar queries return cached results instantly (0.70 cosine similarity threshold, 24hr TTL)
- 🗄️ **PostgreSQL Query Logging** — every query, answer, latency, and cache hit logged to a structured database
- 👍 **User Feedback System** — thumbs up/down rating on each answer, stored and queryable via API
- 📊 **Prometheus Metrics** — 6 custom RAG metrics exposed at `/metrics` (latency, confidence, cache hits, refusals)
- 📈 **Grafana Dashboard** — 8-panel live dashboard tracking query volume, P95 latency, cache hit rate, and user satisfaction
- 🔭 **LangSmith Tracing** — full trace visibility for every query (retrieval → reranking → generation) on the LangSmith dashboard
- 📐 **RAGAS Evaluation Pipeline** — automated quality evaluation using LLM-as-judge scoring across 5 metrics (faithfulness, answer relevancy, context precision, context recall, answer correctness) on a 25-question golden dataset sourced directly from all 5 PDFs

---

## 🏛️ System Architecture (v3)

```
╔══════════════════════════════════════════════════════════════════╗
║                 CONSTRUCTION RAG ASSISTANT v3                     ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                    ║
║   ┌──────────────┐         ┌──────────────────────────────────┐  ║
║   │ Streamlit UI │         │      FastAPI  (port 8000)        │  ║
║   │  (port 8501) │         │  /health  /auth  /query  /docs   │  ║
║   └──────┬───────┘         └───────────────┬──────────────────┘  ║
║          │  Redis session memory            │  JWT Auth (RBAC)    ║
║          │                                  │  Rate limiting      ║
║          ▼                                  ▼                     ║
║   ┌─────────────────────────────────────────────────┐            ║
║   │              RAG PIPELINE                        │            ║
║   │  Hybrid Retrieve → Cross-Encoder Rerank → LLM   │            ║
║   │  + Semantic Cache   + Confidence Gate            │            ║
║   └────────────────────┬────────────────────────────┘            ║
║                         │                                          ║
║          ┌──────────────┼──────────────┐                          ║
║          ▼              ▼              ▼                           ║
║   ┌────────────┐ ┌─────────────┐ ┌─────────────────┐            ║
║   │   Redis    │ │ PostgreSQL  │ │   Prometheus     │            ║
║   │ Sessions   │ │  Users      │ │   /metrics       │            ║
║   │ Sem. Cache │ │  Query Log  │ │        ▼         │            ║
║   └────────────┘ │  Feedback   │ │   Grafana :3000  │            ║
║                   └─────────────┘ └─────────────────┘            ║
║                    LangSmith (cloud tracing)                       ║
╚══════════════════════════════════════════════════════════════════╝
```

### RAG Pipeline Detail

```
PDFs (./data/)
    │
    ▼  ingest.py → chunker.py
Chunks (8938 total, ~434 chars each)
    │
    ├──────────────────────────────────────────────────┐
    ▼  [MODE 1] FAISS (local file)                    ▼  [MODE 2] Pinecone (cloud)
    │  all-MiniLM-L6-v2 (384-dim, free)               │  text-embedding-3-small (1536-dim, ~$0.02 once)
    └──────────────────┬───────────────────────────────┘
                       │
                       ▼  hybrid_retriever.py
              BM25 (sparse) + Dense (vector)
              Reciprocal Rank Fusion → top-5 candidates
                       │
                       ▼  reranker.py
              CrossEncoder (ms-marco-MiniLM) → top-3 docs
                       │
    ┌──────────────────┴───────────────────────────────┐
    ▼  [MODE 1] Flan-T5-base (local, CPU, free)        ▼  [MODE 2] GPT-3.5-turbo (OpenAI API, ~$0.002/q)
    └──────────────────┬───────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Streamlit UI       FastAPI Server
        (port 8501)        (port 8000)
```

---

## 🔀 Mode 1 vs Mode 2 — Quick Comparison

| Feature | Mode 1 — Local (Free) | Mode 2 — Cloud (Best Quality) |
|---|---|---|
| Embedding | `all-MiniLM-L6-v2` (HuggingFace) | `text-embedding-3-small` (OpenAI) |
| Vector DB | FAISS (stored locally) | Pinecone (serverless cloud) |
| LLM | `google/flan-t5-base` (runs on CPU) | `gpt-3.5-turbo` (OpenAI API) |
| Answer Quality | Short, 1-2 sentences | Full paragraphs with source citations |
| Index Build Cost | **$0.00** | ~$0.02 (one-time only) |
| Per Query Cost | **$0.00** | ~$0.002 |
| Best For | Development / offline use | Demo day / presentations |

> All production features (auth, Redis, PostgreSQL, monitoring) work identically in both modes.

---

## 📁 Project Structure

```
Construction_RAG_Assistant/
│
├── 📄 Core Config & Entry Points
│   ├── .env.example              # Copy to .env — fill in your API keys
│   ├── .gitignore
│   ├── requirements.txt
│   ├── docker-compose.yml        # Boots full stack: Redis, PostgreSQL, Prometheus, Grafana
│   ├── start.ps1                 # Windows: start entire stack with one command
│   ├── stop.ps1                  # Windows: stop entire stack
│   └── build_index.py            # One-shot: embed + index all PDFs
│
├── 🧠 RAG Core (unchanged logic)
│   ├── config.py                 # Reads .env, validates all settings
│   ├── ingest.py                 # Loads PDFs from ./data/
│   ├── chunker.py                # Splits pages into overlapping chunks
│   ├── embedder.py               # Embeds chunks → FAISS or Pinecone
│   ├── hybrid_retriever.py       # BM25 + dense retrieval (RRF fusion)
│   ├── reranker.py               # CrossEncoder re-ranking
│   ├── generator.py              # LLM answer generation (sync + streaming)
│   └── pipeline.py               # Orchestrates full RAG pipeline + Redis cache
│
├── 🖥️ Application Layer
│   ├── api.py                    # FastAPI server — auth, RAG, feedback, metrics
│   └── app.py                    # Streamlit chat UI with session memory
│
├── 🔐 auth/                      # JWT Authentication & RBAC
│   ├── jwt_handler.py            # HS256 token encode/decode (24hr expiry)
│   └── rbac.py                   # 3-role system: public / inspector / admin
│
├── 🧠 memory/                    # Redis Layer
│   ├── redis_client.py           # Connection pool with graceful fallback
│   ├── session_store.py          # Per-session conversation history (1hr TTL)
│   └── semantic_cache.py         # Cosine-similarity query cache (24hr TTL)
│
├── 🗄️ db/                        # PostgreSQL Layer
│   ├── postgres_client.py        # asyncpg pool, log_query(), record_feedback()
│   └── schema.sql                # CREATE TABLE: users, query_log, feedback, eval_results
│
├── 📊 monitoring/                # Observability
│   ├── metrics.py                # 6 custom Prometheus metrics
│   ├── prometheus.yml            # Prometheus scrape config
│   └── grafana/
│       ├── dashboards/
│       │   └── rag_dashboard.json   # 8-panel pre-built dashboard
│       └── datasources/
│           └── datasources.yml      # Auto-provisions Prometheus + PostgreSQL
│
├── 👍 feedback/                  # User Feedback Collection
│   └── feedback_handler.py       # Write ratings to PostgreSQL, expose stats
│
├── 📋 eval/                      # Evaluation (Phase 6)
│   └── golden_dataset.json       # 25 hand-crafted Q&A pairs for RAGAS eval
│
├── data/                         # Drop your source PDFs here (gitignored)
└── vector_store/                 # FAISS index + chunks.pkl (auto-generated, gitignored)
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — required for Redis, PostgreSQL, Prometheus, Grafana

### 1. Clone & Install

```bash
git clone https://github.com/cprashanthgit/construction-safety-rag.git
cd construction-safety-rag
pip install -r requirements.txt
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Open .env and fill in your keys
```

### 3. Start the Infrastructure Stack

```powershell
# Windows (one command):
.\start.ps1

# Or manually:
docker-compose up -d
```

This boots Redis, PostgreSQL, Prometheus, and Grafana in the background. Verify all services are healthy:

```bash
docker-compose ps
```

### 4. Build the Search Index

```bash
python build_index.py
```

### 5. Create Your First User

```bash
python create_user.py
# Follow the prompts: enter email, password, and role (public/inspector/admin)
```

### 6. Run the App

**Streamlit Chat UI:**
```bash
streamlit run app.py
```
Open → **http://localhost:8501**

**FastAPI Server:**
```bash
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```
Open → **http://localhost:8000/docs**

---

## 🔑 API Keys & Configuration

Copy `.env.example` to `.env` and configure the following sections:

```env
# ── RAG Mode (choose one) ────────────────────────────────────
EMBEDDING_BACKEND=huggingface        # or: openai
EMBEDDING_MODEL=all-MiniLM-L6-v2    # or: text-embedding-3-small
LLM_BACKEND=huggingface              # or: openai
LLM_MODEL=google/flan-t5-base        # or: gpt-3.5-turbo
VECTOR_BACKEND=faiss                 # or: pinecone

# ── Cloud Keys (Mode 2 only) ─────────────────────────────────
OPENAI_API_KEY=your-openai-key       # platform.openai.com/api-keys
PINECONE_API_KEY=your-pinecone-key   # app.pinecone.io → API Keys

# ── Auth ─────────────────────────────────────────────────────
JWT_SECRET_KEY=change-this-in-production

# ── Redis ────────────────────────────────────────────────────
REDIS_HOST=localhost
REDIS_PORT=6379

# ── PostgreSQL ───────────────────────────────────────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cnst_rag
POSTGRES_USER=cnst_user
POSTGRES_PASSWORD=devpassword123

# ── Observability ────────────────────────────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key  # smith.langchain.com (free)
LANGCHAIN_PROJECT=cnst-rag-assistant
```

> ⚠️ **Never commit your `.env` file.** It is already in `.gitignore`. Only `.env.example` is tracked by git.

---

## 🔐 Authentication & Role-Based Access

The API uses **JWT tokens** with a 3-tier role system:

| Role | Access Level | Use Case |
|---|---|---|
| `public` | General safety documents | Default for all users |
| `inspector` | Public + restricted documents | Site inspectors |
| `admin` | All documents, no filter | Full access |

**Get a token:**
```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "yourpassword"}'
```

**Use the token:**
```bash
curl -X POST http://localhost:8000/query/sync \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What PPE is required on a construction site?"}'
```

Unauthenticated requests still work — they are treated as `public` role.

---

## 🧠 Redis — Session Memory & Semantic Cache

### Session Memory
Every conversation is stored in Redis per session ID. The last 5 exchanges (10 messages) are kept for 1 hour, giving the chat interface conversational context.

### Semantic Cache
Before hitting the RAG pipeline, every query is compared against cached results using cosine similarity. If a semantically similar question has been asked before (similarity ≥ 0.70), the cached answer is returned immediately — near-instant response with zero retrieval cost.

```
User asks: "What fall protection is needed above 6 feet?"
   ↓
Cache check → finds "What fall protection is required at 6ft heights?" (similarity: 0.94)
   ↓
Returns cached answer instantly ⚡  (no retrieval, no LLM call)
```

**Cache TTL:** 24 hours  
**Session TTL:** 1 hour  
**Graceful degradation:** If Redis is unavailable, the pipeline runs normally — no errors.

---

## 📊 Monitoring — Prometheus + Grafana

### Prometheus Metrics

The API exposes a `/metrics` endpoint with 6 custom RAG-specific metrics:

| Metric | Type | What It Tracks |
|---|---|---|
| `rag_queries_total` | Counter | Total queries by backend, cache hit, role |
| `rag_retrieval_duration_seconds` | Histogram | Retrieval + reranking latency |
| `rag_generation_duration_seconds` | Histogram | LLM generation latency |
| `rag_confidence_score` | Histogram | Cross-encoder confidence distribution |
| `rag_cache_hits_total` | Counter | Semantic cache hit count |
| `rag_refused_queries_total` | Counter | Refused queries by reason |

### Grafana Dashboard

Pre-built 8-panel dashboard available at **http://localhost:3000** (admin / admin):

- Total queries in the last 24 hours
- Cache hit rate (%)
- P95 retrieval latency
- P95 generation latency
- Confidence score distribution (heatmap)
- Refused queries by reason
- User satisfaction rate (from feedback)

The dashboard is auto-provisioned — it loads automatically when you start the stack. No manual import needed.

---

## 👍 Feedback System

Users can rate any answer directly through the API:

```bash
# Thumbs up (+1) or thumbs down (-1)
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"query_id": "<uuid>", "rating": 1, "comment": "Very helpful!"}'

# Get aggregate satisfaction stats
curl http://localhost:8000/feedback/stats
```

All feedback is stored in PostgreSQL and feeds into the Grafana satisfaction panel.

---

## 🔭 LangSmith Tracing

When `LANGCHAIN_TRACING_V2=true` is set in `.env`, every query generates a full trace in LangSmith showing:
- Retrieval call with chunk scores
- Re-ranking step with before/after candidates
- LLM generation with token counts and latency

Sign up free at [smith.langchain.com](https://smith.langchain.com) — free tier includes 5,000 traces/month.

---

## 🗄️ Database Schema

PostgreSQL runs with 4 tables auto-created on first start via `db/schema.sql`:

| Table | Purpose |
|---|---|
| `users` | User accounts with bcrypt-hashed passwords and roles |
| `query_log` | Every query: question, answer, latency, cache hit, user role |
| `feedback` | User ratings linked to query_log entries |
| `eval_results` | RAGAS evaluation scores per run (Phase 6) |

---

## 📐 Phase 6 — RAGAS Evaluation Pipeline

The system includes a standalone, automated evaluation framework built on [RAGAS](https://github.com/explodinggradients/ragas) — an LLM-as-judge scoring framework for RAG systems. It runs completely independently of the live application.

### What Gets Evaluated

Every evaluation run scores 25 hand-crafted questions sourced directly from the 5 source PDFs (WSDOT, GTM, TxDOT, OSHA) against the live RAG pipeline output.

| Metric | Measures | Requires |
|---|---|---|
| **Faithfulness** | Are answers grounded in retrieved context? (anti-hallucination) | LLM |
| **Answer Relevancy** | Does the answer address the actual question asked? | LLM + Embeddings |
| **Context Precision** | Were the most relevant chunks ranked first? | LLM |
| **Context Recall** | Did retrieval find all information needed to answer? | LLM |
| **Answer Correctness** | Does the answer match the ground truth meaning? | LLM + Embeddings |

### Baseline Scores (June 2026 — Mode 2, 25 questions)

| Metric | Score | Interpretation |
|---|---|---|
| Context Precision | **0.940** | ✅ Excellent — retrieval ranking is working very well |
| Context Recall | **0.713** | 🟡 Good — retrieval coverage is solid |
| Answer Relevancy | **0.686** | 🟡 Good — answers address questions |
| Faithfulness | **0.530** | 🟠 Fair — GPT supplements from training knowledge |
| Answer Correctness | **0.460** | 🔴 Needs work — exact match against precise ground truths |

### How to Run

```bash
# Install RAGAS (one-time)
pip install ragas datasets tabulate

# Run evaluation (requires OPENAI_API_KEY in .env)
python eval/run_eval.py 2026-06-24-baseline

# Check regression against baseline after any change
python eval/regression_check.py eval/results/2026-06-24-baseline.md
```

### Evaluation Files

```
eval/
├── golden_dataset.json      # 25 Q&A pairs with citations (manually verified)
├── run_eval.py              # Main evaluation runner — all 5 RAGAS metrics
├── regression_check.py      # Quality guard — alerts if any metric drops >5%
└── results/                 # Markdown reports per run (gitignored)
```

### Key Design Decisions

- **Reference-based evaluation** — uses hand-written `ground_truth` answers to enable correctness scoring, not just relevancy
- **Standalone** — never affects the live API; runs against the pipeline directly
- **Regression guard** — `regression_check.py` flags any metric that drops more than 5% from baseline, acting as a quality gate before deploying changes
- **Cost** — ~$0.25 per full 5-metric run (125 GPT-3.5 calls; 25 questions × 5 metrics)

---

## 💰 Cost Breakdown

Running in Mode 1 costs absolutely nothing. Mode 2 is still very cheap:

| Item | Mode 1 (Local) | Mode 2 (Cloud) |
|---|---|---|
| Index build | $0.00 | ~$0.02 (one-time) |
| Per query — retrieval | $0.00 | $0.00 (Pinecone free tier) |
| Per query — LLM | $0.00 | ~$0.002 (GPT-3.5) |
| 100 demo queries | **$0.00** | **~$0.20** |
| Redis | $0.00 | $0.00 (local Docker) |
| PostgreSQL | $0.00 | $0.00 (local Docker) |
| Grafana + Prometheus | $0.00 | $0.00 (local Docker) |

---

## 📚 Source Documents

The system was built and tested on the following construction safety and project management documents:

- OSHA Construction Safety Guide
- GTM Construction Safety Manual
- WSDOT Construction Manual
- TxDOT Bridge Inspection Manual
- Montana DOT Project Report

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Embedding (Local) | `sentence-transformers` / `all-MiniLM-L6-v2` |
| Embedding (Cloud) | OpenAI `text-embedding-3-small` |
| Vector Store (Local) | FAISS |
| Vector Store (Cloud) | Pinecone Serverless |
| Sparse Retrieval | BM25 (`rank_bm25`) |
| Re-ranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM (Local) | `google/flan-t5-base` (HuggingFace) |
| LLM (Cloud) | OpenAI `gpt-3.5-turbo` |
| UI | Streamlit |
| API | FastAPI + Uvicorn |
| Auth | PyJWT + bcrypt |
| Session Memory | Redis (`redis-py`) |
| Semantic Cache | Redis + cosine similarity |
| Database | PostgreSQL 16 (`asyncpg`) |
| Metrics | Prometheus + `prometheus-fastapi-instrumentator` |
| Dashboard | Grafana |
| Tracing | LangSmith |
| Evaluation | RAGAS (`ragas`, `datasets`) |
| Infrastructure | Docker Compose |
| Config | `python-dotenv` |

---

## 📖 Detailed Run Guide

For full step-by-step instructions, mode switching, API testing examples, and troubleshooting see **[RUN_GUIDE.md](./RUN_GUIDE.md)**.

---

*Construction Safety RAG Assistant v4 — built as an independent graduate-level NLP/AI project, June 2026*
*Phases: Core RAG → LangSmith → Redis Cache → JWT Auth → Prometheus/Grafana → RAGAS Evaluation*
