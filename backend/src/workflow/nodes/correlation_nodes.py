"""Correlation analysis node — cross-asset correlation matrix."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd
import numpy as np

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class CorrelationNode(BaseNode):
    node_type = "correlation"; category = "analysis"; label = "Correlation"
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
        method = config.get("method", "pearson")
        lookback = int(config.get("lookback_days", 60))
        data_source = config.get("data_source", "close_price")
        min_overlap = float(config.get("min_overlap_pct", 0.5))

        # ── Build price panel ─────────────────────────────────────────────────
        panel = None

        if data_source == "close_price":
            ohlcv = inputs.get("ohlcv_data", {})
            if isinstance(ohlcv, pd.DataFrame):
                ohlcv = {"panel": ohlcv}
            if ohlcv:
                closes = {}
                for code, df in ohlcv.items():
                    if isinstance(df, pd.DataFrame) and "close" in df.columns:
                        closes[code] = df["close"]
                if closes:
                    panel = pd.DataFrame(closes).ffill()
        else:
            factor_data = inputs.get("factor_data")
            if isinstance(factor_data, pd.DataFrame):
                panel = factor_data

        if panel is None or panel.empty:
            return {"correlation_matrix": {"labels": [], "matrix": [], "error": "No data"}}

        # ── Slice lookback ────────────────────────────────────────────────────
        if lookback > 0 and len(panel) > lookback:
            panel = panel.iloc[-lookback:]

        # ── Drop columns with too little overlap ──────────────────────────────
        min_obs = max(2, int(len(panel) * min_overlap))
        panel = panel.dropna(axis=1, thresh=min_obs)
        if panel.shape[1] < 2:
            return {"correlation_matrix": {"labels": list(panel.columns), "matrix": [], "error": "Insufficient data after overlap filter"}}

        # ── Compute correlation ───────────────────────────────────────────────
        corr_df = panel.corr(method=method)  # type: ignore[call-overload]
        labels = list(corr_df.columns)
        matrix = corr_df.values.tolist()

        # ── Summary stats ─────────────────────────────────────────────────────
        upper_tri = corr_df.where(np.triu(np.ones(corr_df.shape, dtype=bool), k=1))
        values = upper_tri.values.flatten()
        values = values[~np.isnan(values)]
        summary = {
            "n_assets": len(labels),
            "mean_corr": round(float(np.mean(values)), 4) if len(values) > 0 else None,
            "max_corr": round(float(np.max(values)), 4) if len(values) > 0 else None,
            "min_corr": round(float(np.min(values)), 4) if len(values) > 0 else None,
            "method": method,
            "lookback_days": lookback,
        }

        logger.info("Correlation: %d assets, mean=%.3f", len(labels), summary["mean_corr"] or 0)
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
        import numpy as np

        factor_data = inputs.get("factor_data")
        if isinstance(factor_data, dict):
            # Take first DataFrame if dict
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

        # Compute pairwise Pearson correlation
        corr = df.corr(method="pearson")
        cols = list(corr.columns)

        # Extract high-correlation pairs (upper triangle only)
        crowded_pairs = []
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                val = float(corr.iloc[i, j])
                if abs(val) >= threshold:
                    crowded_pairs.append({
                        "factor_a": cols[i], "factor_b": cols[j],
                        "correlation": round(val, 4),
                    })

        crowded_pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)
        crowded_pairs = crowded_pairs[:top_n]

        n_total_pairs = len(cols) * (len(cols) - 1) // 2
        overall_score = len(crowded_pairs) / max(n_total_pairs, 1)

        warning = None
        if overall_score > 0.30:
            warning = "HIGH: Over 30% of factor pairs are highly correlated — crowded trade risk is elevated"
        elif overall_score > 0.15:
            warning = "MODERATE: 15-30% of pairs correlated — monitor for concentration"
        elif overall_score > 0.05:
            warning = "LOW: Minor crowding detected"

        logger.info("Crowding: %d crowded pairs (%.1f%%), threshold=%.2f",
                     len(crowded_pairs), overall_score * 100, threshold)

        return {
            "crowding_report": {
                "crowded_pairs": crowded_pairs,
                "overall_score": round(overall_score, 4),
                "overall_score_pct": round(overall_score * 100, 1),
                "warning": warning,
                "threshold": threshold,
                "total_pairs": n_total_pairs,
                "total_factors": len(cols),
            },
            "_summary": {
                "crowding": f"{round(overall_score * 100, 1)}%",
                "crowded_pairs": len(crowded_pairs),
                "warning": "yes" if warning and "HIGH" in warning else "no",
            },
            "correlation_matrix": {
                "labels": cols,
                "matrix": corr.values.tolist(),
                "summary": {"crowding_score": round(overall_score, 4)},
            },
        }
