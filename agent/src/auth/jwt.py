"""JWT token creation and verification for user authentication."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

_SECRET = os.getenv("JWT_SECRET", "")

if not _SECRET:
    _SECRET = secrets.token_hex(32)
    os.environ["JWT_SECRET"] = _SECRET

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def create_token(user_id: int, username: str, role: str, token_version: int) -> str:
    """Create a signed JWT for a user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "user_id": user_id,
        "role": role,
        "token_version": token_version,
        "iat": now,
        "exp": now + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return pyjwt.encode(payload, _SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Verify a JWT and return the payload dict, or None if invalid/expired."""
    try:
        payload = pyjwt.decode(token, _SECRET, algorithms=[ALGORITHM])
        return payload
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None


def hash_password(password: str) -> str:
    """Hash a password using SHA256 + random salt (same format as QuantDinger)."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"sha256${salt}${h}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash."""
    if password_hash.startswith("sha256$"):
        parts = password_hash.split("$", 2)
        if len(parts) == 3:
            _, salt, stored = parts
            computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
            return hmac.compare_digest(computed, stored)
    return False
