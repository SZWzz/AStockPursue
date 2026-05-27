"""Paper trading scheduler – asyncio background tasks driving the engines.

Each active paper-trading run gets an asyncio Task that periodically:
  1. Fetches the latest bar(s) via the DataLoader registry
  2. Feeds new bars to the TradingEngine via LiveDriver
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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from papertrade.engine import TradingEngine
from papertrade.models import RiskConfig
from papertrade.repository import PaperTradeRepository
from src.trading.live_driver import LiveDriver, interval_to_seconds
from src.trading.signal_adapter import SignalAdapter

logger = logging.getLogger(__name__)


class PaperTradingScheduler:
    """In-process scheduler managing multiple paper-trading runs.

    Each run runs as an ``asyncio.Task`` inside the event loop.
    SSE events are pushed into per-run ``asyncio.Queue`` instances
    that the SSE route handler reads from.
    """

    def __init__(self) -> None:
        self._active: dict[str, TradingEngine] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._drivers: dict[str, LiveDriver] = {}
        self._repo = PaperTradeRepository()

    # ── Public API ──────────────────────────────────────────────────

    async def start(self, run_id: str) -> None:
        """Launch a paper-trading run as a background task."""
        if run_id in self._tasks:
            raise RuntimeError(f"Run {run_id} is already active")

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

        engine, bridge_mode = self._build_engine(
            run_id, config, strategy_code, market, risk_dict, initial_capital
        )
        self._active[run_id] = engine
        self._queues[run_id] = asyncio.Queue(maxsize=4096)

        self._repo.update_run(run_id, tick_mode=(bridge_mode == "tick"), status="running")
        self._repo.set_start_time(run_id)

        try:
            # Seed with historical data
            self._seed_historical(engine, codes, market, interval, user_id=pt_user_id)

            await self._persist(run_id, engine)

            # Build LiveDriver
            try:
                from src.auth.user_config import load_user_config
                load_user_config(pt_user_id)
            except Exception:
                pass

            from backtest.loaders.registry import resolve_loader
            loader = resolve_loader(market)

            driver = LiveDriver(
                engine=engine,
                loader=loader,
                codes=codes,
                interval=interval,
                on_bar_result=lambda rid, result: self._on_bar_result(rid, result),
                on_error=lambda rid, msg: self._on_loop_error(rid, msg),
                on_heartbeat=lambda rid: self._push_event(rid, "heartbeat", {"timestamp": datetime.now().isoformat()}),
            )
            self._drivers[run_id] = driver

            task = asyncio.create_task(self._run_with_driver(run_id, driver))
            self._tasks[run_id] = task

            await self._push_event(run_id, "status", {"status": "running", "message": "Paper trading started"})
        except Exception as e:
            # Roll back status to "stopped" so the UI doesn't show a stale "running"
            self._active.pop(run_id, None)
            self._queues.pop(run_id, None)
            self._drivers.pop(run_id, None)
            self._repo.update_run(run_id, status="stopped", error_message=f"Failed to start: {e}")
            await self._push_event(run_id, "status", {"status": "stopped", "message": str(e)})
            raise

    async def stop(self, run_id: str, close_positions: bool = True) -> None:
        """Stop a running / paused paper-trading run."""
        driver = self._drivers.pop(run_id, None)
        if driver:
            driver.stop()

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
                current_capital=summary["capital"],
                last_bar_time=engine.last_bar_time,
            )
            await self._push_event(run_id, "status", {"status": "stopped", "message": "Run stopped", "summary": summary})
        else:
            self._repo.update_run(run_id, status="stopped")
            await self._push_event(run_id, "status", {"status": "stopped", "message": "Run stopped"})

        self._queues.pop(run_id, None)

    async def pause(self, run_id: str) -> None:
        """Pause a run (keep positions, cancel polling task)."""
        driver = self._drivers.pop(run_id, None)
        if driver:
            driver.stop()
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

        try:
            from src.auth.user_config import load_user_config
            load_user_config(pt_user_id)
        except Exception:
            pass

        from backtest.loaders.registry import resolve_loader
        loader = resolve_loader(market)

        driver = LiveDriver(
            engine=engine,
            loader=loader,
            codes=codes,
            interval=interval,
            on_bar_result=lambda rid, result: self._on_bar_result(rid, result),
            on_error=lambda rid, msg: self._on_loop_error(rid, msg),
            on_heartbeat=lambda rid: self._push_event(rid, "heartbeat", {"timestamp": datetime.now().isoformat()}),
        )
        self._drivers[run_id] = driver

        self._repo.update_run(run_id, status="running")
        task = asyncio.create_task(self._run_with_driver(run_id, driver))
        self._tasks[run_id] = task
        await self._push_event(run_id, "status", {"status": "running", "message": "Run resumed"})

    # ── SSE queue access ────────────────────────────────────────────

    def get_queue(self, run_id: str) -> asyncio.Queue | None:
        return self._queues.get(run_id)

    def get_engine(self, run_id: str) -> TradingEngine | None:
        return self._active.get(run_id)

    def is_active(self, run_id: str) -> bool:
        return run_id in self._tasks

    # ── Run loop (delegates to LiveDriver) ──────────────────────────

    async def _run_with_driver(self, run_id: str, driver: LiveDriver) -> None:
        """Run the LiveDriver and handle cleanup on exit.

        On normal LiveDriver exit (circuit breaker / stop signal), sets
        DB status to ``stopped`` so the UI reflects reality even when
        the scheduler's in-memory state is lost.
        """
        try:
            await driver.run(run_id)
            # LiveDriver exited normally (circuit breaker or stop signal).
            # Update DB status so the UI doesn't show a stale "running".
            self._repo.update_run(run_id, status="stopped", error_message="LiveDriver stopped — check data source availability")
            await self._push_event(run_id, "status", {"status": "stopped", "message": "LiveDriver exited"})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("LiveDriver crashed for %s: %s\n%s", run_id, e, traceback.format_exc())
            self._repo.update_run(run_id, status="error", error_message=str(e))
            await self._push_event(run_id, "status", {"status": "error", "message": str(e)})
        finally:
            self._tasks.pop(run_id, None)
            self._active.pop(run_id, None)

    # ── LiveDriver callbacks ────────────────────────────────────────

    async def _on_bar_result(self, run_id: str, result: Any) -> None:
        """Called by LiveDriver for each new bar processed."""
        engine = self._active.get(run_id)
        if engine is None:
            return
        await self._persist(run_id, engine)

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
            "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, "isoformat") else str(result.timestamp),
            "equity": result.equity,
            "capital": result.capital,
            "unrealized": result.unrealized,
            "drawdown": result.drawdown,
            "signal_count": len(result.signals),
            "trade_count": len(result.trades),
            "position_count": len(result.positions),
            "positions": pos_list,
            "bars": getattr(result, "bars", {}),
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
                "symbol": sig["symbol"],
                "direction": sig["direction"],
                "price": sig.get("price", 0),
                "reason": sig.get("reason", ""),
                "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, "isoformat") else str(result.timestamp),
            })

    async def _on_loop_error(self, run_id: str, error_msg: str) -> None:
        """Called by LiveDriver on each error."""
        await self._push_event(run_id, "error", {"message": error_msg})

    # ── Internal helpers ─────────────────────────────────────────────

    def _build_engine(
        self, run_id: str, config: dict, strategy_code: str,
        market: str, risk_dict: dict, initial_capital: float,
    ) -> tuple[TradingEngine, str]:
        """Validate and load strategy, construct TradingEngine + market engine."""
        runs_dir = Path(__file__).resolve().parents[1] / "runs" / run_id
        runs_dir.mkdir(parents=True, exist_ok=True)
        code_dir = runs_dir / "code"
        code_dir.mkdir(exist_ok=True)
        (code_dir / "signal_engine.py").write_text(strategy_code, encoding="utf-8")
        (runs_dir / "config.json").write_text(
            json.dumps({**config, "market": market}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        from backtest.runner import _validate_signal_engine_source
        try:
            _validate_signal_engine_source(code_dir / "signal_engine.py")
        except Exception as e:
            raise ValueError(f"Strategy validation failed: {e}") from e

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"signal_engine_{run_id.replace('-', '_')}",
            str(code_dir / "signal_engine.py"),
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        market_engine = self._resolve_market_engine(market, {**config, "initial_cash": initial_capital})

        risk_config = RiskConfig(**risk_dict) if risk_dict else RiskConfig()
        from src.trading.risk_pipeline import RiskPipeline
        risk_manager = RiskPipeline(risk_config, initial_capital)

        signal_adapter = SignalAdapter(module)

        from src.trading.state_machine import FlatStateMachine
        engine = TradingEngine(
            config=config,
            signal_adapter=signal_adapter,
            market_engine=market_engine,
            risk_pipeline=risk_manager,
            state_machine=FlatStateMachine(),
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
            return ChinaAEngine(config)

    @staticmethod
    def _seed_historical(
        engine: TradingEngine,
        codes: list[str],
        market: str,
        interval: str,
        user_id: int = 1,
        lookback: int = 500,
    ) -> None:
        """Fetch historical data and seed the engine for strategy warmup."""
        LiveDriver.seed_historical(engine, codes, market, interval, user_id, lookback)

    async def _persist(self, run_id: str, engine: TradingEngine) -> None:
        """Write current engine state to the database."""
        try:
            summary = engine.get_summary()
            self._repo.update_run(
                run_id,
                state=summary["state"],
                current_capital=summary["capital"],
                last_bar_time=engine.last_bar_time,
            )
            self._repo.save_positions(run_id, dict(engine.positions))
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
