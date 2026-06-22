"""Integration tests for src.db.factor_kb_store — FactorKBStore persistence layer.

Tests FactorKBStore with mock psycopg2 connections.  Verifies SQL, params,
serialisation, deserialisation, error paths, and graceful degradation.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(mock_cursor=None, dsn="postgresql://test:test@localhost/testdb"):
    """Create a FactorKBStore wired to the given mock cursor.

    Args:
        mock_cursor: If provided, wires ``pg_conn.cursor()`` to return this
            cursor so that test assertions on ``cursor.execute`` work.
        dsn: PostgreSQL DSN for the store.
    """
    sys.modules["psycopg2"].connect.reset_mock()
    mock_pg_conn = MagicMock(name="factor_kb_conn")
    mock_pg_conn.autocommit = False
    if mock_cursor is not None:
        mock_pg_conn.cursor.return_value = mock_cursor
    sys.modules["psycopg2"].connect.return_value = mock_pg_conn

    from src.db.factor_kb_store import FactorKBStore

    store = FactorKBStore(dsn=dsn)
    return store, mock_pg_conn


# ---------------------------------------------------------------------------
# Constructor & availability
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestFactorKBStoreConstruction:
    def test_empty_dsn_available_false(self):
        """FactorKBStore with empty DSN: available returns False (disabled mode)."""
        sys.modules["psycopg2"].connect.reset_mock()
        from src.db.factor_kb_store import FactorKBStore

        store = FactorKBStore(dsn="")
        assert store.available is False

    def test_valid_dsn_available_true_after_connect(self):
        """FactorKBStore with valid DSN: available returns True after connect."""
        store, _ = _make_store()
        assert store.available is True


# ---------------------------------------------------------------------------
# save_entry
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSaveEntry:
    def test_saves_entry_returns_true(self, mock_conn):
        """save_entry saves entry dict, returns True."""
        conn, cursor = mock_conn
        store, _ = _make_store(mock_cursor=cursor)

        entry = {
            "alpha_id": "alpha-001",
            "formula_hash": "abc123",
            "name": "Test Factor",
            "formula": "close/MA(close,20)",
            "normalized_formula": "close/MA(close,20)",
            "expression_json": {"type": "div"},
            "theme": ["momentum"],
            "semantic_tags": ["momentum", "price"],
            "source": "mining",
            "source_prompt": "Find momentum factors",
            "economic_rationale": "Momentum persists",
            "data_source_version": "v1",
            "train_ic": 0.05, "test_ic": 0.04, "test_ir": 1.2,
            "sharpe": 1.5, "max_drawdown": -0.1,
            "ic_decay_halflife": 5,
            "oos_ic_per_window": [0.04, 0.03],
            "orthogonality_score": 0.2, "max_corr_with_core": 0.3,
            "status": "discovered", "discovered_at": "now",
            "complexity": 3, "user_id": 1,
            "description_embedding": None,
            "formula_embedding": None,
        }

        result = store.save_entry(entry)

        assert result is True
        cursor.execute.assert_called()
        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO vt_factor_knowledge" in sql

    def test_save_when_disabled_returns_false(self):
        """save_entry returns False without error when store is disabled."""
        sys.modules["psycopg2"].connect.reset_mock()
        from src.db.factor_kb_store import FactorKBStore

        store = FactorKBStore(dsn="")
        result = store.save_entry({"alpha_id": "x"})
        assert result is False


# ---------------------------------------------------------------------------
# load_all_entries
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestLoadAllEntries:
    def test_returns_list_of_deserialized_entries(self, mock_conn):
        conn, cursor = mock_conn
        store, _ = _make_store(mock_cursor=cursor)

        cursor.fetchall.return_value = [
            {"alpha_id": "a1", "name": "Factor 1", "expression_json": json.dumps({"type": "div"}),
             "formula_hash": "h1", "status": "approved", "discovered_at": "2024-01-01"},
            {"alpha_id": "a2", "name": "Factor 2", "expression_json": '{"type": "sub"}',
             "formula_hash": "h2", "status": "paper_trading", "discovered_at": "2024-01-02"},
        ]

        entries = store.load_all_entries()

        assert isinstance(entries, list)
        assert len(entries) == 2
        assert entries[0]["alpha_id"] == "a1"
        assert entries[0]["expression_json"] == {"type": "div"}
        assert entries[1]["expression_json"] == {"type": "sub"}

        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "status != 'archived'" in sql

    def test_returns_empty_list_when_disabled(self):
        sys.modules["psycopg2"].connect.reset_mock()
        from src.db.factor_kb_store import FactorKBStore

        store = FactorKBStore(dsn="")
        result = store.load_all_entries()
        assert result == []


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestUpdateStatus:
    def test_updates_alpha_id_status_returns_true(self, mock_conn):
        conn, cursor = mock_conn
        store, _ = _make_store(mock_cursor=cursor)

        cursor.rowcount = 1

        result = store.update_status("alpha-001", "approved", reason="Good factor")

        assert result is True
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "UPDATE vt_factor_knowledge" in sql
        assert "SET status = %s" in sql

    def test_returns_false_when_disabled(self):
        sys.modules["psycopg2"].connect.reset_mock()
        from src.db.factor_kb_store import FactorKBStore

        store = FactorKBStore(dsn="")
        result = store.update_status("x", "approved")
        assert result is False


# ---------------------------------------------------------------------------
# search_by_embedding / _search_by_tags
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSearch:
    def test_search_by_embedding_returns_list_ranked_by_distance(self, mock_conn):
        conn, cursor = mock_conn
        store, _ = _make_store(mock_cursor=cursor)

        def fake_embedding(text):
            return [0.1] * 10

        cursor.fetchall.return_value = [
            {"alpha_id": "a1", "name": "Factor 1", "similarity": 0.95, "expression_json": "{}"},
            {"alpha_id": "a2", "name": "Factor 2", "similarity": 0.80, "expression_json": "{}"},
        ]

        results = store.search_by_embedding("test query", top_k=5, embedding_fn=fake_embedding)

        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["alpha_id"] == "a1"
        assert results[0]["similarity"] == 0.95

    def test_search_by_tags_fallback(self, mock_conn):
        conn, cursor = mock_conn
        store, _ = _make_store(mock_cursor=cursor)

        cursor.fetchall.return_value = [
            {"alpha_id": "a1", "name": "Momentum Factor", "tag_overlap": 1,
             "expression_json": "{}", "test_ic": 0.05},
        ]

        results = store.search_by_embedding("momentum", top_k=5, embedding_fn=None)

        assert len(results) == 1
        assert results[0]["alpha_id"] == "a1"
        sql = cursor.execute.call_args[0][0]
        assert "semantic_tags" in sql.lower()

    def test_search_returns_empty_when_disabled(self):
        sys.modules["psycopg2"].connect.reset_mock()
        from src.db.factor_kb_store import FactorKBStore

        store = FactorKBStore(dsn="")
        result = store.search_by_embedding("query")
        assert result == []


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestActivityLog:
    def test_log_activity_saves_returns_true(self, mock_conn):
        conn, cursor = mock_conn
        store, _ = _make_store(mock_cursor=cursor)

        result = store.log_activity("mining_complete", user_id=1,
                                     data={"alphas": 5})

        assert result is True
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO vt_activity_log" in sql

    def test_get_recent_activity_returns_list_of_dicts(self, mock_conn):
        conn, cursor = mock_conn
        store, _ = _make_store(mock_cursor=cursor)

        cursor.fetchall.return_value = [
            {"event_type": "mining_complete", "data": json.dumps({"alphas": 5}),
             "created_at": "2024-06-01"},
            {"event_type": "bench_complete", "data": json.dumps({"top": 3}),
             "created_at": "2024-06-02"},
        ]

        results = store.get_recent_activity(user_id=1, limit=10)

        assert len(results) == 2
        assert results[0]["event_type"] == "mining_complete"
        sql = cursor.execute.call_args[0][0]
        assert "FROM vt_activity_log" in sql

    def test_get_recent_activity_returns_empty_when_disabled(self):
        sys.modules["psycopg2"].connect.reset_mock()
        from src.db.factor_kb_store import FactorKBStore

        store = FactorKBStore(dsn="")
        result = store.get_recent_activity(user_id=1)
        assert result == []


# ---------------------------------------------------------------------------
# _serialize_entry
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSerializeEntry:
    def test_handles_none_embedding(self):
        """_serialize_entry handles None embedding gracefully."""
        from src.db.factor_kb_store import FactorKBStore

        store = FactorKBStore(dsn="")
        entry = {"alpha_id": "a1", "formula_hash": "h1",
                  "description_embedding": None, "formula_embedding": None}
        result = store._serialize_entry(entry)

        assert result["description_embedding"] is None
        assert result["formula_embedding"] is None
        assert result["alpha_id"] == "a1"


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestClose:
    def test_close_closes_connection_gracefully(self):
        store, mock_pg_conn = _make_store()
        assert store.available is True

        store.close()

        mock_pg_conn.close.assert_called_once()
        assert store.available is False

    def test_close_on_disabled_store_does_not_crash(self):
        from src.db.factor_kb_store import FactorKBStore

        store = FactorKBStore(dsn="")
        store.close()  # Should not raise
