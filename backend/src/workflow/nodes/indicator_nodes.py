"""Technical indicator computation node.

Delegates all computation to IndicatorEngine.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class IndicatorNode(BaseNode):
    node_type = "indicator"; category = "alpha"; label = "Indicator"
    description = (
        "Compute common technical indicators from OHLCV data: "
        "RSI, SMAs, returns, volatility, volume ratio, high/low ratio, MACD, Bollinger, ATR."
    )
    icon = "FlaskConical"
    resource_profile = "cpu_bound"
    inputs = [
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV,
                         description="OHLCV data dict {code: DataFrame(o,h,l,c,v)}"),
    ]
    outputs = [
        BaseNode.out_port("indicators", PortType.DF_FACTOR,
                          description="Indicator DataFrame(s) keyed by indicator name"),
    ]
    config_schema = {
        "preset": {
            "title": "Preset", "type": "string",
            "enum": ["all", "momentum", "moving_avg", "volatility", "volume"],
            "default": "all", "inline": True,
        },
        "rsi_period": {
            "title": "RSI Period", "type": "integer", "default": 14,
            "minimum": 2, "maximum": 100,
        },
        "sma_windows": {
            "title": "SMA Windows", "type": "string", "default": "20,60",
            "description": "Comma-separated SMA periods",
        },
        "returns_windows": {
            "title": "Returns Windows", "type": "string", "default": "1,5,20",
            "description": "Comma-separated return lookback days",
        },
        "vol_window": {
            "title": "Volatility Window", "type": "integer", "default": 20,
            "minimum": 5, "maximum": 252,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.services.indicator_engine import IndicatorEngine, PRESET_INDICATORS

        ohlcv = inputs.get("ohlcv_data", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}
        if not ohlcv:
            return {"indicators": {}}

        preset = config.get("preset", "all")
        rsi_period = int(config.get("rsi_period", 14))
        sma_windows = [
            int(x.strip()) for x in config.get("sma_windows", "20,60").split(",")
            if x.strip().isdigit()
        ]
        ret_windows = [
            int(x.strip()) for x in config.get("returns_windows", "1,5,20").split(",")
            if x.strip().isdigit()
        ]
        vol_window = int(config.get("vol_window", 20))
        wanted = set(PRESET_INDICATORS.get(preset, PRESET_INDICATORS["all"]))

        engine = IndicatorEngine()

        # Build panels
        panels = engine.build_panels(ohlcv)
        if "close" not in panels:
            return {"indicators": {"error": "No close data found"}}

        # Batch compute
        results = engine.compute_all(
            close=panels["close"],
            volume=panels.get("volume"),
            high=panels.get("high"),
            low=panels.get("low"),
            preset=preset,
            rsi_period=rsi_period,
            sma_windows=sma_windows,
            ret_windows=ret_windows,
            vol_window=vol_window,
        )

        # Filter to wanted keys
        filtered = {k: v for k, v in results.items() if k in wanted or preset == "all"}
        logger.info("Indicator: preset=%s → %d indicator frames", preset, len(filtered))

        # Merge into single wide DataFrame for DF_FACTOR compatibility
        if not filtered:
            return {"indicators": {}}

        merged_parts = []
        for name, df in filtered.items():
            df_renamed = df.copy()
            df_renamed.columns = [f"{col}__{name}" for col in df.columns]
            merged_parts.append(df_renamed)

        merged = pd.concat(merged_parts, axis=1)
        return {"indicators": merged}
