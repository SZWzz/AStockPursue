"""Store and retrieve alpha bench results in PostgreSQL."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from src.db.pool import get_connection

logger = logging.getLogger(__name__)


def save_bench_result(
    user_id: int,
    zoo: str,
    universe: str,
    period: str,
    top: int,
    result: dict[str, Any],
) -> str | None:
    """Persist a completed bench run.  Returns the run UUID or None on failure."""
    run_id = str(uuid.uuid4())

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO vt_alpha_bench_runs
                       (id, user_id, zoo, universe, period, top,
                        alive, reversed, dead, n_alphas_tested, n_skipped,
                        by_theme, top5_by_ir, dead_examples, meta, wall_seconds)
                       VALUES (%s, %s, %s, %s, %s, %s,
                               %s, %s, %s, %s, %s,
                               %s, %s, %s, %s, %s)""",
                    (
                        run_id,
                        user_id,
                        zoo,
                        universe,
                        period,
                        top,
                        result.get("alive", 0),
                        result.get("reversed", 0),
                        result.get("dead", 0),
                        result.get("n_alphas_tested", 0),
                        result.get("n_skipped", 0),
                        json.dumps(result.get("by_theme", {}), ensure_ascii=False),
                        json.dumps(result.get("top5_by_ir", []), ensure_ascii=False),
                        json.dumps(result.get("dead_examples", []), ensure_ascii=False),
                        json.dumps(result.get("meta", {}), ensure_ascii=False),
                        result.get("wall_seconds"),
                    ),
                )
        return run_id
    except Exception:
        logger.exception("Failed to save alpha bench result")
        return None


def list_bench_results(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return recent bench runs for a user (summary only, no JSONB detail)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, zoo, universe, period, top,
                              alive, reversed, dead, n_alphas_tested, n_skipped,
                              wall_seconds, created_at
                       FROM vt_alpha_bench_runs
                       WHERE user_id = %s
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s""",
                    (user_id, limit, offset),
                )
                rows = cur.fetchall()
                return [
                    {
                        "run_id": r[0],
                        "zoo": r[1],
                        "universe": r[2],
                        "period": r[3],
                        "top": r[4],
                        "alive": r[5],
                        "reversed": r[6],
                        "dead": r[7],
                        "n_alphas_tested": r[8],
                        "n_skipped": r[9],
                        "wall_seconds": r[10],
                        "created_at": str(r[11]) if r[11] else "",
                    }
                    for r in rows
                ]
    except Exception:
        logger.exception("Failed to list alpha bench results")
        return []


def get_bench_result(run_id: str) -> dict[str, Any] | None:
    """Return full bench run detail including JSONB columns."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, user_id, zoo, universe, period, top,
                              alive, reversed, dead, n_alphas_tested, n_skipped,
                              by_theme, top5_by_ir, dead_examples, meta, wall_seconds, created_at
                       FROM vt_alpha_bench_runs
                       WHERE id = %s""",
                    (run_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                def _json(v: Any) -> Any:
                    if isinstance(v, str):
                        try:
                            return json.loads(v)
                        except (json.JSONDecodeError, TypeError):
                            return v
                    return v

                return {
                    "run_id": row[0],
                    "user_id": row[1],
                    "zoo": row[2],
                    "universe": row[3],
                    "period": row[4],
                    "top": row[5],
                    "alive": row[6],
                    "reversed": row[7],
                    "dead": row[8],
                    "n_alphas_tested": row[9],
                    "n_skipped": row[10],
                    "by_theme": _json(row[11]),
                    "top5_by_ir": _json(row[12]),
                    "dead_examples": _json(row[13]),
                    "meta": _json(row[14]),
                    "wall_seconds": row[15],
                    "created_at": str(row[16]) if row[16] else "",
                }
    except Exception:
        logger.exception("Failed to get alpha bench result")
        return None


def delete_bench_result(run_id: str) -> bool:
    """Delete a bench run by id. Returns True on success."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM vt_alpha_bench_runs WHERE id = %s", (run_id,))
        return True
    except Exception:
        logger.exception("Failed to delete alpha bench result")
        return False
