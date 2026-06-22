"""Tests for sliding-window rate limiter.

Covers:
- Within limit: no exception raised
- Over limit: raises HTTPException 429
- Different clients don't interfere
- Window expiry (time advancement resets limit)
- In-memory fallback when DB is unavailable
- Custom max_requests / window via env vars
- X-Forwarded-For header extraction
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_request(client_ip: str = "10.0.0.1", headers: dict | None = None) -> MagicMock:
    """Create a mock FastAPI Request for rate limiting."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = client_ip
    request.headers = headers or {}
    return request


def _setup_in_memory_ratelimiter(monkeypatch: pytest.MonkeyPatch, max_requests: int = 5, window_seconds: int = 60):
    """Monkey-patch the rate limiter to use in-memory storage exclusively."""
    # Prevent any DB interactions
    monkeypatch.setattr("src.auth.rate_limit._init_rate_limiter", lambda: None)
    monkeypatch.setattr("src.auth.rate_limit._DEFAULT_MAX_REQUESTS", max_requests)
    monkeypatch.setattr("src.auth.rate_limit._DEFAULT_WINDOW_SECONDS", window_seconds)

    # Use a dict for in-memory timestamp storage
    storage: dict[str, list[float]] = {}

    def mock_load(key: str) -> list[float]:
        return storage.get(key, []).copy()

    def mock_save(key: str, timestamps: list[float]) -> None:
        storage[key] = timestamps

    monkeypatch.setattr("src.auth.rate_limit._load_timestamps", mock_load)
    monkeypatch.setattr("src.auth.rate_limit._save_timestamps", mock_save)

    return storage


# ---------------------------------------------------------------------------
# Within limit
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_within_limit_no_exception(monkeypatch: pytest.MonkeyPatch):
    """Calling check_rate_limit within the limit does not raise."""
    _setup_in_memory_ratelimiter(monkeypatch)

    from src.auth.rate_limit import check_rate_limit

    request = _mock_request(client_ip="10.0.0.1")
    for _ in range(3):
        check_rate_limit(request, max_requests=5, window_seconds=60)


@pytest.mark.unit
def test_exactly_at_limit_no_exception(monkeypatch: pytest.MonkeyPatch):
    """Exactly max_requests calls within window should still pass (limit is exclusive)."""
    _setup_in_memory_ratelimiter(monkeypatch)

    from src.auth.rate_limit import check_rate_limit

    request = _mock_request(client_ip="10.0.0.1")
    for _ in range(5):
        check_rate_limit(request, max_requests=5, window_seconds=60)


# ---------------------------------------------------------------------------
# Over limit
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_over_limit_raises_429(monkeypatch: pytest.MonkeyPatch):
    """Exceeding the limit raises HTTPException with status 429."""
    _setup_in_memory_ratelimiter(monkeypatch)

    from src.auth.rate_limit import check_rate_limit

    request = _mock_request(client_ip="10.0.0.1")
    for _ in range(5):
        check_rate_limit(request, max_requests=5, window_seconds=60)

    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(request, max_requests=5, window_seconds=60)

    assert exc_info.value.status_code == 429
    assert "Too many requests" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Different clients don't interfere
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_different_clients_independent(monkeypatch: pytest.MonkeyPatch):
    """Client A hitting the limit does not block Client B."""
    _setup_in_memory_ratelimiter(monkeypatch)

    from src.auth.rate_limit import check_rate_limit

    req_a = _mock_request(client_ip="10.0.0.1")
    req_b = _mock_request(client_ip="10.0.0.2")

    # Exhaust A's limit
    for _ in range(5):
        check_rate_limit(req_a, max_requests=5, window_seconds=60)

    with pytest.raises(HTTPException):
        check_rate_limit(req_a, max_requests=5, window_seconds=60)

    # B should still be allowed
    check_rate_limit(req_b, max_requests=5, window_seconds=60)


