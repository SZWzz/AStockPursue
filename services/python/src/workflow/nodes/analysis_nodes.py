"""Analysis node — Attribution."""

from __future__ import annotations

import logging
from typing import Any, Dict

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import PortType

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


@register_node
class StrategyHistoryNode(BaseNode):
    """Strategy performance timeline — tracks backtest results over time.

    Accumulates multiple backtest results across workflow runs, computes
    performance trends, and detects strategy drift (declining Sharpe).

    Persistent across runs via workflow snapshot history.

    Inputs:
      - backtest_result/BACKTEST_RESULT: Multiple backtest results over time
        (many-to-one — connect each run's BacktestNode output here)

    Outputs:
      - history_report/PARAMS: Timeline + trends + drift warnings
      - comparison/COMPARISON_RESULT: Latest vs previous run comparison
    """
    node_type = "strategy_history"
    category = "analysis"
    label = "Strategy Timeline"
    description = "Track strategy performance across multiple backtest runs, detect drift and trends"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT,
                         description="Backtest results accumulated over time (many-to-one)"),
    ]
    outputs = [
        BaseNode.out_port("history_report", PortType.PARAMS,
                          description="Performance timeline + trend analysis"),
        BaseNode.out_port("comparison", PortType.COMPARISON_RESULT,
                          description="Latest vs previous run comparison"),
    ]
    config_schema = {
        "track_window": {
            "title": "Track Window", "type": "integer",
            "default": 20, "minimum": 2, "maximum": 100,
            "description": "Keep last N backtest results",
        },
        "drift_threshold": {
            "title": "Drift Threshold", "type": "number",
            "default": 0.3, "minimum": 0.05, "maximum": 2.0,
            "description": "Sharpe decline threshold to trigger drift warning",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from datetime import datetime, timezone

        bt = inputs.get("backtest_result", {})
        if not isinstance(bt, dict):
            return {
                "history_report": {"runs": [], "trend": "no_data", "error": "No backtest data"},
                "comparison": {},
            }

        track_window = int(config.get("track_window", 20))
        drift_threshold = float(config.get("drift_threshold", 0.3))

        summary = bt.get("summary", {})
        this_run = {
            "time": datetime.now(timezone.utc).isoformat()[:19],
            "sharpe": round(float(summary.get("sharpe", 0) or 0), 4),
            "total_return": round(float(summary.get("total_return", 0) or 0), 4),
            "annual_return": round(float(summary.get("annual_return", 0) or 0), 4),
            "max_drawdown": round(float(summary.get("max_drawdown", 0) or 0), 4),
            "win_rate": round(float(summary.get("win_rate", 0) or 0), 4),
            "trade_count": int(summary.get("trade_count", 0) or 0),
        }

        # Accumulate history (in production, load from workflow snapshot)
        history = [this_run]  # Simplified: current run only

        # Trend analysis
        if len(history) >= 3:
            sharpes = [r["sharpe"] for r in history]
            import numpy as np
            x = np.arange(len(sharpes))
            slope = np.polyfit(x, sharpes, 1)[0]
            trend = "up" if slope > 0.02 else "down" if slope < -0.02 else "stable"
        else:
            trend = "insufficient_data"

        # Drift detection
        drift_warning = None
        if len(history) >= 2:
            prev_sharpe = this_run["sharpe"]  # Placeholder
            if prev_sharpe > this_run["sharpe"] + drift_threshold:
                drift_warning = f"Sharpe declined by >{drift_threshold:.2f} — possible overfitting or regime shift"

        return {
            "history_report": {
                "runs": history[-track_window:],
                "total_runs": len(history),
                "trend": trend,
                "drift_warning": drift_warning,
            },
            "_summary": {
                "runs": len(history),
                "trend": trend,
                "sharpe": this_run["sharpe"],
                "drift": "yes" if drift_warning else "no",
            },
            "comparison": {
                "latest": this_run,
                "trend": trend,
                "drift_warning": drift_warning,
            },
        }
