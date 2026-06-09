"""Unified DataStore — one API for Redis → cache → Parquet → API fallback.

The DataStore is the single entry point for all OHLCV data requests.
It automatically walks the data hierarchy::

    0. Redis cache (L0, <1ms, in-memory)
    1. PG cache (L1, hot, per-bar SQL rows)
    2. Parquet store (L2, cold, per-code/per-interval files)
    3. API loaders (L3, external, via registry fallback chain)

All successful API fetches are automatically written back to Redis,
PG cache and Parquet store for future reuse.

Usage::

    from backtest.data_store import DataStore

    store = DataStore()
    df = store.get_ohlcv("600519.SH", "2024-01-01", "2025-12-31", interval="1D")
"""

from __future__ import annotations

import logging
import threading
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
        force_refresh: bool = False,
        cache_max_age_hours: int = 24,
    ) -> pd.DataFrame | None:
        """Fetch OHLCV data, walking Redis → cache → store → API.

        Args:
            code: Stock symbol (e.g. ``AAPL.US``, ``600519.SH``).
            start_date: Start date string ``YYYY-MM-DD``.
            end_date: End date string ``YYYY-MM-DD``.
            interval: Bar interval (``1D``, ``1H``, etc.).
            source: Loader name or ``"auto"`` for fallback chain.
            force_refresh: If True, bypass cache and store, go straight to API.
            cache_max_age_hours: Max age of cached data before re-fetching.
                Data older than this threshold triggers a background refresh.

        Returns:
            DataFrame or ``None`` if all sources fail.
        """
        # 0. Redis L0 cache (skip if force_refresh)
        if not force_refresh:
            df = self._try_redis(code, interval, start_date, end_date, source)
            if df is not None:
                self._stats["cache_hits"] += 1
                return df

            # 1. PG cache
            df = self._try_cache(code, interval, start_date, end_date, cache_max_age_hours)
            if df is not None:
                self._stats["cache_hits"] += 1
                self._write_redis(code, interval, start_date, end_date, source, df)
                return df

            # 2. Parquet store
            df = self._try_store(code, interval, start_date, end_date)
            if df is not None:
                self._stats["store_hits"] += 1
                self._write_cache(code, interval, df)
                self._write_redis(code, interval, start_date, end_date, source, df)
                return df

        # 3. API loaders
        df = self._try_api(code, start_date, end_date, interval, source)
        if df is not None:
            self._stats["api_fetches"] += 1
            self._write_redis(code, interval, start_date, end_date, source, df)
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
        force_refresh: bool = False,
        cache_max_age_hours: int = 24,
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV for multiple codes (concurrent where possible).

        Args:
            force_refresh: If True, skip cache for ALL codes and re-fetch.
            cache_max_age_hours: Max age of cached data before re-fetching.

        Returns ``{code: DataFrame}`` — codes that fail are simply omitted.
        """
        result: dict[str, pd.DataFrame] = {}
        uncached: list[str] = []

        if force_refresh:
            uncached = list(codes)
        else:
            for code in codes:
                # 0. Redis L0
                df = self._try_redis(code, interval, start_date, end_date, source)
                if df is None:
                    df = self._try_cache(code, interval, start_date, end_date, cache_max_age_hours)
                if df is None:
                    df = self._try_store(code, interval, start_date, end_date)
                    if df is not None:
                        self._stats["store_hits"] += 1
                        self._write_cache(code, interval, df)
                        self._write_redis(code, interval, start_date, end_date, source, df)
                if df is not None:
                    self._stats["cache_hits"] += 1
                    result[code] = df
                    if code not in result:
                        self._write_redis(code, interval, start_date, end_date, source, df)
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

    # ── Redis L0 helpers ────────────────────────────────────────────────────

    @staticmethod
    def _run_async(coro):
        """Run an async coroutine safely in either sync or async context.

        Uses ``asyncio.get_running_loop()`` (Python 3.10+) to detect the
        current context.  In a running event loop (FastAPI), dispatches
        via ``run_coroutine_threadsafe``.  In a sync context (tests, CLI,
        notebooks), uses ``asyncio.run()``.

        Args:
            coro: Coroutine object to execute.

        Returns:
            The coroutine's return value, or ``None`` on any error.
        """
        import asyncio
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
            # Async context: dispatch to the running loop from a sync thread
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=5)
        except RuntimeError:
            # No running loop: we're in a sync context, safe to use asyncio.run()
            try:
                return asyncio.run(coro)
            except (ValueError, TypeError, RuntimeError):
                return None
        except (concurrent.futures.TimeoutError, RuntimeError, ValueError):
            return None

    @staticmethod
    def _run_async_fire_and_forget(coro):
        """Like :meth:`_run_async` but returns immediately without waiting.

        Used for write operations (caching) where the result is not needed.
        """
        import asyncio
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError:
            try:
                asyncio.run(coro)
            except (ValueError, TypeError, RuntimeError):
                pass
        except (RuntimeError, ValueError):
            pass

    def _try_redis(
        self, code: str, interval: str, start: str, end: str, source: str,
    ) -> pd.DataFrame | None:
        """Attempt to load OHLCV data from Redis L0 cache.

        Uses the market derived from *source* as part of the cache key.
        Gracefully degrades — any failure returns None so the caller
        falls through to the next tier.
        """
        try:
            from backtest.engines._market_hooks import _detect_market
            market = _detect_market(code) if source == "auto" else source
        except (ImportError, ModuleNotFoundError):
            market = source

        try:
            from src.cache.data_cache import cached_bars
            return self._run_async(cached_bars(market, code, interval, start, end))
        except (RuntimeError, ValueError, TypeError):
            return None

    def _write_redis(
        self, code: str, interval: str, start: str, end: str,
        source: str, df: pd.DataFrame,
    ) -> None:
        """Write fetched OHLCV data back to Redis L0 cache.

        Called automatically after every successful fetch.  Failures are
        silently ignored so Redis unavailability never blocks the pipeline.
        """
        try:
            from backtest.engines._market_hooks import _detect_market
            market = _detect_market(code) if source == "auto" else source
        except (ImportError, ModuleNotFoundError):
            market = source

        try:
            from src.cache.data_cache import cache_bars
            df_copy = df.copy()
            self._run_async_fire_and_forget(
                cache_bars(market, code, interval, start, end, df_copy),
            )
        except (RuntimeError, ValueError, TypeError):
            pass

    # ── Stats ──────────────────────────────────────────────────────────────

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def reset_stats(self) -> None:
        self._stats = {"cache_hits": 0, "store_hits": 0, "api_fetches": 0}

    # ── Internal ───────────────────────────────────────────────────────────

    def _try_cache(
        self, code: str, interval: str, start: str, end: str,
        max_age_hours: int = 24,
    ) -> pd.DataFrame | None:
        """Attempt to load OHLCV data from the PostgreSQL cache layer.

        Queries the per-bar SQL cache table for the given code, interval,
        and date range.  If the latest cached bar is older than
        *max_age_hours* and the requested *end* date falls within that
        freshness window, the cache is bypassed so the caller can fetch
        fresher data from the API.

        Args:
            code: Stock symbol (e.g. ``600519.SH``).
            interval: Bar interval (``1D``, ``1H``, etc.).
            start: Start date string ``YYYY-MM-DD``.
            end: End date string ``YYYY-MM-DD``.
            max_age_hours: Maximum age of cached data before bypassing.

        Returns:
            DataFrame if cache hit and fresh enough, ``None`` otherwise.
            Once any query fails the cache layer is permanently disabled
            for this DataStore instance.
        """
        if self._cache_ok is False:
            return None
        try:
            from backtest.loaders.cache import query_cache
            df = query_cache(code, interval, start, end)
            if df is not None and len(df) >= 5:
                # Check cache freshness: if the latest bar is older than max_age_hours
                # from now AND the end_date includes today/recent, skip cache
                if max_age_hours > 0:
                    latest_bar = df.index.max()
                    now = pd.Timestamp.now()
                    age_hours = (now - latest_bar).total_seconds() / 3600
                    end_dt = pd.Timestamp(end)
                    # If user is requesting data up to today/recent and cache is stale
                    if end_dt >= now - pd.Timedelta(hours=max_age_hours) and age_hours > max_age_hours:
                        logger.debug(
                            "Cache for %s is stale (latest bar: %s, age: %.1fh > %dh), bypassing",
                            code, latest_bar, age_hours, max_age_hours,
                        )
                        return None  # Bypass stale cache
                return df
        except Exception:
            self._cache_ok = False
        self._cache_ok = True
        return None

    def _try_store(self, code: str, interval: str, start: str, end: str) -> pd.DataFrame | None:
        """Attempt to load OHLCV data from the Parquet file store.

        Loads per-code, per-interval Parquet files and filters to the
        requested date range.

        Args:
            code: Stock symbol.
            interval: Bar interval.
            start: Start date string.
            end: End date string.

        Returns:
            DataFrame if found with at least 5 rows, ``None`` otherwise.
            Once any query fails the store layer is permanently disabled.
        """
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
        """Fetch OHLCV data from external API loaders via the fallback chain.

        Looks up the loader registry and tries each loader in the fallback
        chain for the detected market.  If *source* is ``"auto"``, the
        market is auto-detected from the stock code and its full fallback
        chain is tried.  Otherwise only the named loader is tried.

        Args:
            code: Stock symbol.
            start: Start date string.
            end: End date string.
            interval: Bar interval.
            source: Loader name or ``"auto"`` for market fallback chain.

        Returns:
            DataFrame if any loader succeeds, ``None`` if all fail.
        """
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
        """Fetch OHLCV data for multiple codes via API loaders.

        Groups codes by market and tries each market's fallback chain,
        using concurrent fetching where the loader supports it.

        Args:
            codes: List of stock symbols.
            start: Start date string.
            end: End date string.
            interval: Bar interval.
            source: Loader name or ``"auto"``.

        Returns:
            ``{code: DataFrame}`` for every successfully fetched code.
            Failed codes are simply omitted from the result dict.
        """
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
        """Write fetched OHLCV data back to the PostgreSQL cache layer.

        Called automatically after every successful API fetch so
        subsequent requests hit the hot cache.

        Args:
            code: Stock symbol.
            interval: Bar interval.
            df: DataFrame to persist.  Failures are silently ignored.
        """
        try:
            from backtest.loaders.cache import write_cache
            write_cache(code, interval, df)
        except Exception:
            pass

    def _write_store(self, code: str, interval: str, df: pd.DataFrame) -> None:
        """Write fetched OHLCV data back to the Parquet file store.

        Called automatically after every successful API fetch so
        subsequent requests (including from other processes) hit the
        cold store.

        Args:
            code: Stock symbol.
            interval: Bar interval.
            df: DataFrame to persist.  Failures are silently ignored.
        """
        try:
            from backtest.loaders.store import update_store
            update_store(code, interval, df)
        except Exception:
            pass


# ── Global singleton ──────────────────────────────────────────────────────────

_data_store: DataStore | None = None
_data_store_lock = threading.Lock()


def get_data_store() -> DataStore:
    """Get or create the global DataStore singleton."""
    global _data_store
    if _data_store is None:
        with _data_store_lock:
            if _data_store is None:
                _data_store = DataStore()
    return _data_store
