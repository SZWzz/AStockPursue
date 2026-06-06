"""Notification configuration and test endpoints.

Provides REST API for managing notification channels and sending
test messages through the NotifyEngine.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notify", tags=["notify"])


@router.post("/test")
async def test_notification(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a test alert through configured channels.

    Request body:
        channels: list of channel configs (type + credentials)
        message: optional custom message dict {title, body, level}
    """
    from src.notify.channels import Alert, send_alert

    channels = payload.get("channels", [])
    if not channels:
        raise HTTPException(status_code=400, detail="No channels provided")

    msg = payload.get("message", {})
    alert = Alert(
        title=msg.get("title", "Test Notification"),
        body=msg.get("body", "This is a test alert from AStockPursue."),
        level=msg.get("level", "info"),
        source="test",
    )

    results = send_alert(alert, channels)
    return {"success": all(results.values()), "results": results}


@router.get("/channels")
async def list_available_channels(request: Request) -> dict[str, Any]:
    """List available notification channel types."""
    return {
        "channels": [
            {"type": "telegram", "label": "Telegram Bot", "config_keys": ["bot_token", "chat_id"]},
            {"type": "discord", "label": "Discord Webhook", "config_keys": ["webhook_url"]},
            {"type": "feishu", "label": "Feishu/Lark", "config_keys": ["webhook_url"]},
            {"type": "webhook", "label": "Generic Webhook", "config_keys": ["url"]},
            {"type": "email", "label": "Email (SMTP)", "config_keys": ["smtp_host", "smtp_port", "smtp_user", "smtp_pass", "email_to"]},
        ],
    }
