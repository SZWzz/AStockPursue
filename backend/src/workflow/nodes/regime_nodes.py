"""Market regime detection workflow node.

RegimeNode: OHLCV data → market state classification + recommended strategy families.

Typical connection:
    DataLoadNode → RegimeNode → ExperimentNode
                               → StrategyNode (strategy family recommendation)
"""

from __future__ import annotations

import logging
from typing import Any

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class RegimeNode(BaseNode):
    """Market regime detection node.

    Inputs:
      - ohlcv/DF_OHLCV: OHLCV data

    Outputs:
      - regime/REGIME_RESULT: Market regime classification
      - features/PARAMS: Quantitative feature values
      - segments/PARAMS: Historical regime segments
    """
    node_type = "regime"
    category = "analysis"
    label = "Market Regime"
    description = (
        "Detect market state from OHLCV: bull/bear/range/volatile, "
        "with strategy family hints"
    )
    icon = "Activity"

    inputs = [
        BaseNode.in_port("ohlcv", PortType.DF_OHLCV,
                         description="OHLCV data for regime detection"),
    ]
    outputs = [
        BaseNode.out_port("regime", PortType.REGIME_RESULT,
                          description="Market regime result"),
        BaseNode.out_port("features", PortType.PARAMS,
                          description="Quantitative feature values"),
        BaseNode.out_port("segments", PortType.PARAMS,
                          description="Historical regime segments"),
    ]
    config_schema = {
        "market": {
            "title": "Market",
            "type": "string",
            "enum": ["CN_A", "CN_FUTURES", "CRYPTO", "US_EQUITY", "HK_EQUITY", "FOREX"],
            "default": "CN_A",
        },
        "enable_a_share_specific": {
            "title": "A-Share Specific States",
            "type": "boolean",
            "default": True,
            "description": "Enable limit_up_frenzy, bear_grinding, structural_rotation",
        },
        "lookback": {
            "title": "Lookback Bars",
            "type": "integer",
            "default": 60,
            "minimum": 20,
            "maximum": 500,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        import pandas as pd

        ohlcv = inputs.get("ohlcv", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"single": ohlcv}

        if not ohlcv or not isinstance(ohlcv, dict):
            return {
                "regime": {"error": "No OHLCV data provided"},
                "features": {},
                "segments": [],
            }

        market = config.get("market", "CN_A")
        lookback = int(config.get("lookback", 60))

        from src.services.regime_engine import RegimeEngine

        engine = RegimeEngine(lookback=lookback)

        # Use the first code's data, or aggregate across all
        results = []
        for code, df in ohlcv.items():
            if df is None or df.empty:
                continue
            try:
                result = engine.detect(df, market=market)
                result["code"] = str(code)
                results.append(result)
            except Exception as e:
                logger.warning("Regime detection failed for %s: %s", code, e)

        if not results:
            return {
                "regime": {"error": "No valid OHLCV data"},
                "features": {},
                "segments": [],
            }

        # For multi-code: return the most common regime
        primary = results[0]

        return {
            "regime": {
                "regime": primary.get("regime", "transition"),
                "label": primary.get("label", "Transition"),
                "confidence": primary.get("confidence", 0),
                "strategy_families": primary.get("strategy_families", []),
                "codes_analyzed": len(results),
            },
            "features": primary.get("features", {}),
            "segments": primary.get("segments", []),
        }
