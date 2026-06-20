"""Shared trading configuration constants.

Centralises magic numbers that were previously scattered across engine.py
and signal_adapter.py.  All values can be overridden via environment variables
or per-instance config dicts.
"""

from __future__ import annotations

import os

# ── Data history ─────────────────────────────────────────────────────────────

# Maximum bars retained in _data_map for batch-mode strategies.
# Prevents unbounded memory growth in very long backtests (~20 years of daily
# data ≈ 5000 bars).  Long-window factors (e.g. correlation(…, 230)) need 230+
# bars; 5000 provides a comfortable margin.
#
# Override: set TRADING_MAX_HISTORY env var.
MAX_HISTORY: int = int(os.getenv("TRADING_MAX_HISTORY", "5000"))

# ── Signal generation ───────────────────────────────────────────────────────

# Threshold below which signal weights are treated as zero.
EPSILON: float = 1e-9

# ── Workflow engine ──────────────────────────────────────────────────────────

# Default node execution timeout in seconds.
DEFAULT_NODE_TIMEOUT: float = float(os.getenv("WF_NODE_TIMEOUT", "600"))

# Maximum concurrency for workflow DAG execution.
MAX_CONCURRENCY: int = int(os.getenv("WF_MAX_CONCURRENCY", "32"))

# Resource-specific concurrency limits.
RESOURCE_LIMITS: dict[str, int] = {
    "default": int(os.getenv("WF_LIMIT_DEFAULT", "8")),
    "cpu_bound": int(os.getenv("WF_LIMIT_CPU", "4")),
    "io_bound": int(os.getenv("WF_LIMIT_IO", "16")),
    "db_bound": int(os.getenv("WF_LIMIT_DB", "4")),
}

# ── GP evolution ─────────────────────────────────────────────────────────────

# Default population size.
GP_POPULATION_SIZE: int = int(os.getenv("GP_POPULATION_SIZE", "100"))

# Default number of generations.
GP_GENERATIONS: int = int(os.getenv("GP_GENERATIONS", "50"))

# Max parallel workers for GP fitness evaluation.
GP_MAX_WORKERS: int = int(os.getenv("GP_MAX_WORKERS", "4"))

# Tournament selection size.
GP_TOURNAMENT_SIZE: int = int(os.getenv("GP_TOURNAMENT_SIZE", "7"))

# ── Data loading ─────────────────────────────────────────────────────────────

# Max age (hours) for cached OHLCV data before re-fetching.
CACHE_MAX_AGE_HOURS: int = int(os.getenv("DATA_CACHE_MAX_AGE_HOURS", "24"))

# Number of concurrent data fetches.
DATA_FETCH_WORKERS: int = int(os.getenv("DATA_FETCH_WORKERS", "16"))

# Data loader timeout in seconds.
DATA_LOADER_TIMEOUT: float = float(os.getenv("DATA_LOADER_TIMEOUT", "1.0"))

# ── Position sizing ─────────────────────────────────────────────────────────

# Minimum notional value (price × size) for a position to be opened.
# Prevents opening trivially small positions that would be consumed by fees.
# Override: set TRADING_MIN_NOTIONAL env var.
MIN_NOTIONAL: float = float(os.getenv("TRADING_MIN_NOTIONAL", "100"))
