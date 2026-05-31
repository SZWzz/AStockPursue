"""Factor Wide Table ETL.

Daily batch job: compute all Alpha Zoo factors for a universe of stocks
and write results to a wide PostgreSQL table for fast screening queries.

Designed to run after market close (e.g. via scheduler cron "30 15 * * 1-5").
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Migration SQL (also in migrations/ for auto-apply)
# ---------------------------------------------------------------------------

FACTOR_WIDE_DDL = """
CREATE TABLE IF NOT EXISTS vt_factor_daily_wide (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE NOT NULL,
    symbol          VARCHAR(32) NOT NULL,
    -- Technical indicators (always present)
    close           DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    returns_1d      DOUBLE PRECISION,
    returns_5d      DOUBLE PRECISION,
    returns_20d     DOUBLE PRECISION,
    volume_ratio    DOUBLE PRECISION,
    high_low_ratio  DOUBLE PRECISION,
    sma_20          DOUBLE PRECISION,
    sma_60          DOUBLE PRECISION,
    volatility_20d  DOUBLE PRECISION,
    rsi_14          DOUBLE PRECISION,
    -- Alpha Zoo factors (dynamic columns via JSONB for extensibility)
    factor_values   JSONB DEFAULT '{}',
    etl_ts          TIMESTAMPTZ DEFAULT now(),
    UNIQUE(trade_date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_factor_wide_date ON vt_factor_daily_wide(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_factor_wide_symbol ON vt_factor_daily_wide(symbol, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_factor_wide_gin ON vt_factor_daily_wide USING gin(factor_values);
"""


class FactorWideETL:
    """Compute and persist a daily factor wide table snapshot."""

    def __init__(
        self,
        universe: list[str] | None = None,
        lookback_days: int = 60,
    ) -> None:
        self.universe = universe or [
            "000001.SZ", "000002.SZ", "000858.SZ", "002415.SZ",
            "600000.SH", "600036.SH", "600519.SH", "601318.SH",
            "600276.SH", "300750.SZ",
        ]
        self.lookback_days = lookback_days

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def ensure_table(self) -> None:
        """Create the wide table if it doesn't exist."""
        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(FACTOR_WIDE_DDL)
            logger.info("Factor wide table ensured")
        except Exception as e:
            logger.warning("Could not ensure factor wide table: %s", e)

    # ------------------------------------------------------------------
    # Compute technical indicators
    # ------------------------------------------------------------------

    def _compute_technical_indicators(self, panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Compute standard technical indicators from OHLCV panel."""
        close = panel.get("close")
        if close is None or close.empty:
            return pd.DataFrame()

        results = {}
        for sym in close.columns:
            c = close[sym].dropna()
            if len(c) < 60:
                continue
            row: dict[str, Any] = {"symbol": sym}

            # Price
            row["close"] = float(c.iloc[-1])

            # Volume
            if "volume" in panel and sym in panel["volume"].columns:
                v = panel["volume"][sym].dropna()
                if len(v) > 0:
                    row["volume"] = float(v.iloc[-1])

            # Returns
            row["returns_1d"] = float(c.pct_change(1).iloc[-1]) if len(c) > 1 else 0
            row["returns_5d"] = float(c.pct_change(5).iloc[-1]) if len(c) > 5 else 0
            row["returns_20d"] = float(c.pct_change(20).iloc[-1]) if len(c) > 20 else 0

            # Volume ratio
            if "volume" in panel and sym in panel["volume"].columns:
                v = panel["volume"][sym].dropna()
                if len(v) >= 20:
                    vol_ma = v.rolling(20).mean()
                    row["volume_ratio"] = float(v.iloc[-1] / (vol_ma.iloc[-1] + 1e-12))

            # High/Low ratio
            if "high" in panel and "low" in panel:
                h = panel["high"].get(sym)
                l = panel["low"].get(sym)
                if h is not None and l is not None and h.iloc[-1] > 0:
                    row["high_low_ratio"] = float((h.iloc[-1] - l.iloc[-1]) / h.iloc[-1])

            # SMAs
            row["sma_20"] = float(c.rolling(20).mean().iloc[-1]) if len(c) >= 20 else 0
            row["sma_60"] = float(c.rolling(60).mean().iloc[-1]) if len(c) >= 60 else 0

            # Volatility
            if len(c) >= 20:
                row["volatility_20d"] = float(c.pct_change().rolling(20).std().iloc[-1])

            # RSI(14)
            if len(c) >= 15:
                delta = c.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / (loss + 1e-12)
                row["rsi_14"] = float(100 - 100 / (1 + rs.iloc[-1]))

            results[sym] = row

        return pd.DataFrame.from_dict(results, orient="index").reset_index(drop=True)

    # ------------------------------------------------------------------
    # Compute Alpha Zoo factors
    # ------------------------------------------------------------------

    def _compute_zoo_factors(self, panel: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """Compute all registered Alpha Zoo factors."""
        factor_results: dict[str, pd.DataFrame] = {}
        try:
            from src.factors.registry import get_default_registry
            registry = get_default_registry()
            alpha_ids = registry.list()
            logger.info("Computing %d Alpha Zoo factors...", len(alpha_ids))
            for aid in alpha_ids:
                try:
                    result = registry.compute(aid, panel)
                    factor_results[aid] = result
                except Exception:
                    pass  # Skip factors that fail (missing columns, etc.)
            logger.info("Computed %d factors successfully", len(factor_results))
        except Exception as e:
            logger.warning("Factor computation skipped: %s", e)
        return factor_results

    # ------------------------------------------------------------------
    # Run ETL
    # ------------------------------------------------------------------

    def run(self, target_date: str | None = None) -> dict[str, Any]:
        """Execute the full ETL pipeline.

        Args:
            target_date: Trade date in 'YYYY-MM-DD' format. Defaults to latest.

        Returns:
            Status dict with row_count and elapsed time.
        """
        start = time.monotonic()
        self.ensure_table()

        if target_date is None:
            target_date = (pd.Timestamp.now() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        # Load OHLCV data
        try:
            from backtest.data_store import get_data_store
            store = get_data_store()
            lookback_start = (pd.Timestamp(target_date) - pd.Timedelta(days=self.lookback_days)).strftime("%Y-%m-%d")
            data_map = store.get_multi_ohlcv(self.universe, lookback_start, target_date, interval="1D")

            if not data_map:
                logger.warning("No data available for factor wide ETL")
                return {"status": "no_data", "row_count": 0}
        except Exception as e:
            logger.warning("DataStore unavailable: %s", e)
            return {"status": "skipped", "reason": str(e), "row_count": 0}

        # Build panel
        panel: dict[str, pd.DataFrame] = {}
        for col in ["open", "high", "low", "close", "volume"]:
            dfs = []
            for sym in self.universe:
                df = data_map.get(sym)
                if df is not None and col in df.columns:
                    if "date" in df.columns:
                        s = df.set_index("date")[col].rename(sym)
                    else:
                        s = df[col].rename(sym)
                    dfs.append(s)
            if dfs:
                combined = pd.concat(dfs, axis=1)
                combined.index = pd.to_datetime(combined.index)
                combined = combined.sort_index()
                panel[col] = combined.astype(np.float64)

        if not panel:
            return {"status": "no_data", "row_count": 0}

        # Compute technicals and zoo factors
        tech_df = self._compute_technical_indicators(panel)
        zoo_factors = self._compute_zoo_factors(panel)

        # Merge and persist
        import json

        try:
            from src.db.pool import init_pool, get_connection
            init_pool()

            row_count = 0
            with get_connection() as conn:
                with conn.cursor() as cur:
                    for _, row in tech_df.iterrows():
                        sym = row["symbol"]

                        # Extract per-symbol factor values from zoo
                        factor_json: dict[str, float] = {}
                        for aid, fdf in zoo_factors.items():
                            if sym in fdf.columns:
                                last_val = fdf[sym].dropna()
                                if len(last_val) > 0 and not np.isnan(last_val.iloc[-1]):
                                    factor_json[aid] = round(float(last_val.iloc[-1]), 6)

                        cur.execute(
                            """INSERT INTO vt_factor_daily_wide
                               (trade_date, symbol, close, volume, returns_1d, returns_5d, returns_20d,
                                volume_ratio, high_low_ratio, sma_20, sma_60, volatility_20d, rsi_14, factor_values)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                               ON CONFLICT (trade_date, symbol)
                               DO UPDATE SET close=EXCLUDED.close, volume=EXCLUDED.volume,
                                  returns_1d=EXCLUDED.returns_1d, factor_values=EXCLUDED.factor_values,
                                  etl_ts=now()""",
                            (
                                target_date, sym,
                                row.get("close"), row.get("volume"),
                                row.get("returns_1d"), row.get("returns_5d"), row.get("returns_20d"),
                                row.get("volume_ratio"), row.get("high_low_ratio"),
                                row.get("sma_20"), row.get("sma_60"),
                                row.get("volatility_20d"), row.get("rsi_14"),
                                json.dumps(factor_json),
                            ),
                        )
                        row_count += 1

            elapsed = round(time.monotonic() - start, 1)
            logger.info("Factor wide ETL complete: %d rows, %.1fs", row_count, elapsed)
            return {"status": "completed", "row_count": row_count, "elapsed_s": elapsed, "date": target_date}
        except Exception as e:
            logger.error("Factor wide ETL persist failed: %s", e)
            return {"status": "failed", "reason": str(e), "row_count": 0}
