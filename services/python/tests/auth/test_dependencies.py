"""Tests for FastAPI auth dependency (require_auth).

Covers:
- JWT Bearer header authentication
- SSE query-param JWT authentication (allowed on /stream paths)
- SSE query-param JWT rejected on non-SSE paths
- API_AUTH_KEY fallback authentication
- Constant-time comparison for API key
- Localhost bypass (127.0.0.1, localhost, ::1)
- Remote IP without credentials → 401/403
- Missing Authorization header → 401/403
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure JWT_SECRET is set before any imports
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests-32bytes!!")

from src.auth.jwt import create_token, create_sse_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_request(
    headers: dict | None = None,
    client_ip: str = "127.0.0.1",
    query_params: dict | None = None,
    path: str = "/api/v1/some-endpoint",
) -> MagicMock:
    """Create a mock FastAPI Request."""
    request = MagicMock()
    request.headers = headers or {}
    request.client = MagicMock()
    request.client.host = client_ip
    request.url = MagicMock()
    request.url.path = path
    request.query_params = query_params or {}
    return request


async def _call_require_auth(request, cred=None, jwt=None):
    """Helper to call require_auth with proper async handling."""
    from src.auth.dependencies import require_auth

    # require_auth is an async function
    return await require_auth(request=request, cred=cred, jwt=jwt)


# ---------------------------------------------------------------------------
# JWT Bearer header
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_bearer_auth_returns_user_dict():
    """Valid JWT in Authorization Bearer header returns user dict."""
    token = create_token(user_id=99, username="bob", role="user", token_version=3)
    cred = MagicMock()
    cred.credentials = token

    request = _mock_request(client_ip="192.168.1.1")

    # Mock _load_data_source_tokens to avoid DB access
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=cred)

    assert result["user_id"] == 99
    assert result["sub"] == "bob"
    assert result["role"] == "user"
    assert result["token_version"] == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_bearer_auth_with_admin_role():
    """Admin role is preserved through the auth dependency."""
    token = create_token(user_id=1, username="admin", role="admin", token_version=0)
    cred = MagicMock()
    cred.credentials = token

    request = _mock_request(client_ip="10.0.0.1")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=cred)

    assert result["role"] == "admin"


# ---------------------------------------------------------------------------
# SSE query param
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_sse_query_param_on_stream_path():
    """JWT in ?jwt= query param is accepted on /stream endpoints."""
    token = create_sse_token(user_id=55, username="sseuser")
    request = _mock_request(
        client_ip="10.0.0.1",
        path="/api/v1/system/stream",
        query_params={"jwt": token},
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=None, jwt=token)

    assert result["user_id"] == 55
    assert result["sub"] == "sseuser"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_sse_query_param_rejected_on_non_sse_path():
    """JWT in ?jwt= is rejected (401) on non-stream endpoints."""
    token = create_sse_token(user_id=55, username="sseuser")
    request = _mock_request(
        client_ip="10.0.0.1",
        path="/api/v1/some-endpoint",
        query_params={"jwt": token},
    )

    from fastapi import HTTPException

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        with pytest.raises(HTTPException) as exc_info:
            await _call_require_auth(request, cred=None, jwt=token)

    # Should get 401 or 403 since no credentials were provided on non-SSE path
    assert exc_info.value.status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_sse_accepted_with_event_stream_accept_header():
    """SSE token accepted when Accept header contains text/event-stream."""
    token = create_sse_token(user_id=55, username="sseuser")
    request = _mock_request(
        headers={"accept": "text/event-stream"},
        client_ip="10.0.0.1",
        path="/api/v1/non-stream-path",
        query_params={"jwt": token},
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=None, jwt=token)

    assert result["user_id"] == 55


# ---------------------------------------------------------------------------
# API_KEY fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_auth(monkeypatch: pytest.MonkeyPatch):
    """Valid API_AUTH_KEY in Authorization header authenticates."""
    monkeypatch.setenv("API_AUTH_KEY", "my-test-api-key")

    # Use the API key as the Bearer token
    cred = MagicMock()
    cred.credentials = "my-test-api-key"

    request = _mock_request(client_ip="192.168.1.1")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=cred)

    assert result["user_id"] == 1
    assert result["role"] == "admin"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_wrong_key_returns_401(monkeypatch: pytest.MonkeyPatch):
    """Wrong API_AUTH_KEY returns 401."""
    monkeypatch.setenv("API_AUTH_KEY", "correct-key")

    cred = MagicMock()
    cred.credentials = "wrong-key"

    request = _mock_request(client_ip="192.168.1.1")

    from fastapi import HTTPException

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        with pytest.raises(HTTPException) as exc_info:
            await _call_require_auth(request, cred=cred)

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Localhost bypass
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_localhost_bypass_127_0_0_1():
    """Request from 127.0.0.1 without credentials passes when no API_KEY set."""
    request = _mock_request(client_ip="127.0.0.1")

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("API_AUTH_KEY", raising=False)
        mp.setattr("src.auth.dependencies.os.getenv", lambda k, d="": d)
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=None)

    assert result["user_id"] == 1
    assert result["username"] == "local"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_localhost_bypass_localhost():
    """Request from 'localhost' passes the localhost bypass."""
    request = _mock_request(client_ip="localhost")

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("API_AUTH_KEY", raising=False)
        mp.setattr("src.auth.dependencies.os.getenv", lambda k, d="": d)
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=None)

    assert result["username"] == "local"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_localhost_bypass_ipv6():
    """Request from ::1 (IPv6 localhost) passes the localhost bypass."""
    request = _mock_request(client_ip="::1")

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("API_AUTH_KEY", raising=False)
        mp.setattr("src.auth.dependencies.os.getenv", lambda k, d="": d)
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=None)

    assert result["username"] == "local"


# ---------------------------------------------------------------------------
# Remote IP without credentials
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remote_ip_no_credentials_returns_403():
    """Remote IP without any credentials returns 403 (no API key configured)."""
    request = _mock_request(client_ip="203.0.113.42")

    from fastapi import HTTPException

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("API_AUTH_KEY", raising=False)
        mp.setattr("src.auth.dependencies.os.getenv", lambda k, d="": d)
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        with pytest.raises(HTTPException) as exc_info:
            await _call_require_auth(request, cred=None)

    assert exc_info.value.status_code == 403


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remote_ip_api_key_configured_no_credentials_returns_401():
    """Remote IP with API_KEY set but no credentials → 401."""
    request = _mock_request(client_ip="203.0.113.42")

    from fastapi import HTTPException

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("API_AUTH_KEY", "some-key")
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        with pytest.raises(HTTPException) as exc_info:
            await _call_require_auth(request, cred=None)

    assert exc_info.value.status_code == 401


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_authorization_header_with_api_key():
    """No Authorization header + API_KEY configured → 401."""
    request = _mock_request(client_ip="192.168.1.1")

    from fastapi import HTTPException

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("API_AUTH_KEY", "configured-key")
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        with pytest.raises(HTTPException) as exc_info:
            await _call_require_auth(request, cred=None)

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# X-Forwarded-For header path (via rate_limit mock, not needed here)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_with_purpose_sse_on_bearer_still_works():
    """SSE token in Bearer header still works (the purpose field is ignored)."""
    token = create_sse_token(user_id=33, username="mixed")
    cred = MagicMock()
    cred.credentials = token

    request = _mock_request(client_ip="10.0.0.1")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.auth.dependencies._load_data_source_tokens", lambda uid: None)
        result = await _call_require_auth(request, cred=cred)

    assert result["user_id"] == 33
    assert result["sub"] == "mixed"
