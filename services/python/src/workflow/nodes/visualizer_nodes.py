"""Visualizer nodes — passthrough display nodes for backtest results.

Each accepts a ``backtest_result`` from a connected BacktestNode (or similar),
extracts one aspect of the result, and stores it in ``_summary`` for the
frontend to render as a chart or card on the workflow canvas.

Node types:
  - equity_curve:  ECharts equity curve + drawdown chart
  - metrics_view:  KPI card grid (Sharpe, return, maxDD, etc.)
  - trades_view:   Trade history table
"""

from __future__ import annotations

import logging
from typing import Any

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import PortType

logger = logging.getLogger(__name__)


@register_node
class EquityCurveNode(BaseNode):
    """Display equity curve from a backtest result as a chart node on the canvas."""

    node_type = "equity_curve"
    category = "visualization"
    label = "Equity Curve"
    description = "Display equity curve chart from backtest result"
    icon = "TrendingUp"
    resource_profile = "io_bound"

    inputs = [BaseNode.in_port("source", PortType.BACKTEST_RESULT)]
    outputs = [BaseNode.out_port("output", PortType.ANY)]

    config_schema: dict = {}

    async def execute(self, inputs: dict, config: dict) -> dict:
        result: dict = inputs.get("source", {})
        equity_curve: list = result.get("equity_curve", [])
        metrics: dict = result.get("metrics", {})
        summary: dict = result.get("summary", {})

        final_equity = metrics.get("final_value", 0) or metrics.get("final_equity", 0) or summary.get("final_value", 0)
        max_drawdown = metrics.get("max_drawdown", 0) or summary.get("max_drawdown", 0)
        total_return = summary.get("total_return", 0)
        sharpe = summary.get("sharpe", 0)

        return {
            "output": {"equity_curve": equity_curve, "metrics": metrics},
            "_summary": {
                "type": "equity_curve",
                "equity_curve": equity_curve,
                "final_equity": final_equity,
                "max_drawdown": max_drawdown,
                "total_return": total_return,
                "sharpe": sharpe,
            },
        }


@register_node
class MetricsViewNode(BaseNode):
    """Display backtest metrics as a KPI card grid on the canvas."""

    node_type = "metrics_view"
    category = "visualization"
    label = "Metrics"
    description = "Display backtest performance metrics as KPI cards"
    icon = "BarChart3"
    resource_profile = "io_bound"

    inputs = [BaseNode.in_port("source", PortType.BACKTEST_RESULT)]
    outputs = [BaseNode.out_port("output", PortType.ANY)]

    config_schema: dict = {}

    async def execute(self, inputs: dict, config: dict) -> dict:
        result: dict = inputs.get("source", {})
        metrics: dict = result.get("metrics", {})
        summary: dict = result.get("summary", {})

        # Merge metrics and summary for a complete KPI set
        merged: dict[str, Any] = {**summary, **metrics}

        return {
            "output": merged,
            "_summary": {
                "type": "metrics",
                "metrics": merged,
            },
        }


@register_node
class TradesViewNode(BaseNode):
    """Display trade history from a backtest result as a table node on the canvas."""

    node_type = "trades_view"
    category = "visualization"
    label = "Trades"
    description = "Display trade history table from backtest result"
    icon = "FileText"
    resource_profile = "io_bound"

    inputs = [BaseNode.in_port("source", PortType.BACKTEST_RESULT)]
    outputs = [BaseNode.out_port("output", PortType.ANY)]

    config_schema: dict = {}

    async def execute(self, inputs: dict, config: dict) -> dict:
        result: dict = inputs.get("source", {})
        trades: list = result.get("trades", [])
        summary: dict = result.get("summary", {})

        return {
            "output": {"trades": trades},
            "_summary": {
                "type": "trades",
                "trades": trades,
                "trade_count": summary.get("trade_count", len(trades) // 2),
            },
        }
