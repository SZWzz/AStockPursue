"""Tests for src.notify.engine — notification engine and alert helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.notify.engine import (
    NotifyEngine,
    alert_daily_loss,
    alert_drawdown,
    alert_run_error,
    alert_run_state_change,
    alert_stop_loss,
    alert_take_profit,
)


@pytest.mark.unit
class TestNotifyEngineEnabled:
    def test_disabled_when_no_channels_configured(self):
        engine = NotifyEngine({"notify_enabled": True, "notify_channels": []})
        assert engine.enabled is False

    def test_disabled_when_notify_enabled_is_false(self):
        engine = NotifyEngine({
            "notify_enabled": False,
            "notify_channels": [{"type": "webhook", "url": "https://example.com"}],
        })
        assert engine.enabled is False

    def test_enabled_when_channels_and_flag_are_set(self):
        engine = NotifyEngine({
            "notify_enabled": True,
            "notify_channels": [{"type": "webhook", "url": "https://example.com"}],
        })
        assert engine.enabled is True


@pytest.mark.unit
class TestNotifyEngineAlert:
    def test_alert_sends_to_configured_channels(self):
        engine = NotifyEngine({
            "notify_enabled": True,
            "notify_channels": [{"type": "webhook", "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"}],
        })
        alert = alert_stop_loss("600519", 1800.0, 1750.0, -0.0278)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.post", return_value=mock_response):
            results = engine.alert(alert)

        assert len(results) > 0
        assert results.get("webhook") is True

    def test_alert_returns_empty_when_disabled(self):
        engine = NotifyEngine({"notify_enabled": False, "notify_channels": []})
        alert = alert_stop_loss("600519", 1800.0, 1750.0, -0.0278)
        results = engine.alert(alert)
        assert results == {}

    def test_alert_filters_by_level(self):
        """Only warning and critical alerts go through by default."""
        engine = NotifyEngine({
            "notify_enabled": True,
            "notify_channels": [{"type": "webhook", "url": "https://example.com/hook"}],
        })
        # info level should be filtered out
        alert = alert_take_profit("600519", 1800.0, 1900.0, 0.0556)
        assert alert.level == "info"
        results = engine.alert(alert)
        assert results == {}

    def test_alert_respects_custom_levels(self):
        engine = NotifyEngine({
            "notify_enabled": True,
            "notify_channels": [{"type": "webhook", "url": "https://example.com/hook"}],
            "notify_levels": ["info", "warning", "critical", "signal"],
        })
        alert = alert_take_profit("600519", 1800.0, 1900.0, 0.0556)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.post", return_value=mock_response):
            results = engine.alert(alert)

        assert len(results) > 0


@pytest.mark.unit
class TestNotifyEngineRateLimiting:
    def test_rate_limiting_suppresses_after_limit(self):
        engine = NotifyEngine({
            "notify_enabled": True,
            "notify_channels": [{"type": "webhook", "url": "https://example.com/hook"}],
            "notify_rate_limit": 3,
            "notify_levels": ["warning", "critical"],
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.post", return_value=mock_response):
            # Send up to limit
            results1 = engine.alert(alert_stop_loss("A", 10, 9, -0.1))
            results2 = engine.alert(alert_stop_loss("B", 10, 9, -0.1))
            results3 = engine.alert(alert_stop_loss("C", 10, 9, -0.1))
            # This one should be suppressed
            results4 = engine.alert(alert_stop_loss("D", 10, 9, -0.1))

        assert results1 != {}
        assert results2 != {}
        assert results3 != {}
        assert results4 == {}


@pytest.mark.unit
class TestAlertHelpers:
    def test_alert_stop_loss_fields(self):
        alert = alert_stop_loss("600519", 1800.0, 1750.0, -0.0278)
        assert alert.level == "warning"
        assert alert.source == "risk"
        assert "600519" in alert.title
        assert "止损" in alert.title

    def test_alert_take_profit_fields(self):
        alert = alert_take_profit("000001", 12.0, 13.0, 0.0833)
        assert alert.level == "info"
        assert alert.source == "risk"
        assert "止盈" in alert.title

    def test_alert_daily_loss_fields(self):
        alert = alert_daily_loss(0.05, 0.06)
        assert alert.level == "critical"
        assert alert.source == "risk"
        assert "亏损" in alert.body

    def test_alert_drawdown_fields(self):
        alert = alert_drawdown(0.15, 0.20)
        assert alert.level == "critical"
        assert alert.source == "risk"
        assert "回撤" in alert.title

    def test_alert_run_error_fields(self):
        alert = alert_run_error("run-12345-abc", "Division by zero")
        assert alert.level == "critical"
        assert alert.source == "system"
        assert "run-12345" in alert.title

    def test_alert_run_state_change_fields(self):
        alert = alert_run_state_change("run-67890", "running", "completed")
        assert alert.level == "info"
        assert alert.source == "papertrade"
        assert "running" in alert.body
        assert "completed" in alert.body
