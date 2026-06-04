"""Notification engine — integrates with RiskPipeline to emit alerts.

Hooks into the trading lifecycle:
  - RiskPipeline stop-loss / take-profit / daily-loss triggers
  - TradingEngine errors / circuit breaker
  - Paper trading run state changes

Config stored per-user in ``vt_users.notify_config`` JSONB column.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.notify.channels import Alert, send_alert

logger = logging.getLogger(__name__)


class NotifyEngine:
    """Lightweight notification dispatcher.

    Usage::

        ne = NotifyEngine(user_config)
        ne.alert(Alert("Stop Loss Hit", "600519 @ 1850", level="warning", source="risk"))
    """

    def __init__(self, user_config: dict | None = None):
        self._config = user_config or {}
        self._channels: list[dict] = self._config.get("notify_channels", [])
        self._enabled = self._config.get("notify_enabled", False)
        # Per-level suppression
        self._levels_enabled: set[str] = set(
            self._config.get("notify_levels", ["warning", "critical"])
        )
        # Rate limit: max alerts per minute
        self._rate_limit = int(self._config.get("notify_rate_limit", 10))
        self._sent_count = 0
        self._sent_window_start = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled and len(self._channels) > 0

    def alert(self, alert: Alert) -> dict[str, bool]:
        """Send an alert through all configured channels.

        Silently drops alerts below the configured level threshold or above
        the rate limit.
        """
        if not self.enabled:
            return {}

        if alert.level not in self._levels_enabled:
            return {}

        # Simple rate limiting
        import time
        now = time.monotonic()
        if now - self._sent_window_start > 60:
            self._sent_count = 0
            self._sent_window_start = now
        if self._sent_count >= self._rate_limit:
            logger.warning("Notify rate limit reached (%d/min), dropping alert: %s", self._rate_limit, alert.title)
            return {}
        self._sent_count += 1

        try:
            return send_alert(alert, self._channels)
        except Exception:
            logger.exception("Notify engine failed to send alert")
            return {}


# ── Convenience helpers ───────────────────────────────────────────────────────

def alert_stop_loss(symbol: str, entry_price: float, exit_price: float, pnl_pct: float) -> Alert:
    return Alert(
        title=f"止损触发: {symbol}",
        body=f"入场 {entry_price:.2f} → 出场 {exit_price:.2f} | 亏损 {pnl_pct:.2%}",
        level="warning",
        source="risk",
        metadata={"symbol": symbol, "type": "stop_loss", "pnl_pct": pnl_pct},
    )


def alert_take_profit(symbol: str, entry_price: float, exit_price: float, pnl_pct: float) -> Alert:
    return Alert(
        title=f"止盈触发: {symbol}",
        body=f"入场 {entry_price:.2f} → 出场 {exit_price:.2f} | 盈利 {pnl_pct:.2%}",
        level="info",
        source="risk",
        metadata={"symbol": symbol, "type": "take_profit", "pnl_pct": pnl_pct},
    )


def alert_daily_loss(limit_pct: float, current_loss_pct: float) -> Alert:
    return Alert(
        title=f"每日亏损限额触发",
        body=f"亏损 {current_loss_pct:.2%} 已达限额 {limit_pct:.2%}，暂停新开仓",
        level="critical",
        source="risk",
        metadata={"type": "daily_loss", "limit_pct": limit_pct, "current_pct": current_loss_pct},
    )


def alert_drawdown(current_dd_pct: float, max_dd_pct: float) -> Alert:
    return Alert(
        title=f"回撤告警",
        body=f"当前回撤 {current_dd_pct:.2%}（上限 {max_dd_pct:.2%}）",
        level="critical",
        source="risk",
        metadata={"type": "drawdown", "current_dd": current_dd_pct, "max_dd": max_dd_pct},
    )


def alert_run_error(run_id: str, error: str) -> Alert:
    return Alert(
        title=f"运行异常: {run_id[:12]}",
        body=str(error)[:500],
        level="critical",
        source="system",
        metadata={"run_id": run_id, "type": "run_error"},
    )


def alert_run_state_change(run_id: str, old_state: str, new_state: str) -> Alert:
    return Alert(
        title=f"运行状态变更: {run_id[:12]}",
        body=f"{old_state} → {new_state}",
        level="info",
        source="papertrade",
        metadata={"run_id": run_id, "old_state": old_state, "new_state": new_state},
    )
