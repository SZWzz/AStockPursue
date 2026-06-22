"""Async wrapper for the synchronous PostgreSQL connection pool.

Provides `async_get_connection()`, an async context manager that acquires
and releases PG connections via `asyncio.to_thread()` so pool wait / I/O
never blocks the event loop.

Usage::

    async with async_get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from src.db.pool import init_pool, _acquire_with_retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy reference to the pool singleton (populated on first use)
# ---------------------------------------------------------------------------

_pool_ref = None


def _get_pool():
    """Lazily grab a reference to the ThreadedConnectionPool singleton."""
    global _pool_ref
    if _pool_ref is not None:
        return _pool_ref
    from src.db import pool as _pool_mod

    _pool_ref = _pool_mod._pool
    return _pool_ref


# ---------------------------------------------------------------------------
# Synchronous helpers (run in worker threads via asyncio.to_thread)
# ---------------------------------------------------------------------------


def _acquire_conn():
    """Sync: acquire a connection with retry + optional health check."""
    init_pool()
    pool = _get_pool()
    return _acquire_with_retry(pool)


def _release_conn(conn, *, success: bool):
    """Sync: commit or rollback, then return the connection to the pool."""
    pool = _get_pool()
    try:
        if success:
            conn.commit()
        else:
            conn.rollback()
    finally:
        pool.putconn(conn, close=conn.closed != 0)


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


@asynccontextmanager
async def async_get_connection():
    """Async context manager that yields a PG connection.

    Acquire and release run in a worker thread via `asyncio.to_thread`
    so the asyncio event loop is never blocked waiting for the pool.
    """
    conn = await asyncio.to_thread(_acquire_conn)
    success = False
    try:
        yield conn
        success = True
    finally:
        await asyncio.to_thread(_release_conn, conn, success=success)
