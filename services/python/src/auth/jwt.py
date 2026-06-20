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
    from pathlib import Path

    from src.config.paths import get_runtime_root

    _secret_file = Path(get_runtime_root()) / ".jwt_secret"
    try:
        if _secret_file.is_file():
            _SECRET = _secret_file.read_text(encoding="utf-8").strip()
        else:
            _SECRET = secrets.token_hex(32)
            _secret_file.parent.mkdir(parents=True, exist_ok=True)
            # Use umask + tmpfile + replace to avoid race: the key file
            # is never on disk with 644 permissions (even briefly).
            old_umask = os.umask(0o177)  # 0o600
            try:
                import tempfile
                fd, tmp_path = tempfile.mkstemp(dir=str(_secret_file.parent), prefix=".jwt_secret_tmp_")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(_SECRET)
                    os.replace(tmp_path, str(_secret_file))
                except Exception:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
            finally:
                os.umask(old_umask)
    except OSError:
        _SECRET = secrets.token_hex(32)
    os.environ["JWT_SECRET"] = _SECRET

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7
SSE_TOKEN_EXPIRE_MINUTES = 5  # short-lived tokens for SSE query param


def create_token(user_id: int, username: str, role: str, token_version: int) -> str:
    """Create a signed JWT for a user (7-day expiry)."""
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


def create_sse_token(user_id: int, username: str) -> str:
    """Create a short-lived JWT (5 min) for SSE query-param authentication.

    SSE (EventSource) cannot set custom HTTP headers, so the token must
    be passed as a query parameter. By using a very short expiry window,
    we limit the damage if the token is captured in server logs.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "user_id": user_id,
        "purpose": "sse",
        "iat": now,
        "exp": now + timedelta(minutes=SSE_TOKEN_EXPIRE_MINUTES),
    }
    return pyjwt.encode(payload, _SECRET, algorithm=ALGORITHM)


_PBKDF2_ITERATIONS = 600_000
_HASH_ALGORITHM = "sha256"
_DKLEN = 32  # output key length in bytes


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random 16-byte salt."""
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGORITHM,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
        dklen=_DKLEN,
    )
    return f"pbkdf2${salt}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash.

    Supports both the old SHA256 format (``sha256$salt$hash``) and the new
    PBKDF2 format (``pbkdf2$salt$hash``).
    """
    if password_hash.startswith("pbkdf2$"):
        try:
            _, salt, stored = password_hash.split("$", 2)
        except ValueError:
            return False
        computed = hashlib.pbkdf2_hmac(
            _HASH_ALGORITHM,
            password.encode("utf-8"),
            salt.encode("utf-8"),
            _PBKDF2_ITERATIONS,
            dklen=_DKLEN,
        )
        return hmac.compare_digest(computed.hex(), stored)

    if password_hash.startswith("sha256$"):
        parts = password_hash.split("$", 2)
        if len(parts) == 3:
            _, salt, stored = parts
            computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
            return hmac.compare_digest(computed, stored)

    return False
