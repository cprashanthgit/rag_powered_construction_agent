-- ══════════════════════════════════════════════════════════════
-- Construction RAG Assistant — Database Schema
-- This file is auto-executed by PostgreSQL on first container boot.
-- DO NOT edit table names — Python code references them directly.
-- ══════════════════════════════════════════════════════════════

-- pgcrypto gives us gen_random_uuid() for UUID primary keys
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Table 1: User Accounts ─────────────────────────────────────────
-- Stores registered users with hashed passwords and RBAC roles.
-- Roles: public (read-only), inspector (restricted docs), admin (all)
CREATE TABLE IF NOT EXISTS users (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'public'
                  CHECK (role IN ('public', 'inspector', 'admin')),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login    TIMESTAMPTZ,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ── Table 2: Query Log ─────────────────────────────────────────────
-- Every RAG query that hits the system is logged here.
-- Includes latency breakdown, cache hit flag, and which LLM answered.
CREATE TABLE IF NOT EXISTS query_log (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      VARCHAR(255),
    user_id         UUID         REFERENCES users(id),
    user_role       VARCHAR(20)  DEFAULT 'public',
    query           TEXT         NOT NULL,
    answer          TEXT         NOT NULL,
    sources         JSONB,
    confidence      FLOAT,
    retrieval_ms    INTEGER,
    generation_ms   INTEGER,
    total_ms        INTEGER,
    cache_hit       BOOLEAN      DEFAULT FALSE,
    llm_backend     VARCHAR(50),
    llm_model       VARCHAR(100),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── Table 3: User Feedback ─────────────────────────────────────────
-- Thumbs up (+1) / thumbs down (-1) ratings on specific answers.
-- Linked to the query_log row so we know which answer was rated.
CREATE TABLE IF NOT EXISTS feedback (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id    UUID        REFERENCES query_log(id) ON DELETE CASCADE,
    rating      SMALLINT    NOT NULL CHECK (rating IN (-1, 1)),
    comment     TEXT        DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Table 4: RAGAS Evaluation Results ─────────────────────────────
-- Stores scores from each RAGAS evaluation run (Phase 6).
-- One row per question per run — allows tracking quality over time.
CREATE TABLE IF NOT EXISTS eval_results (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              VARCHAR(50) NOT NULL,  -- e.g. '2026-06-15-baseline'
    question            TEXT        NOT NULL,
    faithfulness        FLOAT,
    answer_relevancy    FLOAT,
    context_precision   FLOAT,
    context_recall      FLOAT,
    answer_correctness  FLOAT,
    llm_backend         VARCHAR(50),
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ────────────────────────────────────────────────────────
-- Speeds up common queries: recent queries, session lookups, user lookups
CREATE INDEX IF NOT EXISTS idx_query_log_created  ON query_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_log_session  ON query_log(session_id);
CREATE INDEX IF NOT EXISTS idx_query_log_user     ON query_log(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_query     ON feedback(query_id);
CREATE INDEX IF NOT EXISTS idx_eval_run_id        ON eval_results(run_id);
