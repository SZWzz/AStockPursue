"""Bridge between Indicator Lab and the backtest engine.

Converts QD-style indicator output (df['buy']/df['sell']) into a SignalEngine
compatible with the backtest engine, fetches real market data, and orchestrates
the full backtest pipeline.
"""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LabSignalEngine:
    """SignalEngine adapter: converts df['buy']/df['sell'] to weight series.

    The backtest engine expects ``generate(data_map) -> dict[str, pd.Series]``
    with values in [-1, 1] representing portfolio weights.
    """

    def __init__(self, weight_series: dict[str, pd.Series]):
        self._weights = weight_series

    def generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
        result: dict[str, pd.Series] = {}
        for code, df in data_map.items():
            if code in self._weights:
                s = self._weights[code].reindex(df.index).fillna(0.0).clip(-1.0, 1.0)
            else:
                s = pd.Series(0.0, index=df.index, dtype="float64")
            result[code] = s
        return result


def extract_weight_series(
    df: pd.DataFrame, symbol: str
) -> dict[str, pd.Series]:
    """Convert df['buy']/df['sell'] boolean columns to a weight series.

    buy=True  → +1.0 (full long)
    sell=True → -1.0 (full short)
    both=True →  0.0 (conflict → flat)
    neither   →  0.0 (flat)

    Returns dict mapping symbol to weight Series.
    """
    s = pd.Series(0.0, index=df.index, dtype="float64")

    has_buy = "buy" in df.columns
    has_sell = "sell" in df.columns

    if has_buy:
        s[df["buy"].fillna(False).astype(bool)] = 1.0
    if has_sell:
        s[df["sell"].fillna(False).astype(bool)] = -1.0

    # Resolve conflicts (both buy and sell on same bar → flat)
    if has_buy and has_sell:
        conflict = (
            df["buy"].fillna(False).astype(bool)
            & df["sell"].fillna(False).astype(bool)
        )
        s[conflict] = 0.0

    return {symbol: s}


