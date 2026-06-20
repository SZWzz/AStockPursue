"""LiveDriver – feeds real-time bars through TradingEngine.on_bar().

Extracted from PaperTradingScheduler._run_loop().  Handles:
  - Periodic data fetching
  - New-bar detection
  - Feeding bars to TradingEngine
  - Error handling with consecutive-error circuit breaker

The caller (PaperTradingScheduler) handles SSE event pushing and DB persistence.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

# TODO(P5): migrate to Go gRPC equivalents:
#   - engines → EngineService (not yet exposed)
#   - risk → RiskService (not yet exposed)
#   - brokers → BrokerService (not yet exposed)

logger = logging.getLogger(__name__)


def interval_to_seconds(interval: str) -> float:
    """Convert a bar interval string to polling seconds.

    The polling interval is decoupled from the bar interval so that daily /
    weekly runs check for new data frequently instead of once per bar period.
    This prevents missing bars when the data source updates with a delay
    (e.g. akshare publishing daily close data hours after market close).
    """
    interval = interval.lower().strip()
    # Intraday intervals: poll every 60 s — fast enough to catch new bars,
    # slow enough to avoid hammering the data source.
    if interval in ("1m", "1min", "5m", "5min",
                    "15m", "15min", "30m", "30min",
                    "1h", "1hour", "60min", "4h", "4hour"):
        return 60.0
    # Daily / weekly: poll every 5 min.  Previously 86 400 s (24 h) and
    # 604 800 s (7 d) respectively — a single miss meant waiting a full cycle.
    if interval in ("1d", "1day", "daily", "1w", "1week", "weekly"):
        return 300.0  # 5 minutes
    # Unknown string → try numeric parse, otherwise default to 60 s.
    try:
        # Replace "min" before "m" so "120min" → "120", not "120in"
        return float(interval.replace("min", "").replace("m", "")) * 60.0
    except ValueError:
        return 60.0


class LiveDriver:
    """Drives a TradingEngine with real-time data from a DataLoader.

    The caller provides callbacks for persisting state and pushing events.
    """

    def __init__(
        self,
        engine: Any,  # TradingEngine
        loader: Any,  # DataLoader
        codes: list[str],
        interval: str,
        *,
        on_bar_result: callable = None,  # async (run_id, result) -> None
        on_error: callable = None,  # async (run_id, error_msg) -> None
        on_heartbeat: callable = None,  # async (run_id, info: dict | None = None) -> None
        max_consecutive_errors: int = 5,
    ) -> None:
        self._engine = engine
        self._loader = loader
        self._codes = codes
        self._interval = interval
        self.loader_name: str = getattr(loader, "name", "unknown")
        self._poll_seconds = interval_to_seconds(interval)
        self._on_bar_result = on_bar_result
        self._on_error = on_error
        self._on_heartbeat = on_heartbeat
        self._max_errors = max_consecutive_errors
        self.running = False

    async def run(self, run_id: str) -> None:
        """Main loop: fetch data, detect new bars, feed to engine.

        Runs until cancelled or max consecutive errors reached.
        """
        self.running = True
        consecutive_errors = 0

        while self.running:
            try:
                now = datetime.now()
                lookback_days = 7 if "d" in self._interval.lower() or "w" in self._interval.lower() else 2
                start_date = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
                end_date = now.strftime("%Y-%m-%d")

                data_map = self._loader.fetch(
                    self._codes, start_date, end_date, interval=self._interval
                )

                # Find new bars after engine.last_bar_time
                last_ts = self._engine.last_bar_time
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
                        new_rows = df_sorted.iloc[-1:]

                    if len(new_rows) > 0:
                        row = new_rows.iloc[-1]
                        row.name = new_rows.index[-1]
                        new_bars[code] = row
                        if newest_ts is None or new_rows.index[-1] > newest_ts:
                            newest_ts = new_rows.index[-1]

                if new_bars and newest_ts is not None and newest_ts != last_ts:
                    timestamp = pd.Timestamp(newest_ts)
                    result = self._engine.on_bar(new_bars, timestamp)
                    if self._on_bar_result:
                        await self._on_bar_result(run_id, result)
                    consecutive_errors = 0
                else:
                    if self._on_heartbeat:
                        next_poll = (datetime.now() + timedelta(seconds=self._poll_seconds)).isoformat()
                        await self._on_heartbeat(run_id, {
                            "last_bar_time": str(last_ts) if last_ts else None,
                            "next_poll": next_poll,
                            "poll_seconds": self._poll_seconds,
                            "codes_checked": len(self._codes),
                        })

            except asyncio.CancelledError:
                raise
            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    "LiveDriver error for %s (%d/%d): %s",
                    run_id, consecutive_errors, self._max_errors, e,
                )
                if self._on_error:
                    await self._on_error(run_id, str(e))
                if consecutive_errors >= self._max_errors:
                    break

            await asyncio.sleep(self._poll_seconds)

        self.running = False

    def stop(self) -> None:
        """Signal the loop to stop after the current iteration."""
        self.running = False

    @staticmethod
    def seed_historical(
        engine: Any,
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
                logger.info(
                    "Engine seeded with %d codes, %d+ bars each",
                    len(data_map),
                    max((len(df) for df in data_map.values()), default=0),
                )
            else:
                logger.warning("No historical data returned for warmup")
        except Exception as e:
            logger.warning("Failed to seed historical data: %s", e)
