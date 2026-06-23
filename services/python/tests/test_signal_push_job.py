"""Tests for services.signal_push_job — daily signal push job."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_ics() -> pd.Series:
    """Return a small IC series for tests."""
    return pd.Series(
        {"momentum_20d": 0.042, "reversal_5d": -0.038, "rsi_14": 0.015},
        name="ic",
    )


def _make_mock_factor_values() -> dict[str, pd.DataFrame]:
    """Return factor values dict matching _make_mock_ics keys."""
    dates = pd.date_range("2024-06-17", periods=5, freq="B")
    stocks = ["600519.SH", "000858.SZ", "601318.SH"]
    import numpy as np

    rng = np.random.default_rng(42)
    return {
        "momentum_20d": pd.DataFrame(
            rng.normal(0, 1, (len(dates), len(stocks))),
            index=dates,
            columns=stocks,
        ),
        "reversal_5d": pd.DataFrame(
            rng.normal(0, 1, (len(dates), len(stocks))),
            index=dates,
            columns=stocks,
        ),
        "rsi_14": pd.DataFrame(
            rng.normal(0, 1, (len(dates), len(stocks))),
            index=dates,
            columns=stocks,
        ),
    }


_SUBSCRIBERS_TELEGRAM = {
    1: {"telegram": {"bot_token": "tk", "chat_id": "123"}},
}

_SUBSCRIBERS_MULTI_CHANNEL = {
    1: {
        "telegram": {"bot_token": "tk", "chat_id": "123"},
        "email": {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "a@b.com",
            "smtp_pass": "p",
            "email_to": "a@b.com",
        },
    },
}

_SUBSCRIBERS_TWO_USERS = {
    1: {"telegram": {"bot_token": "tk", "chat_id": "123"}},
    2: {"email": {"smtp_host": "h", "smtp_port": 587, "smtp_user": "u", "smtp_pass": "p", "email_to": "x@y.com"}},
}


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRunSignalPush:
    """End-to-end behaviour of run_signal_push."""

    @patch("services.signal_push_job._get_subscribers")
    @patch("src.notify.channels.send_alert")
    @patch("src.services.signal_brief.SignalBriefGenerator")
    def test_push_with_single_channel_succeeds(
        self, mock_gen_cls, mock_send_alert, mock_get_subscribers
    ):
        """One user with one channel → brief generated, push succeeds."""
        mock_gen = MagicMock()
        mock_gen.compute_daily_factors.return_value = _make_mock_factor_values()
        mock_gen.compute_cross_sectional_ic.return_value = _make_mock_ics()
        mock_gen.select_top_factors.return_value = [
            ("momentum_20d", 0.042),
            ("reversal_5d", -0.038),
        ]
        mock_gen.render_markdown.return_value = "# Brief"
        mock_gen_cls.return_value = mock_gen

        mock_get_subscribers.return_value = _SUBSCRIBERS_TELEGRAM
        mock_send_alert.return_value = {"telegram": True}

        from services.signal_push_job import run_signal_push

        result = run_signal_push(target_date=date(2024, 6, 23))

        assert result["date"] == "2024-06-23"
        assert result["factors_count"] == 2
        assert "telegram" in result["channels_used"]
        assert result["users_notified"] == 1
        assert result["errors"] == []
        mock_send_alert.assert_called_once()

    @patch("services.signal_push_job._get_subscribers")
    @patch("src.services.signal_brief.SignalBriefGenerator")
    def test_no_subscribers_skips_notification(
        self, mock_gen_cls, mock_get_subscribers
    ):
        """No subscribers → push is skipped, no errors raised."""
        mock_gen = MagicMock()
        mock_gen.compute_daily_factors.return_value = _make_mock_factor_values()
        mock_gen.compute_cross_sectional_ic.return_value = _make_mock_ics()
        mock_gen.select_top_factors.return_value = [
            ("momentum_20d", 0.042),
        ]
        mock_gen.render_markdown.return_value = "# Brief"
        mock_gen_cls.return_value = mock_gen

        mock_get_subscribers.return_value = {}

        from services.signal_push_job import run_signal_push

        result = run_signal_push(target_date=date(2024, 6, 23))

        assert result["users_notified"] == 0
        assert result["channels_used"] == []
        assert result["errors"] == []

    @patch("services.signal_push_job._get_subscribers")
    @patch("src.notify.channels.send_alert")
    @patch("src.services.signal_brief.SignalBriefGenerator")
    def test_channel_failure_does_not_block_push(
        self, mock_gen_cls, mock_send_alert, mock_get_subscribers
    ):
        """A send_alert exception is caught; the job continues."""
        mock_gen = MagicMock()
        mock_gen.compute_daily_factors.return_value = _make_mock_factor_values()
        mock_gen.compute_cross_sectional_ic.return_value = _make_mock_ics()
        mock_gen.select_top_factors.return_value = [
            ("momentum_20d", 0.042),
        ]
        mock_gen.render_markdown.return_value = "# Brief"
        mock_gen_cls.return_value = mock_gen

        mock_get_subscribers.return_value = _SUBSCRIBERS_TELEGRAM
        mock_send_alert.side_effect = RuntimeError("Telegram API down")

        from services.signal_push_job import run_signal_push

        result = run_signal_push(target_date=date(2024, 6, 23))

        # The push attempt failed but the job completed without raising
        assert len(result["errors"]) == 1
        assert "Telegram API down" in result["errors"][0]
        assert result["users_notified"] == 0

    @patch("services.signal_push_job._get_subscribers")
    @patch("src.services.signal_brief.SignalBriefGenerator")
    def test_no_factor_data_returns_early(
        self, mock_gen_cls, mock_get_subscribers
    ):
        """compute_daily_factors returns empty dict → early return."""
        mock_gen = MagicMock()
        mock_gen.compute_daily_factors.return_value = {}
        mock_gen_cls.return_value = mock_gen

        mock_get_subscribers.return_value = _SUBSCRIBERS_TELEGRAM

        from services.signal_push_job import run_signal_push

        result = run_signal_push(target_date=date(2024, 6, 23))

        assert "no_factor_data" in result["errors"]
        assert result["factors_count"] == 0
        assert result["users_notified"] == 0

    @patch("services.signal_push_job._get_subscribers")
    @patch("src.notify.channels.send_alert")
    @patch("src.services.signal_brief.SignalBriefGenerator")
    def test_multi_channel_push_uses_all_channels(
        self, mock_gen_cls, mock_send_alert, mock_get_subscribers
    ):
        """User with multiple channels → all channel types recorded."""
        mock_gen = MagicMock()
        mock_gen.compute_daily_factors.return_value = _make_mock_factor_values()
        mock_gen.compute_cross_sectional_ic.return_value = _make_mock_ics()
        mock_gen.select_top_factors.return_value = [
            ("reversal_5d", -0.038),
        ]
        mock_gen.render_markdown.return_value = "# Brief"
        mock_gen_cls.return_value = mock_gen

        mock_get_subscribers.return_value = _SUBSCRIBERS_MULTI_CHANNEL
        mock_send_alert.return_value = {"telegram": True, "email": True}

        from services.signal_push_job import run_signal_push

        result = run_signal_push()

        assert result["users_notified"] == 1
        assert "telegram" in result["channels_used"]
        assert "email" in result["channels_used"]
        assert result["errors"] == []

    @patch("services.signal_push_job._get_subscribers")
    @patch("src.notify.channels.send_alert")
    @patch("src.services.signal_brief.SignalBriefGenerator")
    def test_multiple_users_each_notified(
        self, mock_gen_cls, mock_send_alert, mock_get_subscribers
    ):
        """Two users → both are notified."""
        mock_gen = MagicMock()
        mock_gen.compute_daily_factors.return_value = _make_mock_factor_values()
        mock_gen.compute_cross_sectional_ic.return_value = _make_mock_ics()
        mock_gen.select_top_factors.return_value = [
            ("momentum_20d", 0.042),
        ]
        mock_gen.render_markdown.return_value = "# Brief"
        mock_gen_cls.return_value = mock_gen

        mock_get_subscribers.return_value = _SUBSCRIBERS_TWO_USERS
        mock_send_alert.return_value = {}

        from services.signal_push_job import run_signal_push

        result = run_signal_push()

        assert result["users_notified"] == 2
        assert mock_send_alert.call_count == 2

    @patch("services.signal_push_job._get_subscribers")
    @patch("src.services.signal_brief.SignalBriefGenerator")
    def test_brief_generation_failure_is_caught(
        self, mock_gen_cls, mock_get_subscribers
    ):
        """SignalBriefGenerator raises → error recorded, subscribers not queried."""
        mock_gen_cls.side_effect = RuntimeError("Factor engine unavailable")

        from services.signal_push_job import run_signal_push

        result = run_signal_push()

        assert len(result["errors"]) == 1
        assert "brief_generation_failed" in result["errors"][0]
        assert result["users_notified"] == 0
        # _get_subscribers should not be called (brief failed first)
        mock_get_subscribers.assert_not_called()


@pytest.mark.unit
class TestGetSubscribers:
    """Unit tests for _get_subscribers helper."""

    @patch("src.db.pool.init_pool")
    @patch("src.db.pool.get_connection")
    def test_parses_json_channels(self, mock_get_conn, mock_init_pool):
        """JSONB push_channels column → correctly deserialised."""
        import json

        mock_ctx = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__.return_value = mock_cur
        mock_ctx.__enter__.return_value = mock_ctx
        mock_ctx.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_ctx

        mock_cur.fetchall.return_value = [
            (1, json.dumps({"telegram": {"chat_id": "123"}})),
            (2, {"email": {"email_to": "a@b.com"}}),
        ]

        from services.signal_push_job import _get_subscribers

        subscribers = _get_subscribers()

        assert len(subscribers) == 2
        assert 1 in subscribers
        assert subscribers[1]["telegram"]["chat_id"] == "123"
        assert 2 in subscribers
        assert subscribers[2]["email"]["email_to"] == "a@b.com"

    @patch("src.db.pool.init_pool")
    @patch("src.db.pool.get_connection")
    def test_empty_channels_filtered_out(self, mock_get_conn, mock_init_pool):
        """User with NULL or empty push_channels is excluded."""
        mock_ctx = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__.return_value = mock_cur
        mock_ctx.__enter__.return_value = mock_ctx
        mock_ctx.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_ctx

        mock_cur.fetchall.return_value = [(3, None), (4, "{}"), (5, {})]

        from services.signal_push_job import _get_subscribers

        subscribers = _get_subscribers()

        assert subscribers == {}

    @patch("src.db.pool.init_pool")
    @patch("src.db.pool.get_connection")
    def test_db_error_returns_empty(self, mock_get_conn, mock_init_pool):
        """Database error → empty dict, no exception propagated."""
        mock_get_conn.side_effect = RuntimeError("Connection refused")

        from services.signal_push_job import _get_subscribers

        subscribers = _get_subscribers()

        assert subscribers == {}
