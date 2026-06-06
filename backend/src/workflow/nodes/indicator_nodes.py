"""Technical indicator computation node.

Wraps ScreenerEngine._compute_indicators for built-in indicators (RSI, SMA, returns,
volatility, volume ratio) and exposes them as a workflow node.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)

# ── Built-in indicator presets ─────────────────────────────────────────────────

PRESET_INDICATORS: Dict[str, List[str]] = {
    "all":          ["rsi", "sma_20", "sma_60", "ret_1d", "ret_5d", "ret_20d", "vol_ratio", "high_low_ratio", "volatility_20"],
    "momentum":     ["rsi", "ret_1d", "ret_5d", "ret_20d"],
    "moving_avg":   ["sma_20", "sma_60"],
    "volatility":   ["volatility_20", "high_low_ratio"],
    "volume":       ["vol_ratio"],
}


@register_node
class IndicatorNode(BaseNode):
    node_type = "indicator"; category = "alpha"; label = "Indicator"
    description = (
        "Compute common technical indicators from OHLCV data: "
        "RSI, SMAs, returns, volatility, volume ratio, high/low ratio."
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
        ohlcv = inputs.get("ohlcv_data", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}
        if not ohlcv:
            return {"indicators": {}}

        preset = config.get("preset", "all")
        rsi_period = int(config.get("rsi_period", 14))
        sma_windows = [int(x.strip()) for x in config.get("sma_windows", "20,60").split(",") if x.strip().isdigit()]
        ret_windows = [int(x.strip()) for x in config.get("returns_windows", "1,5,20").split(",") if x.strip().isdigit()]
        vol_window = int(config.get("vol_window", 20))
        wanted = set(PRESET_INDICATORS.get(preset, PRESET_INDICATORS["all"]))

        # ── Build wide panel ──────────────────────────────────────────────────
        all_frames: Dict[str, pd.DataFrame] = {}
        for code, df in ohlcv.items():
            if not isinstance(df, pd.DataFrame):
                continue
            for col in ["close", "volume", "high", "low"]:
                if col not in df.columns:
                    continue
                key = f"{code}__{col}"
                series = df[col].copy()
                series.name = code
                all_frames.setdefault(col, []).append(series)

        panels: Dict[str, pd.DataFrame] = {}
        for col, series_list in all_frames.items():
            if series_list:
                df = pd.concat(series_list, axis=1)
                panels[col] = df.ffill()

        if "close" not in panels:
            return {"indicators": {"error": "No close data found"}}

        close = panels["close"]
        volume = panels.get("volume")
        high = panels.get("high")
        low = panels.get("low")
        results: Dict[str, pd.DataFrame] = {}

        # ── RSI ───────────────────────────────────────────────────────────────
        rsi_key = f"rsi_{rsi_period}"
        if any(k.startswith("rsi") for k in wanted):
            delta = close.diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.rolling(rsi_period, min_periods=rsi_period).mean()
            avg_loss = loss.rolling(rsi_period, min_periods=rsi_period).mean()
            # Wilder smoothing after initial SMA
            for i in range(rsi_period, len(avg_gain)):
                avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (rsi_period - 1) + gain.iloc[i]) / rsi_period
                avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (rsi_period - 1) + loss.iloc[i]) / rsi_period
            rs = avg_gain / avg_loss.replace(0, 1e-9)
            results[rsi_key] = 100.0 - (100.0 / (1.0 + rs))

        # ── SMAs ──────────────────────────────────────────────────────────────
        for w in sma_windows:
            sma_key = f"sma_{w}"
            if sma_key in wanted:
                results[sma_key] = close.rolling(w, min_periods=w).mean()

        # ── Returns ───────────────────────────────────────────────────────────
        for w in ret_windows:
            ret_key = f"ret_{w}d"
            if ret_key in wanted:
                results[ret_key] = close.pct_change(w)

        # ── Volume ratio (vs 20-day average) ──────────────────────────────────
        if "vol_ratio" in wanted and volume is not None:
            vol_ma = volume.rolling(20, min_periods=5).mean()
            results["vol_ratio"] = volume / vol_ma.replace(0, 1)

        # ── High/Low ratio ────────────────────────────────────────────────────
        if "high_low_ratio" in wanted and high is not None and low is not None:
            results["high_low_ratio"] = high / low.replace(0, 1)

        # ── Volatility (annualised from daily returns) ─────────────────────────
        if f"volatility_{vol_window}" in wanted:
            log_ret = close.pct_change().apply(lambda x: x.replace([np.inf, -np.inf], np.nan))  # type: ignore[name-defined]
            results[f"volatility_{vol_window}"] = log_ret.rolling(vol_window, min_periods=vol_window // 2).std() * (252 ** 0.5)

        # ── Filter to wanted indicators ───────────────────────────────────────
        filtered = {k: v for k, v in results.items() if k in wanted or preset == "all"}
        logger.info("Indicator: preset=%s → %d indicator frames", preset, len(filtered))

        # Merge into single wide DataFrame for DF_FACTOR compatibility
        if not filtered:
            return {"indicators": {}}

        # Prefix each indicator's columns with its name for disambiguation
        merged_parts = []
        for name, df in filtered.items():
            df_renamed = df.copy()
            df_renamed.columns = [f"{col}__{name}" for col in df.columns]
            merged_parts.append(df_renamed)

        merged = pd.concat(merged_parts, axis=1)
        return {"indicators": merged}
