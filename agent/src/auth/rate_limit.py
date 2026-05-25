"""In-memory sliding-window rate limiter for authentication endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import HTTPException, Request

# Default: 5 attempts per 60-second window
_DEFAULT_MAX_REQUESTS = 5
_DEFAULT_WINDOW_SECONDS = 60
_CLEANUP_INTERVAL = 300  # 5 minutes

# {client_key: [timestamp, ...]}
_windows: Dict[str, List[float]] = {}
_last_cleanup = time.monotonic()


def _get_client_key(request: Request) -> str:
    """Extract client identity from request headers or IP."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _cleanup_expired() -> None:
    """Remove expired timestamps from all windows."""
    global _last_cleanup, _windows
    now = time.monotonic()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    cutoff = now - _DEFAULT_WINDOW_SECONDS
    for key in list(_windows.keys()):
        _windows[key] = [ts for ts in _windows[key] if ts > cutoff]
        if not _windows[key]:
            del _windows[key]


def check_rate_limit(
    request: Request,
    max_requests: int = _DEFAULT_MAX_REQUESTS,
    window_seconds: int = _DEFAULT_WINDOW_SECONDS,
) -> None:
    """Raise 429 if the client has exceeded the rate limit.

    Args:
        request: The incoming HTTP request.
        max_requests: Maximum allowed requests within the window.
        window_seconds: Sliding window duration in seconds.
    """
    _cleanup_expired()
    key = _get_client_key(request)
    now = time.monotonic()
    cutoff = now - window_seconds

    if key not in _windows:
        _windows[key] = []

    # Slide the window
    _windows[key] = [ts for ts in _windows[key] if ts > cutoff]

    if len(_windows[key]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
        )

    _windows[key].append(now)
