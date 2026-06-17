# -*- coding: utf-8 -*-
"""
feedback/feedback_handler.py — Feedback collection helpers

Thin wrapper around db.postgres_client feedback functions.
Kept as a separate module so feedback logic can be extended later
(e.g. sending alerts when satisfaction drops below a threshold).
"""

from db.postgres_client import record_feedback, get_feedback_stats


async def submit_feedback(query_id: str, rating: int, comment: str = "") -> dict:
    """
    Record a user rating and return updated stats.

    Args:
        query_id: UUID of the query_log row being rated
        rating:   +1 (helpful) or -1 (not helpful)
        comment:  Optional free-text comment

    Returns:
        {"status": "recorded", "query_id": str}
    """
    await record_feedback(query_id, rating, comment)
    return {"status": "recorded", "query_id": query_id}


async def fetch_stats() -> dict:
    """
    Return aggregate feedback stats.

    Returns:
        {"total": int, "positive": int, "satisfaction_pct": float}
    """
    return await get_feedback_stats()
