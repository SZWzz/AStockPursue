"""Alpha factor computation node."""

from __future__ import annotations

import logging

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import PortType

logger = logging.getLogger(__name__)


@register_node
class AlphaZooNode(BaseNode):
    node_type = "alpha_zoo"; category = "alpha"; label = "Alpha Zoo"
    description = "Select and compute a pre-built alpha factor from the Zoo (academic, alpha101, gtja191, qlib158)"
    icon = "Microscope"; resource_profile = "cpu_bound"
    inputs = [BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV)]
    outputs = [
        BaseNode.out_port("factor", PortType.DF_FACTOR),
        BaseNode.out_port("factor_result", PortType.FACTOR_RESULT),
    ]
    config_schema = {
        "alpha_id": {"title": "Alpha ID", "type": "string", "default": "", "description": "e.g. 'alpha101_001'"},
        "zoo": {"title": "Zoo", "type": "string", "enum": ["academic", "alpha101", "gtja191", "qlib158", "mined"], "default": "alpha101", "inline": True},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.factors.registry import get_default_registry
        from src.factors.factor_analysis_core import compute_ic_series

        ohlcv = inputs.get("ohlcv_data", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}
        if not ohlcv:
            return {"factor": pd.DataFrame(), "factor_result": {"error": "No input data"}}

        alpha_id = config.get("alpha_id", "")
        zoo = config.get("zoo", "alpha101")
        registry = get_default_registry()

        if not alpha_id:
            available = registry.list(zoo=zoo)
            if not available:
                return {"factor": pd.DataFrame(), "factor_result": {"error": f"No factors in zoo={zoo}"}}
            alpha_id = available[0]

        try:
            factor_df = registry.compute(alpha_id, ohlcv)
        except Exception as e:
            logger.exception("AlphaZoo compute failed")
            return {"factor": pd.DataFrame(), "factor_result": {"error": str(e)}}

        ic_stats = {}
        try:
            closes = {c: df["close"] for c, df in ohlcv.items() if "close" in df.columns}
            if closes:
                price_panel = pd.DataFrame(closes).ffill()
                fwd = price_panel.pct_change(1).shift(-1)
                ic = compute_ic_series(factor_df, fwd)
                ic_stats = {"IC_mean": round(float(ic.mean()), 4), "IC_std": round(float(ic.std()), 4), "IR": round(float(ic.mean() / (ic.std() + 1e-9)), 4)}
        except Exception:
            pass

        return {"factor": factor_df, "factor_result": {"alpha_id": alpha_id, "zoo": zoo, "shape": list(factor_df.shape), "ic_stats": ic_stats}}
