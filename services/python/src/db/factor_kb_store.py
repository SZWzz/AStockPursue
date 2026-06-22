"""FactorKB PostgreSQL/pgvector persistence adapter — Phase C P3.

Bridges the in-memory FactorKnowledgeBase to PostgreSQL with pgvector
semantic search.  Falls back gracefully to in-memory-only mode when
PostgreSQL is unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class FactorKBStore:
    """PostgreSQL-backed FactorKB persistence with pgvector search.

    Graceful degradation: if PostgreSQL is unavailable, all methods
    become no-ops and the caller should use the in-memory KB directly.
    """

    def __init__(self, dsn: str = "") -> None:
        self._dsn = dsn
        self._conn = None
        self._available = False
        if HAS_PSYCOPG2 and dsn:
            self._connect()

    def _connect(self) -> None:
        """Establish a PostgreSQL connection for FactorKB persistence.

        Uses the DSN provided at construction time.  On failure the store
        remains in degraded (in-memory-only) mode — all public methods
        gracefully become no-ops.

        Sets ``self._available`` to indicate whether the connection is
        usable.
        """
        try:
            self._conn = psycopg2.connect(self._dsn)
            self._conn.autocommit = False
            self._available = True
            logger.info("FactorKBStore connected to PostgreSQL")
        except Exception as exc:
            logger.debug("FactorKBStore unavailable (PG not reachable): %s", exc)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available and self._conn is not None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_entry(self, entry_dict: dict[str, Any]) -> bool:
        """Insert or update a factor entry in PostgreSQL using upsert logic.

        Uses ``ON CONFLICT (formula_hash) DO UPDATE`` so that re-mining
        the same formula updates the existing row rather than creating a
        duplicate.  On conflict the row's ``last_validated_at``,
        ``test_ic``, and ``status`` are refreshed while existing embedding
        vectors are preserved via ``COALESCE`` (new embeddings only
        overwrite if non-null).  This ensures pgvector semantic search
        (``description_embedding`` / ``formula_embedding`` columns)
        continues to work across updates.

        Args:
            entry_dict: Factor entry as a dict (from ``FactorEntry.to_dict()``
                or the in-memory KB).  Must include ``formula_hash``,
                ``alpha_id``, and all metric columns.

        Returns:
            ``True`` if the upsert succeeded, ``False`` on any error
            (connection lost, constraint violation, etc.).
        """
        if not self.available:
            return False
        try:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT INTO vt_factor_knowledge (
                    alpha_id, formula_hash, name, formula, normalized_formula,
                    expression_json, theme, semantic_tags, source, source_prompt,
                    economic_rationale, data_source_version,
                    train_ic, test_ic, test_ir, sharpe, max_drawdown,
                    ic_decay_halflife, oos_ic_per_window,
                    orthogonality_score, max_corr_with_core,
                    status, discovered_at, complexity, user_id,
                    description_embedding, formula_embedding
                ) VALUES (
                    %(alpha_id)s, %(formula_hash)s, %(name)s, %(formula)s, %(normalized_formula)s,
                    %(expression_json)s, %(theme)s, %(semantic_tags)s, %(source)s, %(source_prompt)s,
                    %(economic_rationale)s, %(data_source_version)s,
                    %(train_ic)s, %(test_ic)s, %(test_ir)s, %(sharpe)s, %(max_drawdown)s,
                    %(ic_decay_halflife)s, %(oos_ic_per_window)s,
                    %(orthogonality_score)s, %(max_corr_with_core)s,
                    %(status)s, %(discovered_at)s, %(complexity)s, %(user_id)s,
                    %(description_embedding)s, %(formula_embedding)s
                )
                ON CONFLICT (formula_hash) DO UPDATE SET
                    last_validated_at = NOW(),
                    test_ic = EXCLUDED.test_ic,
                    status = EXCLUDED.status,
                    description_embedding = COALESCE(EXCLUDED.description_embedding, vt_factor_knowledge.description_embedding),
                    formula_embedding = COALESCE(EXCLUDED.formula_embedding, vt_factor_knowledge.formula_embedding)
            """, self._serialize_entry(entry_dict))
            self._conn.commit()
            return True
        except Exception as exc:
            logger.debug("FactorKBStore save_entry failed: %s", exc)
            self._conn.rollback()
            return False

    def load_all_entries(self) -> list[dict[str, Any]]:
        """Load all non-archived factor entries from PostgreSQL.

        Excludes entries with ``status = 'archived'`` and returns rows
        ordered by ``discovered_at DESC`` so that the newest factors
        appear first.

        Returns:
            List of factor entry dicts ready for ``FactorEntry.from_dict()``.
            Returns an empty list if the store is unavailable or the
            query fails.
        """
        if not self.available:
            return []
        try:
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT * FROM vt_factor_knowledge
                WHERE status != 'archived'
                ORDER BY discovered_at DESC
            """)
            rows = cur.fetchall()
            return [self._deserialize_entry(dict(r)) for r in rows]
        except Exception as exc:
            logger.debug("FactorKBStore load_all_entries failed: %s", exc)
            return []

    def update_status(self, alpha_id: str, new_status: str, reason: str = "") -> bool:
        """Update a factor's lifecycle status in PostgreSQL.

        When transitioning to ``'archived'`` the ``archived_at`` timestamp
        and ``archived_reason`` are set automatically.  Other transitions
        leave those columns unchanged.

        Args:
            alpha_id: Unique factor identifier.
            new_status: Target lifecycle status (e.g. ``'approved'``,
                ``'production'``, ``'archived'``).
            reason: Human-readable reason for the transition (stored in
                ``archived_reason`` on archive).

        Returns:
            ``True`` if at least one row was updated, ``False`` if the
            factor was not found or the store is unavailable.
        """
        if not self.available:
            return False
        try:
            cur = self._conn.cursor()
            cur.execute("""
                UPDATE vt_factor_knowledge
                SET status = %s,
                    archived_at = CASE WHEN %s = 'archived' THEN NOW() ELSE archived_at END,
                    archived_reason = %s
                WHERE alpha_id = %s
            """, (new_status, new_status, reason, alpha_id))
            self._conn.commit()
            return cur.rowcount > 0
        except Exception as exc:
            logger.debug("FactorKBStore update_status failed: %s", exc)
            self._conn.rollback()
            return False

    # ------------------------------------------------------------------
    # pgvector semantic search
    # ------------------------------------------------------------------

    def search_by_embedding(
        self,
        query_text: str,
        top_k: int = 10,
        embedding_fn=None,
    ) -> list[dict[str, Any]]:
        """Natural language factor search using pgvector cosine similarity.

        Args:
            query_text: Natural language query (e.g. "低换手率价值反转因子").
            top_k: Max results to return.
            embedding_fn: Function (text) -> list[float]. Uses text-embedding-3-small
                dimension 1536. If None, falls back to tag-based search.

        Returns:
            List of factor entry dicts sorted by similarity descending.
        """
        if not self.available:
            return []

        if embedding_fn is None:
            # Fallback: use tag-based search via SQL
            return self._search_by_tags(query_text, top_k)

        try:
            embedding = embedding_fn(query_text)
            embedding_str = f"[{','.join(str(e) for e in embedding)}]"

            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT alpha_id, name, formula, theme, economic_rationale,
                       train_ic, test_ic, status,
                       1 - (description_embedding <=> %s::vector) AS similarity
                FROM vt_factor_knowledge
                WHERE status IN ('approved', 'paper_trading', 'production')
                  AND description_embedding IS NOT NULL
                ORDER BY description_embedding <=> %s::vector
                LIMIT %s
            """, (embedding_str, embedding_str, top_k))

            return [self._deserialize_entry(dict(r)) for r in cur.fetchall()]
        except Exception as exc:
            logger.debug("FactorKBStore pgvector search failed: %s", exc)
            return self._search_by_tags(query_text, top_k)

    def _search_by_tags(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Fallback search: match against semantic_tags."""
        if not self.available:
            return []
        try:
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            query_lower = query.lower()
            cur.execute("""
                SELECT *, array_length(array(
                    SELECT unnest(semantic_tags)
                    INTERSECT SELECT unnest(string_to_array(%s, ' '))
                ), 1) AS tag_overlap
                FROM vt_factor_knowledge
                WHERE status IN ('approved', 'paper_trading', 'production')
                  AND EXISTS (
                      SELECT 1 FROM unnest(semantic_tags) t
                      WHERE lower(t) LIKE '%%' || %s || '%%'
                  )
                ORDER BY tag_overlap DESC NULLS LAST, abs(test_ic) DESC
                LIMIT %s
            """, (query_lower, query_lower, top_k))
            return [self._deserialize_entry(dict(r)) for r in cur.fetchall()]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Activity log (for Dashboard)
    # ------------------------------------------------------------------

    def log_activity(self, event_type: str, user_id: int, data: dict[str, Any]) -> bool:
        """Write an activity event for the Dashboard 'Recent Activity' feed."""
        if not self.available:
            return False
        try:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT INTO vt_activity_log (user_id, event_type, data, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (user_id, event_type, json.dumps(data, default=str)))
            self._conn.commit()
            return True
        except Exception as exc:
            logger.debug("FactorKBStore log_activity failed: %s", exc)
            self._conn.rollback()
            return False

    def get_recent_activity(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent activity events for the Dashboard."""
        if not self.available:
            return []
        try:
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT event_type, data, created_at
                FROM vt_activity_log
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _serialize_entry(self, d: dict[str, Any]) -> dict[str, Any]:
        """Convert FactorEntry dict to PG-compatible params."""
        # [P0-06 fix] Include embedding vectors for pgvector semantic search.
        desc_emb = d.get("description_embedding")
        form_emb = d.get("formula_embedding")
        return {
            "alpha_id": d.get("alpha_id", ""),
            "formula_hash": d.get("formula_hash", ""),
            "name": d.get("name", ""),
            "formula": d.get("formula", ""),
            "normalized_formula": d.get("normalized_formula", ""),
            "expression_json": json.dumps(d.get("expression_json", {})),
            "theme": d.get("theme", []),
            "semantic_tags": d.get("semantic_tags", []),
            "source": d.get("source", ""),
            "source_prompt": d.get("source_prompt", ""),
            "economic_rationale": d.get("economic_rationale", ""),
            "data_source_version": d.get("data_source_version", ""),
            "train_ic": d.get("train_ic", 0.0),
            "test_ic": d.get("test_ic", 0.0),
            "test_ir": d.get("test_ir", 0.0),
            "sharpe": d.get("sharpe", 0.0),
            "max_drawdown": d.get("max_drawdown", 0.0),
            "ic_decay_halflife": d.get("ic_decay_halflife"),
            "oos_ic_per_window": d.get("oos_ic_per_window", []),
            "orthogonality_score": d.get("orthogonality_score", 0.0),
            "max_corr_with_core": d.get("max_corr_with_core", 0.0),
            "status": d.get("status", "discovered"),
            "discovered_at": d.get("discovered_at", "now"),
            "complexity": d.get("complexity", 0),
            "user_id": d.get("user_id", 1),
            "description_embedding": _embedding_to_pg_vector(desc_emb) if desc_emb else None,
            "formula_embedding": _embedding_to_pg_vector(form_emb) if form_emb else None,
        }

    def _deserialize_entry(self, d: dict[str, Any]) -> dict[str, Any]:
        """Convert PG row to FactorEntry-compatible dict."""
        expr_json = d.get("expression_json")
        if isinstance(expr_json, str):
            expr_json = json.loads(expr_json)
        return {
            **d,
            "expression_json": expr_json,
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._available = False


def _embedding_to_pg_vector(embedding) -> str | None:
    """Convert a Python list/array to a pgvector-compatible string literal.

    pgvector accepts ``'[0.1, 0.2, ...]'`` as a vector literal.
    Returns None if the input is empty or invalid.
    """
    if embedding is None:
        return None
    if isinstance(embedding, str):
        return embedding  # already formatted
    try:
        return f"[{','.join(str(float(e)) for e in embedding)}]"
    except (TypeError, ValueError):
        return None
