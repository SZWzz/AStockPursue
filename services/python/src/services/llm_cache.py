"""LLM Prompt Cache — hash-based deduplication with TTL.

Avoids redundant LLM calls when semantically identical prompts are submitted
within a configurable TTL window.  Uses SHA-256 over (system_prompt + user_prompt).

Also records cache hit/miss counts for monitoring.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

class _CacheEntry:
    __slots__ = ("response", "created_at", "ttl_s")

    def __init__(self, response: str, ttl_s: int = 3600) -> None:
        self.response = response
        self.created_at = time.monotonic()
        self.ttl_s = ttl_s

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl_s


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class LLMCache:
    """In-memory LRU-ish cache for LLM responses.

    Not thread-safe for writes — callers should serialise, or use the
    ``with_cache`` context manager which acquires a module-level lock.
    """

    def __init__(self, max_entries: int = 500, default_ttl_s: int = 3600) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._max_entries = max_entries
        self._default_ttl_s = default_ttl_s
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

    # ---- key generation ----

    @staticmethod
    def make_key(system_prompt: str, user_prompt: str) -> str:
        """Build a deterministic cache key from prompt text."""
        raw = f"{system_prompt}\n---\n{user_prompt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ---- get / set ----

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.expired:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry.response

    def set(self, key: str, response: str, ttl_s: int | None = None) -> None:
        with self._lock:
            # Evict oldest if at capacity
            if len(self._store) >= self._max_entries:
                oldest_key = min(
                    self._store.keys(),
                    key=lambda k: self._store[k].created_at,
                )
                del self._store[oldest_key]
            self._store[key] = _CacheEntry(response, ttl_s or self._default_ttl_s)

    # ---- stats ----

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / max(total, 1), 4),
                "max_entries": self._max_entries,
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    # ---- context manager for LLM caller integration ----

    def cache_or_call(
        self,
        system_prompt: str,
        user_prompt: str,
        call_fn,
        ttl_s: int | None = None,
    ) -> str:
        """Return cached response if available, otherwise call *call_fn* and cache result.

        Args:
            system_prompt: System message.
            user_prompt: User message.
            call_fn: Zero-argument callable that returns the LLM response string.
            ttl_s: Override default TTL (seconds).

        Returns:
            LLM response string (from cache or fresh).
        """
        key = self.make_key(system_prompt, user_prompt)
        cached = self.get(key)
        if cached is not None:
            logger.debug("LLM cache HIT for key %s...", key[:12])
            return cached

        logger.debug("LLM cache MISS for key %s...", key[:12])
        response = call_fn()
        self.set(key, response, ttl_s)
        return response


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cache: LLMCache | None = None
_cache_lock = threading.Lock()


def get_llm_cache() -> LLMCache:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                max_entries = int(__import__("os").environ.get("FM_LLM_CACHE_SIZE", "500"))
                ttl_hours = int(__import__("os").environ.get("FM_LLM_CACHE_TTL_HOURS", "24"))
                _cache = LLMCache(max_entries=max_entries, default_ttl_s=ttl_hours * 3600)
    return _cache
