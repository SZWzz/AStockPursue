"""Tests for src.notify.channels — alert data model and delivery channels."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.notify.channels import (
    Alert,
    _detect_dialect,
    _send_webhook,
    send_alert,
)


@pytest.mark.unit
class TestAlertInit:
    def test_alert_all_fields_set_correctly(self):
        alert = Alert(
            title="Test Alert",
            body="This is a test",
            level="warning",
            source="risk",
            metadata={"key": "value"},
            symbol="600519",
            signal_type="buy",
            price=1850.0,
            quantity=100.0,
        )
        assert alert.title == "Test Alert"
        assert alert.body == "This is a test"
        assert alert.level == "warning"
        assert alert.source == "risk"
        assert alert.metadata == {"key": "value"}
        assert alert.symbol == "600519"
        assert alert.signal_type == "buy"
        assert alert.price == 1850.0
        assert alert.quantity == 100.0

    def test_alert_default_values(self):
        alert = Alert(title="Minimal", body="Just a body")
        assert alert.level == "info"
        assert alert.source == "system"
        assert alert.metadata == {}
        assert alert.symbol == ""
        assert alert.signal_type == ""
        assert alert.price == 0.0
        assert alert.quantity == 0.0


@pytest.mark.unit
class TestAlertFormatting:
    def test_to_markdown_produces_markdown_string(self):
        alert = Alert(title="Test", body="Hello world", level="warning")
        md = alert.to_markdown()
        assert "Test" in md
        assert "Hello world" in md
        # Should contain markdown bold markers
        assert "**" in md

    def test_to_markdown_with_symbol_and_signal(self):
        alert = Alert(
            title="Signal",
            body="Buy signal",
            symbol="000001",
            signal_type="buy",
            price=12.5,
            quantity=1000.0,
        )
        md = alert.to_markdown()
        assert "000001" in md
        assert "买入" in md
        assert "12.50" in md

    def test_to_html_produces_html_string(self):
        alert = Alert(title="Test", body="Body text", level="critical")
        html = alert.to_html()
        assert "<b>Test</b>" in html
        assert "Body text" in html
        assert "<pre>" in html

    def test_to_html_with_symbol(self):
        alert = Alert(title="Alert", body="Content", symbol="600519")
        html = alert.to_html()
        assert "<code>600519</code>" in html


@pytest.mark.unit
class TestAlertLevels:
    @pytest.mark.parametrize("level", ["info", "warning", "critical", "signal"])
    def test_alert_different_levels(self, level):
        alert = Alert(title="Test", body="Body", level=level)
        assert alert.level == level
        md = alert.to_markdown()
        assert len(md) > 0
        html = alert.to_html()
        assert len(html) > 0

    @pytest.mark.parametrize("source", ["risk", "oms", "system", "papertrade", "strategy"])
    def test_alert_different_sources(self, source):
        alert = Alert(title="Test", body="Body", source=source)
        assert alert.source == source


@pytest.mark.unit
class TestDetectDialect:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc", "wecom"),
            ("https://oapi.dingtalk.com/robot/send?access_token=abc", "dingtalk"),
            ("https://open.feishu.cn/open-apis/bot/v2/hook/abc", "feishu"),
            ("https://open.larksuite.com/open-apis/bot/v2/hook/abc", "feishu"),
            ("https://hooks.slack.com/services/T00/B00/xxx", "slack"),
            ("https://discord.com/api/webhooks/123/abc", "discord"),
            ("https://custom.example.com/webhook", "generic"),
        ],
    )
    def test_detect_dialect(self, url, expected):
        assert _detect_dialect(url) == expected


@pytest.mark.unit
class TestSendWebhook:
    def test_send_webhook_calls_requests_post(self):
        alert = Alert(title="Test", body="Hello", level="warning")
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = _send_webhook(alert, "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test")
            assert result is True
            mock_post.assert_called_once()

    def test_send_webhook_returns_false_on_http_error(self):
        alert = Alert(title="Test", body="Hello")
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Error"

        with patch("requests.post", return_value=mock_response):
            result = _send_webhook(alert, "https://hooks.example.com/webhook")
            assert result is False

    def test_send_webhook_returns_false_on_exception(self):
        alert = Alert(title="Test", body="Hello")

        with patch("requests.post", side_effect=Exception("Connection refused")):
            result = _send_webhook(alert, "https://hooks.example.com/webhook")
            assert result is False


@pytest.mark.unit
class TestSendAlert:
    def test_send_alert_distributes_to_multiple_channels(self):
        alert = Alert(title="Test", body="Body", level="warning")
        configs = [
            {"type": "webhook", "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=a"},
            {"type": "feishu", "webhook_url": "https://open.feishu.cn/hook"},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.post", return_value=mock_response):
            results = send_alert(alert, configs)

        assert len(results) == 2
        assert all(results.values())

    def test_send_alert_with_empty_channel_list(self):
        alert = Alert(title="Test", body="Body")
        results = send_alert(alert, [])
        assert results == {}

    def test_send_alert_with_unknown_channel_type(self):
        alert = Alert(title="Test", body="Body")
        results = send_alert(alert, [{"type": "unknown_type"}])
        assert results == {"unknown_type": False}

    def test_send_alert_with_missing_url(self):
        alert = Alert(title="Test", body="Body")
        results = send_alert(alert, [{"type": "webhook"}])
        assert results == {"webhook": False}
