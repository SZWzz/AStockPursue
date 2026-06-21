"""Correlation analysis node — cross-asset correlation matrix."""

from __future__ import annotations

import logging

import pandas as pd
import numpy as np

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import PortType

logger = logging.getLogger(__name__)


@register_node
class CorrelationNode(BaseNode):
    node_type = "correlation"; category = "analysis"; label = "Correlation"
    quick_tool_route = "/correlation"
    description = (
        "Compute cross-asset correlation matrix from OHLCV close prices or factor data. "
        "Supports Pearson and Spearman methods with optional rolling window."
    )
    icon = "BarChart3"
    inputs = [
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV, required=False,
                         description="OHLCV data dict {code: DataFrame} — close prices used"),
        BaseNode.in_port("factor_data", PortType.DF_FACTOR, required=False,
                         description="Factor DataFrame (index=date, columns=codes)"),
    ]
    outputs = [
        BaseNode.out_port("correlation_matrix", PortType.CORRELATION_MATRIX,
                          description="Correlation matrix (labels + matrix array)"),
    ]
    config_schema = {
        "method": {
            "title": "Method", "type": "string",
            "enum": ["pearson", "spearman"], "default": "pearson", "inline": True,
        },
        "lookback_days": {
            "title": "Lookback Days", "type": "integer", "default": 60,
            "minimum": 1, "maximum": 3650,
            "description": "Number of days to include (most recent). 0 = full history.",
        },
        "data_source": {
            "title": "Data Source", "type": "string",
            "enum": ["close_price", "factor"], "default": "close_price",
        },
        "min_overlap_pct": {
            "title": "Min Overlap %", "type": "number", "default": 0.5,
            "minimum": 0.1, "maximum": 1.0,
            "description": "Minimum data overlap ratio to include a pair.",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.services.correlation_engine import CorrelationEngine

        method = config.get("method", "pearson")
        lookback = int(config.get("lookback_days", 60))
        data_source = config.get("data_source", "close_price")
        min_overlap = float(config.get("min_overlap_pct", 0.5))

        engine = CorrelationEngine()

        # ── Build panel ──────────────────────────────────────────────────────
        panel = None
        if data_source == "close_price":
            ohlcv = inputs.get("ohlcv_data", {})
            panel = engine.build_panel_from_ohlcv(ohlcv, column="close")
        else:
            factor_data = inputs.get("factor_data")
            if isinstance(factor_data, pd.DataFrame):
                panel = factor_data

        # ── Compute ───────────────────────────────────────────────────────────
        corr_df, summary = engine.compute_matrix(
            panel, method=method, lookback=lookback,
            min_overlap_pct=min_overlap,
        )

        # Handle error cases
        if "error" in summary:
            labels = list(corr_df.columns) if not corr_df.empty else []
            return {"correlation_matrix": {
                "labels": labels, "matrix": corr_df.values.tolist() if not corr_df.empty else [],
                "error": summary["error"],
            }}

        labels = list(corr_df.columns)
        matrix = corr_df.values.tolist()

        logger.info("Correlation: %d assets, mean=%.3f", len(labels), summary.get("mean_corr") or 0)
        return {"correlation_matrix": {"labels": labels, "matrix": matrix, "summary": summary}}


@register_node
class CrowdingNode(BaseNode):
    """Factor crowding detection — warns when multiple factors are highly correlated.

    Computes pairwise Pearson correlation between factor columns and flags
    pairs exceeding the threshold.  High crowding scores indicate elevated
    risk of crowded trades when multiple strategies trade the same signal.

    Inputs:
      - factor_data/DF_FACTOR: Multi-factor DataFrame (columns = factors)

    Outputs:
      - crowding_report/PARAMS: {crowded_pairs, overall_score, warning}
      - correlation_matrix/CORRELATION_MATRIX: Full pairwise matrix
    """
    node_type = "crowding"
    category = "analysis"
    label = "Crowding Check"
    description = "Detect factor crowding: high pairwise correlations between factors → crowded trade risk"
    icon = "Filter"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("factor_data", PortType.DF_FACTOR,
                         description="Multi-factor DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("crowding_report", PortType.PARAMS,
                          description="Crowding analysis report"),
        BaseNode.out_port("correlation_matrix", PortType.CORRELATION_MATRIX,
                          description="Full pairwise correlation matrix"),
    ]
    config_schema = {
        "threshold": {
            "title": "Crowding Threshold", "type": "number",
            "default": 0.75, "minimum": 0.3, "maximum": 0.99,
        },
        "top_n_pairs": {
            "title": "Top N Pairs", "type": "integer",
            "default": 10, "minimum": 1, "maximum": 50,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.services.correlation_engine import CorrelationEngine

        factor_data = inputs.get("factor_data")
        if isinstance(factor_data, dict):
            factor_data = next(iter(factor_data.values()), None)
        if not isinstance(factor_data, pd.DataFrame) or factor_data.empty:
            return {
                "crowding_report": {"error": "No factor data"},
                "correlation_matrix": {"labels": [], "matrix": []},
            }

        df = factor_data.select_dtypes(include=[np.number])
        if df.shape[1] < 2:
            return {
                "crowding_report": {"error": "Need at least 2 factor columns"},
                "correlation_matrix": {"labels": [], "matrix": []},
            }

        threshold = float(config.get("threshold", 0.75))
        top_n = int(config.get("top_n_pairs", 10))

        engine = CorrelationEngine()
        corr = df.corr(method="pearson")
        crowding = engine.find_crowded_pairs(corr, threshold=threshold, top_n=top_n)

        logger.info("Crowding: %d crowded pairs (%.1f%%), threshold=%.2f",
                     len(crowding["crowded_pairs"]), crowding["overall_score"] * 100, threshold)

        return {
            "crowding_report": crowding,
            "_summary": {
                "crowding": f"{crowding['overall_score_pct']}%",
                "crowded_pairs": len(crowding["crowded_pairs"]),
                "warning": "yes" if crowding.get("warning") and "HIGH" in str(crowding["warning"]) else "no",
            },
            "correlation_matrix": {
                "labels": list(corr.columns),
                "matrix": corr.values.tolist(),
                "summary": {"crowding_score": crowding["overall_score"]},
            },
        }
