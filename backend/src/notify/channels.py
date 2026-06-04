"""Notification channels: webhook (WeCom/DingTalk/Discord/Slack) + email (SMTP).

Each channel is a callable that accepts a :class:`Alert` and delivers it.
Add new channels by implementing ``def send(alert: Alert, config: dict) -> bool``.
"""

from __future__ import annotations

import json
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Any

import requests

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────

class Alert:
    """A structured alert emitted by the trading system."""

    def __init__(
        self,
        title: str,
        body: str,
        level: str = "info",          # info | warning | critical
        source: str = "system",       # risk / oms / system / papertrade
        metadata: dict[str, Any] | None = None,
    ):
        self.title = title
        self.body = body
        self.level = level
        self.source = source
        self.metadata = metadata or {}

    def to_markdown(self) -> str:
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(self.level, "📢")
        return f"{emoji} **{self.title}**\n>{self.body}"


# ── Webhook channel ───────────────────────────────────────────────────────────

_WEBHOOK_DEFAULTS: dict[str, str] = {
    "wecom":  "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=",
    "dingtalk": "https://oapi.dingtalk.com/robot/send?access_token=",
}


def _send_webhook(alert: Alert, url: str, webhook_type: str = "generic") -> bool:
    """Send alert to a webhook URL."""
    if webhook_type == "wecom":
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": alert.to_markdown()},
        }
    elif webhook_type == "dingtalk":
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": alert.title, "text": alert.to_markdown()},
        }
    else:
        # Discord / Slack / generic
        payload = {
            "content": alert.to_markdown() if webhook_type == "discord" else None,
            "text": alert.to_markdown(),
            "title": alert.title,
            "level": alert.level,
        }
        # Clean None values
        payload = {k: v for k, v in payload.items() if v is not None}

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code < 400:
            return True
        logger.warning("Webhook %s returned %d: %s", webhook_type, r.status_code, r.text[:200])
        return False
    except Exception as exc:
        logger.warning("Webhook %s failed: %s", webhook_type, exc)
        return False


# ── Email channel ─────────────────────────────────────────────────────────────

def _send_email(alert: Alert, config: dict) -> bool:
    """Send alert via SMTP email."""
    smtp_host = config.get("smtp_host", "")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user", "")
    smtp_pass = config.get("smtp_pass", "")
    to_addrs = config.get("email_to", "")

    if not all([smtp_host, smtp_user, smtp_pass, to_addrs]):
        logger.warning("Email channel not fully configured (missing smtp_host/user/pass/to)")
        return False

    msg = MIMEText(f"{alert.title}\n\n{alert.body}\n\n---\nAStockPursue Alert", "plain", "utf-8")
    msg["Subject"] = f"[{alert.level.upper()}] {alert.title}"
    msg["From"] = smtp_user
    msg["To"] = to_addrs

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_addrs.split(","), msg.as_string())
        server.quit()
        return True
    except Exception as exc:
        logger.warning("Email send failed: %s", exc)
        return False


# ── Channel registry ──────────────────────────────────────────────────────────

_CHANNEL_SENDERS: dict[str, Any] = {
    "webhook": _send_webhook,
    "email": _send_email,
}


def send_alert(alert: Alert, channel_configs: list[dict]) -> dict[str, bool]:
    """Send *alert* through all configured channels.

    Args:
        alert: The alert to send.
        channel_configs: List of channel configs, each with at least a ``type`` key
            (``"webhook"``, ``"email"``) and relevant connection parameters.

    Returns:
        ``{channel_type: success}`` mapping.
    """
    results: dict[str, bool] = {}
    for cfg in channel_configs:
        ch_type = cfg.get("type", "")
        sender = _CHANNEL_SENDERS.get(ch_type)
        if sender is None:
            logger.debug("Unknown channel type: %s", ch_type)
            results[ch_type] = False
            continue

        if ch_type == "webhook":
            url = cfg.get("url", "")
            wt = cfg.get("webhook_type", "generic")
            if not url:
                results[ch_type] = False
                continue
            results[ch_type] = _send_webhook(alert, url, wt)
        elif ch_type == "email":
            results[ch_type] = _send_email(alert, cfg)

    return results
