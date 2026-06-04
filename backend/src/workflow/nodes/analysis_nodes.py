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
    description = (
        "Analyse backtest performance with Brinson decomposition, factor attribution, "
        "sector attribution, time-series decomposition, and transaction cost analysis."
    )
    icon = "PieChart"
    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT,
                         description="Backtest result with metrics and equity curve"),
        BaseNode.in_port("factor_data", PortType.DF_FACTOR, required=False,
                         description="Factor DataFrame for factor attribution"),
        BaseNode.in_port("codes", PortType.STOCK_LIST, required=False,
                         description="Stock codes for sector attribution"),
    ]
    outputs = [
        BaseNode.out_port("attribution_report", PortType.ATTRIBUTION,
                          description="Full attribution report"),
    ]
    config_schema = {
        "classification": {
            "title": "Classification", "type": "string",
            "enum": ["sw", "gics"], "default": "sw",
        },
        "methods": {
            "title": "Methods", "type": "string",
            "enum": ["all", "brinson", "factor", "sector", "time_series", "tca"], "default": "all",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        bt_result = inputs.get("backtest_result", {})
        if isinstance(bt_result, dict) and bt_result.get("error"):
            return {"attribution_report": {"error": bt_result["error"]}}

        classification = config.get("classification", "sw")
        methods = config.get("methods", "all")

        metrics = bt_result.get("metrics", {}) if isinstance(bt_result, dict) else {}
        equity = bt_result.get("equity_curve") or bt_result.get("equity")
        report: Dict[str, Any] = {
            "classification": classification,
            "methods_requested": methods,
        }

        # ── Basic summary ─────────────────────────────────────────────────────
        if metrics:
            report["summary"] = {
                k: round(float(v), 4)
                for k, v in metrics.items()
                if isinstance(v, (int, float))
                and k in ("sharpe", "max_drawdown", "win_rate", "total_return", "annual_return")
            }
            report["summary"]["trade_count"] = metrics.get("trade_count", 0)

        # ── Use AttributionEngine for advanced methods ────────────────────────
        try:
            from src.services.attribution_engine import AttributionEngine

            engine = AttributionEngine()

            # Convert equity curve to returns series if available
            returns = None
            benchmark_returns = None
            if equity is not None:
                if isinstance(equity, list) and len(equity) > 1:
                    import numpy as np
                    eq = np.array(equity, dtype=float)
                    returns = np.diff(eq) / (eq[:-1] + 1e-9)

            if returns is not None and len(returns) > 1:
                if methods in ("all", "brinson"):
                    try:
                        report["brinson"] = engine.brinson(returns, classification=classification)
                    except Exception as e:
                        report["brinson"] = {"error": str(e)}

                if methods in ("all", "factor"):
                    try:
                        report["factor_attribution"] = engine.factor_attribution(returns)
                    except Exception as e:
                        report["factor_attribution"] = {"error": str(e)}

                if methods in ("all", "time_series"):
                    try:
                        report["time_series"] = engine.time_series_decomposition(returns)
                    except Exception as e:
                        report["time_series"] = {"error": str(e)}

                if methods in ("all", "tca"):
                    try:
                        report["tca"] = engine.transaction_cost_attribution(returns)
                    except Exception as e:
                        report["tca"] = {"error": str(e)}

            # Sector attribution with codes
            codes = inputs.get("codes", [])
            if isinstance(codes, pd.DataFrame):
                codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)
            if codes and methods in ("all", "sector"):
                try:
                    report["sector"] = engine.sector_attribution(codes, classification=classification)
                except Exception as e:
                    report["sector"] = {"error": str(e)}

        except ImportError:
            report["_engine"] = "AttributionEngine not available — showing basic summary only"

        # ── Factor data summary ───────────────────────────────────────────────
        factor_data = inputs.get("factor_data")
        if factor_data is not None and isinstance(factor_data, pd.DataFrame) and not factor_data.empty:
            try:
                report["factor"] = {
                    "factors": list(factor_data.columns)[:20],
                    "shape": list(factor_data.shape),
                }
            except Exception as e:
                report["factor"] = {"error": str(e)}

        return {"attribution_report": report}
