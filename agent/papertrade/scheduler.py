"""Paper trading scheduler – asyncio background tasks driving the engines.

Each active paper-trading run gets an asyncio Task that periodically:
  1. Fetches the latest bar(s) via the DataLoader registry
  2. Feeds new bars to the PaperTradingEngine
  3. Persists results to PostgreSQL
  4. Pushes SSE events into a per-run queue

On server restart all runs are marked 'stopped' (safe for a research platform).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from papertrade.engine import PaperTradingEngine
from papertrade.models import RiskConfig
from papertrade.repository import PaperTradeRepository

logger = logging.getLogger(__name__)

# ── Interval → poll seconds ──────────────────────────────────────────


def _interval_to_seconds(interval: str) -> float:
    """Convert a bar interval string to polling seconds."""
    interval = interval.lower().strip()
    if interval in ("1m", "1min"):
        return 60.0
    if interval in ("5m", "5min"):
        return 300.0
    if interval in ("15m", "15min"):
        return 900.0
    if interval in ("30m", "30min"):
        return 1800.0
    if interval in ("1h", "1hour", "60min"):
        return 3600.0
    if interval in ("4h", "4hour"):
        return 14400.0
    if interval in ("1d", "1day", "daily"):
        return 86400.0
    if interval in ("1w", "1week", "weekly"):
        return 604800.0
    # Default: parse as minutes
    try:
        return float(interval.replace("m", "").replace("min", "")) * 60.0
    except ValueError:
        return 3600.0  # safe default: 1 hour


# ── Scheduler ─────────────────────────────────────────────────────────


class PaperTradingScheduler:
    """In-process scheduler managing multiple paper-trading runs.

    Each run runs as an ``asyncio.Task`` inside the event loop.
    SSE events are pushed into per-run ``asyncio.Queue`` instances
    that the SSE route handler reads from.
    """

    def __init__(self) -> None:
        self._active: dict[str, PaperTradingEngine] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._repo = PaperTradeRepository()

    # ── Public API ──────────────────────────────────────────────────

    async def start(self, run_id: str) -> None:
        """Launch a paper-trading run as a background task.

        Loads strategy code, market engine, and risk config from the DB,
        seeds the engine with historical data, then enters the poll loop.
        """
        if run_id in self._tasks:
            raise RuntimeError(f"Run {run_id} is already active")

        # 1. Load run metadata from DB
        meta = self._repo.get_run(run_id)
        if meta is None:
            raise ValueError(f"Run {run_id} not found")

        config = meta["config"]
        codes = config.get("codes", [])
        market = meta.get("market", "a_share")
        interval = config.get("interval", "1D")
        initial_capital = float(config.get("initial_capital", 100_000.0))
        risk_dict = meta.get("risk_config", {})
        strategy_code = meta.get("strategy_code", "")
        pt_user_id = int(meta.get("user_id", 1))

        if not strategy_code:
            raise ValueError("Strategy code is empty")

        logger.info("Starting paper trading run %s (%s) — %s %s", run_id, meta["run_name"], market, interval)

        # 2. Persist strategy code + load module
        engine, bridge_mode = self._build_engine(
            run_id, config, strategy_code, market, risk_dict, initial_capital
        )
        self._active[run_id] = engine
        self._queues[run_id] = asyncio.Queue(maxsize=4096)

        # Update DB
        self._repo.update_run(run_id, tick_mode=(bridge_mode == "tick"), status="running")
        self._repo.set_start_time(run_id)

        # 3. Seed with historical data
        self._seed_historical(engine, codes, market, interval, user_id=pt_user_id)

        # Persist initial state
        await self._persist(run_id, engine)

        # 4. Launch background loop
        task = asyncio.create_task(
            self._run_loop(run_id, engine, codes, market, interval, user_id=pt_user_id)
        )
        self._tasks[run_id] = task

        # Push start event
        await self._push_event(run_id, "status", {"status": "running", "message": "Paper trading started"})

    async def stop(self, run_id: str, close_positions: bool = True) -> None:
        """Stop a running / paused paper-trading run."""
        task = self._tasks.pop(run_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        engine = self._active.pop(run_id, None)
        if engine is not None and close_positions:
            trades = engine.force_close_all("end_of_run")
            for t in trades:
                self._repo.save_trade(run_id, t)
            self._repo.save_positions(run_id, {})
            summary = engine.get_summary()
            self._repo.update_run(
                run_id,
                status="stopped",
                state="flat",
                current_capital=engine.capital,
                last_bar_time=engine.last_bar_time,
            )
            await self._push_event(run_id, "status", {"status": "stopped", "message": "Run stopped", "summary": summary})
        else:
            self._repo.update_run(run_id, status="stopped")
            await self._push_event(run_id, "status", {"status": "stopped", "message": "Run stopped"})

        # Keep queue for a few seconds so SSE can drain
        queue = self._queues.pop(run_id, None)

    async def pause(self, run_id: str) -> None:
        """Pause a run (keep positions, cancel polling task)."""
        task = self._tasks.pop(run_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._repo.update_run(run_id, status="paused")
        await self._push_event(run_id, "status", {"status": "paused", "message": "Run paused"})

    async def resume(self, run_id: str) -> None:
        """Resume a paused run."""
        if run_id in self._tasks:
            raise RuntimeError(f"Run {run_id} is already active")

        meta = self._repo.get_run(run_id)
        if meta is None:
            raise ValueError(f"Run {run_id} not found")
        if meta["status"] != "paused":
            raise RuntimeError(f"Run {run_id} is not paused (status={meta['status']})")

        engine = self._active.get(run_id)
        if engine is None:
            raise RuntimeError(f"Engine for {run_id} not found in memory")

        config = meta["config"]
        codes = config.get("codes", [])
        market = meta.get("market", "a_share")
        interval = config.get("interval", "1D")
        pt_user_id = int(meta.get("user_id", 1))

        self._repo.update_run(run_id, status="running")
        task = asyncio.create_task(
            self._run_loop(run_id, engine, codes, market, interval, user_id=pt_user_id)
        )
        self._tasks[run_id] = task
        await self._push_event(run_id, "status", {"status": "running", "message": "Run resumed"})

    # ── SSE queue access ────────────────────────────────────────────

    def get_queue(self, run_id: str) -> asyncio.Queue | None:
        return self._queues.get(run_id)

    def get_engine(self, run_id: str) -> PaperTradingEngine | None:
        return self._active.get(run_id)

    def is_active(self, run_id: str) -> bool:
        return run_id in self._tasks

    # ── Main loop ───────────────────────────────────────────────────

    async def _run_loop(
        self,
        run_id: str,
        engine: PaperTradingEngine,
        codes: list[str],
        market: str,
        interval: str,
        user_id: int = 1,
    ) -> None:
        poll_seconds = _interval_to_seconds(interval)

        try:
            from src.auth.user_config import load_user_config
            load_user_config(user_id)
        except Exception:
            pass

        # Resolve loader
        from backtest.loaders.registry import resolve_loader
        try:
            loader = resolve_loader(market)
        except Exception as e:
            logger.error("Failed to resolve loader for %s: %s", market, e)
            self._repo.update_run(run_id, status="error", error_message=str(e))
            await self._push_event(run_id, "status", {"status": "error", "message": str(e)})
            return

        consecutive_errors = 0
        max_errors = 5

        while True:
            try:
                now = datetime.now()
                # Look back a reasonable window to catch the latest bars
                lookback_days = 7 if "d" in interval.lower() or "w" in interval.lower() else 2
                start_date = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
                end_date = now.strftime("%Y-%m-%d")

                data_map = loader.fetch(codes, start_date, end_date, interval=interval)

                # Find new bars after engine.last_bar_time
                last_ts = engine.last_bar_time
                new_bars: dict[str, pd.Series] = {}
                newest_ts = last_ts

                for code, df in data_map.items():
                    if df is None or len(df) == 0:
                        continue
                    df_sorted = df.sort_index()
                    if last_ts is not None:
                        mask = df_sorted.index > last_ts
                        new_rows = df_sorted[mask]
                    else:
                        # First run — only take the very last bar
                        new_rows = df_sorted.iloc[-1:]

                    if len(new_rows) > 0:
                        row = new_rows.iloc[-1]
                        row.name = new_rows.index[-1]
                        new_bars[code] = row
                        if newest_ts is None or new_rows.index[-1] > newest_ts:
                            newest_ts = new_rows.index[-1]

                if new_bars and newest_ts is not None and newest_ts != last_ts:
                    timestamp = pd.Timestamp(newest_ts)
                    result = engine.on_bar(new_bars, timestamp)
                    await self._persist(run_id, engine)
                    # Serialize positions for real-time UI update
                    pos_list = []
                    for sym, pos in result.positions.items():
                        pos_list.append({
                            "symbol": sym,
                            "direction": pos.direction,
                            "entry_price": pos.entry_price,
                            "size": pos.size,
                            "leverage": pos.leverage,
                        })
                    await self._push_event(run_id, "bar", {
                        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
                        "equity": result.equity,
                        "capital": result.capital,
                        "unrealized": result.unrealized,
                        "drawdown": result.drawdown,
                        "signal_count": len(result.signals),
                        "trade_count": len(result.trades),
                        "position_count": len(result.positions),
                        "positions": pos_list,
                    })
                    for trade in result.trades:
                        await self._push_event(run_id, "trade", {
                            "symbol": trade.symbol,
                            "direction": trade.direction,
                            "entry_price": trade.entry_price,
                            "exit_price": trade.exit_price,
                            "entry_time": str(trade.entry_time) if trade.entry_time else None,
                            "exit_time": str(trade.exit_time) if trade.exit_time else None,
                            "pnl": trade.pnl,
                            "pnl_pct": trade.pnl_pct,
                            "exit_reason": trade.exit_reason,
                        })
                    for sig in result.signals:
                        await self._push_event(run_id, "signal", {
                            "symbol": sig.symbol,
                            "direction": sig.direction,
                            "price": sig.price,
                            "reason": sig.reason if hasattr(sig, "reason") else "",
                            "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
                        })
                    consecutive_errors = 0
                else:
                    # Heartbeat
                    await self._push_event(run_id, "heartbeat", {"timestamp": now.isoformat()})

            except asyncio.CancelledError:
                raise
            except Exception as e:
                consecutive_errors += 1
                logger.error("Paper trading loop error for %s (%d/%d): %s\n%s",
                             run_id, consecutive_errors, max_errors, e,
                             traceback.format_exc())
                await self._push_event(run_id, "error", {"message": str(e)})
                if consecutive_errors >= max_errors:
                    self._repo.update_run(run_id, status="error", error_message=str(e))
                    await self._push_event(run_id, "status", {"status": "error", "message": f"Max errors reached: {e}"})
                    break

            await asyncio.sleep(poll_seconds)

        # Cleanup on exit
        self._tasks.pop(run_id, None)
        self._active.pop(run_id, None)

    # ── Internal helpers ─────────────────────────────────────────────

    def _build_engine(
        self, run_id: str, config: dict, strategy_code: str,
        market: str, risk_dict: dict, initial_capital: float,
    ) -> tuple[PaperTradingEngine, str]:
        """Validate and load strategy, construct engine + market engine."""
        # Write strategy to runs directory (following existing backtest pattern)
        runs_dir = Path(__file__).resolve().parents[1] / "runs" / run_id
        runs_dir.mkdir(parents=True, exist_ok=True)
        code_dir = runs_dir / "code"
        code_dir.mkdir(exist_ok=True)
        (code_dir / "signal_engine.py").write_text(strategy_code, encoding="utf-8")
        (runs_dir / "config.json").write_text(
            json.dumps({**config, "market": market}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Validate strategy source (same AST check used by backtest runner)
        from backtest.runner import _validate_signal_engine_source
        try:
            _validate_signal_engine_source(code_dir / "signal_engine.py")
        except Exception as e:
            raise ValueError(f"Strategy validation failed: {e}") from e

        # Load strategy module via importlib (same as backtest runner)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"signal_engine_{run_id.replace('-', '_')}",
            str(code_dir / "signal_engine.py"),
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        # Build market engine
        market_engine = self._resolve_market_engine(market, {**config, "initial_cash": initial_capital})

        # Build risk manager
        risk_config = RiskConfig(**risk_dict) if risk_dict else RiskConfig()
        from papertrade.risk_manager import RiskManager as RiskManagerCls
        risk_manager = RiskManagerCls(risk_config, initial_capital)

        # Build engine
        engine = PaperTradingEngine(
            config=config,
            signal_module=module,
            market_engine=market_engine,
            risk_manager=risk_manager,
        )

        return engine, engine.tick_mode

    @staticmethod
    def _resolve_market_engine(market: str, config: dict) -> Any:
        """Resolve the correct BaseEngine subclass for a market type."""
        from backtest.engines.china_a import ChinaAEngine
        from backtest.engines.global_equity import GlobalEquityEngine
        from backtest.engines.crypto import CryptoEngine

        market_lower = market.lower().replace("-", "_")
        if market_lower in ("a_share", "a_stock", "china_a"):
            return ChinaAEngine(config)
        elif market_lower in ("us_equity", "hk_equity", "global_equity"):
            return GlobalEquityEngine(config)
        elif market_lower in ("crypto",):
            return CryptoEngine(config)
        else:
            # Default to A-share for Chinese stocks
            return ChinaAEngine(config)

    @staticmethod
    def _seed_historical(
        engine: PaperTradingEngine,
        codes: list[str],
        market: str,
        interval: str,
        user_id: int = 1,
        lookback: int = 500,
    ) -> None:
        """Fetch historical data and seed the engine for strategy warmup."""
        try:
            from src.auth.user_config import load_user_config
            load_user_config(user_id)
        except Exception:
            pass

        from backtest.loaders.registry import resolve_loader

        try:
            loader = resolve_loader(market)
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")
            data_map = loader.fetch(codes, start, end, interval=interval)
            if data_map:
                engine.initialize(data_map)
                logger.info("Engine seeded with %d codes, %d+ bars each",
                            len(data_map),
                            max((len(df) for df in data_map.values()), default=0))
            else:
                logger.warning("No historical data returned for warmup")
        except Exception as e:
            logger.warning("Failed to seed historical data: %s", e)

    async def _persist(self, run_id: str, engine: PaperTradingEngine) -> None:
        """Write current engine state to the database."""
        try:
            summary = engine.get_summary()
            self._repo.update_run(
                run_id,
                state=summary["state"],
                current_capital=summary["capital"],
                last_bar_time=engine.last_bar_time,
            )
            if engine.equity_history:
                # Only persist the latest equity snapshot to avoid duplicates
                snap = engine.equity_history[-1] if hasattr(engine, "equity_history") and engine.equity_history else None
            # Persist current positions
            self._repo.save_positions(run_id, engine.positions)
            # Calculate drawdown for the latest point
            eq = summary["equity"]
            peak = getattr(engine, "_peak_equity", eq)
            dd = (eq - peak) / peak if peak > 0 else 0.0
            self._repo.save_equity_point(
                run_id,
                engine.last_bar_time,
                eq,
                summary["capital"],
                summary["unrealized"],
                dd,
            )
        except Exception as e:
            logger.error("Failed to persist run %s: %s", run_id, e)

    async def _push_event(self, run_id: str, event_type: str, data: dict) -> None:
        """Push an SSE event into the per-run queue."""
        queue = self._queues.get(run_id)
        if queue is None:
            return
        try:
            payload = json.dumps({"event": event_type, "data": data}, default=str, ensure_ascii=False)
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("SSE queue full for run %s, dropping %s event", run_id, event_type)
