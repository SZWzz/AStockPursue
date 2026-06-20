"""Signal construction nodes — bridge factor DataFrames to trading signals.

These nodes convert factor values (DF_FACTOR) into trading signals (SIGNAL)
that the BacktestNode can consume.  They handle stock selection, weight
assignment, rebalancing frequency, and stateful position holding.
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
# HoldSignal — latch: convert cross-events into continuous position
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class HoldSignalNode(BaseNode):
    """Convert point signals (spikes) into a continuous position signal.

    This is the "latch" that makes crossover strategies work:
    - ``enter`` = 1 → position becomes 1 and STAYS 1
    - ``exit`` = 1  → position becomes 0 and STAYS 0
    - Neither pulse → hold previous position

    Without this node, a crossover signal is just a single-bar spike (1 on the
    cross bar, 0 elsewhere).  With HoldSignal, the spike "latches" the position
    open until the opposite spike closes it.

    Typical wiring for a golden/death cross strategy::

        MA(5)  ─→ CrossOver(dir=above) → HoldSignal(enter) ┐
        MA(20) ─→ CrossOver(dir=below) → HoldSignal(exit)  ├→ RankSelect → Backtest
    """

    node_type = "hold_signal"
    category = "strategy"
    label = "Hold/Latch"
    description = "Convert point cross signals into a continuous position — latches on enter pulse, unlatches on exit pulse"
    icon = "GitBranch"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("enter", PortType.DF_FACTOR, required=False,
                         description="Enter signal (1 = open position).  Connect e.g. golden cross output."),
        BaseNode.in_port("exit", PortType.DF_FACTOR, required=False,
                         description="Exit signal (1 = close position).  Connect e.g. death cross output.  "
                                     "If not connected, position is held forever once entered."),
    ]
    outputs = [
        BaseNode.out_port("position", PortType.SIGNAL,
                          description="Continuous position signal dict {code: Series(0 or 1, index=dates)}"),
    ]
    config_schema = {
        "initial": {
            "title": "Initial", "type": "string",
            "enum": ["flat", "long"],
            "default": "flat",
            "inline": True,
            "description": "Initial position state before any signal",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        enter = _to_factor_df(inputs.get("enter"))
        exit_sig = _to_factor_df(inputs.get("exit"))
        initial_long = config.get("initial", "flat") == "long"

        # Determine the universe: dates from union of enter and exit indices
        all_dates: pd.DatetimeIndex = None
        all_codes: List[str] = []

        if not enter.empty:
            all_dates = enter.index
            all_codes = list(enter.columns)
        if not exit_sig.empty:
            all_dates = exit_sig.index if all_dates is None else all_dates.union(exit_sig.index)
            if not all_codes:
                all_codes = list(exit_sig.columns)
            else:
                all_codes = list(set(all_codes) | set(exit_sig.columns))

        if not all_codes or all_dates is None or len(all_dates) == 0:
            return {"position": {}}

        all_dates = all_dates.sort_values()

        # Vectorised: for each code, cummax tracks latched position
        result: Dict[str, pd.Series] = {}
        for code in all_codes:
            # Build enter/exit pulse series aligned to all_dates
            enter_pulse = pd.Series(0, index=all_dates, name=code)
            exit_pulse = pd.Series(0, index=all_dates, name=code)

            if not enter.empty and code in enter.columns:
                common = enter.index.intersection(all_dates)
                enter_pulse.loc[common] = (enter.loc[common, code] > 0.5).astype(int)

            if not exit_sig.empty and code in exit_sig.columns:
                common = exit_sig.index.intersection(all_dates)
                exit_pulse.loc[common] = (exit_sig.loc[common, code] > 0.5).astype(int)

            # Latch: position toggles on enter=1 and exit=1, holds otherwise.
            # cum_enter tracks whether we have ever seen an enter pulse.
            # cum_exit tracks whether we have ever seen an exit pulse.
            # position = (cum_enter - cum_exit).clip(0, 1)
            cum_enter = enter_pulse.cummax()
            if initial_long:
                # Virtual enter at t=0 — position starts long
                cum_enter = cum_enter.clip(lower=1)
            cum_exit = exit_pulse.cummax()
            raw_pos = (cum_enter - cum_exit).clip(0, 1)

            result[code] = raw_pos.astype(float)

        logger.info("HoldSignal: initial=%s → %d codes, %d bars",
                     "long" if initial_long else "flat", len(all_codes), len(all_dates))
        return {"position": result}


# ═══════════════════════════════════════════════════════════════════════════════
# RankSelect — rank stocks by factor, pick top N
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class RankSelectNode(BaseNode):
    """Rank stocks by factor value each bar and select top N with equal weight.

    This is the most common signal construction pattern: "buy the top 10
    stocks by momentum / value / quality".
    """

    node_type = "rank_select"
    category = "strategy"
    label = "Rank Select"
    description = "Rank stocks by factor value at each bar and select top N with equal weight"
    icon = "Target"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("factor", PortType.DF_FACTOR,
                         description="Factor DataFrame (dates × codes, higher = better by default)"),
    ]
    outputs = [
        BaseNode.out_port("signal", PortType.SIGNAL,
                          description="Trading signal dict {code: Series(weight, index=dates)}"),
    ]
    config_schema = {
        "top_n": {
            "title": "Top N", "type": "integer", "default": 10,
            "minimum": 1, "maximum": 100,
            "inline": True,
            "description": "Number of stocks to select",
        },
        "ascending": {
            "title": "Ascending", "type": "string",
            "enum": ["true", "false"],
            "default": "false",
            "inline": True,
            "description": "true = pick lowest values, false = pick highest",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        factor = _to_factor_df(inputs.get("factor"))
        if factor.empty:
            return {"signal": {}}

        top_n = int(config.get("top_n", 10))
        ascending = config.get("ascending", "false") == "true"
        weight = 1.0 / max(top_n, 1)

        # Vectorised: rank each row cross-sectionally, then threshold
        ranked = factor.rank(axis=1, ascending=ascending, method="first", pct=False)
        selected_mask = ranked <= top_n

        # Build {code: Series(weight where selected else 0)}
        signals: Dict[str, pd.Series] = {}
        for code in factor.columns:
            s = pd.Series(0.0, index=factor.index, name=code)
            mask = selected_mask[code]
            s.loc[mask] = weight
            signals[code] = s

        logger.info("RankSelect: top_n=%d ascending=%s → %d codes, %d bars",
                     top_n, ascending, len(factor.columns), len(factor.index))
        return {"signal": signals}


# ═══════════════════════════════════════════════════════════════════════════════
# ThresholdSelect — select stocks where factor crosses threshold
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class ThresholdSelectNode(BaseNode):
    """Select stocks where factor value meets a threshold condition each bar.

    Useful for: "buy when RSI < 30", "buy when volume > 2× average", etc.
    """

    node_type = "threshold_select"
    category = "strategy"
    label = "Threshold Select"
    description = "Select stocks where factor value meets a threshold condition at each bar"
    icon = "Filter"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("factor", PortType.DF_FACTOR,
                         description="Factor DataFrame (dates × codes)"),
    ]
    outputs = [
        BaseNode.out_port("signal", PortType.SIGNAL,
                          description="Trading signal dict {code: Series(weight, index=dates)}"),
    ]
    config_schema = {
        "threshold": {
            "title": "Threshold", "type": "number", "default": 0.0,
            "inline": True,
            "description": "Threshold value for selection",
        },
        "op": {
            "title": "Op", "type": "string",
            "enum": ["gt", "lt", "gte", "lte"],
            "default": "gt",
            "inline": True,
            "description": "Condition: gt = factor > threshold, lt = factor < threshold",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        factor = _to_factor_df(inputs.get("factor"))
        if factor.empty:
            return {"signal": {}}

        threshold = float(config.get("threshold", 0.0))
        op = config.get("op", "gt")

        # Vectorised: compute boolean mask in one shot
        if op == "gt":
            selected_mask = factor > threshold
        elif op == "lt":
            selected_mask = factor < threshold
        elif op == "gte":
            selected_mask = factor >= threshold
        elif op == "lte":
            selected_mask = factor <= threshold
        else:
            selected_mask = factor > threshold

        # Count selected stocks per bar (row-wise)
        n_selected_per_bar = selected_mask.sum(axis=1).clip(lower=1)

        # Equal weight among selected stocks per bar
        weight_df = selected_mask.astype(float).div(n_selected_per_bar, axis=0)

        # Build result dict
        signals: Dict[str, pd.Series] = {}
        for code in factor.columns:
            signals[code] = weight_df[code]

        logger.info("ThresholdSelect: %s %.4f → %d codes, %d bars",
                     op, threshold, len(factor.columns), len(factor.index))
        return {"signal": signals}


# ═══════════════════════════════════════════════════════════════════════════════
# SignalWeight — assign or transform weights
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class SignalWeightNode(BaseNode):
    """Assign or transform weights for an existing signal.

    Two modes:
    - **equal**: Normalise all non-zero weights to equal weight (1/N).
      Useful after threshold/boolean signals.
    - **factor_proportional**: Scale weights by factor values. Stocks with
      higher factor values get higher weight. Requires a factor input.
    """

    node_type = "signal_weight"
    category = "strategy"
    label = "Signal Weight"
    description = "Assign equal or factor-proportional weights to a trading signal"
    icon = "Layers"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("signal", PortType.SIGNAL,
                         description="Input trading signal dict"),
        BaseNode.in_port("factor", PortType.DF_FACTOR, required=False,
                         description="Factor DataFrame for factor_proportional mode"),
    ]
    outputs = [
        BaseNode.out_port("signal", PortType.SIGNAL,
                          description="Weighted trading signal dict"),
    ]
    config_schema = {
        "mode": {
            "title": "Mode", "type": "string",
            "enum": ["equal", "factor_proportional"],
            "default": "equal",
            "inline": True,
            "description": "equal = 1/N per selected stock; factor_proportional = weight by factor value",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        signal = inputs.get("signal", {})
        if not isinstance(signal, dict) or not signal:
            return {"signal": {}}

        mode = config.get("mode", "equal")
        factor = _to_factor_df(inputs.get("factor")) if mode == "factor_proportional" else None

        result: Dict[str, pd.Series] = {}

        if mode == "equal":
            # Vectorised: build a DataFrame from all signal series, then normalise each row
            signal_dfs = {}
            for code, s in signal.items():
                if isinstance(s, pd.Series) and not s.empty:
                    signal_dfs[code] = s
            if not signal_dfs:
                return {"signal": {}}

            signal_df = pd.DataFrame(signal_dfs)
            signal_df = signal_df.fillna(0.0)

            # Count non-zero signals per bar (row-wise)
            n_active = (signal_df != 0).sum(axis=1).clip(lower=1)
            active_mask = signal_df != 0

            # Equal weight: 1/N per active stock
            weight_df = active_mask.astype(float).div(n_active, axis=0)

            for code in signal_df.columns:
                result[code] = weight_df[code]

        elif mode == "factor_proportional" and factor is not None and not factor.empty:
            # Build signal DataFrame and align with factor
            signal_dfs = {}
            for code, s in signal.items():
                if isinstance(s, pd.Series) and code in factor.columns:
                    signal_dfs[code] = s
            if not signal_dfs:
                return {"signal": {}}

            signal_df = pd.DataFrame(signal_dfs)
            common_idx = signal_df.index.intersection(factor.index)
            common_cols = signal_df.columns.intersection(factor.columns)
            if len(common_idx) == 0 or len(common_cols) == 0:
                return {"signal": {k: (v.copy() if isinstance(v, pd.Series) else pd.Series())
                                  for k, v in signal.items()}}

            signal_aligned = signal_df.loc[common_idx, common_cols].fillna(0.0)
            factor_aligned = factor.loc[common_idx, common_cols].abs()

            # Weight by absolute factor value among active stocks per bar
            active_mask = signal_aligned != 0
            weighted = factor_aligned * active_mask
            total_per_bar = weighted.sum(axis=1).clip(lower=1e-9)
            weight_df = weighted.div(total_per_bar, axis=0)

            for code in common_cols:
                result[code] = weight_df[code]

            # Preserve codes not in the factor panel
            for code in signal:
                if code not in result and isinstance(signal.get(code), pd.Series):
                    result[code] = signal[code].copy()
        else:
            result = {k: (v.copy() if isinstance(v, pd.Series) else pd.Series())
                      for k, v in signal.items()}

        logger.info("SignalWeight: mode=%s → %d codes", mode, len(result))
        return {"signal": result}


# ═══════════════════════════════════════════════════════════════════════════════
# Rebalance — control position update frequency
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class RebalanceNode(BaseNode):
    """Control how often the portfolio rebalances.

    Between rebalance dates, the previous weights are held (no changes).
    This simulates real-world trading where you don't adjust positions every bar.

    Example: frequency=20 means rebalance every 20 bars (≈ monthly for daily data).
    """

    node_type = "rebalance"
    category = "strategy"
    label = "Rebalance"
    description = "Hold positions between rebalance dates — only update weights every N bars"
    icon = "Clock"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("signal", PortType.SIGNAL,
                         description="Input trading signal dict (raw, every-bar)"),
    ]
    outputs = [
        BaseNode.out_port("signal", PortType.SIGNAL,
                          description="Rebalanced trading signal dict"),
    ]
    config_schema = {
        "frequency": {
            "title": "Frequency", "type": "integer", "default": 20,
            "minimum": 1, "maximum": 252,
            "inline": True,
            "description": "Rebalance every N bars (1 = every bar, 20 ≈ monthly for daily data)",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        signal = inputs.get("signal", {})
        if not isinstance(signal, dict) or not signal:
            return {"signal": {}}

        frequency = int(config.get("frequency", 20))
        if frequency <= 1:
            return {"signal": {k: (v.copy() if isinstance(v, pd.Series) else pd.Series())
                               for k, v in signal.items()}}

        # Collect all dates
        all_dates: set = set()
        for s in signal.values():
            if isinstance(s, pd.Series):
                all_dates.update(s.index)
        sorted_dates = sorted(all_dates)
        codes = list(signal.keys())

        result: Dict[str, pd.Series] = {}
        for code in codes:
            s = signal.get(code)
            if not isinstance(s, pd.Series):
                result[code] = pd.Series(0.0, index=sorted_dates, name=code)
                continue

            new_s = pd.Series(0.0, index=sorted_dates, name=code)
            last_rebalance_idx = -frequency  # force rebalance at bar 0

            for i, date in enumerate(sorted_dates):
                if i - last_rebalance_idx >= frequency:
                    # Rebalance: use this bar's raw signal weight
                    if date in s.index:
                        new_s.at[date] = s.at[date]
                    last_rebalance_idx = i
                else:
                    # Hold: find the last rebalance weight from any code
                    # (just copy the previous bar's weight — positions stay)
                    if i > 0:
                        new_s.at[date] = new_s.at[sorted_dates[i - 1]]

            result[code] = new_s

        logger.info("Rebalance: frequency=%d bars → %d codes, %d bars",
                     frequency, len(codes), len(sorted_dates))
        return {"signal": result}


# ═══════════════════════════════════════════════════════════════════════════════
# EntrySignal / ExitSignal — label a df_factor as entry or exit trading signal
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class EntrySignalNode(BaseNode):
    """Convert a factor/cross DataFrame into an ENTRY trading signal (SIGNAL type)."""

    node_type = "entry_signal"
    category = "strategy"
    label = "Entry Signal"
    description = "Label a factor/cross DataFrame as an ENTRY trading signal"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("signal", PortType.DF_FACTOR,
                         description="Cross/factor to mark as entry (e.g. golden cross, RSI<30)"),
    ]
    outputs = [
        BaseNode.out_port("entry", PortType.DF_FACTOR,
                          description="Entry signal DataFrame (same shape as input) — connect to HoldSignal.enter"),
    ]
    config_schema = {}

    async def execute(self, inputs: dict, config: dict) -> dict:
        df = _to_factor_df(inputs.get("signal"))
        if df.empty:
            return {"entry": pd.DataFrame()}
        logger.info("EntrySignal: %d codes, %d bars", len(df.columns), len(df))
        return {"entry": df}


@register_node
class ExitSignalNode(BaseNode):
    """Convert a factor/cross DataFrame into an EXIT trading signal (DF_FACTOR type)."""

    node_type = "exit_signal"
    category = "strategy"
    label = "Exit Signal"
    description = "Label a factor/cross DataFrame as an EXIT trading signal"
    icon = "TrendingDown"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("signal", PortType.DF_FACTOR,
                         description="Cross/factor to mark as exit (e.g. death cross, RSI>70)"),
    ]
    outputs = [
        BaseNode.out_port("exit", PortType.DF_FACTOR,
                          description="Exit signal DataFrame (same shape as input) — connect to HoldSignal.exit"),
    ]
    config_schema = {}

    async def execute(self, inputs: dict, config: dict) -> dict:
        df = _to_factor_df(inputs.get("signal"))
        if df.empty:
            return {"exit": pd.DataFrame()}
        logger.info("ExitSignal: %d codes, %d bars", len(df.columns), len(df))
        return {"exit": df}


# ═══════════════════════════════════════════════════════════════════════════════
# Turnover Constraint
# ═══════════════════════════════════════════════════════════════════════════════


@register_node
class TurnoverConstraintNode(BaseNode):
    """Limit single-period portfolio turnover to control trading costs.

    Typical placement: between SignalWeightNode and BacktestNode.
    """

    node_type = "turnover_constraint"
    category = "risk"
    label = "换手率限制"
    description = "限制单期换手率，避免过度调仓带来的交易成本"
    icon = "Gauge"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("target_weights", PortType.SIGNAL,
                         description="策略生成的未受限目标权重"),
        BaseNode.in_port("current_weights", PortType.SIGNAL, required=False,
                         description="当前持仓权重（默认为零）"),
    ]
    outputs = [
        BaseNode.out_port("constrained_weights", PortType.SIGNAL,
                          description="换手率受限后的权重"),
        BaseNode.out_port("turnover_report", PortType.PARAMS,
                          description="换手率统计 + 成本估算"),
    ]
    config_schema = {
        "max_turnover": {
            "title": "最大换手率", "type": "number", "default": 0.5,
            "minimum": 0.05, "maximum": 1.0,
            "description": "单期最大换手率 (0–1)",
        },
        "turnover_cost_bps": {
            "title": "换手成本 (bps)", "type": "number", "default": 10,
            "minimum": 0, "maximum": 100,
            "description": "每单位换手的双向成本估算",
        },
        "mode": {
            "title": "约束模式", "type": "string",
            "enum": ["cap", "scale"], "default": "cap",
            "description": "cap=截断单只权重变化; scale=等比缩放整体",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        target = _to_weight_dict(inputs.get("target_weights", {}))
        current = _to_weight_dict(inputs.get("current_weights", {}))
        max_to = float(config.get("max_turnover", 0.5))
        mode = config.get("mode", "cap")
        cost_bps = float(config.get("turnover_cost_bps", 10))

        if not target:
            return {
                "constrained_weights": target,
                "turnover_report": {"error": "No target weights"},
            }

        # Calculate total turnover
        total_turnover = sum(abs(target.get(c, 0) - current.get(c, 0)) for c in set(target) | set(current))

        if total_turnover <= max_to:
            # Within limit — pass through
            return {
                "constrained_weights": target,
                "turnover_report": {
                    "total_turnover": round(total_turnover, 4),
                    "cost_estimate_bps": round(total_turnover * cost_bps, 2),
                    "constrained": False,
                    "mode": mode,
                },
            }

        # Apply constraint
        constrained: dict[str, float] = {}
        if mode == "scale":
            # Proportional scaling: shrink all weight changes proportionally
            scale = max_to / total_turnover
            for c in set(target) | set(current):
                tw = target.get(c, 0)
                cw = current.get(c, 0)
                constrained[c] = cw + (tw - cw) * scale
        else:
            # Cap mode: clip individual weight changes to max_turnover
            for c in set(target) | set(current):
                tw = target.get(c, 0)
                cw = current.get(c, 0)
                diff = tw - cw
                if abs(diff) > max_to:
                    diff = max_to * (1 if diff > 0 else -1)
                constrained[c] = cw + diff

        constrained_turnover = sum(abs(constrained.get(c, 0) - current.get(c, 0))
                                  for c in set(constrained) | set(current))

        logger.info("Turnover: %.1f%% → %.1f%% (max %.1f%%, mode=%s)",
                     total_turnover * 100, constrained_turnover * 100, max_to * 100, mode)

        return {
            "constrained_weights": constrained,
            "turnover_report": {
                "original_turnover": round(total_turnover, 4),
                "constrained_turnover": round(constrained_turnover, 4),
                "cost_estimate_bps": round(constrained_turnover * cost_bps, 2),
                "constrained": True,
                "mode": mode,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers — imported from _utils
# ═══════════════════════════════════════════════════════════════════════════════
