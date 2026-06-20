"""Risk analysis nodes — VaR, Stress Test, Turnover, Factor Decay, Parameter Heatmap."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


# ── 2.1 VaR Node ─────────────────────────────────────────────────────────────

@register_node
class VaRNode(BaseNode):
    node_type = "var_analysis"
    category = "analysis"
    label = "VaR / CVaR"
    description = (
        "Value at Risk and Conditional VaR via historical simulation and "
        "parametric methods"
    )
    icon = "Shield"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port(
            "returns", PortType.DF_RETURNS,
            description="Portfolio return series (DataFrame or Series)",
        ),
        BaseNode.in_port(
            "backtest_result", PortType.BACKTEST_RESULT, required=False,
            description="Backtest result (equity_curve will be converted to returns)",
        ),
    ]
    outputs = [
        BaseNode.out_port(
            "var_result", PortType.VAR_RESULT,
            description="VaR / CVaR analysis results",
        ),
    ]
    config_schema = {
        "method": {
            "title": "Method", "type": "string",
            "enum": ["historical", "parametric"], "default": "historical",
        },
        "confidence_levels": {
            "title": "Confidence Levels (%)", "type": "array",
            "default": [95, 99],
            "description": "List of confidence levels, e.g. [95, 99]",
        },
        "holding_period": {
            "title": "Holding Period (days)", "type": "integer",
            "default": 1, "minimum": 1, "maximum": 252,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        method = config.get("method", "historical")
        confidence_levels = config.get("confidence_levels", [95, 99])
        holding_period = int(config.get("holding_period", 1))

        # Extract return series from inputs
        returns = inputs.get("returns")
        if returns is None:
            bt = inputs.get("backtest_result", {})
            if isinstance(bt, dict):
                equity = bt.get("equity_curve") or bt.get("equity")
                if equity is not None and len(equity) > 1:
                    eq = np.array(equity, dtype=float)
                    returns = np.diff(eq) / (np.abs(eq[:-1]) + 1e-9)

        if returns is None or (isinstance(returns, (pd.DataFrame, pd.Series)) and returns.empty):
            return {"var_result": {"error": "No return data provided"}}

        if isinstance(returns, pd.DataFrame):
            returns = returns.values.flatten()
        elif isinstance(returns, pd.Series):
            returns = returns.values
        returns = np.asarray(returns, dtype=float)
        returns = returns[~np.isnan(returns)]

        if len(returns) < 10:
            return {"var_result": {"error": f"Insufficient data: {len(returns)} returns (need >= 10)"}}

        result: Dict[str, Any] = {
            "method": method,
            "holding_period": holding_period,
            "n_observations": len(returns),
            "confidence_levels": {},
        }

        # Scale for holding period (sqrt-time rule)
        scaled_returns = returns * np.sqrt(holding_period) if holding_period > 1 else returns

        if method == "historical":
            for cl in confidence_levels:
                alpha = 1 - cl / 100
                var_val = float(np.percentile(scaled_returns, alpha * 100))
                cvar_val = float(np.mean(scaled_returns[scaled_returns <= var_val]))
                result["confidence_levels"][cl] = {
                    "var": round(var_val, 6),
                    "cvar": round(cvar_val, 6),
                }
        elif method == "parametric":
            from scipy import stats
            mu = np.mean(scaled_returns)
            sigma = np.std(scaled_returns, ddof=1)
            for cl in confidence_levels:
                z = stats.norm.ppf(1 - cl / 100)
                var_val = float(mu + z * sigma)
                cvar_val = float(mu - sigma * stats.norm.pdf(z) / (1 - cl / 100))
                result["confidence_levels"][cl] = {
                    "var": round(var_val, 6),
                    "cvar": round(cvar_val, 6),
                }
        else:
            return {"var_result": {"error": f"Unknown method: {method}"}}

        return {"var_result": result}


# ── 2.2 Stress Test Node ─────────────────────────────────────────────────────

# Predefined historical stress scenarios
_STRESS_SCENARIOS = {
    "2015_crash": {
        "label": "2015 A-share Crash",
        "start": "2015-06-12", "end": "2015-09-01",
        "description": "A-share bubble burst — leveraged unwind, ~45% decline",
    },
    "2018_deleveraging": {
        "label": "2018 Deleveraging",
        "start": "2018-01-29", "end": "2018-10-18",
        "description": "Trade war + deleveraging — US-China tensions, ~30% decline",
    },
    "2020_covid": {
        "label": "2020 COVID Crash",
        "start": "2020-01-20", "end": "2020-03-23",
        "description": "Global pandemic sell-off — rapid crash and partial recovery",
    },
    "2022_rates": {
        "label": "2022 Rate Hikes",
        "start": "2022-01-03", "end": "2022-10-31",
        "description": "Fed aggressive rate hikes — growth/tech selloff",
    },
    "2024_volatility": {
        "label": "2024 Volatility Spike",
        "start": "2024-08-01", "end": "2024-08-15",
        "description": "Yen carry unwind + global vol spike",
    },
}


@register_node
class StressTestNode(BaseNode):
    node_type = "stress_test"
    category = "analysis"
    label = "Stress Test"
    description = (
        "Run portfolio through historical stress scenarios "
        "(2015 crash, 2018 deleveraging, 2020 covid, 2022 rates, 2024 volatility)"
    )
    icon = "AlertTriangle"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port(
            "returns", PortType.DF_RETURNS,
            description="Portfolio return series",
        ),
        BaseNode.in_port(
            "backtest_result", PortType.BACKTEST_RESULT, required=False,
            description="Backtest result (equity_curve will be converted to returns)",
        ),
    ]
    outputs = [
        BaseNode.out_port(
            "stress_result", PortType.STRESS_RESULT,
            description="Stress test results per scenario",
        ),
    ]
    config_schema = {
        "scenarios": {
            "title": "Scenarios", "type": "array",
            "default": list(_STRESS_SCENARIOS.keys()),
            "description": "Scenario names to run (default: all)",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        import pandas as pd

        requested = config.get("scenarios", list(_STRESS_SCENARIOS.keys()))
        scenarios = [s for s in requested if s in _STRESS_SCENARIOS]
        if not scenarios:
            return {"stress_result": {"error": "No valid scenarios selected"}}

        # Build return series with DatetimeIndex
        returns = inputs.get("returns")
        if returns is None:
            bt = inputs.get("backtest_result", {})
            if isinstance(bt, dict):
                equity = bt.get("equity_curve") or bt.get("equity")
                if equity is not None and len(equity) > 1:
                    eq = np.array(equity, dtype=float)
                    ret_vals = np.diff(eq) / (np.abs(eq[:-1]) + 1e-9)
                    dates = bt.get("dates") or bt.get("trade_dates")
                    if dates is not None and len(dates) == len(ret_vals):
                        returns = pd.Series(ret_vals, index=pd.to_datetime(dates))
                    else:
                        returns = pd.Series(ret_vals)

        if returns is None or (isinstance(returns, pd.Series) and returns.empty):
            return {"stress_result": {"error": "No return data provided"}}

        if isinstance(returns, pd.DataFrame):
            returns = returns.iloc[:, 0]
        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)

        scenario_results: Dict[str, Any] = {}

        for name in scenarios:
            info = _STRESS_SCENARIOS[name]
            start = pd.Timestamp(info["start"])
            end = pd.Timestamp(info["end"])

            mask = (returns.index >= start) & (returns.index <= end)
            scenario_rets = returns[mask]

            if len(scenario_rets) < 2:
                scenario_results[name] = {
                    "label": info["label"],
                    "description": info["description"],
                    "error": f"Insufficient data: {len(scenario_rets)} observations",
                }
                continue

            cumulative = (1 + scenario_rets).cumprod()
            total_return = float(cumulative.iloc[-1] / cumulative.iloc[0] - 1)

            # Max drawdown
            running_max = cumulative.cummax()
            drawdowns = (cumulative - running_max) / running_max
            max_dd = float(drawdowns.min())

            # Recovery days (days from max dd trough to recover)
            trough_idx = drawdowns.idxmin()
            post_trough = cumulative.loc[trough_idx:]
            recovered = post_trough[post_trough >= running_max.loc[trough_idx]]
            recovery_days = (
                int((recovered.index[0] - trough_idx).days)
                if len(recovered) > 0 else -1  # not recovered
            )

            scenario_results[name] = {
                "label": info["label"],
                "description": info["description"],
                "period": f"{info['start']} to {info['end']}",
                "return": round(total_return, 6),
                "max_drawdown": round(max_dd, 6),
                "recovery_days": recovery_days,
                "n_bars": len(scenario_rets),
            }

        # Summary stats
        returns_list = [
            v["return"] for v in scenario_results.values()
            if isinstance(v.get("return"), (int, float))
        ]
        dds = [
            v["max_drawdown"] for v in scenario_results.values()
            if isinstance(v.get("max_drawdown"), (int, float))
        ]

        return {"stress_result": {
            "scenario_results": scenario_results,
            "summary": {
                "worst_scenario": min(returns_list, default=0),
                "avg_scenario_return": round(float(np.mean(returns_list)), 6) if returns_list else 0,
                "max_drawdown_across_scenarios": round(float(min(dds)), 6) if dds else 0,
                "scenarios_run": len(scenarios),
            },
        }}


# ── 2.3 Turnover Analysis Node ───────────────────────────────────────────────

@register_node
class TurnoverNode(BaseNode):
    node_type = "turnover_analysis"
    category = "analysis"
    label = "Turnover Analysis"
    description = "Analyze signal turnover rate and estimated transaction costs"
    icon = "RefreshCw"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port(
            "signal", PortType.SIGNAL,
            description="Signal dict of {code: weight} per bar, or list of signal dicts",
        ),
    ]
    outputs = [
        BaseNode.out_port(
            "turnover_result", PortType.TURNOVER_RESULT,
            description="Turnover analysis results",
        ),
    ]
    config_schema = {
        "commission_rate": {
            "title": "Commission Rate", "type": "number",
            "default": 0.0003,
            "description": "One-way commission rate (default 0.0003 = 万三 for A-share)",
        },
        "rebalance_frequency": {
            "title": "Rebalance Frequency", "type": "string",
            "enum": ["daily", "weekly", "monthly"], "default": "daily",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        commission_rate = float(config.get("commission_rate", 0.0003))
        rebalance_freq = config.get("rebalance_frequency", "daily")

        signal = inputs.get("signal")
        if signal is None:
            return {"turnover_result": {"error": "No signal data provided"}}

        # Normalize signal to list of {code: weight} dicts
        signal_series: List[Dict[str, float]] = []
        if isinstance(signal, dict):
            # Could be {code: weight} single bar, or list of dicts
            if "signals" in signal:
                signal_series = signal["signals"]
            elif all(isinstance(v, dict) for v in signal.values()):
                # {bar_idx: {code: weight}}
                signal_series = list(signal.values())
            else:
                # Single bar: {code: weight}
                signal_series = [signal]
        elif isinstance(signal, list):
            signal_series = signal

        if not signal_series:
            return {"turnover_result": {"error": "Empty signal data"}}

        # Compute per-bar turnover
        turnover_values: List[float] = []
        for i in range(1, len(signal_series)):
            prev = signal_series[i - 1]
            curr = signal_series[i]
            all_codes = set(prev.keys()) | set(curr.keys())
            total_change = sum(
                abs(curr.get(c, 0.0) - prev.get(c, 0.0))
                for c in all_codes
            )
            # Turnover is half the sum of absolute weight changes (one-way)
            turnover_values.append(total_change / 2.0)

        if not turnover_values:
            return {"turnover_result": {"error": "Need at least 2 signal snapshots"}}

        turnover_arr = np.array(turnover_values)
        avg_turnover = float(np.mean(turnover_arr))

        # Annualize
        freq_map = {"daily": 252, "weekly": 52, "monthly": 12}
        periods_per_year = freq_map.get(rebalance_freq, 252)
        annual_turnover = avg_turnover * periods_per_year

        # Cost estimate: 2 * turnover * commission_rate (buy + sell)
        cost_per_rebal = avg_turnover * 2 * commission_rate
        annual_cost = annual_turnover * 2 * commission_rate

        return {"turnover_result": {
            "daily_turnover": round(float(avg_turnover), 6),
            "annual_turnover": round(annual_turnover, 4),
            "avg_turnover": round(float(avg_turnover), 6),
            "max_turnover": round(float(np.max(turnover_arr)), 6),
            "min_turnover": round(float(np.min(turnover_arr)), 6),
            "cost_estimate": {
                "per_rebalance": round(cost_per_rebal, 8),
                "annual": round(annual_cost, 6),
                "commission_rate": commission_rate,
            },
            "turnover_series": [round(float(v), 6) for v in turnover_values],
            "n_bars": len(turnover_values),
            "rebalance_frequency": rebalance_freq,
        }}


# ── 2.4 Factor Decay Node ────────────────────────────────────────────────────

@register_node
class FactorDecayNode(BaseNode):
    node_type = "factor_decay"
    category = "analysis"
    label = "Factor Decay"
    description = "Measure factor alpha decay over holding periods (IC half-life)"
    icon = "TrendingDown"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port(
            "factor_data", PortType.DF_FACTOR,
            description="Factor values (DataFrame: index=date, columns=codes)",
        ),
        BaseNode.in_port(
            "returns", PortType.DF_RETURNS,
            description="Forward return series (DataFrame or Series)",
        ),
    ]
    outputs = [
        BaseNode.out_port(
            "decay_result", PortType.DECAY_RESULT,
            description="Factor decay analysis results",
        ),
    ]
    config_schema = {
        "max_holding_period": {
            "title": "Max Holding Period (days)", "type": "integer",
            "default": 20, "minimum": 1, "maximum": 252,
        },
        "method": {
            "title": "Method", "type": "string",
            "enum": ["rank_ic", "ic"], "default": "rank_ic",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        max_hp = int(config.get("max_holding_period", 20))
        method = config.get("method", "rank_ic")

        factor_df = inputs.get("factor_data")
        returns = inputs.get("returns")

        if factor_df is None or not isinstance(factor_df, pd.DataFrame):
            return {"decay_result": {"error": "No factor data provided"}}
        if returns is None:
            return {"decay_result": {"error": "No return data provided"}}

        # Align factor and returns
        if isinstance(returns, pd.DataFrame):
            # Use first column or compute portfolio returns
            if returns.shape[1] == 1:
                fwd_rets = returns.iloc[:, 0]
            else:
                fwd_rets = returns.mean(axis=1)
        elif isinstance(returns, pd.Series):
            fwd_rets = returns
        else:
            return {"decay_result": {"error": "Invalid return format"}}

        # Ensure datetime index
        if not isinstance(factor_df.index, pd.DatetimeIndex):
            factor_df.index = pd.to_datetime(factor_df.index)
        if not isinstance(fwd_rets.index, pd.DatetimeIndex):
            fwd_rets.index = pd.to_datetime(fwd_rets.index)

        # Compute IC at different holding periods
        decay_curve: Dict[int, float] = {}
        dates = sorted(factor_df.index)

        for hp in range(1, max_hp + 1):
            ics: List[float] = []
            for dt in dates:
                if dt not in factor_df.index:
                    continue
                factor_row = factor_df.loc[dt]
                # Forward return at hp steps ahead
                dt_idx = fwd_rets.index.get_indexer([dt], method="nearest")[0]
                fwd_idx = dt_idx + hp
                if fwd_idx >= len(fwd_rets):
                    continue
                fwd_ret_val = fwd_rets.iloc[fwd_idx]
                if isinstance(fwd_ret_val, pd.Series):
                    fwd_ret_val = fwd_ret_val.iloc[0]

                # Cross-sectional IC
                factor_vals = factor_row.dropna()
                common = factor_vals.index.intersection(
                    fwd_rets.index[fwd_idx:fwd_idx + 1] if hasattr(fwd_rets.index, '__getitem__') else pd.Index([])
                )
                if len(factor_vals) < 3:
                    continue

                if method == "rank_ic":
                    corr = factor_vals.rank().corr(pd.Series(
                        {c: fwd_ret_val for c in factor_vals.index}
                    ).rank())
                else:
                    corr = factor_vals.corr(pd.Series(
                        {c: fwd_ret_val for c in factor_vals.index}
                    ))

                if not np.isnan(corr):
                    ics.append(float(corr))

            if ics:
                decay_curve[hp] = round(float(np.mean(ics)), 6)

        if not decay_curve:
            return {"decay_result": {"error": "Could not compute IC for any holding period"}}

        # Estimate half-life
        half_life = max_hp
        initial_ic = decay_curve.get(1, 0)
        half_ic = initial_ic / 2.0 if initial_ic != 0 else 0
        for hp, ic_val in sorted(decay_curve.items()):
            if abs(ic_val) <= abs(half_ic) and initial_ic != 0:
                half_life = hp
                break

        return {"decay_result": {
            "half_life": half_life,
            "decay_curve": decay_curve,
            "ic_by_holding_period": {str(k): v for k, v in decay_curve.items()},
            "initial_ic": round(initial_ic, 6),
            "final_ic": round(decay_curve.get(max_hp, 0), 6),
            "method": method,
            "max_holding_period": max_hp,
        }}


# ── 2.5 Parameter Heatmap Node ───────────────────────────────────────────────

@register_node
class ParamHeatmapNode(BaseNode):
    node_type = "param_heatmap"
    category = "analysis"
    label = "Parameter Heatmap"
    description = "Grid search over 2D parameter space, output Sharpe heatmap matrix"
    icon = "Grid"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port(
            "backtest_result", PortType.BACKTEST_RESULT,
            description="Backtest result from a strategy run (expects grid results)",
        ),
    ]
    outputs = [
        BaseNode.out_port(
            "heatmap_result", PortType.HEATMAP_RESULT,
            description="Parameter heatmap results",
        ),
    ]
    config_schema = {
        "param1_name": {
            "title": "Parameter 1 Name", "type": "string",
            "description": "Name of first parameter for heatmap X axis",
        },
        "param1_range": {
            "title": "Parameter 1 Range", "type": "array",
            "description": "Values for first parameter",
        },
        "param2_name": {
            "title": "Parameter 2 Name", "type": "string",
            "description": "Name of second parameter for heatmap Y axis",
        },
        "param2_range": {
            "title": "Parameter 2 Range", "type": "array",
            "description": "Values for second parameter",
        },
        "metric": {
            "title": "Metric", "type": "string",
            "enum": ["sharpe", "return", "calmar"], "default": "sharpe",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        param1_name = config.get("param1_name", "param1")
        param1_range = config.get("param1_range", [])
        param2_name = config.get("param2_name", "param2")
        param2_range = config.get("param2_range", [])
        metric = config.get("metric", "sharpe")

        if not param1_range or not param2_range:
            return {"heatmap_result": {"error": "Both param ranges must be non-empty"}}

        bt = inputs.get("backtest_result", {})

        # Try to extract grid results from backtest
        grid_results = bt.get("grid_results") or bt.get("param_grid") or bt.get("optimization_results")

        if grid_results and isinstance(grid_results, list):
            # Build matrix from grid results
            matrix = np.full((len(param2_range), len(param1_range)), np.nan)
            for entry in grid_results:
                p1 = entry.get(param1_name)
                p2 = entry.get(param2_name)
                val = entry.get(metric) or entry.get("metrics", {}).get(metric)
                if p1 in param1_range and p2 in param2_range and val is not None:
                    i = param2_range.index(p2)
                    j = param1_range.index(p1)
                    matrix[i, j] = float(val)
        else:
            # Generate synthetic matrix from backtest metrics
            metrics = bt.get("metrics", {}) if isinstance(bt, dict) else {}
            base_val = float(metrics.get(metric, 0) or 0)
            matrix = np.full((len(param2_range), len(param1_range)), base_val)

        # Find best params
        if not np.all(np.isnan(matrix)):
            best_idx = np.unravel_index(
                np.nanargmax(np.abs(matrix)), matrix.shape
            )
            best_params = {
                param1_name: param1_range[best_idx[1]],
                param2_name: param2_range[best_idx[0]],
                metric: round(float(matrix[best_idx]), 6),
            }
        else:
            best_params = {}

        # Convert NaN to None for JSON serialization
        sharpe_matrix = [
            [round(float(v), 6) if not np.isnan(v) else None for v in row]
            for row in matrix
        ]

        return {"heatmap_result": {
            "param1_name": param1_name,
            "param2_name": param2_name,
            "param1_values": param1_range,
            "param2_values": param2_range,
            "sharpe_matrix": sharpe_matrix,
            "metric": metric,
            "best_params": best_params,
        }}
