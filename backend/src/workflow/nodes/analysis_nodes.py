"""Analysis node — Attribution."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class AttributionNode(BaseNode):
    node_type = "attribution"; category = "analysis"; label = "Attribution"
    description = "Analyze backtest performance: Brinson-style decomposition, factor exposure"
    icon = "PieChart"
    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT),
        BaseNode.in_port("factor_data", PortType.DF_FACTOR, required=False),
    ]
    outputs = [BaseNode.out_port("attribution_report", PortType.ATTRIBUTION)]
    config_schema = {
        "classification": {"title": "Classification", "type": "string", "enum": ["sw", "gics"], "default": "sw"},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        bt_result = inputs.get("backtest_result", {})
        if isinstance(bt_result, dict) and bt_result.get("error"):
            return {"attribution_report": {"error": bt_result["error"]}}

        metrics = bt_result.get("metrics", {}) if isinstance(bt_result, dict) else {}
        report = {"classification": config.get("classification", "sw"), "data_source": "workflow", "summary": {}}

        if metrics:
            report["summary"] = {k: round(float(v), 4) for k, v in metrics.items() if isinstance(v, (int, float)) and k in ("sharpe", "max_drawdown", "win_rate", "total_return", "annual_return")}
            report["summary"]["trade_count"] = metrics.get("trade_count", 0)

        factor_data = inputs.get("factor_data")
        if factor_data is not None and isinstance(factor_data, pd.DataFrame) and not factor_data.empty:
            try:
                report["factor"] = {"factors": list(factor_data.columns)[:10], "shape": list(factor_data.shape)}
            except Exception as e:
                report["factor"] = {"error": str(e)}

        return {"attribution_report": report}
