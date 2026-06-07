# -*- coding: utf-8 -*-
"""
memory/session_store.py — Per-session conversation history in Redis

Each browser session gets a unique session_id (generated in app.py).
The conversation history is stored in Redis as a JSON list under the key:
    session:{session_id}:history

Design choices:
  - TTL: 1 hour. If the user is idle for 1 hour, the session expires.
  - MAX_TURNS: 10 messages (5 exchanges). Older messages are dropped.
    This keeps the LLM context window small and avoids token overflows.
  - Format: [{"role": "user", "content": "..."}, {"role": "assistant", ...}]
    This is the standard OpenAI / LangChain message format.
"""

import json
from memory.redis_client import get_redis

# ── Constants ──────────────────────────────────────────────────────────────────
SESSION_TTL = 3600   # seconds — 1 hour of inactivity expires the session
MAX_TURNS   = 10     # max messages stored (5 user + 5 assistant)


def load_history(session_id: str) -> list:
    """
    Load conversation history for a session.

    Returns a list of message dicts, oldest first:
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

    Returns an empty list if the session doesn't exist or has expired.
    """
    raw = get_redis().get(f"session:{session_id}:history")
    return json.loads(raw) if raw else []


def save_turn(session_id: str, user_msg: str, assistant_msg: str) -> None:
    """
    Append a new exchange (user + assistant) to the session history.

    Also resets the TTL so active conversations never expire mid-chat.
    Trims to MAX_TURNS so the list never grows unbounded.
    """
    history = load_history(session_id)

    # Append the new exchange
    history.extend([
        {"role": "user",      "content": user_msg},
        {"role": "assistant", "content": assistant_msg},
    ])

    # Keep only the last MAX_TURNS messages (drop the oldest)
    history = history[-MAX_TURNS:]

    # Write back to Redis, resetting the TTL on every save
    get_redis().setex(
        f"session:{session_id}:history",
        SESSION_TTL,
        json.dumps(history),
    )


def clear_session(session_id: str) -> None:
    """
    Delete all history for a session (used by the 'Clear Chat' button in UI).
    """
    get_redis().delete(f"session:{session_id}:history")
