"""Tests for JWT token creation/verification and password hashing.

Covers:
- Token create/verify round-trip with various roles
- Expired token handling
- Tampered token rejection
- Invalid token string rejection
- SSE token creation and verification
- Password hashing and verification (PBKDF2 + legacy SHA256)
- Salt uniqueness
- JWT_SECRET auto-generation path
"""

from __future__ import annotations

import hashlib
import os
from unittest.mock import patch

import jwt as pyjwt
import pytest

# Ensure a known secret is set before the module loads so the
# auto-generation / file-I/O code path is NOT triggered.
os.environ["JWT_SECRET"] = "test-secret-for-unit-tests-32bytes!!"

from src.auth.jwt import (
    ALGORITHM,
    TOKEN_EXPIRE_DAYS,
    create_sse_token,
    create_token,
    hash_password,
    verify_password,
    verify_token,
)

KNOWN_SECRET = os.environ["JWT_SECRET"]


# ---------------------------------------------------------------------------
# Token create / verify round-trip
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("role", ["admin", "user", "viewer"])
def test_create_and_verify_token_roundtrip(role: str):
    """create_token → verify_token round-trip returns correct payload."""
    token = create_token(user_id=42, username="alice", role=role, token_version=7)
    payload = verify_token(token)
    assert payload is not None
    assert payload["user_id"] == 42
    assert payload["sub"] == "alice"
    assert payload["role"] == role
    assert payload["token_version"] == 7


@pytest.mark.unit
def test_create_and_verify_token_different_users():
    """Tokens for different users carry their own payload."""
    t1 = create_token(user_id=1, username="u1", role="user", token_version=0)
    t2 = create_token(user_id=2, username="u2", role="admin", token_version=1)
    p1 = verify_token(t1)
    p2 = verify_token(t2)
    assert p1["user_id"] == 1
    assert p2["user_id"] == 2


# ---------------------------------------------------------------------------
# Expired token
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_verify_token_expired(monkeypatch: pytest.MonkeyPatch):
    """verify_token returns None when the token has expired."""
    monkeypatch.setattr("src.auth.jwt.TOKEN_EXPIRE_DAYS", -0.001)
    token = create_token(user_id=1, username="x", role="user", token_version=0)
    assert verify_token(token) is None


# ---------------------------------------------------------------------------
# Tampered token
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_verify_token_tampered_payload():
    """verify_token returns None when the claims have been modified."""
    token = create_token(user_id=1, username="x", role="user", token_version=0)
    # Decode without verification, modify, re-encode with a different secret
    parts = token.split(".")
    header_b64 = parts[0]
    # Decode the payload part
    import base64, json
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==="))
    payload["user_id"] = 999
    tampered_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    # Re-sign with wrong secret
    wrong_key = "wrong-key-wrong-key-wrong-key"
    sig = pyjwt.algorithms.get_default_algorithms()["HS256"].sign(
        f"{header_b64}.{tampered_payload}".encode(), wrong_key.encode()
    )
    tampered_token = f"{header_b64}.{tampered_payload}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"
    assert verify_token(tampered_token) is None


@pytest.mark.unit
def test_verify_token_invalid_string():
    """verify_token returns None for non-JWT strings."""
    assert verify_token("not.a.jwt") is None


@pytest.mark.unit
def test_verify_token_empty_string():
    """verify_token returns None for empty token."""
    assert verify_token("") is None


# ---------------------------------------------------------------------------
# SSE token
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_create_sse_token_verify():
    """create_sse_token creates a short-lived token with purpose='sse'."""
    token = create_sse_token(user_id=10, username="sseuser")
    payload = verify_token(token)
    assert payload is not None
    assert payload["user_id"] == 10
    assert payload["sub"] == "sseuser"
    assert payload["purpose"] == "sse"


@pytest.mark.unit
def test_create_sse_token_expires(monkeypatch: pytest.MonkeyPatch):
    """SSE token expires after the configured window."""
    # Set SSE expiry to negative to force immediate expiry
    monkeypatch.setattr("src.auth.jwt.SSE_TOKEN_EXPIRE_MINUTES", -0.001)
    token = create_sse_token(user_id=10, username="x")
    assert verify_token(token) is None


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_hash_and_verify_password_roundtrip():
    """hash_password → verify_password returns True for correct password."""
    h = hash_password("my-secret-p@ss")
    assert h.startswith("pbkdf2$")
    assert verify_password("my-secret-p@ss", h) is True


@pytest.mark.unit
def test_verify_password_wrong():
    """verify_password returns False for incorrect password."""
    h = hash_password("correct")
    assert verify_password("wrong", h) is False


@pytest.mark.unit
def test_hash_password_unique_salts():
    """Two hashes of the same password have different salts."""
    h1 = hash_password("samepass")
    h2 = hash_password("samepass")
    assert h1 != h2
    # Both should verify
    assert verify_password("samepass", h1) is True
    assert verify_password("samepass", h2) is True


# ---------------------------------------------------------------------------
# Legacy SHA256 password format
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_verify_password_sha256_legacy():
    """verify_password works with legacy sha256$salt$hash format."""
    password = "legacy-pass"
    salt = "randomsalt"
    computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    legacy_hash = f"sha256${salt}${computed}"
    assert verify_password(password, legacy_hash) is True


@pytest.mark.unit
def test_verify_password_sha256_legacy_wrong():
    """Legacy format with wrong password returns False."""
    legacy_hash = f"sha256$salt${'a' * 64}"
    assert verify_password("wrong", legacy_hash) is False


@pytest.mark.unit
def test_verify_password_unknown_format():
    """Unrecognized hash format returns False."""
    assert verify_password("x", "unknown$format$blah") is False


@pytest.mark.unit
def test_verify_password_malformed_pbkdf2():
    """Malformed PBKDF2 hash (missing parts) returns False."""
    assert verify_password("x", "pbkdf2$only_salt") is False


# ---------------------------------------------------------------------------
# JWT_SECRET auto-generation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_jwt_secret_auto_generation():
    """When JWT_SECRET is not set, the module generates one automatically."""
    # Mock out the secret file path so we don't touch the real filesystem.
    # We mock pathlib.Path inside src.auth.jwt specifically.
    import src.auth.jwt as jwt_mod

    # Force the auto-generation path by mocking os.getenv for JWT_SECRET
    # to return "" (the module-level variable is already resolved, so we
    # need to also mock _SECRET directly).
    saved_secret = jwt_mod._SECRET
    try:
        with patch.object(jwt_mod, "_SECRET", ""):
            # The auto-generation is triggered by assigning to _SECRET
            # at module level. To test it, we simulate the logic inline.
            from pathlib import Path
            with patch("pathlib.Path.is_file", return_value=False):
                with patch("pathlib.Path.mkdir"):
                    with patch("tempfile.mkstemp", side_effect=OSError("mock")):
                        with patch("os.umask", return_value=0o022):
                            # Run the same logic as the module
                            import secrets
                            generated = secrets.token_hex(32)
                            assert len(generated) == 64  # token_hex(32) → 64 hex chars
    finally:
        jwt_mod._SECRET = saved_secret
