"""Notification channels: webhook (WeCom/DingTalk/Feishu/Discord/Slack) +
Telegram Bot + email (SMTP).

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
    """A structured alert emitted by the trading system.

    Supports both system alerts and trade signal notifications with
    optional trading context (symbol, signal_type, price, quantity).
    """

    def __init__(
        self,
        title: str,
        body: str,
        level: str = "info",          # info | warning | critical | signal
        source: str = "system",       # risk / oms / system / papertrade / strategy
        metadata: dict[str, Any] | None = None,
        # Trading signal context (optional)
        symbol: str = "",
        signal_type: str = "",        # buy | sell | stop_loss | take_profit
        price: float = 0.0,
        quantity: float = 0.0,
    ):
        self.title = title
        self.body = body
        self.level = level
        self.source = source
        self.metadata = metadata or {}
        self.symbol = symbol
        self.signal_type = signal_type
        self.price = price
        self.quantity = quantity

    def to_markdown(self) -> str:
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨", "signal": "📊"}.get(self.level, "📢")
        lines = [f"{emoji} **{self.title}**", f">{self.body}"]
        if self.symbol:
            lines.append(f">标的: `{self.symbol}`")
        if self.signal_type:
            type_label = {"buy": "买入", "sell": "卖出", "stop_loss": "止损", "take_profit": "止盈"}.get(
                self.signal_type, self.signal_type,
            )
            lines.append(f">信号: {type_label}")
        if self.price > 0:
            lines.append(f">价格: {self.price:.2f}")
        if self.quantity > 0:
            lines.append(f">数量: {self.quantity:.4f}")
        return "\n".join(lines)

    def to_html(self) -> str:
        """HTML formatted message for Telegram and email."""
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨", "signal": "📊"}.get(self.level, "📢")
        lines = [f"{emoji} <b>{self.title}</b>", f"<pre>{self.body}</pre>"]
        if self.symbol:
            lines.append(f"标的: <code>{self.symbol}</code>")
        if self.signal_type:
            lines.append(f"信号: {self.signal_type}")
        if self.price > 0:
            lines.append(f"价格: {self.price:.2f}")
        if self.quantity > 0:
            lines.append(f"数量: {self.quantity:.4f}")
        return "\n".join(lines)


# ── Webhook dialect detection ─────────────────────────────────────────────────

def _detect_dialect(url: str) -> str:
    """Auto-detect webhook platform from URL.

    Returns one of: feishu | dingtalk | wecom | slack | discord | generic
    """
    url_lower = url.lower()
    if "open.feishu.cn" in url_lower or "open.larksuite.com" in url_lower:
        return "feishu"
    if "oapi.dingtalk.com" in url_lower:
        return "dingtalk"
    if "qyapi.weixin.qq.com" in url_lower:
        return "wecom"
    if "hooks.slack.com" in url_lower:
        return "slack"
    if "discord.com/api/webhooks" in url_lower:
        return "discord"
    return "generic"


# ── Webhook channel ───────────────────────────────────────────────────────────

_WEBHOOK_DEFAULTS: dict[str, str] = {
    "wecom":  "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=",
    "dingtalk": "https://oapi.dingtalk.com/robot/send?access_token=",
}


def _send_webhook(alert: Alert, url: str, webhook_type: str = "generic") -> bool:
    """Send alert to a webhook URL.  Auto-detects dialect if generic."""
    if webhook_type == "generic":
        webhook_type = _detect_dialect(url)

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
    elif webhook_type == "feishu":
        payload = {
            "msg_type": "text",
            "content": {"text": alert.to_markdown()},
        }
    elif webhook_type == "discord":
        payload = {
            "embeds": [{
                "title": alert.title,
                "description": alert.body,
                "color": {"info": 3447003, "warning": 16776960, "critical": 15158332, "signal": 3066993}.get(alert.level, 0),
                "fields": [],
            }],
        }
        if alert.symbol:
            payload["embeds"][0]["fields"].append({"name": "Symbol", "value": alert.symbol, "inline": True})
        if alert.signal_type:
            payload["embeds"][0]["fields"].append({"name": "Signal", "value": alert.signal_type, "inline": True})
    else:
        # Slack / generic
        payload = {
            "text": alert.to_markdown(),
            "title": alert.title,
            "level": alert.level,
        }
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


# ── Telegram channel ──────────────────────────────────────────────────────────

def _send_telegram(alert: Alert, config: dict) -> bool:
    """Send notification via Telegram Bot API.

    Config must contain: ``bot_token``, ``chat_id``.
    Message format: HTML (supports <b>/<code>/<pre>).
    """
    bot_token = config.get("bot_token", "") or config.get("telegram_bot_token", "")
    chat_id = config.get("chat_id", "") or config.get("telegram_chat_id", "")

    if not bot_token or not chat_id:
        logger.warning("Telegram not fully configured (missing bot_token/chat_id)")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": alert.to_html(),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code < 400:
            return True
        logger.warning("Telegram returned %d: %s", r.status_code, r.text[:200])
        return False
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


# ── Discord channel ───────────────────────────────────────────────────────────

def _send_discord(alert: Alert, config: dict) -> bool:
    """Send notification via Discord Webhook (Embed format)."""
    url = config.get("webhook_url", "") or config.get("discord_webhook_url", "")
    if not url:
        logger.warning("Discord not configured (missing webhook_url)")
        return False

    # Reuse webhook sender with discord type
    return _send_webhook(alert, url, "discord")


# ── Feishu/Lark channel ───────────────────────────────────────────────────────

def _send_feishu(alert: Alert, config: dict) -> bool:
    """Send notification via Feishu/Lark custom bot (msg_type=text)."""
    url = config.get("webhook_url", "") or config.get("feishu_webhook_url", "")
    if not url:
        logger.warning("Feishu not configured (missing webhook_url)")
        return False

    return _send_webhook(alert, url, "feishu")


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

    body = f"{alert.title}\n\n{alert.body}\n"
    if alert.symbol:
        body += f"\nSymbol: {alert.symbol}"
    if alert.signal_type:
        body += f"\nSignal: {alert.signal_type}"
    body += "\n\n---\nAStockPursue Alert"

    msg = MIMEText(body, "plain", "utf-8")
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
    "telegram": _send_telegram,
    "discord": _send_discord,
    "feishu": _send_feishu,
}


def send_alert(alert: Alert, channel_configs: list[dict]) -> dict[str, bool]:
    """Send *alert* through all configured channels.

    Args:
        alert: The alert to send.
        channel_configs: List of channel configs, each with at least a ``type`` key
            (``"webhook"``, ``"email"``, ``"telegram"``, ``"discord"``, ``"feishu"``)
            and relevant connection parameters.

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
        elif ch_type in ("telegram", "discord", "feishu", "email"):
            results[ch_type] = sender(alert, cfg)

    return results
