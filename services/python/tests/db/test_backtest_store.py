"""Integration tests for src.db.backtest_store — save/list/get/delete backtest runs.

Mocks psycopg2 connections via ``mock_conn`` fixture and verifies that
correct SQL is executed, parameters are passed, return values are
properly deserialised, and error paths are handled.
"""

from __future__ import annotations

from unittest.mock import MagicMock, ANY

import pytest

import src.db.backtest_store as mod
from tests.db.conftest import mock_get_connection_factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_get_connection(monkeypatch, conn):
    monkeypatch.setattr(mod, "get_connection", mock_get_connection_factory(conn))


# ---------------------------------------------------------------------------
# save_backtest_result
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSaveBacktestResult:
    def test_basic_save_returns_string_run_id(self, monkeypatch, mock_conn):
        """save_backtest_result returns a string UUID."""
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        run_id = mod.save_backtest_result(run_name="test_run")

        assert isinstance(run_id, str)
        assert len(run_id) > 0
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO vt_backtest_runs" in sql

    def test_save_with_equity_trades_ohlcv_calls_insert_helpers(self, monkeypatch, mock_conn):
        """When equity_curve/trades/ohlcv_bars are provided the internal insert helpers are called."""
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        mock_equity = MagicMock()
        mock_trades = MagicMock()
        mock_ohlcv = MagicMock()
        monkeypatch.setattr(mod, "_insert_equity", mock_equity)
        monkeypatch.setattr(mod, "_insert_trades", mock_trades)
        monkeypatch.setattr(mod, "_insert_ohlcv", mock_ohlcv)

        equity = [{"time": "2024-01-01", "equity": 100000, "drawdown": 0.0}]
        trades = [{"symbol": "000001", "entry_time": "2024-01-01", "exit_time": "2024-01-02",
                    "entry_price": 10.0, "exit_price": 11.0, "size": 100, "side": "long",
                    "pnl": 100.0, "return_pct": 0.01, "exit_reason": "target"}]
        ohlcv = [{"code": "000001", "bar_time": "2024-01-01", "open": 10.0, "high": 11.0,
                   "low": 9.5, "close": 10.5, "volume": 1000000}]

        run_id = mod.save_backtest_result(
            run_name="full_run", equity_curve=equity, trades=trades, ohlcv_bars=ohlcv
        )

        assert isinstance(run_id, str)
        run_id_val = cursor.execute.call_args[0][1][0]
        mock_equity.assert_called_once_with(cursor, run_id_val, equity)
        mock_trades.assert_called_once_with(cursor, run_id_val, trades)
        mock_ohlcv.assert_called_once_with(cursor, run_id_val, ohlcv)

    def test_save_with_all_optional_fields(self, monkeypatch, mock_conn):
        """save_backtest_result passes tags, user_id, config, metrics to SQL."""
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        config = {"start": "2023-01-01", "capital": 500000}
        metrics = {"sharpe": 1.5, "max_dd": -0.15}
        tags = ["momentum", "daily"]

        run_id = mod.save_backtest_result(
            run_name="full_run",
            run_type="alpha",
            config=config,
            metrics=metrics,
            user_id=5,
            tags=tags,
            status="success",
            error_message="",
        )

        assert isinstance(run_id, str)
        _, params = cursor.execute.call_args[0]
        assert params[1] == 5       # user_id
        assert params[3] == "alpha"  # run_type
        assert params[8] == tags    # tags

    def test_save_with_empty_equity_trades_does_not_crash(self, monkeypatch, mock_conn):
        """Empty equity_curve / trades / ohlcv_bars are handled gracefully (no crash)."""
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        # Don't mock insert helpers — verify they are never called
        mock_equity = MagicMock()
        mock_trades = MagicMock()
        mock_ohlcv = MagicMock()
        monkeypatch.setattr(mod, "_insert_equity", mock_equity)
        monkeypatch.setattr(mod, "_insert_trades", mock_trades)
        monkeypatch.setattr(mod, "_insert_ohlcv", mock_ohlcv)

        run_id = mod.save_backtest_result(
            run_name="empty_run", equity_curve=[], trades=[], ohlcv_bars=[]
        )

        assert isinstance(run_id, str)
        mock_equity.assert_not_called()
        mock_trades.assert_not_called()
        mock_ohlcv.assert_not_called()


# ---------------------------------------------------------------------------
# list_backtest_runs
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestListBacktestRuns:
    def test_returns_list_of_dicts_with_expected_keys(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchall.return_value = [
            ("id-1", "run1", "strategy", {"sharpe": 1.0}, "success", "2024-06-01T00:00:00"),
            ("id-2", "run2", "alpha", {}, "failed", "2024-06-02T00:00:00"),
        ]

        result = mod.list_backtest_runs()

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert "id" in item
            assert "run_name" in item
            assert "run_type" in item
            assert "metrics" in item
            assert "status" in item
            assert "created_at" in item

        assert result[0]["id"] == "id-1"
        assert result[1]["status"] == "failed"

    def test_respects_limit_and_offset(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchall.return_value = []

        mod.list_backtest_runs(limit=10, offset=5)

        sql = cursor.execute.call_args[0][0]
        params = cursor.execute.call_args[0][1]
        assert "LIMIT %s OFFSET %s" in sql
        assert params == (10, 5)


# ---------------------------------------------------------------------------
# get_backtest_run
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetBacktestRun:
    def test_returns_dict_with_sub_lists(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        # Row for the run itself
        run_row = ("rid", "my run", "strategy", {"capital": 1e6}, {"sharpe": 1.2},
                    "success", "", "2024-01-01T00:00:00")
        equity_rows = [("2024-01-01T10:00:00", 100000.0, 0.0)]
        trade_rows = [("000001", "2024-01-01T10:00:00", "2024-01-02T10:00:00",
                        10.0, 11.0, 100, "long", 100.0, 0.01, "target")]
        ohlcv_rows = [("000001", "2024-01-01T10:00:00", 10.0, 11.0, 9.5, 10.5, 1000000)]

        cursor.fetchone.return_value = run_row
        cursor.fetchall.side_effect = [equity_rows, trade_rows, ohlcv_rows]

        result = mod.get_backtest_run("rid")

        assert result is not None
        assert result["id"] == "rid"
        assert result["run_name"] == "my run"
        assert "equity_curve" in result
        assert "trades" in result
        assert "ohlcv_bars" in result
        assert len(result["equity_curve"]) == 1
        assert result["equity_curve"][0]["equity"] == 100000.0
        assert len(result["trades"]) == 1
        assert result["trades"][0]["symbol"] == "000001"

    def test_returns_none_for_nonexistent_run_id(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchone.return_value = None

        result = mod.get_backtest_run("non-existent")

        assert result is None


# ---------------------------------------------------------------------------
# delete_backtest_run
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDeleteBacktestRun:
    def test_returns_true_on_successful_delete(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.rowcount = 1

        result = mod.delete_backtest_run("rid")

        assert result is True
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "DELETE FROM vt_backtest_runs" in sql

    def test_returns_false_on_nonexistent_run_id(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.rowcount = 0

        result = mod.delete_backtest_run("non-existent")

        assert result is False
