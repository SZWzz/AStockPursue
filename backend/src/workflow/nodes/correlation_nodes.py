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
            "enum": ["pearson", "spearman"], "default": "pearson",
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
