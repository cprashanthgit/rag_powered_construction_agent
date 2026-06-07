# -*- coding: utf-8 -*-
"""
memory/redis_client.py — Redis connection pool with graceful fallback

This module owns the single Redis connection for the entire app.
Every other memory module imports get_redis() from here.

Key design decision: redis_available() is always called before any
Redis operation. If Redis is down, the pipeline degrades gracefully —
session memory and cache are simply skipped, but the app keeps working.
"""

import os
from typing import Optional
import redis

# ── Singleton connection (created once, reused across requests) ────────────────
_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """
    Return the shared Redis client. Creates it on first call.

    Settings come from .env:
        REDIS_HOST     (default: localhost)
        REDIS_PORT     (default: 6379)
        REDIS_PASSWORD (default: empty — no auth for local Docker)
    """
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD") or None,
            decode_responses=True,          # always return str, not bytes
            socket_connect_timeout=3,       # fail fast if Redis is down
            socket_timeout=3,
        )
    return _client


def redis_available() -> bool:
    """
    Ping Redis. Returns True if reachable, False if not.

    Call this before every Redis operation so the app degrades
    gracefully instead of crashing when Redis is unavailable.
    """
    try:
        get_redis().ping()
        return True
    except Exception:
        return False
