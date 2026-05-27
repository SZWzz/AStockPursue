"""PostgreSQL-backed sliding-window rate limiter for authentication endpoints.

Persists rate-limit state in the database so a server restart does not reset
brute-force counters. Falls back to in-memory if the DB is unavailable.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Default: 5 attempts per 60-second window
_DEFAULT_MAX_REQUESTS = 5
_DEFAULT_WINDOW_SECONDS = 60

# In-memory fallback when DB is unavailable
_fallback_windows: Dict[str, List[float]] = {}


# ── DB-backed rate limit table ───────────────────────────────────────────

_RATE_LIMIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS vt_rate_limits (
    client_key    TEXT PRIMARY KEY,
    timestamps    JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _ensure_rate_limit_table() -> None:
    """Create the rate_limits table if it doesn't exist."""
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_RATE_LIMIT_TABLE_SQL)
            conn.commit()
    except Exception as e:
        logger.warning("Failed to create rate_limits table (falling back to in-memory): %s", e)


_load_ts_sql = "SELECT timestamps FROM vt_rate_limits WHERE client_key = %s"
_save_ts_sql = """
INSERT INTO vt_rate_limits (client_key, timestamps, updated_at)
VALUES (%s, %s::jsonb, NOW())
ON CONFLICT (client_key) DO UPDATE SET
    timestamps = EXCLUDED.timestamps,
    updated_at = NOW()
"""


def _get_client_key(request: Request) -> str:
    """Extract client identity from request headers or IP."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _load_timestamps(key: str) -> list[float]:
    """Load timestamps from DB (or in-memory fallback)."""
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_load_ts_sql, (key,))
                row = cur.fetchone()
                if row and row[0]:
                    return [float(ts) for ts in row[0] if ts]
    except Exception as e:
        logger.debug("Rate-limit DB read failed (fallback to memory): %s", e)
    return _fallback_windows.get(key, [])


def _save_timestamps(key: str, timestamps: list[float]) -> None:
    """Save timestamps to DB (or in-memory fallback)."""
    import json
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                ts_json = json.dumps(timestamps)
                cur.execute(_save_ts_sql, (key, ts_json))
            conn.commit()
    except Exception as e:
        logger.debug("Rate-limit DB write failed (fallback to memory): %s", e)
        _fallback_windows[key] = timestamps


def _init_rate_limiter() -> None:
    """Idempotent init: ensure table exists."""
    if not hasattr(_init_rate_limiter, "_done"):
        _ensure_rate_limit_table()
        _init_rate_limiter._done = True


def check_rate_limit(
    request: Request,
    max_requests: int = _DEFAULT_MAX_REQUESTS,
    window_seconds: int = _DEFAULT_WINDOW_SECONDS,
) -> None:
    """Raise 429 if the client has exceeded the rate limit.

    Uses PostgreSQL-backed storage so rate-limit state survives server
    restarts. Falls back to in-memory if the DB is unavailable.

    Args:
        request: The incoming HTTP request.
        max_requests: Maximum allowed requests within the window.
        window_seconds: Sliding window duration in seconds.
    """
    _init_rate_limiter()
    key = _get_client_key(request)
    now = time.monotonic()
    cutoff = now - window_seconds

    # Load + slide window
    timestamps = _load_timestamps(key)
    timestamps = [ts for ts in timestamps if ts > cutoff]

    if len(timestamps) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
        )

    timestamps.append(now)
    _save_timestamps(key, timestamps)
