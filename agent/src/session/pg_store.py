"""PostgreSQL-backed session store.

Drop-in replacement for the file-based SessionStore. All session/message/attempt
data is stored in vt_sessions / vt_messages / vt_attempts tables.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.db.pool import get_connection
from src.session.models import Attempt, AttemptStatus, Message, Session, SessionStatus

logger = logging.getLogger(__name__)


class PgSessionStore:
    """PostgreSQL session persistence."""

    # ── Sessions ───────────────────────────────────────────────────────────

    def create_session(self, session: Session) -> Session:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO vt_sessions (id, user_id, title, status, config, created_at, updated_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            session.session_id,
                            1,  # default user
                            session.title,
                            session.status.value if hasattr(session.status, "value") else str(session.status),
                            json.dumps(session.config, ensure_ascii=False),
                            session.created_at,
                            session.updated_at,
                        ),
                    )
        except Exception as e:
            logger.exception("Failed to create session %s", session.session_id)
            raise
        return session

    def get_session(self, session_id: str) -> Session | None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, title, status, config, created_at, updated_at, "
                        "(SELECT id FROM vt_attempts WHERE session_id = vt_sessions.id ORDER BY created_at DESC LIMIT 1) "
                        "FROM vt_sessions WHERE id = %s",
                        (session_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    return Session(
                        session_id=row[0],
                        title=row[1] or "",
                        status=SessionStatus(row[2]) if row[2] else SessionStatus.ACTIVE,
                        config=row[3] if isinstance(row[3], dict) else {},
                        created_at=str(row[4]) if row[4] else "",
                        updated_at=str(row[5]) if row[5] else "",
                        last_attempt_id=row[6] or None,
                    )
        except Exception as e:
            logger.exception("Failed to get session %s", session_id)
            return None

    def update_session(self, session: Session) -> None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE vt_sessions SET title=%s, status=%s, config=%s, updated_at=%s WHERE id=%s",
                        (
                            session.title,
                            session.status.value if hasattr(session.status, "value") else str(session.status),
                            json.dumps(session.config, ensure_ascii=False),
                            session.updated_at,
                            session.session_id,
                        ),
                    )
        except Exception as e:
            logger.exception("Failed to update session %s", session.session_id)

    def delete_session(self, session_id: str) -> bool:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM vt_sessions WHERE id = %s", (session_id,))
                    return cur.rowcount > 0
        except Exception as e:
            logger.exception("Failed to delete session %s", session_id)
            return False

    def list_sessions(self, limit: int = 50) -> list[Session]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, title, status, config, created_at, updated_at FROM vt_sessions "
                        "ORDER BY updated_at DESC NULLS LAST LIMIT %s",
                        (limit,),
                    )
                    return [
                        Session(
                            session_id=r[0], title=r[1] or "",
                            status=SessionStatus(r[2]) if r[2] else SessionStatus.ACTIVE,
                            config=r[3] if isinstance(r[3], dict) else {},
                            created_at=str(r[4]) if r[4] else "",
                            updated_at=str(r[5]) if r[5] else "",
                        )
                        for r in cur.fetchall()
                    ]
        except Exception as e:
            logger.exception("Failed to list sessions")
            return []

    # ── Messages ───────────────────────────────────────────────────────────

    def append_message(self, message: Message) -> None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO vt_messages (id, session_id, role, content, linked_attempt_id, metadata, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            message.message_id,
                            message.session_id,
                            message.role,
                            message.content,
                            getattr(message, "linked_attempt_id", None),
                            json.dumps(getattr(message, "metadata", {}) or {}, ensure_ascii=False),
                            message.created_at,
                        ),
                    )
        except Exception as e:
            logger.exception("Failed to append message %s", message.message_id)

    def get_messages(self, session_id: str, limit: int = 100) -> list[Message]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, session_id, role, content, linked_attempt_id, metadata, created_at "
                        "FROM vt_messages WHERE session_id = %s ORDER BY created_at ASC "
                        "LIMIT %s",
                        (session_id, limit),
                    )
                    return [
                        Message(
                            message_id=r[0], session_id=r[1], role=r[2],
                            content=r[3], linked_attempt_id=r[4],
                            metadata=r[5] if isinstance(r[5], dict) else {},
                            created_at=str(r[6]) if r[6] else "",
                        )
                        for r in cur.fetchall()
                    ]
        except Exception as e:
            logger.exception("Failed to get messages for session %s", session_id)
            return []

    # ── Attempts ───────────────────────────────────────────────────────────

    def create_attempt(self, attempt: Attempt) -> Attempt:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO vt_attempts (id, session_id, parent_attempt_id, status, prompt, run_dir, summary, react_trace, metrics, error, created_at, completed_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            attempt.attempt_id,
                            attempt.session_id,
                            attempt.parent_attempt_id,
                            attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status),
                            attempt.prompt,
                            attempt.run_dir or "",
                            attempt.summary,
                            json.dumps(attempt.react_trace, ensure_ascii=False),
                            json.dumps(attempt.metrics or {}, ensure_ascii=False),
                            attempt.error,
                            attempt.created_at,
                            attempt.completed_at,
                        ),
                    )
        except Exception as e:
            logger.exception("Failed to create attempt %s", attempt.attempt_id)
            raise
        return attempt

    def get_attempt(self, session_id: str, attempt_id: str) -> Attempt | None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, session_id, parent_attempt_id, status, prompt, run_dir, summary, react_trace, metrics, error, created_at, completed_at "
                        "FROM vt_attempts WHERE id = %s AND session_id = %s",
                        (attempt_id, session_id),
                    )
                    r = cur.fetchone()
                    if not r:
                        return None
                    return Attempt(
                        attempt_id=r[0], session_id=r[1], parent_attempt_id=r[2],
                        status=AttemptStatus(r[3]) if r[3] else AttemptStatus.PENDING,
                        prompt=r[4] or "", run_dir=r[5] or None, summary=r[6],
                        react_trace=r[7] if isinstance(r[7], list) else [],
                        metrics=r[8] if isinstance(r[8], dict) else {},
                        error=r[9], created_at=str(r[10]) if r[10] else "",
                        completed_at=str(r[11]) if r[11] else None,
                    )
        except Exception as e:
            logger.exception("Failed to get attempt %s", attempt_id)
            return None

    def update_attempt(self, attempt: Attempt) -> None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE vt_attempts SET status=%s, run_dir=%s, summary=%s, react_trace=%s, metrics=%s, error=%s, completed_at=%s
                           WHERE id=%s""",
                        (
                            attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status),
                            attempt.run_dir or "",
                            attempt.summary,
                            json.dumps(attempt.react_trace, ensure_ascii=False),
                            json.dumps(attempt.metrics or {}, ensure_ascii=False),
                            attempt.error,
                            attempt.completed_at,
                            attempt.attempt_id,
                        ),
                    )
        except Exception as e:
            logger.exception("Failed to update attempt %s", attempt.attempt_id)

    # ── Search ─────────────────────────────────────────────────────────────

    def search_messages(self, query: str, limit: int = 20) -> list[Message]:
        """Full-text search across message content using PG tsvector."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT m.id, m.session_id, m.role, m.content, m.linked_attempt_id, m.metadata, m.created_at
                           FROM vt_messages m
                           WHERE to_tsvector('english', m.content) @@ plainto_tsquery('english', %s)
                           ORDER BY m.created_at DESC LIMIT %s""",
                        (query, limit),
                    )
                    return [
                        Message(
                            message_id=r[0], session_id=r[1], role=r[2],
                            content=r[3], linked_attempt_id=r[4],
                            metadata=r[5] if isinstance(r[5], dict) else {},
                            created_at=str(r[6]) if r[6] else "",
                        )
                        for r in cur.fetchall()
                    ]
        except Exception as e:
            logger.exception("Search failed for query: %s", query)
            return []
