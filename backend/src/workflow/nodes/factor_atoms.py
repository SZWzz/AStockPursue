"""Atomic factor computation nodes — composable building blocks for factor pipelines.

These nodes are the "lego bricks" of factor construction.  Each node does exactly
one thing: extract a column, compute a rolling transform, perform arithmetic
between two series, or emit a boolean signal.

Nodes are organised in four layers:
    Layer 0 — Data extraction (OHLCV → single-column DF_FACTOR)
    Layer 1 — Transforms      (DF_FACTOR → DF_FACTOR)
    Layer 2 — Arithmetic      (DF_FACTOR × DF_FACTOR → DF_FACTOR)
    Layer 3 — Logic / signals (DF_FACTOR × DF_FACTOR → DF_FACTOR boolean)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType
from src.workflow.nodes._utils import to_factor_df as _to_factor_df

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 0 — Data extraction
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class ColumnExtractNode(BaseNode):
    """Extract a single column (close, volume, high, low, open) from OHLCV data.

    This is the entry point for factor construction — every factor pipeline
    starts by extracting one or more columns from the raw OHLCV feed.
    """

    node_type = "column_extract"
    category = "data"
    label = "Column Extract"
    description = "Extract a single column (close/volume/high/low/open) from OHLCV data as a factor DataFrame"
    icon = "Database"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV,
                         description="OHLCV data dict {code: DataFrame}"),
    ]
    outputs = [
        BaseNode.out_port("series", PortType.DF_FACTOR,
                          description="Single-column factor DataFrame (dates × codes)"),
    ]
    config_schema = {
        "column": {
            "title": "Column", "type": "string",
            "enum": ["close", "volume", "high", "low", "open"],
            "default": "close",
            "inline": True,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        ohlcv = inputs.get("ohlcv_data", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}
        if not ohlcv:
            return {"series": pd.DataFrame()}

        column = config.get("column", "close")
        series_list = []
        for code, df in ohlcv.items():
            if not isinstance(df, pd.DataFrame):
                continue
            if column not in df.columns:
                continue
            s = df[column].copy()
            s.name = code
            series_list.append(s)

        if not series_list:
            return {"series": pd.DataFrame()}

        result = pd.concat(series_list, axis=1).ffill()
        logger.info("ColumnExtract: column=%s → %d codes, %d bars", column, len(series_list), len(result))
        return {"series": result}


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1 — Rolling transforms (Series → Series)
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class MANode(BaseNode):
    """Simple Moving Average over a rolling window."""

    node_type = "ma"
    category = "alpha"
    label = "MA"
    description = "Simple Moving Average over a rolling window of N bars"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("ma", PortType.DF_FACTOR,
                          description="Moving average DataFrame"),
    ]
    config_schema = {
        "window": {
            "title": "Window", "type": "integer", "default": 20,
            "minimum": 1, "maximum": 500,
            "inline": True,
            "description": "Number of bars for the rolling window",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"ma": series}

        window = int(config.get("window", 20))
        result = series.rolling(window, min_periods=max(1, window // 2)).mean()
        return {"ma": result}


@register_node
class EMANode(BaseNode):
    """Exponential Moving Average."""

    node_type = "ema"
    category = "alpha"
    label = "EMA"
    description = "Exponential Moving Average with adjustable span"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("ema", PortType.DF_FACTOR,
                          description="EMA DataFrame"),
    ]
    config_schema = {
        "window": {
            "title": "Window", "type": "integer", "default": 12,
            "minimum": 1, "maximum": 500,
            "inline": True,
            "description": "Span for EMA calculation",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"ema": series}

        window = int(config.get("window", 12))
        result = series.ewm(span=window, min_periods=max(1, window // 2), adjust=False).mean()
        return {"ema": result}


@register_node
class DeltaNode(BaseNode):
    """Absolute difference over N periods: series[t] - series[t-N]."""

    node_type = "delta"
    category = "alpha"
    label = "Delta"
    description = "Absolute difference over N periods: value[t] - value[t-N]"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("delta", PortType.DF_FACTOR,
                          description="Delta DataFrame"),
    ]
    config_schema = {
        "periods": {
            "title": "Periods", "type": "integer", "default": 1,
            "minimum": 1, "maximum": 252,
            "inline": True,
            "description": "Lookback periods for difference",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"delta": series}

        periods = int(config.get("periods", 1))
        result = series.diff(periods)
        return {"delta": result}


@register_node
class PctChangeNode(BaseNode):
    """Percentage change over N periods: (value[t] - value[t-N]) / value[t-N]."""

    node_type = "pct_change"
    category = "alpha"
    label = "Pct Change"
    description = "Percentage change over N periods (returns)"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("returns", PortType.DF_FACTOR,
                          description="Percentage change DataFrame"),
    ]
    config_schema = {
        "periods": {
            "title": "Periods", "type": "integer", "default": 1,
            "minimum": 1, "maximum": 252,
            "inline": True,
            "description": "Lookback periods for percent change",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"returns": series}

        periods = int(config.get("periods", 1))
        result = series.pct_change(periods)
        return {"returns": result}


@register_node
class StdDevNode(BaseNode):
    """Rolling standard deviation (volatility)."""

    node_type = "std_dev"
    category = "alpha"
    label = "StdDev"
    description = "Rolling standard deviation over N bars"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("std", PortType.DF_FACTOR,
                          description="Standard deviation DataFrame"),
    ]
    config_schema = {
        "window": {
            "title": "Window", "type": "integer", "default": 20,
            "minimum": 2, "maximum": 500,
            "inline": True,
            "description": "Rolling window for std calculation",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"std": series}

        window = int(config.get("window", 20))
        result = series.rolling(window, min_periods=max(2, window // 2)).std()
        return {"std": result}


@register_node
class RankNode(BaseNode):
    """Cross-sectional rank (across stocks) at each time point.

    Output ranges from 0 to 1 (fractional rank).
    """

    node_type = "rank"
    category = "alpha"
    label = "Rank"
    description = "Cross-sectional percentile rank across stocks (0–1) at each bar"
    icon = "BarChart3"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("rank", PortType.DF_FACTOR,
                          description="Rank DataFrame (0–1)"),
    ]
    config_schema = {
        "ascending": {
            "title": "Ascending", "type": "string",
            "enum": ["true", "false"],
            "default": "true",
            "inline": True,
            "description": "true = lowest value ranks first, false = highest first",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"rank": series}

        ascending = config.get("ascending", "true") == "true"
        result = series.rank(axis=1, ascending=ascending, pct=True)
        return {"rank": result}


@register_node
class ScaleNode(BaseNode):
    """Scale values: z-score (standardise) or min-max (0–1 normalisation)."""

    node_type = "scale"
    category = "alpha"
    label = "Scale"
    description = "Scale values: z-score (mean 0, std 1) or min-max (0–1)"
    icon = "Layers"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("scaled", PortType.DF_FACTOR,
                          description="Scaled DataFrame"),
    ]
    config_schema = {
        "method": {
            "title": "Method", "type": "string",
            "enum": ["zscore", "minmax"],
            "default": "zscore",
            "inline": True,
            "description": "Scaling method",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"scaled": series}

        method = config.get("method", "zscore")
        if method == "minmax":
            mi, ma = series.min(), series.max()
            denom = (ma - mi).replace(0, 1e-9)
            result = (series - mi) / denom
        else:
            result = (series - series.mean()) / series.std().replace(0, 1e-9)
        return {"scaled": result}


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 2 — Arithmetic (two Series → one Series)
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class ArithmeticNode(BaseNode):
    """Element-wise arithmetic between two factor DataFrames.

    Both inputs must share the same index (dates) and columns (codes).
    """

    node_type = "arithmetic"
    category = "alpha"
    label = "Arithmetic"
    description = "Element-wise add, subtract, multiply, or divide two factor DataFrames"
    icon = "Layers"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("a", PortType.DF_FACTOR,
                         description="Left operand DataFrame"),
        BaseNode.in_port("b", PortType.DF_FACTOR,
                         description="Right operand DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Result DataFrame"),
    ]
    config_schema = {
        "op": {
            "title": "Op", "type": "string",
            "enum": ["add", "sub", "mul", "div", "pow"],
            "default": "add",
            "inline": True,
            "description": "Arithmetic operation",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        a = _to_factor_df(inputs.get("a"))
        b = _to_factor_df(inputs.get("b"))
        if a.empty or b.empty:
            return {"result": pd.DataFrame()}

        op = config.get("op", "add")
        # Align on index & columns
        common_idx = a.index.intersection(b.index)
        common_cols = a.columns.intersection(b.columns)
        if len(common_idx) == 0 or len(common_cols) == 0:
            logger.warning("Arithmetic: no common index/columns — returning empty")
            return {"result": pd.DataFrame()}

        a_aligned = a.loc[common_idx, common_cols]
        b_aligned = b.loc[common_idx, common_cols]

        if op == "add":
            result = a_aligned + b_aligned
        elif op == "sub":
            result = a_aligned - b_aligned
        elif op == "mul":
            result = a_aligned * b_aligned
        elif op == "div":
            result = a_aligned / b_aligned.replace(0, np.nan)
        elif op == "pow":
            result = (a_aligned.clip(lower=-100, upper=100) ** b_aligned.clip(-5, 5)).replace([np.inf, -np.inf], np.nan)
        else:
            result = a_aligned + b_aligned

        return {"result": result}


@register_node
class ExtremumNode(BaseNode):
    """Element-wise max or min between two factor DataFrames."""

    node_type = "extremum"
    category = "alpha"
    label = "Max/Min"
    description = "Element-wise maximum or minimum of two factor DataFrames"
    icon = "Layers"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("a", PortType.DF_FACTOR,
                         description="First operand DataFrame"),
        BaseNode.in_port("b", PortType.DF_FACTOR,
                         description="Second operand DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Result DataFrame"),
    ]
    config_schema = {
        "op": {
            "title": "Op", "type": "string",
            "enum": ["max", "min"],
            "default": "max",
            "inline": True,
            "description": "Maximum or minimum",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        a = _to_factor_df(inputs.get("a"))
        b = _to_factor_df(inputs.get("b"))
        if a.empty or b.empty:
            return {"result": pd.DataFrame()}

        op = config.get("op", "max")
        common_idx = a.index.intersection(b.index)
        common_cols = a.columns.intersection(b.columns)
        if len(common_idx) == 0 or len(common_cols) == 0:
            return {"result": pd.DataFrame()}

        a_aligned = a.loc[common_idx, common_cols]
        b_aligned = b.loc[common_idx, common_cols]

        if op == "max":
            result = np.maximum(a_aligned, b_aligned)
        else:
            result = np.minimum(a_aligned, b_aligned)

        result = pd.DataFrame(result, index=common_idx, columns=common_cols)
        return {"result": result}


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 3 — Logic / signal emission (Series → boolean Series)
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class CrossOverNode(BaseNode):
    """Detect when a fast series crosses a slow series.

    Output is 1 on the bar where the crossover occurs, 0 otherwise.

    direction = "above": golden cross — fast crosses ABOVE slow
    direction = "below": death cross — fast crosses BELOW slow

    event_type = "entry": cross event used as entry signal
    event_type = "exit":  cross event used as exit signal
    """

    node_type = "cross_over"
    category = "alpha"
    label = "CrossOver"
    description = "Detect when fast line crosses slow line (golden or death cross)"
    icon = "GitBranch"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("fast", PortType.DF_FACTOR,
                         description="Fast series (e.g. MA 5)"),
        BaseNode.in_port("slow", PortType.DF_FACTOR,
                         description="Slow series (e.g. MA 20)"),
    ]
    outputs = [
        BaseNode.out_port("signal", PortType.DF_FACTOR,
                          description="Cross signal (1 = cross detected, 0 = otherwise)"),
    ]
    config_schema = {
        "direction": {
            "title": "交叉方向", "type": "string",
            "enum": ["above", "below"],
            "default": "above",
            "inline": True,
            "description": "above=快线上穿慢线(金叉), below=快线下穿慢线(死叉)",
        },
        "event_type": {
            "title": "信号用途", "type": "string",
            "enum": ["entry", "exit"],
            "default": "entry",
            "inline": True,
            "description": "entry=产生入场信号, exit=产生出场信号",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        fast = _to_factor_df(inputs.get("fast"))
        slow = _to_factor_df(inputs.get("slow"))
        if fast.empty or slow.empty:
            return {"signal": pd.DataFrame()}

        direction = config.get("direction", "above")
        # event_type is a semantic label only — doesn't change the math
        # (the same crossover math applies regardless of trading intent)

        # Align
        common_idx = fast.index.intersection(slow.index)
        common_cols = fast.columns.intersection(slow.columns)
        if len(common_idx) < 2 or len(common_cols) == 0:
            return {"signal": pd.DataFrame()}

        f = fast.loc[common_idx, common_cols]
        s = slow.loc[common_idx, common_cols]

        if direction == "below":
            # Death cross: f < s now AND f >= s previously
            below_now = f < s
            below_prev = f.shift(1) >= s.shift(1)
            signal = (below_now & below_prev).astype(float)
        else:
            # Golden cross: f > s now AND f <= s previously
            above_now = f > s
            above_prev = f.shift(1) <= s.shift(1)
            signal = (above_now & above_prev).astype(float)

        return {"signal": signal}


@register_node
class CompareNode(BaseNode):
    """Element-wise comparison between two factor DataFrames.

    Output is 1 where the condition holds, 0 otherwise.
    """

    node_type = "compare"
    category = "alpha"
    label = "Compare"
    description = "Element-wise comparison: a > b, a < b, a >= b, a <= b, a == b, a != b"
    icon = "GitBranch"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("a", PortType.DF_FACTOR,
                         description="Left operand DataFrame"),
        BaseNode.in_port("b", PortType.DF_FACTOR,
                         description="Right operand DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Boolean result (1/0) DataFrame"),
    ]
    config_schema = {
        "op": {
            "title": "Op", "type": "string",
            "enum": ["gt", "lt", "gte", "lte", "eq", "neq"],
            "default": "gt",
            "inline": True,
            "description": "Comparison operator",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        a = _to_factor_df(inputs.get("a"))
        b = _to_factor_df(inputs.get("b"))
        if a.empty or b.empty:
            return {"result": pd.DataFrame()}

        op = config.get("op", "gt")
        common_idx = a.index.intersection(b.index)
        common_cols = a.columns.intersection(b.columns)
        if len(common_idx) == 0 or len(common_cols) == 0:
            return {"result": pd.DataFrame()}

        a_aligned = a.loc[common_idx, common_cols]
        b_aligned = b.loc[common_idx, common_cols]

        if op == "gt":
            result = (a_aligned > b_aligned).astype(float)
        elif op == "lt":
            result = (a_aligned < b_aligned).astype(float)
        elif op == "gte":
            result = (a_aligned >= b_aligned).astype(float)
        elif op == "lte":
            result = (a_aligned <= b_aligned).astype(float)
        elif op == "eq":
            result = (a_aligned == b_aligned).astype(float)
        elif op == "neq":
            result = (a_aligned != b_aligned).astype(float)
        else:
            result = (a_aligned > b_aligned).astype(float)

        return {"result": result}


@register_node
class BoolCombineNode(BaseNode):
    """Combine two boolean (0/1) DataFrames with AND or OR logic."""

    node_type = "bool_combine"
    category = "alpha"
    label = "Bool Combine"
    description = "Combine two boolean (0/1) DataFrames: AND (both true) or OR (either true)"
    icon = "GitBranch"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("a", PortType.DF_FACTOR,
                         description="First boolean DataFrame (0/1)"),
        BaseNode.in_port("b", PortType.DF_FACTOR,
                         description="Second boolean DataFrame (0/1)"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Combined boolean DataFrame"),
    ]
    config_schema = {
        "op": {
            "title": "Op", "type": "string",
            "enum": ["and", "or"],
            "default": "and",
            "inline": True,
            "description": "Logical operation",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        a = _to_factor_df(inputs.get("a"))
        b = _to_factor_df(inputs.get("b"))
        if a.empty or b.empty:
            return {"result": pd.DataFrame()}

        op = config.get("op", "and")
        common_idx = a.index.intersection(b.index)
        common_cols = a.columns.intersection(b.columns)
        if len(common_idx) == 0 or len(common_cols) == 0:
            return {"result": pd.DataFrame()}

        a_aligned = a.loc[common_idx, common_cols]
        b_aligned = b.loc[common_idx, common_cols]

        # Treat values > 0.5 as True for robustness
        a_bool = a_aligned > 0.5
        b_bool = b_aligned > 0.5

        if op == "and":
            result = (a_bool & b_bool).astype(float)
        else:
            result = (a_bool | b_bool).astype(float)

        return {"result": result}


@register_node
class BoolNotNode(BaseNode):
    """Invert a boolean (0/1) DataFrame: 0 → 1, 1 → 0."""

    node_type = "bool_not"
    category = "alpha"
    label = "NOT"
    description = "Invert a boolean (0/1) DataFrame"
    icon = "GitBranch"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("input", PortType.DF_FACTOR,
                         description="Boolean DataFrame (0/1)"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Inverted boolean DataFrame"),
    ]
    config_schema = {}

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("input"))
        if series.empty:
            return {"result": series}

        result = (series <= 0.5).astype(float)
        return {"result": result}


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 3.5 — Extended transforms & conditionals
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class ConstantNode(BaseNode):
    """Output a DataFrame filled with a constant value.

    Takes a reference input to determine the output shape (dates × codes).
    Used primarily by the ExpressionTree → workflow converter for constant leaf nodes.
    """

    node_type = "constant"
    category = "data"
    label = "Constant"
    description = "Output a constant value matching the shape of a reference DataFrame"
    icon = "Circle"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("reference", PortType.DF_FACTOR, required=False,
                         description="Reference DataFrame to match shape (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("value", PortType.DF_FACTOR,
                          description="Constant-filled DataFrame"),
    ]
    config_schema = {
        "constant": {
            "title": "Value", "type": "number", "default": 1.0,
            "inline": True,
            "description": "Constant value to fill",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        ref = _to_factor_df(inputs.get("reference"))
        const_val = float(config.get("constant", 1.0))

        if ref.empty:
            # No reference — produce a minimal 1×1 DataFrame
            return {"value": pd.DataFrame({"_const": [const_val]}, index=[pd.Timestamp.now().normalize()])}

        result = pd.DataFrame(const_val, index=ref.index, columns=ref.columns)
        return {"value": result}


@register_node
class MathTransformNode(BaseNode):
    """Unary mathematical transforms: abs, log, sqrt, neg, inv, sign.

    Operates element-wise on every cell of the input DataFrame.
    """

    node_type = "math_transform"
    category = "alpha"
    label = "Math"
    description = "Unary math: abs, log, sqrt, neg (×-1), inv (1/x), sign"
    icon = "Layers"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Transformed DataFrame"),
    ]
    config_schema = {
        "op": {
            "title": "Op", "type": "string",
            "enum": ["abs", "log", "sqrt", "neg", "inv", "sign"],
            "default": "abs",
            "inline": True,
            "description": "Mathematical transform to apply",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"result": series}

        op = config.get("op", "abs")
        if op == "abs":
            result = series.abs()
        elif op == "log":
            result = np.log(series.clip(lower=1e-12))
        elif op == "sqrt":
            result = np.sqrt(series.clip(lower=0))
        elif op == "neg":
            result = -series
        elif op == "inv":
            result = (1.0 / series.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        elif op == "sign":
            result = np.sign(series)
        else:
            result = series.abs()
        return {"result": result}


@register_node
class RollingExtremumNode(BaseNode):
    """Rolling maximum or minimum over a window.

    Maps to ExpressionTree ts_max / ts_min operators.
    """

    node_type = "rolling_extremum"
    category = "alpha"
    label = "Rolling Max/Min"
    description = "Rolling maximum or minimum over N bars"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Rolling max/min DataFrame"),
    ]
    config_schema = {
        "window": {
            "title": "Window", "type": "integer", "default": 20,
            "minimum": 1, "maximum": 500,
            "inline": True,
        },
        "op": {
            "title": "Op", "type": "string",
            "enum": ["max", "min"],
            "default": "max",
            "inline": True,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"result": series}

        window = int(config.get("window", 20))
        op = config.get("op", "max")
        win = min(window, max(1, len(series) // 4))
        min_p = max(1, win // 2)

        if op == "max":
            result = series.rolling(win, min_periods=min_p).max()
        else:
            result = series.rolling(win, min_periods=min_p).min()
        return {"result": result}


@register_node
class RollingRankNode(BaseNode):
    """Rolling rank over a time-series window.

    At each bar, ranks the last W values and returns the rank (0–1) of the
    most recent observation.  Maps to ExpressionTree ts_rank.
    """

    node_type = "rolling_rank"
    category = "alpha"
    label = "Rolling Rank"
    description = "Rolling percentile rank over N bars (0–1)"
    icon = "BarChart3"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("rank", PortType.DF_FACTOR,
                          description="Rolling rank DataFrame (0–1)"),
    ]
    config_schema = {
        "window": {
            "title": "Window", "type": "integer", "default": 20,
            "minimum": 3, "maximum": 500,
            "inline": True,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"rank": series}

        window = int(config.get("window", 20))
        win = min(window, max(3, len(series) // 4))
        min_p = max(3, win // 2)

        def _rank_last(s: pd.Series) -> float:
            if len(s) < 3:
                return np.nan
            ranked = s.rank(pct=True)
            return float(ranked.iloc[-1])

        result = series.rolling(win, min_periods=min_p).apply(_rank_last, raw=False)
        return {"rank": result}


@register_node
class RollingScaleNode(BaseNode):
    """Rolling z-score: (x - rolling_mean) / rolling_std over a window.

    Maps to ExpressionTree ts_zscore.
    """

    node_type = "rolling_scale"
    category = "alpha"
    label = "Rolling ZScore"
    description = "Rolling z-score normalisation over N bars"
    icon = "Layers"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("series", PortType.DF_FACTOR,
                         description="Input factor DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("zscore", PortType.DF_FACTOR,
                          description="Rolling z-score DataFrame"),
    ]
    config_schema = {
        "window": {
            "title": "Window", "type": "integer", "default": 20,
            "minimum": 2, "maximum": 500,
            "inline": True,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        series = _to_factor_df(inputs.get("series"))
        if series.empty:
            return {"zscore": series}

        window = int(config.get("window", 20))
        win = min(window, max(2, len(series) // 4))
        min_p = max(2, win // 2)

        rolling_mean = series.rolling(win, min_periods=min_p).mean()
        rolling_std = series.rolling(win, min_periods=min_p).std(ddof=1)
        result = (series - rolling_mean) / rolling_std.replace(0, np.nan)
        result = result.replace([np.inf, -np.inf], np.nan)
        return {"zscore": result}


@register_node
class RollingCorrelationNode(BaseNode):
    """Rolling Pearson correlation or covariance between two DataFrames.

    Maps to ExpressionTree ts_corr / ts_cov.
    """

    node_type = "rolling_correlation"
    category = "alpha"
    label = "Rolling Corr/Cov"
    description = "Rolling Pearson correlation or covariance between two factor DataFrames"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("a", PortType.DF_FACTOR,
                         description="First factor DataFrame"),
        BaseNode.in_port("b", PortType.DF_FACTOR,
                         description="Second factor DataFrame"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Rolling correlation/covariance DataFrame"),
    ]
    config_schema = {
        "window": {
            "title": "Window", "type": "integer", "default": 20,
            "minimum": 3, "maximum": 500,
            "inline": True,
        },
        "method": {
            "title": "Method", "type": "string",
            "enum": ["correlation", "covariance"],
            "default": "correlation",
            "inline": True,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        a = _to_factor_df(inputs.get("a"))
        b = _to_factor_df(inputs.get("b"))
        if a.empty or b.empty:
            return {"result": pd.DataFrame()}

        window = int(config.get("window", 20))
        method = config.get("method", "correlation")

        common_idx = a.index.intersection(b.index)
        common_cols = a.columns.intersection(b.columns)
        if len(common_idx) < 3 or len(common_cols) == 0:
            return {"result": pd.DataFrame()}

        a_aligned = a.loc[common_idx, common_cols]
        b_aligned = b.loc[common_idx, common_cols]

        win = min(window, max(3, len(common_idx) // 4))
        min_p = max(3, win // 2)

        ma = a_aligned.rolling(win, min_periods=min_p).mean()
        mb = b_aligned.rolling(win, min_periods=min_p).mean()
        cov = ((a_aligned - ma) * (b_aligned - mb)).rolling(win, min_periods=min_p).mean()

        if method == "correlation":
            sa = a_aligned.rolling(win, min_periods=min_p).std(ddof=1)
            sb = b_aligned.rolling(win, min_periods=min_p).std(ddof=1)
            result = cov / (sa * sb)
        else:
            result = cov

        result = result.replace([np.inf, -np.inf], np.nan)
        return {"result": result}


@register_node
class IfElseNode(BaseNode):
    """Ternary conditional: if condition > 0 then use true_branch else false_branch.

    Maps to ExpressionTree if_else.  All three DataFrames are aligned to
    common dates × codes before applying np.where.
    """

    node_type = "if_else"
    category = "alpha"
    label = "If-Else"
    description = "Ternary: if condition > 0 then value_a else value_b"
    icon = "GitBranch"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("condition", PortType.DF_FACTOR,
                         description="Condition DataFrame (> 0 = True)"),
        BaseNode.in_port("true_branch", PortType.DF_FACTOR,
                         description="Value when condition is True"),
        BaseNode.in_port("false_branch", PortType.DF_FACTOR,
                         description="Value when condition is False"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.DF_FACTOR,
                          description="Selected values DataFrame"),
    ]
    config_schema = {}

    async def execute(self, inputs: dict, config: dict) -> dict:
        cond = _to_factor_df(inputs.get("condition"))
        t_val = _to_factor_df(inputs.get("true_branch"))
        f_val = _to_factor_df(inputs.get("false_branch"))

        if cond.empty:
            return {"result": f_val if not f_val.empty else t_val}

        # Align all three to common index & columns
        common_idx = cond.index
        common_cols = cond.columns
        if not t_val.empty:
            common_idx = common_idx.intersection(t_val.index)
            common_cols = common_cols.union(t_val.columns)
        if not f_val.empty:
            common_idx = common_idx.intersection(f_val.index)
            common_cols = common_cols.union(f_val.columns)
        common_cols = cond.columns.intersection(common_cols)

        if len(common_idx) == 0 or len(common_cols) == 0:
            return {"result": pd.DataFrame()}

        cond_a = cond.reindex(index=common_idx, columns=common_cols).fillna(0)
        t_a = t_val.reindex(index=common_idx, columns=common_cols).fillna(0) if not t_val.empty else pd.DataFrame(0, index=common_idx, columns=common_cols)
        f_a = f_val.reindex(index=common_idx, columns=common_cols).fillna(0) if not f_val.empty else pd.DataFrame(0, index=common_idx, columns=common_cols)

        result = pd.DataFrame(
            np.where(cond_a.to_numpy(dtype=np.float64) > 0,
                     t_a.to_numpy(dtype=np.float64),
                     f_a.to_numpy(dtype=np.float64)),
            index=common_idx,
            columns=common_cols,
        )
        return {"result": result}


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers — imported from _utils
# ═══════════════════════════════════════════════════════════════════════════════
