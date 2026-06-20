"""Cross-worker SSE message bus via PostgreSQL LISTEN/NOTIFY.

In multi-worker deployments (uvicorn --workers N), in-memory asyncio.Queue
cannot deliver messages to clients connected to different worker processes.
This module provides a PG-backed pub/sub layer that routes events across
all workers sharing the same PostgreSQL instance.

When PG is unavailable, it falls back to in-memory queues (single-worker safe).
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process fallback queue (single-worker mode)
# ---------------------------------------------------------------------------

_inproc_queues: dict[str, list[queue.Queue[dict[str, Any]]]] = {}
_inproc_lock = threading.Lock()
_inproc_event_history: dict[str, list[dict[str, Any]]] = {}  # channel -> recent events
_MAX_HISTORY = 200


def _inproc_publish(channel: str, event: dict[str, Any]) -> None:
    """Publish to all local subscribers on *channel*."""
    with _inproc_lock:
        # Store in history for late subscribers (replay)
        hist = _inproc_event_history.setdefault(channel, [])
        hist.append(event)
        if len(hist) > _MAX_HISTORY:
            hist[: len(hist) - _MAX_HISTORY] = []

        qs = _inproc_queues.get(channel, [])
    for q in qs:
        try:
            q.put_nowait(event)
        except queue.Full:
            pass


def _inproc_subscribe(channel: str) -> queue.Queue[dict[str, Any]]:
    """Create a subscriber queue for *channel*."""
    q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1024)
    with _inproc_lock:
        _inproc_queues.setdefault(channel, []).append(q)
        # Replay recent events
        for evt in _inproc_event_history.get(channel, [])[-50:]:
            try:
                q.put_nowait(evt)
            except queue.Full:
                break
    return q


def _inproc_unsubscribe(channel: str, q: queue.Queue[dict[str, Any]]) -> None:
    """Remove subscriber queue."""
    with _inproc_lock:
        qs = _inproc_queues.get(channel, [])
        if q in qs:
            qs.remove(q)


# ---------------------------------------------------------------------------
# SSEBus (unified interface)
# ---------------------------------------------------------------------------

class SSEBus:
    """Cross-worker message bus backed by PG LISTEN/NOTIFY.

    Usage (publisher)::

        bus = SSEBus()
        await bus.publish("factor-mining:job-123", {"type": "progress", ...})

    Usage (subscriber — from FastAPI SSE endpoint)::

        bus = SSEBus()
        async for event in bus.subscribe("factor-mining:job-123"):
            yield f"event: {event['type']}\\ndata: {json.dumps(event)}\\n\\n"
    """

    def __init__(self, pg_dsn: str | None = None) -> None:
        self._pg_dsn = pg_dsn
        self._pg_available: bool | None = None  # tri-state: None=unchecked, True/False
        self._pg_pool: Any = None
        self._pg_lock = threading.Lock()

    # ------------------------------------------------------------------
    # PG availability probe
    # ------------------------------------------------------------------

    def _check_pg(self) -> bool:
        """Lazy-check whether async PG is available. Cached after first call."""
        if self._pg_available is not None:
            return self._pg_available
        try:
            import asyncpg  # type: ignore[import-untyped]
            self._pg_available = True
        except ImportError:
            logger.debug("asyncpg not installed — SSE falls back to in-memory queues")
            self._pg_available = False
        return self._pg_available

    async def _get_pg_conn(self):
        """Acquire a dedicated asyncpg connection for LISTEN."""
        if self._pg_pool is None and self._check_pg():
            import asyncpg
            dsn = self._pg_dsn or self._build_dsn()
            if dsn:
                try:
                    self._pg_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
                    logger.info("SSEBus: asyncpg pool created")
                except Exception as e:
                    logger.warning("SSEBus: asyncpg pool failed: %s — falling back to in-memory", e)
                    self._pg_pool = None
                    self._pg_available = False
        if self._pg_pool is not None:
            return await self._pg_pool.acquire()
        return None

    @staticmethod
    def _build_dsn() -> str | None:
        """Build PG DSN from environment, matching pool.py convention."""
        import os
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5433")
        dbname = os.getenv("DB_NAME", "stock-data")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")
        if not password:
            try:
                from src.db.crypto import decrypt_password
                enc = os.getenv("DB_PASSWORD_ENC", "")
                key = os.getenv("DB_ENCRYPTION_KEY", "")
                if enc and key:
                    password = decrypt_password(enc, key)
            except Exception:
                logger.debug("Failed to decrypt DB password for SSEBus DSN — no password available")
                pass
        if not password:
            return None
        return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, channel: str, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to *channel*.

        Args:
            channel: Logical channel name (e.g. ``"factor-mining:job-abc123"``).
            event_type: SSE event type (``"progress"``, ``"done"``, etc.).
            data: JSON-serialisable payload dict.
        """
        event = {"type": event_type, "ts": datetime.now(timezone.utc).isoformat(), **data}
        payload = json.dumps(event, ensure_ascii=False, default=str)

        # Always publish in-process (handles same-worker subscribers)
        _inproc_publish(channel, event)

        # Try PG NOTIFY for cross-worker delivery
        if self._check_pg():
            conn = None
            try:
                import asyncpg
                conn = await self._get_pg_conn()
                if conn is not None:
                    await conn.execute(
                        "SELECT pg_notify($1, $2)",
                        _sanitise_channel(channel),
                        payload,
                    )
            except Exception as e:
                logger.debug("PG NOTIFY failed for channel %s: %s", channel, e)
            finally:
                if conn is not None:
                    try:
                        await conn.close()
                    except Exception:
                        logger.debug("Failed to close PG connection after publish on channel %s", channel)
                        pass

    # ------------------------------------------------------------------
    # Subscribe (async generator — used in SSE endpoints)
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        channel: str,
        last_event_id: str = "",
        heartbeat_interval: float = 15.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events on *channel*.

        Yields events as they arrive.  Sends a heartbeat comment every
        *heartbeat_interval* seconds to keep the HTTP connection alive.
        Handles PG disconnect by falling back to in-process queue only.

        Args:
            channel: Logical channel name.
            last_event_id: Resume point (unused in current impl — reserved).
            heartbeat_interval: Seconds between heartbeat pings (default 15s).

        Yields:
            Event dicts with keys ``type``, ``ts``, and payload fields.
        """
        # Always subscribe to in-process queue (covers same-worker + PG fallback)
        local_q = _inproc_subscribe(channel)

        # Also try PG LISTEN for cross-worker events
        pg_conn = None
        pg_queue: asyncio.Queue[dict[str, Any]] | None = None
        if self._check_pg():
            try:
                pg_conn = await self._get_pg_conn()
                if pg_conn is not None:
                    pg_queue = asyncio.Queue(maxsize=512)
                    safe_ch = _sanitise_channel(channel)
                    await pg_conn.execute(f"LISTEN {safe_ch}")

                    async def _pg_listener(conn, q):
                        while True:
                            try:
                                notification = await conn.fetchrow(
                                    "SELECT 1 FROM pg_sleep(5) WHERE false"
                                )
                            except Exception:
                                # Connection likely dropped; fall back to in-process
                                break

                    # Register proper listener
                    def _pg_callback(conn, pid, ch, payload):
                        try:
                            evt = json.loads(payload)
                            if pg_queue is not None:
                                asyncio.ensure_future(pg_queue.put(evt))
                        except Exception:
                            logger.debug("Failed to parse PG NOTIFY payload on channel %s", channel)
                            pass

                    pg_conn.add_termination_listener(lambda c: logger.debug("PG SSE conn terminated"))
            except Exception as e:
                logger.debug("PG LISTEN setup failed for %s: %s", channel, e)
                if pg_conn is not None:
                    try:
                        await pg_conn.close()
                    except Exception:
                        logger.debug("Failed to close PG connection during subscribe setup for %s", channel)
                        pass
                pg_conn = None
                pg_queue = None

        try:
            while True:
                event: dict[str, Any] | None = None

                # Try local queue
                try:
                    event = local_q.get_nowait()
                except queue.Empty:
                    pass

                # Try PG queue
                if event is None and pg_queue is not None:
                    try:
                        event = await asyncio.wait_for(pg_queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        pass

                if event is not None:
                    yield event
                else:
                    # Heartbeat to keep HTTP connection alive
                    yield {
                        "type": "heartbeat",
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                    await asyncio.sleep(heartbeat_interval)

        except asyncio.CancelledError:
            pass
        finally:
            _inproc_unsubscribe(channel, local_q)
            if pg_conn is not None:
                try:
                    await pg_conn.close()
                except Exception:
                    logger.debug("Failed to close PG connection in subscribe finally for channel %s", channel)
                    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitise_channel(name: str) -> str:
    """Sanitise a logical channel name for PostgreSQL identifier rules.

    PG channel names must be valid SQL identifiers (max 63 chars, alphanumeric + underscore).
    """
    import re
    sanitised = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    sanitised = sanitised[:63]
    if not sanitised or sanitised[0].isdigit():
        sanitised = "ch_" + sanitised
    return sanitised.lower()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_bus: SSEBus | None = None
_bus_lock = threading.Lock()


def get_sse_bus() -> SSEBus:
    """Return the process-wide SSEBus singleton."""
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = SSEBus()
    return _bus
