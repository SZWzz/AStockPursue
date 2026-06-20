"""Notification workflow node — push results to Telegram/Email/Webhook/Discord.

Typical position: workflow tail, receiving BacktestResult or OrderResult
and pushing key metrics to user-configured notification channels.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


# ── Actionable error hints ──────────────────────────────────────────────

_ERROR_HINTS = [
    ("authentication required", "请在设置页面配置 API 密钥，或使用浏览器登录后重试 → Settings → API Key"),
    ("no data", "数据源可能不可用，请检查数据源状态页面或尝试其他数据源 → Data Sources"),
    ("timeout", "执行超时，尝试减少标的数量或扩大K线周期 → 简化策略参数后重试"),
    ("no trading signals", "缺少交易信号输入，请确认上游 Strategy 节点已正确连接 → 检查工作流连线"),
    ("no ohlcv", "缺少行情数据，请确认 OHLCV Loader 节点已连接且数据源可用 → 检查数据源配置"),
    ("import error", "依赖包缺失，请运行 pip install -r requirements.txt 安装所需依赖 → 终端执行"),
    ("permission denied", "权限不足，请联系管理员或检查文件/目录权限 → 检查服务器权限设置"),
    ("not found", "资源未找到，工作流或项目可能已被删除 → 检查项目列表"),
    ("api key", "API 密钥未配置或无效，请在设置中填入有效的密钥 → Settings → API Key"),
    ("connection refused", "无法连接到服务，请确认目标服务正在运行 → 检查网络和服务状态"),
]


def _error_hint(error: str) -> str:
    """Return an actionable hint for a given error message."""
    err_lower = error.lower()
    for pattern, hint in _ERROR_HINTS:
        if pattern in err_lower:
            return hint
    return ""


@register_node
class NotifyNode(BaseNode):
    """Send notifications from workflow canvas.

    Auto-formats upstream backtest results or custom messages and pushes
    them through configured channels (telegram, email, webhook, discord).

    Input ports:
      - backtest_result (optional): Auto-extracts core metrics
      - order_result (optional): Auto-extracts order info
      - custom_message (optional): PARAMS dict with custom content

    Output ports:
      - notify_status: Per-channel send results
    """
    node_type = "send_notification"
    category = "output"
    label = "Send Notification"
    description = "Push results to Telegram/Email/Webhook/Discord — auto-formats from upstream"
    icon = "Bell"
    resource_profile = "io_bound"

    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT, required=False,
                         description="Backtest result to auto-format"),
        BaseNode.in_port("order_result", PortType.PARAMS, required=False,
                         description="Order execution result"),
        BaseNode.in_port("custom_message", PortType.PARAMS, required=False,
                         description="Custom message dict with title/body"),
    ]
    outputs = [
        BaseNode.out_port("notify_status", PortType.PARAMS,
                          description="Per-channel send results"),
    ]
    config_schema = {
        "channels": {
            "title": "Channels",
            "type": "array",
            "items": {"type": "string", "enum": ["telegram", "email", "webhook", "discord", "feishu"]},
            "default": ["telegram"],
        },
        "telegram_chat_id": {
            "title": "Telegram Chat ID", "type": "string", "default": "",
        },
        "telegram_bot_token": {
            "title": "Telegram Bot Token", "type": "string", "default": "",
        },
        "email_to": {
            "title": "Email To", "type": "string", "default": "",
        },
        "webhook_url": {
            "title": "Webhook URL", "type": "string", "default": "",
        },
        "discord_webhook_url": {
            "title": "Discord Webhook URL", "type": "string", "default": "",
        },
        "include_backtest_summary": {
            "title": "Include Backtest Summary", "type": "boolean", "default": True,
        },
        "include_equity_chart": {
            "title": "Include Chart", "type": "boolean", "default": False,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.notify.channels import Alert, send_alert

        channels = config.get("channels", ["telegram"])
        if not channels:
            return {"notify_status": {"sent": False, "reason": "No channels configured"}}

        # Build channel configs
        channel_configs = []
        for ch in channels:
            cfg = {"type": ch}
            if ch == "telegram":
                cfg["chat_id"] = config.get("telegram_chat_id", "")
                cfg["bot_token"] = config.get("telegram_bot_token", "")
            elif ch == "email":
                cfg["email_to"] = config.get("email_to", "")
            elif ch == "webhook":
                cfg["url"] = config.get("webhook_url", "")
            elif ch == "discord":
                cfg["webhook_url"] = config.get("discord_webhook_url", "")
            elif ch == "feishu":
                cfg["webhook_url"] = config.get("webhook_url", "")
            channel_configs.append(cfg)

        # Build alert from inputs
        title = "AStockPursue Notification"
        body = ""
        level = "info"

        # Auto-format backtest result
        bt = inputs.get("backtest_result", {})
        if isinstance(bt, dict) and config.get("include_backtest_summary", True):
            summary = bt.get("summary", {})
            if summary:
                title = "Backtest Complete"
                lines = [
                    f"Total Return: {summary.get('total_return', 0):.2%}",
                    f"Annual Return: {summary.get('annual_return', 0):.2%}",
                    f"Sharpe: {summary.get('sharpe', 0):.2f}",
                    f"Max Drawdown: {summary.get('max_drawdown', 0):.2%}",
                    f"Win Rate: {summary.get('win_rate', 0):.2%}",
                    f"Trades: {summary.get('trade_count', 0)}",
                ]
                body = "\n".join(lines)
                level = "signal"
            elif "error" in bt:
                title = "Backtest Failed"
                err = str(bt.get("error", ""))
                body = err
                # Append actionable guidance based on error pattern
                hint = _error_hint(err)
                if hint:
                    body += f"\n\n💡 {hint}"
                level = "critical"

        # Auto-format order result
        order = inputs.get("order_result", {})
        if isinstance(order, dict) and order.get("submitted"):
            title = "Orders Submitted"
            lines = []
            for o in order.get("submitted", [])[:10]:
                lines.append(f"{o.get('code', '?'):12s} {o.get('side', '?'):4s} qty={o.get('quantity', 0)}")
            if not body:
                body = "\n".join(lines)
            else:
                body += "\n\nOrders:\n" + "\n".join(lines)
            level = "signal"

        # Custom message override
        custom = inputs.get("custom_message", {})
        if isinstance(custom, dict):
            if custom.get("title"):
                title = custom["title"]
            if custom.get("body"):
                body = custom["body"]
            if custom.get("level"):
                level = custom["level"]

        if not body:
            body = "Workflow notification"

        alert = Alert(title=title, body=body, level=level, source="workflow")
        results = send_alert(alert, channel_configs)

        all_ok = all(results.values()) if results else False
        logger.info("NotifyNode: channels=%s results=%s", channels, results)

        # Build error_action for frontend CTA rendering
        error_action = None
        if level == "critical":
            hint = _error_hint(body)
            if hint:
                error_action = hint

        return {
            "notify_status": {
                "sent": all_ok,
                "channels": channels,
                "results": results,
                "error_action": error_action,
            },
            "_summary": {
                "sent": "yes" if all_ok else "partial",
                "channels": len(channels),
                "error_action": error_action,
            },
        }
