"""Reflection Worker — periodic background validation of historical AI decisions.

Flow (runs daily at 02:00):
  1. Query unvalidated analysis records from 7 days ago (LIMIT 200)
  2. Load subsequent market data for each symbol
  3. Compute actual return over the holding period
  4. Judge: bullish+up / bearish+down / neutral+flat(±2%) → correct
  5. Update analysis_memory with validation results
  6. If recent accuracy < 45%, log an alert
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class ReflectionWorker:
    """Periodically validates AI analysis decisions against actual outcomes."""

    def __init__(self, min_age_days: int = 7, batch_size: int = 200):
        self.min_age_days = min_age_days
        self.batch_size = batch_size

    async def run_cycle(self) -> dict[str, Any]:
        """Execute one validation cycle.

        Returns:
            Dict with ``validated``, ``correct``, ``incorrect``, ``accuracy``.
        """
        records = await self._fetch_unvalidated()
        if not records:
            logger.debug("ReflectionWorker: no unvalidated records found")
            return {"validated": 0, "correct": 0, "incorrect": 0, "accuracy": 0.0}

        validated = 0
        correct = 0
        incorrect = 0

        for record in records:
            try:
                outcome = await self._validate_record(record)
                if outcome is not None:
                    await self._update_record(record["id"], outcome)
                    validated += 1
                    if outcome.get("was_correct"):
                        correct += 1
                    else:
                        incorrect += 1
            except Exception as exc:
                logger.warning("ReflectionWorker: validation failed for record %s: %s",
                               record.get("id"), exc)

        accuracy = correct / validated if validated > 0 else 0.0

        # Alert if accuracy is concerning
        if validated >= 10 and accuracy < 0.45:
            logger.warning(
                "ReflectionWorker: low accuracy %.1f%% (%d/%d correct over %d records)",
                accuracy * 100, correct, validated, validated,
            )

        logger.info(
            "ReflectionWorker: validated=%d correct=%d incorrect=%d accuracy=%.1f%%",
            validated, correct, incorrect, accuracy * 100,
        )

        return {
            "validated": validated,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": round(accuracy, 4),
        }

    # ── Internal ───────────────────────────────────────────────────────────

    async def _fetch_unvalidated(self) -> list[dict]:
        """Fetch unvalidated analysis records older than min_age_days."""
        from datetime import timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.min_age_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        try:
            from src.database import get_db
            db = get_db()
            if db is None:
                return []

            rows = await db.fetch(
                """
                SELECT id, user_id, symbol, decision, confidence,
                       price_at_analysis, created_at
                FROM analysis_memory
                WHERE validated_at IS NULL
                  AND created_at <= $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                cutoff_str, self.batch_size,
            )
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning("ReflectionWorker: fetch_unvalidated failed: %s", exc)
            return []

    async def _validate_record(self, record: dict) -> dict | None:
        """Validate a single analysis record against subsequent market data.

        Returns a dict with was_correct, actual_return_pct, or None if data unavailable.
        """
        symbol = record.get("symbol", "")
        decision = record.get("decision", "neutral")
        created_at = record.get("created_at", "")

        if not symbol or not created_at:
            return None

        try:
            # Load market data for the symbol from analysis date + min_age_days
            analysis_date = pd.Timestamp(created_at)
            end_date = analysis_date + timedelta(days=self.min_age_days + 1)

            from backtest.data_store import get_data_store
            store = get_data_store()
            df = store.get_ohlcv(
                symbol,
                analysis_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                interval="1D",
            )

            if df is None or df.empty or len(df) < 2:
                return None

            start_price = float(df["close"].iloc[0])
            end_price = float(df["close"].iloc[-1])

            if start_price <= 0:
                return None

            actual_return = (end_price - start_price) / start_price

            # Judge correctness
            was_correct = False
            if decision == "bullish" and actual_return > 0.01:
                was_correct = True
            elif decision == "bearish" and actual_return < -0.01:
                was_correct = True
            elif decision == "neutral" and abs(actual_return) <= 0.02:
                was_correct = True
            # Partial: direction correct but magnitude small
            elif decision == "bullish" and actual_return > 0:
                was_correct = True
            elif decision == "bearish" and actual_return < 0:
                was_correct = True

            return {
                "was_correct": was_correct,
                "actual_return_pct": round(actual_return, 6),
                "start_price": round(start_price, 4),
                "end_price": round(end_price, 4),
            }

        except Exception as exc:
            logger.debug("ReflectionWorker: symbol %s validation error: %s", symbol, exc)
            return None

    async def _update_record(self, record_id: int, outcome: dict) -> None:
        """Update the analysis_memory row with validation results."""
        try:
            from src.database import get_db
            db = get_db()
            if db is None:
                return

            await db.execute(
                """
                UPDATE analysis_memory
                SET validated_at = NOW(),
                    was_correct = $1,
                    actual_return_pct = $2,
                    actual_outcome = $3
                WHERE id = $4
                """,
                outcome.get("was_correct", False),
                outcome.get("actual_return_pct", 0.0),
                "correct" if outcome.get("was_correct") else "incorrect",
                record_id,
            )
        except Exception as exc:
            logger.warning("ReflectionWorker: update_record failed for id %s: %s", record_id, exc)