def fetch_ohlcv(
    symbol: str,
    start_date: str,
    end_date: str,
    source: str = "auto",
    interval: str = "1D",
) -> dict[str, pd.DataFrame]:
    """Fetch real OHLCV data for a symbol using available data loaders.

    Args:
        symbol: e.g. "BTC/USDT", "AAPL", "600519.SH"
        start_date: ISO date string.
        end_date: ISO date string.
        source: "auto", "mootdx", "eastmoney", "tencent", "baidu", "tushare", "yfinance", "okx", "akshare", "ccxt", "twelvedata", "finnhub", "futu", "coingecko", "global_indices", "commodities".
        interval: "1D", "1H", "4H" etc.

    Returns:
        dict mapping symbol → DataFrame with OHLCV columns.

    Raises:
        RuntimeError: No loader available or fetch failed.
    """
    import time

    from backtest.loaders.registry import (
        LOADER_REGISTRY, FALLBACK_CHAINS, _ensure_registered,
    )
    from backtest.loaders.base import NoAvailableSourceError
    from backtest.engines._market_hooks import _detect_market

    _ensure_registered()

    # ── 1. Try PostgreSQL cache first (unless disabled) ──────────────────
    try:
        from backtest.loaders.cache import query_cache, write_cache
        _cache_available = True
    except Exception:
        logger.debug("PG cache module not available", exc_info=True)
        _cache_available = False

    if _cache_available:
        cached = query_cache(symbol, interval, start_date, end_date)
        if cached is not None and len(cached) >= 5:
            logger.debug("OHLCV cache hit for %s/%s (%d bars)", symbol, interval, len(cached))
            from backtest.loaders.base import FetchResult
            return FetchResult({symbol: cached}, meta={"source": "pg_cache", "fetch_time": time.time(), "data_start": str(cached.index[0].date()) if len(cached) else "", "data_end": str(cached.index[-1].date()) if len(cached) else "", "n_bars": len(cached)})

    # ── 2. Walk the fallback chain ──────────────────────────────────────
    if source == "auto":
        market = _detect_market(symbol)
        loader_names = FALLBACK_CHAINS.get(market, [])
    else:
        loader_names = [source]

    last_error: Exception | None = None
    tried: list[str] = []
    max_retries = 3

    for name in loader_names:
        cls = LOADER_REGISTRY.get(name)
        if cls is None:
            continue
        try:
            loader = cls()
            if hasattr(loader, "is_available") and not loader.is_available():
                tried.append(f"{name} (not available)")
                continue

            for attempt in range(max_retries):
                try:
                    t0 = time.time()
                    data = loader.fetch(
                        codes=[symbol],
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                    )
                    latency = time.time() - t0
                    if data and symbol in data and len(data[symbol]) >= 5:
                        # Record health
                        try:
                            from backtest.loaders.health import get_health_tracker
                            get_health_tracker().record_success(name, latency)
                        except Exception:
                            logger.debug("Failed to record loader health success", exc_info=True)
                        # Write back to cache
                        if _cache_available:
                            try:
                                n = write_cache(symbol, interval, data[symbol])
                                logger.debug("Cached %d bars for %s/%s", n, symbol, interval)
                            except Exception:
                                logger.debug("Failed to write OHLCV cache for %s", symbol, exc_info=True)
                        # Wrap with provenance metadata
                        df = data[symbol]
                        from backtest.loaders.base import FetchResult
                        return FetchResult({symbol: df}, meta={
                            "source": name,
                            "fetch_time": time.time(),
                            "fetch_latency_s": round(latency, 3),
                            "data_start": str(df.index[0].date()) if len(df) else "",
                            "data_end": str(df.index[-1].date()) if len(df) else "",
                            "n_bars": len(df),
                        })
                    tried.append(f"{name} (fetched {len(data.get(symbol, [])) if data else 0} rows)")
                    break  # empty data, don't retry
                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = (attempt + 1) * 2
                        logger.debug(f"{name} attempt {attempt+1} failed, retry in {delay}s: {e}")
                        time.sleep(delay)
                    else:
                        raise
        except NoAvailableSourceError:
            tried.append(f"{name} (no source available)")
            continue
        except Exception as e:
            last_error = e
            tried.append(f"{name} ({e})")
            logger.warning(f"Loader {name} failed for {symbol}: {e}")
            try:
                from backtest.loaders.health import get_health_tracker
                get_health_tracker().record_failure(name)
            except Exception:
                logger.debug("Failed to record loader health failure", exc_info=True)
            continue

    # When specific source fails, try auto fallback chain
    if source != "auto":
        market = _detect_market(symbol)
        fallback_names = FALLBACK_CHAINS.get(market, [])
        for name in fallback_names:
            if name in tried:
                continue
            cls = LOADER_REGISTRY.get(name)
            if cls is None:
                continue
            try:
                loader = cls()
                if hasattr(loader, "is_available") and not loader.is_available():
                    continue
                data = loader.fetch(
                    codes=[symbol],
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                )
                if data and symbol in data and len(data[symbol]) >= 30:
                    # Write back to cache
                    if _cache_available:
                        try:
                            write_cache(symbol, interval, data[symbol])
                        except Exception:
                            logger.debug("Failed to write fallback cache for %s", symbol, exc_info=True)
                    return data
            except Exception:
                logger.debug("Fallback loader %s failed for %s", name, symbol, exc_info=True)
                continue

    tried_str = "; ".join(tried) if tried else "none"
    tip = "Set TUSHARE_TOKEN in .env for stable A-share data, or try source=auto."
    if last_error:
        raise RuntimeError(
            f"Cannot fetch {symbol}: tried [{tried_str}]. Last error: {last_error}. {tip}"
        )
    raise RuntimeError(f"Cannot fetch {symbol}: tried [{tried_str}]. {tip}")