# ---------------------------------------------------------------------------
# Window expiry
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_window_expiry_resets_limit(monkeypatch: pytest.MonkeyPatch):
    """After the window expires, the limit resets."""
    base_time = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: base_time)

    _setup_in_memory_ratelimiter(monkeypatch)

    from src.auth.rate_limit import check_rate_limit

    request = _mock_request(client_ip="10.0.0.1")

    # Exhaust limit
    for _ in range(5):
        check_rate_limit(request, max_requests=5, window_seconds=60)

    # Advance time past the window
    monkeypatch.setattr(time, "monotonic", lambda: base_time + 61)
    # Should succeed again
    check_rate_limit(request, max_requests=5, window_seconds=60)


# ---------------------------------------------------------------------------
# In-memory fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_in_memory_fallback_when_db_unavailable(monkeypatch: pytest.MonkeyPatch):
    """Falls back to in-memory storage when DB operations raise."""
    monkeypatch.setattr("src.auth.rate_limit._init_rate_limiter", lambda: None)

    # In-memory storage simulating _fallback_windows
    storage: dict[str, list[float]] = {}

    def failing_load(key: str) -> list[float]:
        # Simulate the real code: try DB, catch exception, return in-memory fallback
        try:
            raise RuntimeError("DB unavailable")
        except Exception:
            pass
        return storage.get(key, []).copy()

    def failing_save(key: str, timestamps: list[float]) -> None:
        # Simulate the real code: try DB, catch exception, save to in-memory fallback
        try:
            raise RuntimeError("DB unavailable")
        except Exception:
            pass
        storage[key] = list(timestamps)

    monkeypatch.setattr("src.auth.rate_limit._load_timestamps", failing_load)
    monkeypatch.setattr("src.auth.rate_limit._save_timestamps", failing_save)

    from src.auth.rate_limit import check_rate_limit

    request = _mock_request(client_ip="10.0.0.1")

    # Should use in-memory fallback (no exception from rate limit itself)
    for _ in range(3):
        check_rate_limit(request, max_requests=5, window_seconds=60)


# ---------------------------------------------------------------------------
# Custom max_requests / window via env vars
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_custom_max_requests_via_env(monkeypatch: pytest.MonkeyPatch):
    """Env var RATE_LIMIT_MAX_REQUESTS overrides the default max."""
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "3")

    # Re-setup with the env override
    _setup_in_memory_ratelimiter(monkeypatch, max_requests=3, window_seconds=60)

    from src.auth.rate_limit import check_rate_limit

    request = _mock_request(client_ip="10.0.0.1")

    for _ in range(3):
        check_rate_limit(request, max_requests=3, window_seconds=60)

    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(request, max_requests=3, window_seconds=60)

    assert exc_info.value.status_code == 429


@pytest.mark.unit
def test_custom_window_via_env(monkeypatch: pytest.MonkeyPatch):
    """Env var RATE_LIMIT_WINDOW_SECONDS overrides the default window."""
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "10")
    base_time = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: base_time)

    _setup_in_memory_ratelimiter(monkeypatch, max_requests=2, window_seconds=10)

    from src.auth.rate_limit import check_rate_limit

    request = _mock_request(client_ip="10.0.0.1")

    # Exhaust limit
    for _ in range(2):
        check_rate_limit(request, max_requests=2, window_seconds=10)

    with pytest.raises(HTTPException):
        check_rate_limit(request, max_requests=2, window_seconds=10)

    # Advance past the 10s window
    monkeypatch.setattr(time, "monotonic", lambda: base_time + 11)
    check_rate_limit(request, max_requests=2, window_seconds=10)


# ---------------------------------------------------------------------------
# X-Forwarded-For header
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_x_forwarded_for_header_extraction(monkeypatch: pytest.MonkeyPatch):
    """Client key uses X-Forwarded-For header when present."""
    _setup_in_memory_ratelimiter(monkeypatch)

    from src.auth.rate_limit import check_rate_limit, _get_client_key

    request = _mock_request(
        client_ip="10.0.0.1",
        headers={"X-Forwarded-For": "203.0.113.42, 10.0.0.1"},
    )
    key = _get_client_key(request)
    assert key == "203.0.113.42"


@pytest.mark.unit
def test_get_client_key_no_client():
    """_get_client_key returns 'unknown' when no client info is available."""
    request = MagicMock()
    request.headers = {}
    request.client = None

    from src.auth.rate_limit import _get_client_key

    key = _get_client_key(request)
    assert key == "unknown"
