"""PostgreSQL-backed indicator/strategy repository.

Drop-in replacement for the file-based IndicatorRepository.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.db.pool import get_connection
from src.lab.params import IndicatorParamsParser, StrategyConfigParser
from src.lab.storage.repository import _extract_meta_from_code

logger = logging.getLogger(__name__)


class PgIndicatorRepository:
    """PostgreSQL-backed indicator storage."""

    def __init__(self, user_id: int = 1):
        self.user_id = user_id

    # ── Indicators ────────────────────────────────────────────────────────

    def list(self) -> list[dict]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, name, description, params, strategy_config, created_at, updated_at "
                        "FROM vt_indicators WHERE user_id = %s ORDER BY updated_at DESC",
                        (self.user_id,),
                    )
                    return [
                        {
                            "id": str(r[0]), "name": r[1], "description": r[2] or "",
                            "params": r[3] if isinstance(r[3], list) else [],
                            "strategy_config": r[4] if isinstance(r[4], dict) else {},
                            "created_at": str(r[5]), "updated_at": str(r[6]),
                        }
                        for r in cur.fetchall()
                    ]
        except Exception as e:
            logger.error("Failed to list indicators: %s", e)
            return []

    def get(self, indicator_id: str) -> dict | None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, name, description, code, params, strategy_config, created_at, updated_at "
                        "FROM vt_indicators WHERE id = %s",
                        (indicator_id,),
                    )
                    r = cur.fetchone()
                    if not r:
                        return None
                    return {
                        "id": str(r[0]), "name": r[1], "description": r[2] or "",
                        "code": r[3], "params": r[4] if isinstance(r[4], list) else [],
                        "strategy_config": r[5] if isinstance(r[5], dict) else {},
                        "created_at": str(r[6]), "updated_at": str(r[7]),
                    }
        except Exception as e:
            logger.error("Failed to get indicator %s: %s", indicator_id, e)
            return None

    def get_code(self, indicator_id: str) -> str | None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT code FROM vt_indicators WHERE id = %s", (indicator_id,))
                    r = cur.fetchone()
                    return r[0] if r else None
        except Exception:
            logger.warning("Failed to get code for indicator %s: %s", indicator_id, exc_info=True)
            return None

    def save(self, code: str, indicator_id: str | None = None) -> dict:
        name, description = _extract_meta_from_code(code)
        params = IndicatorParamsParser.parse_params(code)
        strategy = StrategyConfigParser.parse(code)
        now = datetime.now(timezone.utc).isoformat()

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    if indicator_id:
                        cur.execute(
                            "UPDATE vt_indicators SET name=%s, description=%s, code=%s, params=%s, strategy_config=%s, updated_at=%s WHERE id=%s RETURNING id",
                            (name, description, code, json.dumps(params, ensure_ascii=False),
                             json.dumps(strategy, ensure_ascii=False), now, indicator_id),
                        )
                        row = cur.fetchone()
                        if row:
                            indicator_id = str(row[0])
                    else:
                        cur.execute(
                            "INSERT INTO vt_indicators (user_id, name, description, code, params, strategy_config, created_at, updated_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                            (self.user_id, name, description, code, json.dumps(params, ensure_ascii=False),
                             json.dumps(strategy, ensure_ascii=False), now, now),
                        )
                        indicator_id = str(cur.fetchone()[0])

            return {"id": indicator_id, "name": name, "description": description,
                    "param_count": len(params), "strategy_config": strategy,
                    "created_at": now, "updated_at": now}
        except Exception:
            logger.exception("Failed to save indicator")
            raise

    def delete(self, indicator_id: str) -> bool:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM vt_indicators WHERE id = %s", (indicator_id,))
                    return cur.rowcount > 0
        except Exception:
            logger.warning("Failed to delete indicator %s: %s", indicator_id, exc_info=True)
            return False

    def history(self, indicator_id: str) -> list[dict]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, change_message, created_at FROM vt_indicator_versions "
                        "WHERE indicator_id = %s ORDER BY created_at DESC",
                        (indicator_id,),
                    )
                    return [
                        {"commit_hash": str(r[0])[:8], "timestamp": str(r[2]), "message": r[1] or ""}
                        for r in cur.fetchall()
                    ]
        except Exception:
            logger.warning("Failed to load history for indicator %s: %s", indicator_id, exc_info=True)
            return []

    def rollback(self, indicator_id: str, version_id: str) -> dict | None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT code FROM vt_indicator_versions WHERE id = %s", (version_id,))
                    r = cur.fetchone()
                    if not r:
                        return None
                    old_code = r[0]
                    return self.save(code=old_code, indicator_id=indicator_id)
        except Exception:
            logger.warning("Failed to rollback indicator %s to version %s: %s", indicator_id, version_id, exc_info=True)
            return None

    # ── Strategies ─────────────────────────────────────────────────────────

    def list_strategies(self) -> list[dict]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, name, description, code, created_at, updated_at "
                        "FROM vt_strategies WHERE user_id = %s ORDER BY updated_at DESC",
                        (self.user_id,),
                    )
                    return [
                        {"id": str(r[0]), "name": r[1], "description": r[2] or "",
                         "code": r[3] or "", "created_at": str(r[4]), "updated_at": str(r[5])}
                        for r in cur.fetchall()
                    ]
        except Exception:
            logger.warning("Failed to list strategies: %s", exc_info=True)
            return []

    def get_strategy(self, strategy_id: str) -> dict | None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, name, description, code, created_at, updated_at FROM vt_strategies WHERE id = %s",
                        (strategy_id,),
                    )
                    r = cur.fetchone()
                    if not r:
                        return None
                    return {"id": str(r[0]), "name": r[1], "description": r[2] or "",
                            "code": r[3], "created_at": str(r[4]), "updated_at": str(r[5])}
        except Exception:
            logger.warning("Failed to get strategy %s: %s", strategy_id, exc_info=True)
            return None

    def save_strategy(self, code: str, strategy_id: str | None = None, name: str = "") -> dict:
        if not name:
            from src.lab.storage.repository import _extract_meta_from_code as _em
            name, description = _em(code)
            # Fallback: extract from class name or use timestamp
            if not name:
                import re
                m = re.search(r'class\s+(\w+)\s*[:\(]', code)
                if m:
                    name = m.group(1)
                else:
                    name = f"Strategy {datetime.now().strftime('%m-%d %H:%M')}"
        else:
            description = ""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    if strategy_id:
                        cur.execute(
                            "UPDATE vt_strategies SET name=%s, description=%s, code=%s, updated_at=%s WHERE id=%s RETURNING id",
                            (name, description, code, now, strategy_id),
                        )
                    else:
                        cur.execute(
                            "INSERT INTO vt_strategies (user_id, name, description, code, created_at, updated_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                            (self.user_id, name, description, code, now, now),
                        )
                    row = cur.fetchone()
                    return {"id": str(row[0]), "name": name, "description": description,
                            "created_at": now, "updated_at": now}
        except Exception:
            logger.warning("Failed to save strategy %s: %s", strategy_id or name, exc_info=True)
            raise

    def delete_strategy(self, strategy_id: str) -> bool:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM vt_strategies WHERE id = %s", (strategy_id,))
                    return cur.rowcount > 0
        except Exception:
            logger.warning("Failed to delete strategy %s: %s", strategy_id, exc_info=True)
            return False
