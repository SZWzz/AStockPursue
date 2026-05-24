"""Paper trading repository – PostgreSQL CRUD for paper trading entities.

Uses the existing ``src.db.pool.get_connection()`` context manager.
All methods are synchronous (called from async routes via thread pool).

Ownership: every run is owned by a ``user_id``.  Callers MUST supply the
authenticated user's id so that users cannot access each other's runs.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class OwnershipError(Exception):
    """Raised when a caller tries to access a run belonging to another user."""


class PaperTradeRepository:
    """CRUD operations for paper trading runs, equity, positions, and trades."""

    # ── Run CRUD ──────────────────────────────────────────────────────

    def create_run(
        self,
        *,
        run_name: str,
        market: str,
        codes: list[str],
        interval: str,
        initial_capital: float,
        strategy_code: str,
        user_id: int,
        risk_config: dict | None = None,
    ) -> str:
        from src.db.pool import get_connection

        config = {
            "codes": codes,
            "interval": interval,
            "initial_capital": initial_capital,
        }
        risk = risk_config or {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vt_papertrading_runs
                        (user_id, run_name, market, config, risk_config,
                         strategy_code, current_capital)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        run_name,
                        market,
                        json.dumps(config, ensure_ascii=False),
                        json.dumps(risk, ensure_ascii=False),
                        strategy_code,
                        initial_capital,
                    ),
                )
                row = cur.fetchone()
                run_id = str(row[0])
        logger.info("Created paper trading run %s for user %s: %s", run_id, user_id, run_name)
        return run_id

    def get_run(self, run_id: str, *, user_id: int | None = None) -> dict | None:
        """Return run metadata.  Raises ``OwnershipError`` if *user_id* is
        supplied and the run belongs to a different user.
        """
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, run_name, market, status, config,
                           risk_config, strategy_code, tick_mode, state,
                           current_capital, start_time, last_bar_time,
                           error_message, created_at, updated_at
                    FROM vt_papertrading_runs
                    WHERE id = %s
                    """,
                    (run_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                d = self._row_to_dict(row)
                if user_id is not None and int(d.get("user_id", 0)) != user_id:
                    raise OwnershipError(
                        f"Run {run_id} belongs to user {d.get('user_id')}, not {user_id}"
                    )
                return d

    def list_runs(self, *, user_id: int, limit: int = 50) -> list[dict]:
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, run_name, market, status, config,
                           risk_config, strategy_code, tick_mode, state,
                           current_capital, start_time, last_bar_time,
                           error_message, created_at, updated_at
                    FROM vt_papertrading_runs
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                return [self._row_to_dict(r) for r in cur.fetchall()]

    def update_run(
        self,
        run_id: str,
        *,
        run_name: str | None = None,
        status: str | None = None,
        state: str | None = None,
        tick_mode: bool | None = None,
        current_capital: float | None = None,
        last_bar_time: Any | None = None,
        error_message: str | None = None,
        risk_config: dict | None = None,
        user_id: int | None = None,
    ) -> bool:
        """Update run fields.  Returns True if a row was updated.

        When *user_id* is supplied the update is scoped to that owner.
        """
        from src.db.pool import get_connection

        sets: list[str] = []
        params: list[Any] = []

        if run_name is not None:
            sets.append("run_name = %s")
            params.append(run_name)
        if status is not None:
            sets.append("status = %s")
            params.append(status)
        if state is not None:
            sets.append("state = %s")
            params.append(state)
        if tick_mode is not None:
            sets.append("tick_mode = %s")
            params.append(tick_mode)
        if current_capital is not None:
            sets.append("current_capital = %s")
            params.append(current_capital)
        if last_bar_time is not None:
            sets.append("last_bar_time = %s")
            params.append(last_bar_time)
        if error_message is not None:
            sets.append("error_message = %s")
            params.append(error_message)
        if risk_config is not None:
            sets.append("risk_config = %s")
            params.append(json.dumps(risk_config, ensure_ascii=False))

        if not sets:
            return False

        sets.append("updated_at = %s")
        now = datetime.now(timezone.utc)
        params.append(now)

        where = "id = %s"
        params.append(run_id)
        if user_id is not None:
            where += " AND user_id = %s"
            params.append(user_id)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE vt_papertrading_runs SET {', '.join(sets)} WHERE {where}",
                    params,
                )
                return cur.rowcount > 0

    def set_start_time(self, run_id: str) -> None:
        from src.db.pool import get_connection

        now = datetime.now(timezone.utc)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_papertrading_runs SET start_time = %s, status = 'running', error_message = '', updated_at = %s WHERE id = %s",
                    (now, now, run_id),
                )

    def mark_stopped_on_startup(self) -> None:
        """Mark all 'running' / 'paused' runs as 'stopped' after server restart."""
        from src.db.pool import get_connection

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE vt_papertrading_runs SET status = 'stopped', error_message = 'Server restarted', updated_at = %s WHERE status IN ('running', 'paused')",
                        (datetime.now(timezone.utc),),
                    )
                    if cur.rowcount > 0:
                        logger.info("Marked %s runs as stopped after restart", cur.rowcount)
        except Exception:
            pass  # table may not exist yet on first run

    def delete_run(self, run_id: str, *, user_id: int | None = None) -> bool:
        """Delete a run.  When *user_id* is supplied only deletes runs owned by that user."""
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                if user_id is not None:
                    cur.execute(
                        "DELETE FROM vt_papertrading_runs WHERE id = %s AND user_id = %s",
                        (run_id, user_id),
                    )
                else:
                    cur.execute("DELETE FROM vt_papertrading_runs WHERE id = %s", (run_id,))
                return cur.rowcount > 0

    # ── Equity ────────────────────────────────────────────────────────

    def save_equity_point(
        self,
        run_id: str,
        point_time: Any,
        equity: float,
        capital: float,
        unrealized: float,
        drawdown: float,
    ) -> None:
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vt_papertrading_equity
                        (run_id, point_time, equity, capital, unrealized, drawdown)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (run_id, point_time, equity, capital, unrealized, drawdown),
                )

    def get_equity(self, run_id: str, since: Any = None) -> list[dict]:
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                if since:
                    cur.execute(
                        """
                        SELECT point_time, equity, capital, unrealized, drawdown
                        FROM vt_papertrading_equity
                        WHERE run_id = %s AND point_time >= %s
                        ORDER BY point_time ASC
                        """,
                        (run_id, since),
                    )
                else:
                    cur.execute(
                        """
                        SELECT point_time, equity, capital, unrealized, drawdown
                        FROM vt_papertrading_equity
                        WHERE run_id = %s
                        ORDER BY point_time ASC
                        """,
                        (run_id,),
                    )
                return [
                    {
                        "point_time": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]),
                        "equity": float(r[1]),
                        "capital": float(r[2]),
                        "unrealized": float(r[3]),
                        "drawdown": float(r[4]),
                    }
                    for r in cur.fetchall()
                ]

    # ── Positions ─────────────────────────────────────────────────────

    def save_positions(self, run_id: str, positions: dict) -> None:
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM vt_papertrading_positions WHERE run_id = %s", (run_id,))
                for symbol, pos in positions.items():
                    cur.execute(
                        """
                        INSERT INTO vt_papertrading_positions
                            (run_id, symbol, direction, entry_price, entry_time,
                             size, leverage, entry_commission)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            run_id,
                            symbol,
                            pos.direction,
                            float(pos.entry_price),
                            pos.entry_time,
                            float(pos.size),
                            float(getattr(pos, "leverage", 1.0)),
                            float(getattr(pos, "entry_commission", 0.0)),
                        ),
                    )

    def get_positions(self, run_id: str) -> list[dict]:
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT symbol, direction, entry_price, entry_time,
                           size, leverage, entry_commission
                    FROM vt_papertrading_positions
                    WHERE run_id = %s
                    """,
                    (run_id,),
                )
                return [
                    {
                        "symbol": r[0],
                        "direction": r[1],
                        "entry_price": float(r[2]),
                        "entry_time": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                        "size": float(r[4]),
                        "leverage": float(r[5]),
                        "entry_commission": float(r[6]),
                    }
                    for r in cur.fetchall()
                ]

    # ── Trades ────────────────────────────────────────────────────────

    def save_trade(self, run_id: str, trade: Any) -> None:
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vt_papertrading_trades
                        (run_id, symbol, direction, entry_price, exit_price,
                         entry_time, exit_time, size, leverage, pnl, pnl_pct,
                         exit_reason, holding_bars, commission)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id,
                        trade.symbol,
                        trade.direction,
                        float(trade.entry_price),
                        float(trade.exit_price),
                        trade.entry_time,
                        trade.exit_time,
                        float(trade.size),
                        float(getattr(trade, "leverage", 1.0)),
                        float(trade.pnl),
                        float(trade.pnl_pct),
                        trade.exit_reason,
                        int(getattr(trade, "holding_bars", 0)),
                        float(getattr(trade, "commission", 0.0)),
                    ),
                )

    def get_trades(
        self, run_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        from src.db.pool import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, symbol, direction, entry_price, exit_price,
                           entry_time, exit_time, size, leverage, pnl, pnl_pct,
                           exit_reason, holding_bars, commission
                    FROM vt_papertrading_trades
                    WHERE run_id = %s
                    ORDER BY exit_time DESC
                    LIMIT %s OFFSET %s
                    """,
                    (run_id, limit, offset),
                )
                return [
                    {
                        "id": r[0],
                        "symbol": r[1],
                        "direction": r[2],
                        "entry_price": float(r[3]),
                        "exit_price": float(r[4]),
                        "entry_time": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
                        "exit_time": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                        "size": float(r[7]),
                        "leverage": float(r[8]),
                        "pnl": float(r[9]),
                        "pnl_pct": float(r[10]),
                        "exit_reason": r[11],
                        "holding_bars": r[12],
                        "commission": float(r[13]),
                    }
                    for r in cur.fetchall()
                ]

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: tuple) -> dict:
        cols = [
            "id", "user_id", "run_name", "market", "status", "config",
            "risk_config", "strategy_code", "tick_mode", "state",
            "current_capital", "start_time", "last_bar_time",
            "error_message", "created_at", "updated_at",
        ]
        d = dict(zip(cols, row))
        if isinstance(d.get("config"), str):
            d["config"] = json.loads(d["config"])
        if isinstance(d.get("risk_config"), str):
            d["risk_config"] = json.loads(d["risk_config"])
        for ts_col in ("start_time", "last_bar_time", "created_at", "updated_at"):
            if d.get(ts_col) and hasattr(d[ts_col], "isoformat"):
                d[ts_col] = d[ts_col].isoformat()
            elif d.get(ts_col):
                d[ts_col] = str(d[ts_col])
        d["id"] = str(d["id"])
        return d
