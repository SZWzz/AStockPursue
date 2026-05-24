"""Store and retrieve backtest results in PostgreSQL."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from src.db.pool import get_connection

logger = logging.getLogger(__name__)


def save_backtest_result(
    run_name: str = "",
    run_type: str = "strategy",
    config: dict | None = None,
    metrics: dict | None = None,
    equity_curve: list[dict] | None = None,
    trades: list[dict] | None = None,
    status: str = "success",
    error_message: str = "",
    user_id: int = 1,
) -> str:
    """Save a backtest run and its results to PostgreSQL.

    Returns the run UUID.
    """
    run_id = str(uuid.uuid4())

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                import json

                cur.execute(
                    """INSERT INTO vt_backtest_runs (id, user_id, run_name, run_type, config, metrics, status, error_message)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        run_id,
                        user_id,
                        run_name,
                        run_type,
                        json.dumps(config or {}, ensure_ascii=False),
                        json.dumps(metrics or {}, ensure_ascii=False),
                        status,
                        error_message,
                    ),
                )

                if equity_curve:
                    _insert_equity(cur, run_id, equity_curve)

                if trades:
                    _insert_trades(cur, run_id, trades)

        logger.info("Backtest saved: %s (%s trades, %s equity points)",
                     run_id, len(trades or []), len(equity_curve or []))
    except Exception as e:
        logger.error("Failed to save backtest result: %s", e)
        raise

    return run_id


def _insert_equity(cur, run_id: str, equity: list[dict]) -> None:
    from psycopg2.extras import execute_values

    rows = [
        (run_id, p.get("time"), p.get("equity"), p.get("drawdown"))
        for p in equity
    ]
    execute_values(
        cur,
        "INSERT INTO vt_backtest_equity (run_id, point_time, equity, drawdown) VALUES %s",
        rows,
        template="(%s, %s::timestamptz, %s, %s)",
    )


def _insert_trades(cur, run_id: str, trades: list[dict]) -> None:
    from psycopg2.extras import execute_values

    rows = [
        (run_id, t.get("symbol", ""), t.get("entry_time"), t.get("exit_time"),
         t.get("side", ""), t.get("pnl"), t.get("return_pct"))
        for t in trades
    ]
    execute_values(
        cur,
        "INSERT INTO vt_backtest_trades (run_id, symbol, entry_time, exit_time, side, pnl, return_pct) VALUES %s",
        rows,
        template="(%s, %s, %s::timestamptz, %s::timestamptz, %s, %s, %s)",
    )


def list_backtest_runs(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """List recent backtest runs."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, run_name, run_type, metrics, status, created_at
                       FROM vt_backtest_runs
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s""",
                    (limit, offset),
                )
                return [
                    {
                        "id": r[0],
                        "run_name": r[1],
                        "run_type": r[2],
                        "metrics": r[3] if isinstance(r[3], dict) else {},
                        "status": r[4],
                        "created_at": str(r[5]),
                    }
                    for r in cur.fetchall()
                ]
    except Exception as e:
        logger.error("Failed to list backtest runs: %s", e)
        raise


def get_backtest_run(run_id: str) -> dict[str, Any] | None:
    """Get a single backtest run with equity and trades."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, run_name, run_type, config, metrics, status, error_message, created_at FROM vt_backtest_runs WHERE id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                result = {
                    "id": row[0],
                    "run_name": row[1],
                    "run_type": row[2],
                    "config": row[3] if isinstance(row[3], dict) else {},
                    "metrics": row[4] if isinstance(row[4], dict) else {},
                    "status": row[5],
                    "error_message": row[6] or "",
                    "created_at": str(row[7]),
                }

                # Load equity
                cur.execute(
                    "SELECT point_time, equity, drawdown FROM vt_backtest_equity WHERE run_id = %s ORDER BY point_time",
                    (run_id,),
                )
                result["equity_curve"] = [
                    {"time": str(r[0]), "equity": r[1], "drawdown": r[2]}
                    for r in cur.fetchall()
                ]

                # Load trades
                cur.execute(
                    "SELECT symbol, entry_time, exit_time, side, pnl, return_pct FROM vt_backtest_trades WHERE run_id = %s",
                    (run_id,),
                )
                result["trades"] = [
                    {"symbol": r[0], "entry_time": str(r[1]), "exit_time": str(r[2]),
                     "side": r[3], "pnl": r[4], "return_pct": r[5]}
                    for r in cur.fetchall()
                ]

                return result
    except Exception as e:
        logger.error("Failed to get backtest run %s: %s", run_id, e)
        raise


def delete_backtest_run(run_id: str) -> bool:
    """Delete a backtest run. Cascade deletes equity and trades."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM vt_backtest_runs WHERE id = %s", (run_id,))
                deleted = cur.rowcount > 0
        return deleted
    except Exception as e:
        logger.error("Failed to delete backtest run %s: %s", run_id, e)
        raise
