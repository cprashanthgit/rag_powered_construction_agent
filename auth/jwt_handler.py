# -*- coding: utf-8 -*-
"""
auth/jwt_handler.py — JWT token creation and decoding

JSON Web Tokens (JWT) are the industry standard for stateless authentication.
A token is a cryptographically signed string that encodes the user's identity
and role. The server never stores the token — it just verifies the signature.

Token structure (decoded):
    {
        "sub":   "550e8400-e29b-41d4-a716-446655440000",  ← user UUID
        "email": "inspector@example.com",
        "role":  "inspector",                              ← drives RBAC
        "exp":   1718000000                               ← Unix timestamp (24hr)
    }

Security note:
    JWT_SECRET_KEY must be set in .env to a long random string.
    Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
    Anyone who knows the secret can forge tokens — keep it secret.
"""

import os
from datetime import datetime, timedelta, timezone

import jwt

# ── Config ─────────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("JWT_SECRET_KEY", "change-this-in-production")
ALGORITHM    = "HS256"
EXPIRE_HOURS = 24


def create_token(user_id: str, email: str, role: str) -> str:
    """
    Create a signed JWT token for a successfully authenticated user.

    Args:
        user_id: UUID string from the users table (primary key)
        email:   User's email address
        role:    One of 'public', 'inspector', 'admin'

    Returns:
        Encoded JWT string — send this to the client.
    """
    payload = {
        "sub":   user_id,
        "email": email,
        "role":  role,
        "exp":   datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Raises:
        jwt.ExpiredSignatureError  — token is older than 24 hours
        jwt.InvalidTokenError      — token was tampered with or malformed

    Returns:
        The decoded payload dict: {"sub", "email", "role", "exp"}
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
