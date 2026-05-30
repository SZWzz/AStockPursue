"""Unified DataStore — one API for cache → Parquet → API fallback.

The DataStore is the single entry point for all OHLCV data requests.
It automatically walks the data hierarchy::

    1. PG cache (hot, per-bar SQL rows)
    2. Parquet store (cold, per-code/per-interval files)
    3. API loaders (external, via registry fallback chain)

All successful API fetches are automatically written back to both
PG cache and Parquet store for future reuse.

Usage::

    from backtest.data_store import DataStore

    store = DataStore()
    df = store.get_ohlcv("600519.SH", "2024-01-01", "2025-12-31", interval="1D")
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class DataStore:
    """Unified data access layer: cache → store → API, with write-back."""

    def __init__(self):
        self._cache_ok: bool | None = None
        self._store_ok: bool | None = None
        self._stats: dict[str, int] = {"cache_hits": 0, "store_hits": 0, "api_fetches": 0}

    # ── Public API ─────────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        code: str,
        start_date: str,
        end_date: str,
        interval: str = "1D",
        source: str = "auto",
    ) -> pd.DataFrame | None:
        """Fetch OHLCV data, walking cache → store → API.

        Returns a DataFrame with columns [open, high, low, close, volume]
        and a DatetimeIndex named ``trade_date``, or ``None`` if all sources fail.
        """
        # 1. PG cache
        df = self._try_cache(code, interval, start_date, end_date)
        if df is not None:
            self._stats["cache_hits"] += 1
            return df

        # 2. Parquet store
        df = self._try_store(code, interval, start_date, end_date)
        if df is not None:
            self._stats["store_hits"] += 1
            # Write back to PG cache
            self._write_cache(code, interval, df)
            return df

        # 3. API loaders
        df = self._try_api(code, start_date, end_date, interval, source)
        if df is not None:
            self._stats["api_fetches"] += 1
            # Write back to both
            self._write_cache(code, interval, df)
            self._write_store(code, interval, df)
        return df

    def get_multi_ohlcv(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        interval: str = "1D",
        source: str = "auto",
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV for multiple codes (concurrent where possible).

        Returns ``{code: DataFrame}`` — codes that fail are simply omitted.
        """
        result: dict[str, pd.DataFrame] = {}
        uncached: list[str] = []

        # Check cache/store first for each code
        for code in codes:
            df = self._try_cache(code, interval, start_date, end_date)
            if df is None:
                df = self._try_store(code, interval, start_date, end_date)
                if df is not None:
                    self._stats["store_hits"] += 1
                    self._write_cache(code, interval, df)
            if df is not None:
                self._stats["cache_hits"] += 1
                result[code] = df
            else:
                uncached.append(code)

        if not uncached:
            return result

        # Fetch remaining via API
        api_result = self._try_api_multi(uncached, start_date, end_date, interval, source)
        if api_result:
            self._stats["api_fetches"] += len(api_result)
            for code, df in api_result.items():
                result[code] = df
                self._write_cache(code, interval, df)
                self._write_store(code, interval, df)

        return result

    # ── Preload / warm-up ──────────────────────────────────────────────────

    def preload(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        interval: str = "1D",
        source: str = "auto",
    ) -> None:
        """Preload data for *codes* — useful before a backtest run.

        Fetches all missing data and populates cache + store.  Does not return
        anything — just ensures data is ready.
        """
        self.get_multi_ohlcv(codes, start_date, end_date, interval, source)

    # ── Stats ──────────────────────────────────────────────────────────────

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def reset_stats(self) -> None:
        self._stats = {"cache_hits": 0, "store_hits": 0, "api_fetches": 0}

    # ── Internal ───────────────────────────────────────────────────────────

    def _try_cache(self, code: str, interval: str, start: str, end: str) -> pd.DataFrame | None:
        if self._cache_ok is False:
            return None
        try:
            from backtest.loaders.cache import query_cache
            df = query_cache(code, interval, start, end)
            if df is not None and len(df) >= 5:
                return df
        except Exception:
            self._cache_ok = False
        self._cache_ok = True
        return None

    def _try_store(self, code: str, interval: str, start: str, end: str) -> pd.DataFrame | None:
        if self._store_ok is False:
            return None
        try:
            from backtest.loaders.store import load_from_store
            df = load_from_store(code, interval, start, end)
            if df is not None and len(df) >= 5:
                return df
        except Exception:
            self._store_ok = False
        self._store_ok = True
        return None

    def _try_api(
        self, code: str, start: str, end: str, interval: str, source: str,
    ) -> pd.DataFrame | None:
        try:
            from backtest.loaders.registry import (
                LOADER_REGISTRY, FALLBACK_CHAINS, _ensure_registered,
            )
            from backtest.engines._market_hooks import _detect_market

            _ensure_registered()

            if source == "auto":
                market = _detect_market(code)
                loader_names = FALLBACK_CHAINS.get(market, [])
            else:
                loader_names = [source]

            for name in loader_names:
                cls = LOADER_REGISTRY.get(name)
                if cls is None:
                    continue
                try:
                    loader = cls()
                    if hasattr(loader, "is_available") and not loader.is_available():
                        continue
                    data = loader.fetch([code], start, end, interval=interval)
                    if data and code in data and not data[code].empty:
                        return data[code]
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("DataStore API fetch failed for %s: %s", code, exc)
        return None

    def _try_api_multi(
        self, codes: list[str], start: str, end: str, interval: str, source: str,
    ) -> dict[str, pd.DataFrame]:
        try:
            from backtest.loaders.registry import (
                LOADER_REGISTRY, FALLBACK_CHAINS, _ensure_registered,
            )
            from backtest.loaders.base import fetch_concurrent
            from backtest.engines._market_hooks import _detect_market

            _ensure_registered()

            # Group by market
            groups: dict[str, list[str]] = {}
            for code in codes:
                if source == "auto":
                    market = _detect_market(code)
                else:
                    market = source
                groups.setdefault(market, []).append(code)

            result: dict[str, pd.DataFrame] = {}
            for market, group_codes in groups.items():
                chain = FALLBACK_CHAINS.get(market, [source])
                for name in chain:
                    cls = LOADER_REGISTRY.get(name)
                    if cls is None:
                        continue
                    try:
                        loader = cls()
                        if hasattr(loader, "is_available") and not loader.is_available():
                            continue
                        data = fetch_concurrent(loader, group_codes, start, end, interval=interval)
                        result.update(data)
                        if data:
                            break
                    except Exception:
                        continue

            return result
        except Exception as exc:
            logger.debug("DataStore multi-API fetch failed: %s", exc)
            return {}

    def _write_cache(self, code: str, interval: str, df: pd.DataFrame) -> None:
        try:
            from backtest.loaders.cache import write_cache
            write_cache(code, interval, df)
        except Exception:
            pass

    def _write_store(self, code: str, interval: str, df: pd.DataFrame) -> None:
        try:
            from backtest.loaders.store import update_store
            update_store(code, interval, df)
        except Exception:
            pass


# ── Global singleton ──────────────────────────────────────────────────────────

_data_store: DataStore | None = None


def get_data_store() -> DataStore:
    """Get or create the global DataStore singleton."""
    global _data_store
    if _data_store is None:
        _data_store = DataStore()
    return _data_store
