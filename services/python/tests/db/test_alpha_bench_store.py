"""Integration tests for src.db.alpha_bench_store — save/list/get/delete bench results.

Mocks psycopg2 connections via ``mock_conn`` fixture and verifies that
correct SQL, parameters and deserialisation are used.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import src.db.alpha_bench_store as mod
from tests.db.conftest import mock_get_connection_factory


def _patch_get_connection(monkeypatch, conn):
    monkeypatch.setattr(mod, "get_connection", mock_get_connection_factory(conn))


# ---------------------------------------------------------------------------
# save_bench_result
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSaveBenchResult:
    def test_basic_save_returns_string_run_id(self, monkeypatch, mock_conn):
        """save_bench_result returns a string run_id."""
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        result_dict = {
            "alive": 5, "reversed": 2, "dead": 3,
            "n_alphas_tested": 50, "n_skipped": 5,
            "by_theme": {}, "top5_by_ir": [], "dead_examples": [], "meta": {},
            "wall_seconds": 12.5,
        }
        run_id = mod.save_bench_result(
            user_id=1, zoo="momentum", universe="csi500", period="1y", top=10,
            result=result_dict,
        )

        assert isinstance(run_id, str)
        assert len(run_id) > 0
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO vt_alpha_bench_runs" in sql

    def test_save_with_nested_result_dict(self, monkeypatch, mock_conn):
        """save_bench_result serialises nested by_theme, top5_by_ir, dead_examples, meta."""
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        result_dict = {
            "alive": 3, "reversed": 1, "dead": 1,
            "n_alphas_tested": 20, "n_skipped": 0,
            "by_theme": {"momentum": 2, "value": 1},
            "top5_by_ir": [{"name": "alpha1", "ir": 2.5}],
            "dead_examples": [{"name": "dead1", "reason": "low_ic"}],
            "meta": {"engine": "v2"},
            "wall_seconds": 30.0,
        }

        run_id = mod.save_bench_result(
            user_id=1, zoo="mixed", universe="csi300", period="3m", top=5,
            result=result_dict,
        )

        assert isinstance(run_id, str)
        _, params = cursor.execute.call_args[0]
        assert params[1] == 1  # user_id
        assert params[2] == "mixed"  # zoo
        assert params[5] == 5  # top
        assert params[6] == 3  # alive
        assert json.loads(params[11]) == {"momentum": 2, "value": 1}  # by_theme
        assert json.loads(params[12]) == [{"name": "alpha1", "ir": 2.5}]  # top5_by_ir

    def test_save_error_propagation_returns_none(self, monkeypatch, mock_conn):
        """When db raises, save_bench_result returns None."""
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)
        cursor.execute.side_effect = Exception("DB error")

        result = mod.save_bench_result(
            user_id=1, zoo="x", universe="y", period="1d", top=1,
            result={"alive": 0, "reversed": 0, "dead": 0,
                     "n_alphas_tested": 0, "n_skipped": 0,
                     "by_theme": {}, "top5_by_ir": [], "dead_examples": [], "meta": {},
                     "wall_seconds": 0},
        )
        assert result is None


# ---------------------------------------------------------------------------
# list_bench_results
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestListBenchResults:
    def test_returns_list_of_dicts(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchall.return_value = [
            ("r1", "momentum", "csi300", "1y", 10, 5, 2, 3, 50, 5, 12.5, "2024-06-01"),
            ("r2", "value", "csi500", "3m", 5, 3, 1, 1, 20, 0, 5.0, "2024-06-02"),
        ]

        results = mod.list_bench_results(user_id=1)

        assert isinstance(results, list)
        assert len(results) == 2
        for r in results:
            for key in ("run_id", "zoo", "universe", "period", "top",
                         "alive", "reversed", "dead", "n_alphas_tested",
                         "n_skipped", "wall_seconds", "created_at"):
                assert key in r

        assert results[0]["run_id"] == "r1"
        assert results[1]["zoo"] == "value"

    def test_respects_limit_and_offset(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchall.return_value = []

        mod.list_bench_results(user_id=1, limit=5, offset=10)

        sql = cursor.execute.call_args[0][0]
        params = cursor.execute.call_args[0][1]
        assert "LIMIT %s OFFSET %s" in sql
        assert params == (1, 5, 10)


# ---------------------------------------------------------------------------
# get_bench_result
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetBenchResult:
    def test_returns_dict_with_expected_keys(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchone.return_value = (
            "r1", 1, "momentum", "csi300", "1y", 10,
            5, 2, 3, 50, 5,
            json.dumps({"momentum": 3, "value": 2}),                    # by_theme
            json.dumps([{"name": "a1", "ir": 2.5}]),                   # top5_by_ir
            json.dumps([{"name": "d1", "reason": "low_ic"}]),          # dead_examples
            json.dumps({"engine": "v1"}),                              # meta
            12.5, "2024-06-01T00:00:00",
        )

        result = mod.get_bench_result("r1")

        assert result is not None
        for key in ("run_id", "user_id", "zoo", "universe", "period", "top",
                      "alive", "reversed", "dead", "n_alphas_tested", "n_skipped",
                      "by_theme", "top5_by_ir", "dead_examples", "meta",
                      "wall_seconds", "created_at"):
            assert key in result

        assert result["by_theme"] == {"momentum": 3, "value": 2}
        assert result["top5_by_ir"] == [{"name": "a1", "ir": 2.5}]
        assert result["dead_examples"] == [{"name": "d1", "reason": "low_ic"}]
        assert result["meta"] == {"engine": "v1"}

    def test_returns_none_for_nonexistent_run_id(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchone.return_value = None

        result = mod.get_bench_result("non-existent")
        assert result is None


# ---------------------------------------------------------------------------
# delete_bench_result
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDeleteBenchResult:
    def test_returns_true_on_successful_delete(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        result = mod.delete_bench_result("r1")

        assert result is True
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "DELETE FROM vt_alpha_bench_runs" in sql

    def test_returns_false_on_error(self, monkeypatch, mock_conn):
        """delete_bench_result returns False when DB raises an exception."""
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)
        cursor.execute.side_effect = Exception("DB error")

        result = mod.delete_bench_result("r1")
        assert result is False
