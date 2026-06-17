# -*- coding: utf-8 -*-
"""
auth/rbac.py — Role-Based Access Control (RBAC) for FastAPI

Defines the 3 user roles and the get_current_user() FastAPI dependency.

How FastAPI dependencies work:
    Any endpoint that includes `user = Depends(get_current_user)` will
    automatically have this function run before the endpoint handler.
    The result (user dict) is injected as the `user` argument.

Role hierarchy:
    public    → can access: general construction/safety documents
    inspector → can access: public + restricted inspection reports
    admin     → can access: everything, no document filters applied

Anonymous access:
    If no Authorization header is present, the user is treated as
    role='public' (not an error). This keeps the API usable without login
    while still applying document filters.
"""

import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_handler import decode_token

# ── Bearer token extractor ─────────────────────────────────────────────────────
# auto_error=False → don't raise 403 if header is missing; handle it ourselves
security = HTTPBearer(auto_error=False)

# ── Role → allowed document access levels ─────────────────────────────────────
ROLE_ACCESS = {
    "public":    ["public"],
    "inspector": ["public", "restricted"],
    "admin":     ["public", "restricted", "confidential"],
}


def get_current_user(
    creds: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """
    FastAPI dependency — decodes the Bearer token and returns the user payload.

    Usage in any endpoint:
        @app.post("/query/sync")
        async def query_sync(request: QueryRequest, user = Depends(get_current_user)):
            role = user["role"]  # 'public', 'inspector', or 'admin'

    Returns:
        dict with keys: sub (user_id), email, role
        Anonymous users (no token) get: {"sub": "anonymous", "role": "public", "email": ""}

    Raises:
        HTTPException 401 — if token is expired or tampered with
    """
    if creds is None:
        # No Authorization header → anonymous public access
        return {"sub": "anonymous", "role": "public", "email": ""}

    try:
        return decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def retrieval_filter_for(role: str) -> dict:
    """
    Returns the Pinecone/FAISS metadata filter for a given role.

    Admins get no filter (see everything).
    All other roles get a filter restricting to their allowed access levels.

    Usage in pipeline (future):
        filter = retrieval_filter_for(user["role"])
        retrieve(query, retriever, metadata_filter=filter)
    """
    if role == "admin":
        return {}  # no filter — see everything
    allowed = ROLE_ACCESS.get(role, ["public"])
    return {"access_level": {"$in": allowed}}
