"""Strategy Version Control — diffs, history, rollback."""

from __future__ import annotations

import difflib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class VersionControlService:
    """Git-like version management for strategies, backed by PG."""

    def save_version(
        self,
        strategy_id: int,
        user_id: int,
        code: str,
        title: str = "",
        change_note: str = "",
    ) -> dict[str, Any]:
        """Save a new version for a strategy.  Computes diff from the previous version."""
        prev_code = self._get_latest_code(strategy_id)
        diff = ""
        if prev_code is not None and prev_code != code:
            diff = "\n".join(
                difflib.unified_diff(
                    prev_code.splitlines(keepends=True),
                    code.splitlines(keepends=True),
                    fromfile=f"v_{strategy_id}_prev",
                    tofile=f"v_{strategy_id}_new",
                    lineterm="",
                )
            )[:50000]  # cap at 50KB

        next_num = self._next_version_num(strategy_id)

        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            version_id = uuid.uuid4().hex[:12]
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO vt_strategy_versions
                           (id, strategy_id, user_id, version_num, code, title, change_note, diff_prev, code_size)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (version_id, strategy_id, user_id, next_num, code, title, change_note, diff, len(code)),
                    )
            logger.info("Saved version %d for strategy %d", next_num, strategy_id)
            return {"version_id": version_id, "version_num": next_num, "code_size": len(code)}
        except Exception as e:
            logger.error("Failed to save version: %s", e)
            raise

    def list_versions(self, strategy_id: int) -> list[dict[str, Any]]:
        """List all versions for a strategy (newest first)."""
        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT id, version_num, title, change_note, code_size,
                                  LENGTH(diff_prev) as diff_len, created_at
                           FROM vt_strategy_versions
                           WHERE strategy_id = %s
                           ORDER BY version_num DESC""",
                        (strategy_id,),
                    )
                    return [
                        {
                            "id": str(r[0]),
                            "version_num": r[1],
                            "title": r[2] or f"v{r[1]}",
                            "change_note": r[3] or "",
                            "code_size": r[4],
                            "diff_len": r[5],
                            "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                        }
                        for r in cur.fetchall()
                    ]
        except Exception:
            return []

    def get_version(self, strategy_id: int, version_num: int) -> dict[str, Any] | None:
        """Get a specific version with code and diff."""
        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT id, version_num, code, title, change_note, diff_prev, code_size, created_at
                           FROM vt_strategy_versions
                           WHERE strategy_id = %s AND version_num = %s""",
                        (strategy_id, version_num),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    return {
                        "id": str(row[0]),
                        "version_num": row[1],
                        "code": row[2],
                        "title": row[3] or f"v{row[1]}",
                        "change_note": row[4] or "",
                        "diff_prev": row[5] or "",
                        "code_size": row[6],
                        "created_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
                    }
        except Exception:
            return None

    def get_diff(self, strategy_id: int, from_version: int, to_version: int) -> str:
        """Get a unified diff between two versions."""
        v1 = self.get_version(strategy_id, from_version)
        v2 = self.get_version(strategy_id, to_version)
        if not v1 or not v2:
            return ""
        return "\n".join(
            difflib.unified_diff(
                v1["code"].splitlines(keepends=True),
                v2["code"].splitlines(keepends=True),
                fromfile=f"v{from_version}",
                tofile=f"v{to_version}",
                lineterm="",
            )
        )[:50000]

    def revert(self, strategy_id: int, user_id: int, version_num: int) -> dict[str, Any]:
        """Revert a strategy to a previous version (creates a new version)."""
        target = self.get_version(strategy_id, version_num)
        if target is None:
            raise ValueError(f"Version {version_num} not found")
        return self.save_version(
            strategy_id=strategy_id,
            user_id=user_id,
            code=target["code"],
            title=f"Revert to v{version_num}",
            change_note=f"Reverted from latest to v{version_num}",
        )

    def _get_latest_code(self, strategy_id: int) -> str | None:
        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT code FROM vt_strategy_versions WHERE strategy_id = %s ORDER BY version_num DESC LIMIT 1",
                        (strategy_id,),
                    )
                    row = cur.fetchone()
                    return row[0] if row else None
        except Exception:
            return None

    def _next_version_num(self, strategy_id: int) -> int:
        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COALESCE(MAX(version_num), 0) + 1 FROM vt_strategy_versions WHERE strategy_id = %s",
                        (strategy_id,),
                    )
                    return int(cur.fetchone()[0])
        except Exception:
            return 1
