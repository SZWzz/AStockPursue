"""Parquet-based local OHLCV store with incremental update support.

Stores per-code/per-interval OHLCV data as Parquet files for fast
columnar reads and high compression.  Integrates with the PG cache
layer — PG is the hot cache, Parquet is the cold persistent store.

Usage::

    from backtest.loaders.store import load_from_store, update_store

    df = load_from_store("600519.SH", "1D", "2024-01-01", "2025-12-31")
    if df is None:
        df = fetch_from_api(...)
        update_store("600519.SH", "1D", df)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default store root: ~/.AStockPursue/data/
_STORE_ROOT = Path.home() / ".AStockPursue" / "data"


def _store_path(code: str, interval: str) -> Path:
    """File path for a given code + interval."""
    safe_code = code.replace("/", "_").replace("\\", "_")
    return _STORE_ROOT / safe_code / f"{interval}.parquet"


def load_from_store(
    code: str,
    interval: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame | None:
    """Load OHLCV data from Parquet store, sliced to [start_date, end_date].

    Returns ``None`` if the file does not exist or cannot be read.
    """
    path = _store_path(code, interval)
    if not path.exists():
        return None

    try:
        df = pd.read_parquet(path)
        if df is None or df.empty:
            return None
        # Ensure DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                df = df.set_index("trade_date")
            else:
                df.index = pd.to_datetime(df.index)
        df.index.name = "trade_date"
        df = df.sort_index()
        # Slice
        result = df.loc[start_date:end_date]
        return result if not result.empty else None
    except Exception:
        logger.debug("Failed to load Parquet store for %s/%s", code, interval, exc_info=True)
        return None


def update_store(code: str, interval: str, new_df: pd.DataFrame) -> int:
    """Merge *new_df* into the Parquet store, deduplicating by index.

    Returns the number of new bars written.
    """
    if new_df is None or new_df.empty:
        return 0

    # Normalise index
    df = new_df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("trade_date")
        else:
            df.index = pd.to_datetime(df.index)
    df.index.name = "trade_date"
    df = df.sort_index()

    # Keep only OHLCV columns
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    if not keep:
        return 0
    df = df[keep]

    path = _store_path(code, interval)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            existing = pd.read_parquet(path)
            # Merge — new data overwrites old on same dates
            combined = pd.concat([existing, df])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
        except Exception:
            combined = df
    else:
        combined = df

    try:
        combined.to_parquet(path, compression="snappy", index=True)
        new_bars = len(combined) - (len(pd.read_parquet(path)) if path.exists() else 0) + len(df)
        logger.debug("Parquet store updated: %s/%s → %d bars total", code, interval, len(combined))
        return max(0, len(df))
    except Exception as exc:
        logger.warning("Failed to write Parquet store for %s/%s: %s", code, interval, exc)
        return 0


def get_store_info(code: str, interval: str) -> dict:
    """Get metadata about stored data for a code+interval.

    Returns:
        {exists, path, bars, start_date, end_date, file_size_mb}.
    """
    path = _store_path(code, interval)
    if not path.exists():
        return {"exists": False, "path": str(path), "bars": 0}

    try:
        df = pd.read_parquet(path)
        return {
            "exists": True,
            "path": str(path),
            "bars": len(df),
            "start_date": str(df.index[0].date()) if len(df) > 0 else "",
            "end_date": str(df.index[-1].date()) if len(df) > 0 else "",
            "file_size_mb": round(path.stat().st_size / 1024 / 1024, 2),
        }
    except Exception as exc:
        return {"exists": True, "path": str(path), "bars": 0, "error": str(exc)}


def sync_to_store(code: str, interval: str, df: pd.DataFrame | None = None) -> int:
    """Ensure the Parquet store has the latest data.

    If *df* is provided, merges it.  Otherwise, checks last bar date and
    returns how many days behind the store is (negative = needs update).

    CLI: ``python -m backtest.loaders.store --sync 600519.SH --interval 1D``
    """
    if df is not None:
        return update_store(code, interval, df)

    path = _store_path(code, interval)
    if not path.exists():
        return -999  # no data at all

    existing = load_from_store(code, interval, "2000-01-01", "2099-12-31")
    if existing is None or existing.empty:
        return -999

    from datetime import date
    last_bar = existing.index[-1].date() if hasattr(existing.index[-1], "date") else existing.index[-1]
    days_behind = (date.today() - last_bar).days
    return -days_behind
