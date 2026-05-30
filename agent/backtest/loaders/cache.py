"""PostgreSQL-based OHLCV cache layer.

Caches individual K-line bars in the project's existing PostgreSQL database,
keyed by (code, interval, bar_date).  Uses the shared connection pool from
``src.db.pool`` — no extra dependency.

Usage::

    from backtest.loaders.cache import query_cache, write_cache

    cached = query_cache("600519.SH", "1D", "2024-01-01", "2024-12-31")
    if cached is not None:
        # hit — use cached DataFrame
        ...

    write_cache("600519.SH", "1D", new_df)   # INSERT ... ON CONFLICT DO NOTHING
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd

logger = logging.getLogger(__name__)

# ── DDL (idempotent, auto-applied via init_database) ────────────────────────

CACHE_DDL = """
CREATE TABLE IF NOT EXISTS ohlcv_cache (
    code       VARCHAR(16) NOT NULL,
    interval   VARCHAR(8)  NOT NULL,
    bar_date   DATE        NOT NULL,
    open       DOUBLE PRECISION,
    high       DOUBLE PRECISION,
    low        DOUBLE PRECISION,
    close      DOUBLE PRECISION,
    volume     DOUBLE PRECISION,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (code, interval, bar_date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_code_intv
    ON ohlcv_cache(code, interval);

CREATE INDEX IF NOT EXISTS idx_ohlcv_updated
    ON ohlcv_cache(updated_at);
"""


def _get_connection():
    """Lazily import and return a PG connection from the shared pool."""
    from src.db.pool import get_connection
    return get_connection()


def query_cache(
    code: str,
    interval: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame | None:
    """Query cached OHLCV bars for *code* in *date_range*.

    Returns a DataFrame with columns [open, high, low, close, volume]
    indexed by bar_date, or ``None`` if the cache has no matching rows.
    """
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT bar_date, open, high, low, close, volume
                    FROM ohlcv_cache
                    WHERE code = %s
                      AND interval = %s
                      AND bar_date >= %s
                      AND bar_date <= %s
                    ORDER BY bar_date ASC
                    """,
                    (code, interval, start_date, end_date),
                )
                rows = cur.fetchall()
    except Exception:
        logger.debug("Cache query failed for %s/%s", code, interval, exc_info=True)
        return None

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=["bar_date", "open", "high", "low", "close", "volume"])
    df["bar_date"] = pd.to_datetime(df["bar_date"])
    df = df.set_index("bar_date")
    df.index.name = "trade_date"
    return df


def write_cache(code: str, interval: str, df: pd.DataFrame) -> int:
    """Write OHLCV bars into the cache (INSERT ... ON CONFLICT DO NOTHING).

    *df* must have columns [open, high, low, close, volume] and a datetime
    index (``trade_date``).

    Returns the number of rows actually inserted.
    """
    if df is None or df.empty:
        return 0

    # Ensure we have the expected columns
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        logger.warning("Cache write skipped for %s: missing columns %s", code, missing)
        return 0

    # Convert rows to list of tuples
    rows: list[tuple] = []
    for idx, row in df.iterrows():
        try:
            bar_date = idx.date() if isinstance(idx, (datetime, pd.Timestamp)) else date.fromisoformat(str(idx)[:10])
        except (ValueError, TypeError):
            continue
        rows.append((
            code,
            interval,
            bar_date,
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            float(row["volume"]),
        ))

    if not rows:
        return 0

    # Batch insert
    inserted = 0
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                from psycopg2.extras import execute_values
                execute_values(
                    cur,
                    """
                    INSERT INTO ohlcv_cache (code, interval, bar_date, open, high, low, close, volume)
                    VALUES %s
                    ON CONFLICT (code, interval, bar_date) DO NOTHING
                    """,
                    rows,
                    page_size=200,
                )
                inserted = cur.rowcount
    except Exception:
        logger.debug("Cache write failed for %s/%s", code, interval, exc_info=True)

    return inserted


def init_cache_table() -> None:
    """Execute the cache DDL (idempotent). Safe to call on every startup."""
    try:
        from src.db.pool import init_pool
        init_pool()
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(CACHE_DDL)
        logger.info("ohlcv_cache table ready")
    except Exception:
        logger.warning("Failed to initialise ohlcv_cache table", exc_info=True)