def run_indicator_backtest(
    code: str,
    symbol: str,
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    source: str = "auto",
    interval: str = "1D",
    initial_cash: float = 100_000.0,
    leverage: float = 1.0,
    benchmark: str | None = "auto",
) -> dict[str, Any]:
    """Run a full backtest of indicator code against real market data.

    Returns:
        dict with keys: success, error, run_id.
        Run artifacts are written to runs/{run_id}/ for RunDetail page rendering.
    """
    from src.security.sandbox import build_safe_builtins, safe_exec_with_validation

    # 1. Fetch real data
    try:
        data_map = fetch_ohlcv(symbol, start_date, end_date, source, interval)
    except Exception as e:
        return {"success": False, "error": f"Data fetch failed: {e}"}

    df = data_map[symbol]

    # 2. Run indicator code against real data
    exec_env: dict[str, Any] = {
        "__builtins__": build_safe_builtins(),
        "df": df.copy(),
        "open": df["open"].astype("float64"),
        "high": df["high"].astype("float64"),
        "low": df["low"].astype("float64"),
        "close": df["close"].astype("float64"),
        "volume": df["volume"].astype("float64"),
        "np": np,
        "pd": pd,
        "params": {},
    }

    exec_result = safe_exec_with_validation(code=code, exec_globals=exec_env, timeout=60)
    if not exec_result.get("success"):
        return {"success": False, "error": f"Indicator execution failed: {exec_result.get('error')}"}

    result_df = exec_env.get("df", df)

    # 3. Convert buy/sell to weight series
    weight_series = extract_weight_series(result_df, symbol)

    # 4. Create official run_dir under backend/runs/
    import time as _time
    RUNS_DIR = Path(__file__).resolve().parents[2] / "runs"
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"{_time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    run_dir = RUNS_DIR / run_id
    (run_dir / "code").mkdir(parents=True, exist_ok=True)

    config = {
        "codes": [symbol],
        "start_date": start_date,
        "end_date": end_date,
        "source": source,
        "interval": interval,
        "initial_cash": initial_cash,
        "leverage": leverage,
        "engine": "daily",
        "benchmark": benchmark,
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))

    # Write state.json so RunDetail page can find it
    (run_dir / "state.json").write_text(json.dumps({"status": "success"}))

    # Write req.json for run card metadata
    (run_dir / "req.json").write_text(json.dumps({
        "prompt": f"Indicator Lab backtest: {symbol}",
        "source": source,
        "interval": interval,
    }))

    # 5. Create engine and run
    from backtest.runner import _AutoLoader, _create_market_engine

    loader = _AutoLoader(data_map)
    signal_engine = LabSignalEngine(weight_series)

    try:
        engine = _create_market_engine(source, config, [symbol])
        metrics = engine.run_backtest(
            config=config,
            loader=loader,
            signal_engine=signal_engine,
            run_dir=run_dir,
            bars_per_year=365,
        )
    except Exception as e:
        logger.exception("Backtest engine failed")
        (run_dir / "state.json").write_text(json.dumps({"status": "failed", "error": str(e)}))
        return {"success": False, "error": f"Backtest engine failed: {e}", "run_id": run_id}

    # 6. Persist metadata to PostgreSQL
    try:
        from src.db.backtest_store import save_backtest_result
        summary = {
            "total_return": float(metrics.get("total_return", 0)),
            "sharpe": float(metrics.get("sharpe_ratio", 0)),
            "max_drawdown": float(metrics.get("max_drawdown", 0)),
            "win_rate": float(metrics.get("win_rate", 0)),
            "trade_count": int(metrics.get("trade_count", 0)),
            "profit_factor": float(metrics.get("profit_factor", 0)),
        }
        save_backtest_result(
            run_name=f"ILab: {symbol}",
            run_type="indicator",
            config={"symbol": symbol, "source": source, "interval": interval},
            metrics=summary,
            status="success",
        )
    except Exception:
        logger.debug("Failed to persist backtest to PG", exc_info=True)

    return {"success": True, "error": None, "run_id": run_id}
