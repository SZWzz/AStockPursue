"""BacktestDriver – feeds historical bars through TradingEngine.on_bar().

Two modes:
  - **Fast mode (default)**: pre-computes target weights via ``generate()``
    + ``_align()``, then feeds bars with precomputed weights.  Backward-compatible
    with existing backtest results.
  - **Simulation mode**: feeds bars one-by-one through the full signal pipeline,
    matching live-trading behavior for validation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from backtest.engines.base import _align, _load_optimizer, _maybe_enrich_fundamentals
from backtest.metrics import by_exit_reason_stats, by_symbol_stats, calc_metrics

import logging

# TODO(P5): migrate to Go gRPC equivalents:
#   - engines → EngineService (not yet exposed)
#   - risk → RiskService (not yet exposed)
#   - brokers → BrokerService (not yet exposed)

logger = logging.getLogger(__name__)


class BacktestDriver:
    """Run a backtest by feeding historical bars through a TradingEngine."""

    def __init__(self):
        self.last_engine = None

    def run(
        self,
        config: dict,
        loader: Any,
        signal_engine: Any,
        run_dir: Path,
        market_engine: Any,
        bars_per_year: int = 252,
        *,
        simulation_mode: bool = False,
    ) -> dict:
        """Full backtest pipeline.

        Args:
            config: Backtest configuration dict.
            loader: DataLoader with ``fetch()`` method.
            signal_engine: SignalEngine instance with ``generate()`` method.
            run_dir: Artifacts output directory.
            market_engine: BaseEngine subclass for market rules + state.
            bars_per_year: Annualisation factor.
            simulation_mode: If True, use per-bar signal generation (matches live).

        Returns:
            Metrics dictionary.
        """
        # TODO(P6): migrate backtest execution to Go TradingEngine
        from src.trading.engine import TradingEngine
        from src.trading.signal_adapter import SignalAdapter

        codes = config.get("codes", [])
        interval = config.get("interval", "1D")
        extra_fields = config.get("extra_fields") or None

        # 1. Load data
        data_map = loader.fetch(
            codes,
            config.get("start_date", ""),
            config.get("end_date", ""),
            fields=extra_fields,
            interval=interval,
        )
        if not data_map:
            print(json.dumps({"error": "No data fetched"}))
            return {"error": "No data fetched"}
        data_map = _maybe_enrich_fundamentals(data_map, config)

        # 2. Build TradingEngine (no risk, no state machine for backtest compat)
        signal_adapter = SignalAdapter(engine=signal_engine)
        engine = TradingEngine(
            config=config,
            signal_adapter=signal_adapter,
            market_engine=market_engine,
            risk_pipeline=None,
            state_machine=None,
        )
        self.last_engine = engine  # for trade extraction after run()

        if simulation_mode:
            return self._run_simulation(engine, data_map, config, run_dir, bars_per_year)
        else:
            return self._run_fast(engine, signal_engine, data_map, config, run_dir, bars_per_year)

    # ── Fast mode ────────────────────────────────────────────────────

    def _run_fast(
        self,
        engine: Any,
        signal_engine: Any,
        data_map: dict,
        config: dict,
        run_dir: Path,
        bars_per_year: int,
    ) -> dict:
        """Pre-compute all weights, then feed bars through TradingEngine."""
        codes = config.get("codes", [])
        if not codes:
            codes = sorted(data_map.keys())

        # Generate signals progressively — strategy only sees data up to the
        # current bar.  This prevents look-ahead bias by construction: the
        # signal value at bar T is computed using only data[0..T].
        warmup_bars = config.get("warmup_bars", 0) or max(min(50, len(data_map) or 1), 1)

        all_dates_set: set = set()
        for df in data_map.values():
            all_dates_set.update(df.index)
        all_dates = pd.DatetimeIndex(sorted(all_dates_set))

        signal_map: dict[str, pd.Series] = {}
        for c in codes:
            if c in data_map:
                signal_map[c] = pd.Series(index=data_map[c].index, dtype=float)

        if len(all_dates) > 0:
            wb = min(warmup_bars, len(all_dates) - 1)
            for i in range(wb, len(all_dates)):
                ts = all_dates[i]
                truncated: dict[str, pd.DataFrame] = {}
                for c in codes:
                    if c in data_map and ts in data_map[c].index:
                        truncated[c] = data_map[c].loc[:ts]
                if not truncated:
                    continue
                sig = signal_engine.generate(truncated)
                for c in truncated:
                    s = sig.get(c)
                    if s is not None and len(s) > 0:
                        signal_map[c].loc[ts] = float(s.iloc[-1])

        valid_codes = sorted(c for c in signal_map if c in data_map)
        if not valid_codes:
            return {"error": "No valid signals generated"}

        # Pre-compute target weights (with optimizer)
        opt_fn = _load_optimizer(config)
        dates, close_df, target_pos, ret_df = _align(
            data_map, signal_map, valid_codes, optimizer=opt_fn,
        )
        valid_codes = [c for c in valid_codes if c in target_pos.columns]

        # Seed engine with historical data for initialization
        engine.initialize(data_map)

        # Bar-by-bar execution with precomputed weights.
        # TradingEngine.on_bar() handles market hooks internally.
        for i, ts in enumerate(dates):
            bar = {}
            weights = {}
            for c in valid_codes:
                if ts in data_map[c].index:
                    bar[c] = data_map[c].loc[ts]
                try:
                    w = float(target_pos.at[ts, c]) if ts in target_pos.index else 0.0
                    if abs(w) > 1e-9:
                        weights[c] = w
                except Exception:
                    pass

            # Session filter: skip bars outside trading hours (China futures night session)
            if self._should_filter_session(config):
                bar = self._filter_bar_by_session(bar, ts)

            if bar:
                engine.on_bar(bar, ts, precomputed_weights=weights)

            # Delisting detection: if this is the LAST bar for a code with an
            # open position, force-close it now.  (Codes whose data ends before
            # the global end_date are treated as delisted.)
            for c in list(engine.positions.keys()):
                df = data_map.get(c)
                if df is not None and len(df) > 0:
                    last_ts = df.index[-1]
                    if ts >= last_ts:
                        # [P1-05 fix] Check if position still exists — it may
                        # have been closed during on_bar() by a stop-loss or
                        # take-profit on this same bar.
                        if c not in engine.positions:
                            logger.debug(
                                "Delisting close skipped for %s: position already "
                                "exited during bar processing at %s", c, ts,
                            )
                            continue
                        trade = engine.force_close_symbol(c, "delisted")
                        if trade:
                            logger.info("Delisting close: %s at %s (last bar)", c, ts)

        # Force-close remaining positions at end
        if len(dates) > 0:
            engine.force_close_all("end_of_backtest")

        # Build equity series from market engine's snapshots
        equity_series = self._build_equity_series(engine, dates)
        bench_ret = ret_df.mean(axis=1) if ret_df.shape[1] > 0 else pd.Series(0.0, index=dates)

        # External benchmark
        benchmark_metadata: dict = {}
        bench_ticker = config.get("benchmark")
        if bench_ticker:
            from backtest.benchmark import resolve_benchmark
            # "auto" → let resolve_benchmark pick based on market
            explicit = bench_ticker if bench_ticker != "auto" else None
            bench_result = resolve_benchmark(
                strategy_codes=codes,
                source=config.get("source", "yfinance"),
                start_date=config.get("start_date", ""),
                end_date=config.get("end_date", ""),
                interval=config.get("interval", "1D"),
                explicit=explicit,
            )
            if bench_result is not None:
                bench_ret = bench_result.ret_series.reindex(dates).fillna(0.0)
                benchmark_metadata = {
                    "benchmark_ticker": bench_result.ticker,
                    "benchmark_return": bench_result.total_ret,
                }

        bench_equity = engine.initial_capital * (1 + bench_ret).cumprod()

        # Metrics
        m = calc_metrics(equity_series, engine.trades, engine.initial_capital, bars_per_year, bench_ret)
        m.update(benchmark_metadata)
        m["by_symbol"] = by_symbol_stats(engine.trades)
        m["by_exit_reason"] = by_exit_reason_stats(engine.trades)

        # Validation
        if config.get("validation"):
            from backtest.validation import run_validation
            v_results = run_validation(
                config, equity_series, engine.trades, engine.initial_capital, bars_per_year,
            )
            m["validation"] = v_results
            v_path = run_dir / "artifacts" / "validation.json"
            v_path.parent.mkdir(parents=True, exist_ok=True)
            v_path.write_text(json.dumps(v_results, indent=2, ensure_ascii=False), encoding="utf-8")

        # Artifacts
        self._write_artifacts(
            run_dir, data_map, dates, equity_series, bench_equity, bench_ret,
            target_pos, m, valid_codes, engine,
        )

        # Run card
        from backtest.run_card import write_run_card
        write_run_card(
            run_dir,
            config,
            m,
            data_sources=self._run_card_data_sources(config, None),
            strategy_path=run_dir / "code" / "signal_engine.py",
            warnings=config.get("_warnings"),
        )

        # Persist to PG for history/compare
        self._persist_to_db(config, m, equity_series, engine, run_dir, data_map)

        print(json.dumps({k: v for k, v in m.items() if not isinstance(v, dict)}, indent=2))
        return m

    # ── Simulation mode ──────────────────────────────────────────────

    def _run_simulation(
        self,
        engine: Any,
        data_map: dict,
        config: dict,
        run_dir: Path,
        bars_per_year: int,
    ) -> dict:
        """Feed bars one-by-one through the full signal pipeline (matches live)."""
        valid_codes = sorted(c for c in data_map)
        if not valid_codes:
            return {"error": "No data fetched"}

        # Build unified date index
        all_dates = set()
        for c in valid_codes:
            all_dates.update(data_map[c].index)
        dates = pd.DatetimeIndex(sorted(all_dates))

        # Build close DataFrame for metrics
        close_df = pd.DataFrame(index=dates, columns=valid_codes, dtype=float)
        for c in valid_codes:
            close_df[c] = data_map[c]["close"].reindex(dates)
        close_df = close_df.ffill(limit=10)
        ret_df = close_df.pct_change().fillna(0.0)

        # Seed engine with initial lookback (configurable, default 20% of data)
        warmup_bars = config.get("simulation_warmup_bars", 0) or max(min(50, len(dates) // 5), 1)
        split_idx = max(min(warmup_bars, len(dates) - 1), 1)
        warmup_dates = dates[:split_idx]
        warmup_data = {
            c: data_map[c].loc[:warmup_dates[-1]]
            for c in valid_codes
            if warmup_dates[-1] in data_map[c].index
        }
        engine.initialize(warmup_data)

        # Feed remaining bars through full pipeline
        for ts in dates[split_idx:]:
            bar = {}
            for c in valid_codes:
                if ts in data_map[c].index:
                    bar[c] = data_map[c].loc[ts]

            # Session filter: skip bars outside trading hours
            if self._should_filter_session(config):
                bar = self._filter_bar_by_session(bar, ts)

            if bar:
                engine.on_bar(bar, ts)  # full pipeline: signal → execute

            # Delisting detection for simulation mode
            # [P1-05 fix] Check position still exists before force-closing
            for c in list(engine.positions.keys()):
                df = data_map.get(c)
                if df is not None and len(df) > 0:
                    last_ts = df.index[-1]
                    if ts >= last_ts:
                        if c not in engine.positions:
                            logger.debug(
                                "Delisting close skipped for %s: already exited at %s",
                                c, ts,
                            )
                            continue
                        engine.force_close_symbol(c, "delisted")

        engine.force_close_all("end_of_backtest")

        # Build equity series
        equity_series = self._build_equity_series(engine, dates)
        bench_ret = ret_df.mean(axis=1)

        # Metrics
        m = calc_metrics(equity_series, engine.trades, engine.initial_capital, bars_per_year, bench_ret)
        m["by_symbol"] = by_symbol_stats(engine.trades)
        m["by_exit_reason"] = by_exit_reason_stats(engine.trades)

        # Artifacts
        target_pos = pd.DataFrame(0.0, index=dates, columns=valid_codes)
        bench_equity = engine.initial_capital * (1 + bench_ret).cumprod()
        self._write_artifacts(
            run_dir, data_map, dates, equity_series, bench_equity, bench_ret,
            target_pos, m, valid_codes, engine,
        )

        # Persist to PG for history/compare
        self._persist_to_db(config, m, equity_series, engine, run_dir, data_map)

        print(json.dumps({k: v for k, v in m.items() if not isinstance(v, dict)}, indent=2))
        return m

    # ── Helpers ──────────────────────────────────────────────────────

    def _persist_to_db(
        self,
        config: dict,
        metrics: dict,
        equity_series: pd.Series,
        engine: Any,
        run_dir: Path,
        data_map: dict,
    ) -> str | None:
        """Persist backtest result to PostgreSQL for history browsing.

        Non-fatal: if the DB is unavailable the backtest still completes.
        Returns the run UUID on success, None on failure.
        """
        try:
            from src.db.backtest_store import save_backtest_result

            # ── Build equity_curve for DB ──────────────────────────────
            peak = equity_series.cummax()
            dd = (equity_series - peak) / peak.replace(0, 1)
            equity_curve = []
            for ts, eq_val in equity_series.items():
                equity_curve.append({
                    "time": str(ts),
                    "equity": round(float(eq_val), 4),
                    "drawdown": round(float(dd.get(ts, 0)), 6),
                })

            # ── Build trades for DB ───────────────────────────────────
            trades = []
            for t in engine.trades:
                if getattr(t, "exit_time", None) is None:
                    continue
                try:
                    direction = getattr(t, "direction", 1)
                    side = "long" if direction == 1 else "short"
                    trades.append({
                        "symbol": str(getattr(t, "symbol", "")),
                        "entry_time": str(getattr(t, "entry_time", "")),
                        "exit_time": str(getattr(t, "exit_time", "")),
                        "entry_price": round(float(getattr(t, "entry_price", 0)), 4),
                        "exit_price": round(float(getattr(t, "exit_price", 0)), 4),
                        "size": round(float(getattr(t, "size", 0)), 6),
                        "side": side,
                        "pnl": round(float(getattr(t, "pnl", 0)), 4),
                        "return_pct": round(float(getattr(t, "pnl_pct", 0)), 6),
                        "exit_reason": str(getattr(t, "exit_reason", "")),
                    })
                except Exception:
                    continue

            # ── Build OHLCV bars for K-line chart ──────────────────────
            ohlcv_bars: list[dict] = []
            for code, df in data_map.items():
                if not isinstance(df, pd.DataFrame):
                    continue
                for idx, row in df.iterrows():
                    try:
                        ohlcv_bars.append({
                            "code": str(code),
                            "bar_time": str(idx),
                            "open": float(row.get("open", 0)),
                            "high": float(row.get("high", 0)),
                            "low": float(row.get("low", 0)),
                            "close": float(row.get("close", 0)),
                            "volume": float(row.get("volume", 0)),
                        })
                    except Exception:
                        continue

            # ── Build serialisable config ──────────────────────────────
            safe_config = {}
            for k, v in config.items():
                if callable(v) or str(type(v)).startswith("<class"):
                    continue
                if k.startswith("_"):    # internal flags
                    continue
                try:
                    import json as _json
                    _json.dumps(v)
                    safe_config[k] = v
                except (TypeError, ValueError):
                    safe_config[k] = str(v)

            # ── Determine run name ────────────────────────────────────
            run_name = config.get("run_name", "")
            if not run_name:
                run_name = run_dir.name

            # ── Determine persistence level ────────────────────────────
            # Internal keys (prefixed with _) are read from config but
            # excluded from safe_config above.
            persist_level = config.get("_db_persist", "full")
            if persist_level == "minimal":
                # Grid search / walk-forward intermediates: skip bulky data
                equity_curve = None
                trades = None

            # ── Build tags ────────────────────────────────────────────
            tags = self._auto_tags(config, metrics)

            run_id = save_backtest_result(
                run_name=run_name,
                run_type=config.get("run_type", config.get("engine", "strategy")),
                config=safe_config,
                metrics={k: v for k, v in metrics.items() if not callable(v)},
                equity_curve=equity_curve,
                trades=trades,
                ohlcv_bars=ohlcv_bars if persist_level == "full" else None,
                status="success",
                user_id=config.get("user_id", 1),
                tags=tags,
            )

            logger.info("Backtest persisted to PG: %s tags=%s", run_id, tags)
            return run_id

        except Exception as e:
            logger.warning("Failed to persist backtest to PG (non-fatal): %s", e)
            return None

    @staticmethod
    def _auto_tags(config: dict, metrics: dict) -> list[str]:
        """Generate descriptive tags from config and metrics."""
        tags = []

        # Market
        market = config.get("market", "")
        engine_type = config.get("engine", "")
        if market:
            tags.append(f"market:{market}")
        elif engine_type:
            tags.append(f"engine:{engine_type}")

        # Interval
        interval = config.get("interval", "1D")
        tags.append(f"interval:{interval}")

        # Source / data origin
        source = config.get("source", "")
        if source and source != "auto":
            tags.append(f"source:{source}")

        # User-supplied tags (e.g. from grid search)
        user_tags = config.get("_db_tags")
        if isinstance(user_tags, list):
            tags.extend([str(t) for t in user_tags])

        # Strategy class
        strategy_cls = config.get("strategy_class", "")
        if strategy_cls:
            tags.append(f"strategy:{strategy_cls}")

        # Performance tier
        sharpe = metrics.get("sharpe_ratio", 0) or metrics.get("sharpe", 0)
        try:
            sharpe = float(sharpe)
            if sharpe >= 2.0:
                tags.append("perf:excellent")
            elif sharpe >= 1.0:
                tags.append("perf:good")
            elif sharpe >= 0:
                tags.append("perf:positive")
            else:
                tags.append("perf:negative")
        except (TypeError, ValueError):
            pass

        # Default if empty
        if not tags:
            tags.append("source:backtest_driver")

        return tags

    @staticmethod
    def _should_filter_session(config: dict) -> bool:
        """Return True if this backtest should filter bars by trading session."""
        interval = config.get("interval", "1D")
        if interval in ("1D", "1W", "4W"):
            return False  # daily+ bars span the full session
        source = config.get("source", "")
        engine = config.get("engine", "daily")
        return "futures" in str(engine).lower()

    @staticmethod
    def _filter_bar_by_session(bar: dict, ts: pd.Timestamp) -> dict:
        """Remove codes whose trading session does not include this timestamp."""
        try:
            from backtest.engines.china_futures import bar_in_trading_session

        except ImportError:
            return bar
        return {c: s for c, s in bar.items() if bar_in_trading_session(c, ts)}

    @staticmethod
    def _build_equity_series(engine: Any, dates: pd.DatetimeIndex) -> pd.Series:
        """Build equity curve from market engine's equity_snapshots."""
        snapshots = engine.equity_snapshots
        if not snapshots:
            return pd.Series(engine.initial_capital, index=dates[:1] if len(dates) > 0 else dates)

        equity_data = {s.timestamp: s.equity for s in snapshots}
        s = pd.Series(equity_data, name="equity")
        s = s.reindex(dates).ffill().fillna(engine.initial_capital)
        return s

    @staticmethod
    def _run_card_data_sources(config: dict, loader: Any) -> list[str]:
        configured = config.get("_run_card_effective_sources")
        if isinstance(configured, list):
            return [str(s) for s in configured if str(s).strip()]
        if isinstance(configured, str) and configured.strip():
            return [configured.strip()]
        loader_name = getattr(loader, "name", None)
        if loader_name:
            return [str(loader_name)]
        source = config.get("source")
        return [str(source)] if source else []

    def _write_artifacts(
        self,
        run_dir: Path,
        data_map: dict,
        dates: pd.DatetimeIndex,
        equity_series: pd.Series,
        bench_equity: pd.Series,
        bench_ret: pd.Series,
        target_pos: pd.DataFrame,
        metrics: dict,
        codes: list,
        engine: Any,
    ) -> None:
        """Write CSV artifacts compatible with existing format."""
        out = run_dir / "artifacts"
        out.mkdir(parents=True, exist_ok=True)

        for code, df in data_map.items():
            df.to_csv(out / f"ohlcv_{code}.csv")

        port_ret = equity_series.pct_change().fillna(0.0)
        peak = equity_series.cummax()
        dd = (equity_series - peak) / peak.replace(0, 1)
        eq_df = pd.DataFrame({
            "ret": port_ret,
            "equity": equity_series,
            "drawdown": dd,
            "benchmark_equity": bench_equity.reindex(dates),
            "active_ret": port_ret - bench_ret.reindex(dates).fillna(0.0),
        }, index=dates)
        eq_df.index.name = "timestamp"
        eq_df.to_csv(out / "equity.csv")

        target_pos.index.name = "timestamp"
        target_pos.to_csv(out / "positions.csv")

        trade_rows = []
        for t in engine.trades:
            trade_rows.append({
                "timestamp": str(t.entry_time.date()) if hasattr(t.entry_time, "date") else str(t.entry_time),
                "code": t.symbol,
                "side": "buy" if t.direction == 1 else "sell",
                "price": round(t.entry_price, 4),
                "qty": round(t.size, 6),
                "reason": "signal",
                "pnl": 0.0,
                "holding_days": 0,
                "return_pct": 0.0,
            })
            try:
                hold_days = (t.exit_time - t.entry_time).days
            except Exception:
                hold_days = 0
            trade_rows.append({
                "timestamp": str(t.exit_time.date()) if hasattr(t.exit_time, "date") else str(t.exit_time),
                "code": t.symbol,
                "side": "sell" if t.direction == 1 else "buy",
                "price": round(t.exit_price, 4),
                "qty": round(t.size, 6),
                "reason": t.exit_reason,
                "pnl": round(t.pnl, 4),
                "holding_days": hold_days,
                "return_pct": round(t.pnl_pct, 2),
            })

        trade_cols = ["timestamp", "code", "side", "price", "qty", "reason", "pnl", "holding_days", "return_pct"]
        pd.DataFrame(trade_rows or [], columns=trade_cols).to_csv(out / "trades.csv", index=False)

        flat_metrics = {k: v for k, v in metrics.items() if not isinstance(v, dict)}
        pd.DataFrame([flat_metrics]).to_csv(out / "metrics.csv", index=False)
