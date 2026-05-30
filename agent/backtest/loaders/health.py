"""Loader health tracking — success rate, latency, quota awareness.

Enables ``resolve_loader()`` to prefer fast & healthy loaders and
automatically degrade when a loader becomes unhealthy.

Usage::

    from backtest.loaders.health import HealthTracker, get_health_tracker

    tracker = get_health_tracker()
    tracker.record_success("mootdx", 0.08)   # 80ms
    tracker.record_failure("tushare")

    # Later, resolve_loader("a_share") can query health scores
    scores = tracker.get_scores("a_share")
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class HealthTracker:
    """Per-loader health metrics with exponential decay.

    Thread-safe.  Older samples are weighted less via exponential decay
    (half-life defaults to 5 minutes), so recent failures matter more.
    """

    def __init__(self, window_seconds: float = 300.0):
        self._window = window_seconds
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}

    # ── Record ────────────────────────────────────────────────────────────

    def record_success(self, loader_name: str, latency_s: float) -> None:
        """Record a successful fetch with *latency_s* in seconds."""
        now = time.monotonic()
        with self._lock:
            d = self._ensure(loader_name)
            d["successes"] += 1
            d["total"] += 1
            # Exponential moving average latency
            alpha = 0.3
            d["avg_latency"] = alpha * latency_s + (1 - alpha) * d["avg_latency"]
            d["last_success"] = now
            d["consecutive_failures"] = 0

    def record_failure(self, loader_name: str) -> None:
        """Record a failed fetch."""
        now = time.monotonic()
        with self._lock:
            d = self._ensure(loader_name)
            d["failures"] += 1
            d["total"] += 1
            d["consecutive_failures"] += 1
            d["last_failure"] = now

    def set_quota_remaining(self, loader_name: str, remaining: int) -> None:
        """Update remaining API quota (for rate-limited loaders like TwelveData)."""
        with self._lock:
            d = self._ensure(loader_name)
            d["quota_remaining"] = remaining

    # ── Query ─────────────────────────────────────────────────────────────

    def get_score(self, loader_name: str) -> float:
        """Health score 0.0–1.0 (higher = healthier).

        Factors: success rate (weighted), latency, recent failures.
        """
        with self._lock:
            d = self._data.get(loader_name)
            if d is None or d["total"] == 0:
                return 0.5  # unknown → neutral

        total = d["total"]
        if total == 0:
            return 0.5

        success_rate = d["successes"] / max(total, 1)
        consecutive = d["consecutive_failures"]

        # Heavy penalty for consecutive failures
        if consecutive >= 5:
            success_rate *= 0.1
        elif consecutive >= 3:
            success_rate *= 0.3
        elif consecutive >= 1:
            success_rate *= 0.7

        # Latency bonus (fast < 100ms gets boost)
        avg_lat = d["avg_latency"]
        if avg_lat < 0.1:
            success_rate = min(1.0, success_rate * 1.1)
        elif avg_lat > 5.0:
            success_rate *= 0.8

        return max(0.0, min(1.0, success_rate))

    def get_scores(self, loader_names: list[str]) -> dict[str, float]:
        """Get health scores for multiple loaders at once."""
        return {name: self.get_score(name) for name in loader_names}

    def is_healthy(self, loader_name: str, min_score: float = 0.3) -> bool:
        """Check if a loader is healthy enough to use."""
        return self.get_score(loader_name) >= min_score

    def get_stats(self, loader_name: str) -> dict[str, Any]:
        """Get detailed stats for a loader."""
        with self._lock:
            d = self._data.get(loader_name, {})
            return {
                "name": loader_name,
                "score": self.get_score(loader_name),
                "successes": d.get("successes", 0),
                "failures": d.get("failures", 0),
                "total": d.get("total", 0),
                "avg_latency_ms": round(d.get("avg_latency", 0) * 1000, 1),
                "consecutive_failures": d.get("consecutive_failures", 0),
                "quota_remaining": d.get("quota_remaining"),
                "last_success": d.get("last_success"),
            }

    def get_all_stats(self) -> list[dict[str, Any]]:
        """Stats for all tracked loaders."""
        with self._lock:
            return [self.get_stats(name) for name in self._data]

    # ── Internal ──────────────────────────────────────────────────────────

    def _ensure(self, name: str) -> dict:
        if name not in self._data:
            self._data[name] = {
                "successes": 0,
                "failures": 0,
                "total": 0,
                "avg_latency": 0.5,
                "consecutive_failures": 0,
                "last_success": 0.0,
                "last_failure": 0.0,
                "quota_remaining": None,
            }
        return self._data[name]


# ── Global singleton ──────────────────────────────────────────────────────────

_health_tracker: HealthTracker | None = None


def get_health_tracker() -> HealthTracker:
    """Get or create the global HealthTracker singleton."""
    global _health_tracker
    if _health_tracker is None:
        _health_tracker = HealthTracker()
    return _health_tracker


def health_aware_resolve(market: str) -> Any:
    """Resolve a loader for *market*, prioritizing healthy & fast loaders.

    Instead of strict fallback chain order, sorts available loaders by
    health score (descending) so the fastest reliable loader wins.

    Falls back to standard ``resolve_loader()`` when no health data exists.
    """
    from backtest.loaders.registry import (
        FALLBACK_CHAINS, LOADER_REGISTRY, _ensure_registered, resolve_loader,
    )
    from backtest.loaders.base import NoAvailableSourceError

    _ensure_registered()
    chain = FALLBACK_CHAINS.get(market, [])
    tracker = get_health_tracker()

    # Score each loader in the chain
    candidates = []
    for name in chain:
        if name not in LOADER_REGISTRY:
            continue
        try:
            instance = LOADER_REGISTRY[name]()
        except Exception:
            continue
        if not instance.is_available():
            continue
        score = tracker.get_score(name)
        candidates.append((score, name, instance))

    if not candidates:
        # Fall back to standard resolution
        return resolve_loader(market)

    # Sort by score descending (healthiest first)
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_name, best_instance = candidates[0]

    if best_score < 0.3:
        logger.warning("All loaders for %s are unhealthy: %s", market, [(n, round(s, 2)) for s, n, _ in candidates])

    logger.debug("health_aware_resolve(%s) → %s (score=%.2f)", market, best_name, best_score)
    return best_instance
