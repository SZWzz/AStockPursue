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

logger = logging.getLogger(__name__)


class BacktestDriver:
    """Run a backtest by feeding historical bars through a TradingEngine."""

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
            sys.exit(1)
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
            print(json.dumps({"error": "No valid signals generated"}))
            sys.exit(1)

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

            if bar:
                engine.on_bar(bar, ts, precomputed_weights=weights)

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
            print(json.dumps({"error": "No data fetched"}))
            sys.exit(1)

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

            if bar:
                engine.on_bar(bar, ts)  # full pipeline: signal → execute

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

        print(json.dumps({k: v for k, v in m.items() if not isinstance(v, dict)}, indent=2))
        return m

    # ── Helpers ──────────────────────────────────────────────────────

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
