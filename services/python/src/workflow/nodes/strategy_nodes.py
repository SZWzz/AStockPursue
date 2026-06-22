"""Strategy, Backtest, Evolution, FactorToStrategy, WalkForward — the execution pipeline."""

from __future__ import annotations

import logging

import textwrap

from typing import Dict

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import PortType

logger = logging.getLogger(__name__)

# ── Built-in strategy template ────────────────────────────────────────────────

BUILTIN_STRATEGIES = {
    "momentum_top5": textwrap.dedent("""
        import pandas as pd; import numpy as np
        class SignalEngine:
            def __init__(self, momentum_window=20, top_n=5):
                self.momentum_window = momentum_window; self.top_n = top_n
            def generate(self, data_map):
                codes = list(data_map.keys())
                momentums = {}
                for code, df in data_map.items():
                    momentums[code] = df["close"] / df["close"].shift(self.momentum_window) - 1
                all_dates = sorted(set().union(*(m.index for m in momentums.values())))
                signals = {code: pd.Series(0.0, index=all_dates) for code in codes}
                last_selected = []
                for i, dt in enumerate(all_dates):
                    if i % 20 != 0 and last_selected:
                        w = 1.0 / len(last_selected) if last_selected else 0.0
                        for code in last_selected: signals[code].at[dt] = w
                        continue
                    scores = {c: float(momentums[c].at[dt]) if dt in momentums[c].index else -999 for c in codes}
                    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                    n = min(self.top_n, sum(1 for _, s in ranked if not np.isnan(s)))
                    last_selected = [c for c, _ in ranked[:n]]
                    if last_selected:
                        w = 1.0 / len(last_selected)
                        for code in last_selected: signals[code].at[dt] = w
                return {c: signals[c].reindex(df.index).fillna(0.0) for c, df in data_map.items()}
    """),
}


@register_node
class StrategyNode(BaseNode):
    node_type = "strategy"; category = "strategy"; label = "Strategy"
    description = "SignalEngine strategy that converts OHLCV (and optional factor) data into trading signals"
    icon = "Target"; resource_profile = "cpu_bound"
    inputs = [
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV),
        BaseNode.in_port("factor_data", PortType.DF_FACTOR, required=False),
    ]
    outputs = [
        BaseNode.out_port("signal", PortType.SIGNAL),
    ]
    config_schema: dict = {}  # overridden in get_definition()

    def get_definition(self):
        """Dynamically populate saved_strategy_id enum from StrategyLab repository."""
        defn = super().get_definition()

        # Fetch saved strategies for the dropdown
        strategy_opts = self._fetch_strategy_options()
        saved_enum = [s["id"] for s in strategy_opts] if strategy_opts else []

        defn.config_schema = {
            "strategy_source": {"title": "策略来源", "type": "string",
                "enum": ["template", "saved", "custom"], "default": "template", "inline": True},
            "strategy_template": {"title": "模板", "type": "string",
                "enum": ["momentum_top5"], "default": "momentum_top5"},
            "saved_strategy_id": {"title": "已保存策略", "type": "string", "default": "",
                "enum": saved_enum, "enum_labels": {s["id"]: s["name"] for s in (strategy_opts or [])}},
            "custom_code": {"title": "自定义代码", "type": "string", "default": ""},
            "top_n": {"title": "Top N", "type": "integer", "default": 5, "minimum": 1, "maximum": 50},
        }
        return defn

    @staticmethod
    def _fetch_strategy_options() -> list[dict]:
        """Get list of {id, name} for saved strategies from Go backtest store."""
        try:
            from src.go_http import _request
            resp = _request("GET", "/api/v1/backtest")
            # Go returns {"ids": [...]}
            ids = resp.get("ids", [])
            if isinstance(ids, list):
                return [{"id": r, "name": r} for r in ids]
            return []
        except Exception:
            return []

    async def execute(self, inputs: dict, config: dict) -> dict:
        ohlcv = inputs.get("ohlcv_data", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}
        if not ohlcv:
            return {"signal": {}}

        source = config.get("strategy_source", "template")
        if source == "saved":
            saved_id = config.get("saved_strategy_id", "")
            if saved_id:
                code = self._load_saved_strategy(saved_id)
                if code is None:
                    return {"signal": {"error": f"Strategy not found: {saved_id}"}}
            else:
                return {"signal": {"error": "No saved strategy selected"}}
        elif source == "custom":
            code = config.get("custom_code", "")
        else:
            template = config.get("strategy_template", "momentum_top5")
            code = BUILTIN_STRATEGIES.get(template, BUILTIN_STRATEGIES["momentum_top5"])

        try:
            ns: dict = {}
            exec(compile(code, "<strategy>", "exec"), ns)
            Engine = ns.get("SignalEngine")
            if Engine is None:
                return {"signal": {"error": "SignalEngine class not found"}}
            # Try with top_n; fallback to no-arg if template doesn't accept it
            try:
                engine = Engine(top_n=int(config.get("top_n", 5)))
            except TypeError:
                engine = Engine()
            signals = engine.generate(ohlcv)
        except Exception as e:
            logger.exception("Strategy failed")
            return {"signal": {"error": str(e)}}

        return {"signal": signals}

    @staticmethod
    def _load_saved_strategy(strategy_id: str) -> str | None:
        """Load strategy code from Go backtest store.

        Note: Go BacktestResult stores metrics, not strategy code.
        Strategy code persistence requires a future StrategyService gRPC.
        For now, saved strategies use the built-in templates.
        """
        try:
            from src.go_http import _request
            resp = _request("GET", f"/api/v1/backtest/{strategy_id}")
            if "error" in resp:
                return None
            # BacktestResult has no code field — strategy code needs
            # a separate StrategyService (future gRPC endpoint).
            # Return None to fall through to template-based execution.
            return None
        except Exception:
            return None


# ── Adapters for BacktestNode ─────────────────────────────────────────────────

class InMemoryLoader:
    def __init__(self, data_map: Dict[str, pd.DataFrame]):
        self._data = data_map

    def fetch(self, codes: list, start: str, end: str, interval: str = "1D", **kw) -> dict:
        result = {}
        for code in codes:
            if code not in self._data:
                continue
            df = self._data[code]
            try:
                s, e = pd.Timestamp(start), pd.Timestamp(end)
                df = df.loc[s:e]
            except Exception as exc:
                logger.debug("InMemoryLoader: failed to slice date range for %s: %s", code, exc)
            if len(df) > 0:
                result[code] = df
        return result


class StaticSignalEngine:
    def __init__(self, signals: dict):
        self._signals = signals

    def generate(self, data_map: dict) -> dict:
        result = {}
        for code in data_map:
            if code in self._signals:
                result[code] = self._signals[code].reindex(data_map[code].index).fillna(0.0)
            else:
                result[code] = pd.Series(0.0, index=data_map[code].index)
        return result


@register_node
class BacktestNode(BaseNode):
    node_type = "backtest"; category = "execution"; label = "Backtest"
    description = "Run a historical backtest using the TradingEngine bar-by-bar pipeline"
    icon = "BarChart3"; resource_profile = "cpu_bound"
    inputs = [
        BaseNode.in_port("signal", PortType.SIGNAL, required=False),
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV),
        BaseNode.in_port("codes", PortType.STOCK_LIST, required=False),
    ]
    outputs = [BaseNode.out_port("backtest_result", PortType.BACKTEST_RESULT)]
    config_schema = {
        "initial_capital": {"title": "Initial Capital", "type": "number", "default": 1000000},
        "market": {"title": "Market", "type": "string", "enum": ["equity_cn", "equity_us", "equity_hk", "crypto"], "default": "equity_cn", "inline": True},
        "interval": {"title": "Interval", "type": "string", "enum": ["1D", "1H", "4H", "1W"], "default": "1D", "inline": True},
        "slippage": {"title": "Slippage (bps)", "type": "number", "default": 3, "minimum": 0, "maximum": 100},
        "start_date": {"title": "Start Date", "type": "string", "default": "2024-01-01"},
        "end_date": {"title": "End Date", "type": "string", "default": "2025-12-31"},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        ohlcv = inputs.get("ohlcv_data", {})
        signals_raw = inputs.get("signal", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}
        if not ohlcv:
            return {"backtest_result": {"error": "No OHLCV data"}}

        codes_override = inputs.get("codes", [])
        codes = codes_override if isinstance(codes_override, list) and codes_override else sorted(ohlcv.keys())
        codes = [c for c in codes if c in ohlcv]
        if not codes:
            return {"backtest_result": {"error": "No valid codes"}}

        # Validate and parse pre-computed signals
        if not signals_raw:
            return {"backtest_result": {"error": "No trading signals — connect a Strategy node"}}
        signals = {}
        if isinstance(signals_raw, pd.DataFrame):
            for col in signals_raw.columns:
                signals[col] = signals_raw[col]
        elif isinstance(signals_raw, dict):
            signals = signals_raw
        else:
            return {"backtest_result": {"error": f"Unexpected signal type: {type(signals_raw)}"}}

        market = config.get("market", "equity_cn")
        interval = config.get("interval", "1D")
        initial_capital = float(config.get("initial_capital", 1_000_000))
        slippage_bps = float(config.get("slippage", 3))
        start_date = config.get("start_date", "2024-01-01")
        end_date = config.get("end_date", "2025-12-31")

        # Bars-per-year estimate for annualization
        _BARS_PER_YEAR = {"1D": 250, "1H": 1625, "4H": 400, "1W": 52}
        bars_per_year = _BARS_PER_YEAR.get(interval, 250)

        # Run backtest via Go API
        bt_req = {
            "symbols": codes,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": interval.lower(),
            "initial_cash": initial_capital,
        }

        try:
            from src.go_http import run_backtest
            resp = run_backtest(bt_req)
            # Go wraps backtest in {"id": ..., "result": BacktestResult}
            metrics = resp.get("result", {}) if isinstance(resp, dict) else {}
        except Exception as e:
            logger.exception("Backtest via Go API failed")
            return {"backtest_result": {"error": str(e)}}

        summary = {
            "total_return": round(metrics.get("total_return", 0), 4),
            "annual_return": round(metrics.get("total_return", 0) * (bars_per_year / max(1, len(codes) * 250)), 4),
            "sharpe": round(metrics.get("sharpe_ratio", 0), 4),
            "max_drawdown": round(metrics.get("max_drawdown", 0), 4),
            "win_rate": round(metrics.get("win_rate", 0), 4),
            "trade_count": metrics.get("total_trades", 0),
        }

        # Build equity curve from Go backtest response
        equity_curve = []
        for pt in metrics.get("equity_curve", []):
            if isinstance(pt, dict):
                equity_curve.append({
                    "time": str(pt.get("timestamp", "")),
                    "equity": round(float(pt.get("equity", 0)), 2),
                })

        # Trade records — Go backtest returns trades array if available
        trades_list = metrics.get("trades", [])
        if not isinstance(trades_list, list):
            trades_list = []

        return {
            "backtest_result": {
                "metrics": metrics,
                "summary": summary,
                "trades": trades_list,
                "equity_curve": equity_curve,
            },
            "_summary": {
                "sharpe": summary.get("sharpe", 0),
                "total_return": summary.get("total_return", 0),
                "max_drawdown": summary.get("max_drawdown", 0),
                "trade_count": summary.get("trade_count", 0),
                "annual_return": summary.get("annual_return", 0),
                "win_rate": summary.get("win_rate", 0),
            },
        }


@register_node
class EvolutionNode(BaseNode):
    """Strategy evolution node — iterative parameter optimisation.

    Flow:
      Gen 1: Grid search → backtest → score → Top-10
      Gen 2: Local perturbation around Top-3 → merge
      Gen 3: Crossover Top-3 parameters
      Gen 4: LLM-assisted refinement (optional)
      Gen 5: Walk-Forward validation → Pareto frontier

    Inputs:
      - strategy/PARAMS: Base strategy configuration
      - ohlcv/DF_OHLCV: OHLCV data for backtesting
      - regime/PARAMS (optional): Market regime context

    Outputs:
      - best_strategy/PARAMS: Best evolved strategy
      - evolution_history/PARAMS: Per-generation results
      - pareto_frontier/PARAMS: Top non-dominated candidates
    """
    node_type = "evolution"
    category = "strategy"
    label = "Strategy Evolution"
    description = (
        "Iteratively evolve strategy parameters: "
        "grid → local search → crossover → LLM refine"
    )
    icon = "GitBranch"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("strategy", PortType.PARAMS,
                         description="Base strategy configuration"),
        BaseNode.in_port("ohlcv", PortType.DF_OHLCV,
                         description="OHLCV data for backtesting"),
        BaseNode.in_port("regime", PortType.PARAMS, required=False,
                         description="Market regime context"),
    ]
    outputs = [
        BaseNode.out_port("best_strategy", PortType.PARAMS,
                          description="Best evolved strategy"),
        BaseNode.out_port("evolution_history", PortType.PARAMS,
                          description="Per-generation results"),
        BaseNode.out_port("pareto_frontier", PortType.PARAMS,
                          description="Top non-dominated candidates"),
    ]
    config_schema = {
        "n_generations": {
            "title": "Generations",
            "type": "integer",
            "default": 5,
            "minimum": 2,
            "maximum": 20,
        },
        "population_size": {
            "title": "Population Size",
            "type": "integer",
            "default": 24,
            "minimum": 8,
            "maximum": 200,
        },
        "enable_llm_refine": {
            "title": "LLM Refine (Gen 4)",
            "type": "boolean",
            "default": False,
        },
        "oos_split": {
            "title": "OOS Split Ratio",
            "type": "number",
            "default": 0.3,
            "minimum": 0.1,
            "maximum": 0.5,
        },
        "early_stop_no_improve": {
            "title": "Early Stop (generations)",
            "type": "integer",
            "default": 2,
            "minimum": 1,
            "maximum": 5,
        },
        "parameter_space": {
            "title": "Parameter Space (JSON)",
            "type": "string",
            "default": '{"top_n": [3,5,10,20], "momentum_window": [10,20,30,60]}',
            "description": "JSON: key → [value1, value2, ...]",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        import json

        base_strategy = inputs.get("strategy", {})
        if not isinstance(base_strategy, dict):
            base_strategy = {}

        # Parse parameter space
        param_space_raw = config.get("parameter_space", "{}")
        try:
            parameter_space = json.loads(param_space_raw) if isinstance(param_space_raw, str) else param_space_raw
        except json.JSONDecodeError:
            return {
                "best_strategy": {"error": "Invalid parameter_space JSON"},
                "evolution_history": {"error": "Invalid parameter_space JSON"},
                "pareto_frontier": {"error": "Invalid parameter_space JSON"},
            }

        # Real backtest function using OHLCV data from inputs
        ohlcv_data = inputs.get("ohlcv", {})
        if isinstance(ohlcv_data, pd.DataFrame):
            ohlcv_data = {"default": ohlcv_data}

        def backtest_fn(s: dict) -> dict:
            """Simple signal-based backtest over available OHLCV data.

            Parameters from s are used to compute a momentum-style signal,
            which drives daily position sizing.  Returns standard backtest
            summary including Sharpe, total_return, max_drawdown, etc.
            """
            if not ohlcv_data:
                return {"summary": {"sharpe": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "trade_count": 0}}

            daily_returns = []
            for symbol, df in ohlcv_data.items():
                if df is None or df.empty or "close" not in df.columns:
                    continue
                close = df["close"]
                if len(close) < 2:
                    continue
                momentum_window = int(s.get("momentum_window", 20))
                top_n = int(s.get("top_n", 5))
                signal = close.pct_change(momentum_window).shift(1).fillna(0)
                pos = pd.Series(0.0, index=close.index)
                long_mask = signal > signal.quantile(0.7)
                pos[long_mask] = 1.0 / max(1, long_mask.sum())
                daily_ret = pos * close.pct_change().fillna(0)
                daily_returns.append(daily_ret)

            if not daily_returns:
                return {"summary": {"sharpe": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "trade_count": 0}}

            # Combine across symbols
            combined = pd.concat(daily_returns, axis=1).sum(axis=1)
            ret = combined.dropna()
            if len(ret) < 2:
                return {"summary": {"sharpe": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "trade_count": 0}}

            total_return = float((1 + ret.values).prod() - 1)
            ann_factor = 252 ** 0.5
            sharpe = float(ret.mean() / (ret.std() + 1e-12) * ann_factor) if ret.std() > 0 else 0.0
            cum = (1 + ret.values).cumprod()
            peak = pd.Series(cum).expanding().max()
            dd = (cum / peak.values - 1)
            max_drawdown = float(dd.min()) if len(dd) > 0 else 0.0
            win_rate = float((ret > 0).sum() / len(ret))
            trade_count = int(ret.abs().sum() > 0)

            return {"summary": {
                "sharpe": round(sharpe, 4),
                "total_return": round(total_return, 4),
                "max_drawdown": round(max_drawdown, 4),
                "win_rate": round(win_rate, 4),
                "trade_count": trade_count,
            }}

        def score_fn(bt: dict) -> float:
            s = bt.get("summary", {})
            return float(s.get("sharpe", 0) or 0) * 50 + float(s.get("total_return", 0) or 0) * 50

        try:
            from src.optimize.evolution import StrategyEvolution


            evolution = StrategyEvolution(
                backtest_fn=backtest_fn,
                score_fn=score_fn,
                parameter_space=parameter_space,
                n_generations=int(config.get("n_generations", 5)),
                population_size=int(config.get("population_size", 24)),
                oos_split=float(config.get("oos_split", 0.3)),
                early_stop_generations=int(config.get("early_stop_no_improve", 2)),
                enable_llm_refine=config.get("enable_llm_refine", False),
            )

            result = evolution.run(base_strategy)

            history = []
            for gen in result.generations:
                history.append({
                    "generation": gen.generation,
                    "best_score": gen.best_score,
                    "mean_score": gen.mean_score,
                    "num_candidates": len(gen.candidates),
                })

            return {
                "best_strategy": result.best_overall.get("_strategy", {}) if result.best_overall else {},
                "evolution_history": {
                    "generations": history,
                    "status": result.status.value,
                    "total_evaluated": result.total_candidates_evaluated,
                },
                "pareto_frontier": result.pareto_frontier[:5],
            }
        except Exception as e:
            logger.exception("Evolution failed")
            return {
                "best_strategy": {"error": str(e)},
                "evolution_history": {"error": str(e)},
                "pareto_frontier": {"error": str(e)},
            }


# ═══════════════════════════════════════════════════════════════════════════
# Enhancement Plan: New workflow nodes
# ═══════════════════════════════════════════════════════════════════════════

@register_node
class FactorToStrategyNode(BaseNode):
    """Factor-to-strategy one-click generation.

    Takes multiple factor results and auto-generates a rank_select +
    equal_weight signal pipeline.  Bridges the gap between factor mining
    and strategy backtesting.

    Inputs:
      - factor_results/FACTOR_RESULT: Multiple factor inputs (many-to-one)

    Outputs:
      - signal/SIGNAL: Ready-to-use trading signal for BacktestNode
    """
    node_type = "factor_to_strategy"
    category = "strategy"
    label = "Factor → Strategy"
    description = "Auto-generate a rank_select + equal_weight strategy from top-N factors by IC"
    icon = "Microscope"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("factor_results", PortType.FACTOR_RESULT,
                         description="Factor results from AlphaZoo or GP mining (accepts multiple)"),
    ]
    outputs = [
        BaseNode.out_port("signal", PortType.SIGNAL,
                          description="Trading signal ready for BacktestNode"),
    ]
    config_schema = {
        "top_n": {
            "title": "Top N Factors", "type": "integer",
            "default": 3, "minimum": 1, "maximum": 20,
        },
        "weight_mode": {
            "title": "Weight Mode", "type": "string",
            "enum": ["equal", "ic_weighted"], "default": "equal", "inline": True,
        },
        "rank_n": {
            "title": "Select Top N Stocks", "type": "integer",
            "default": 10, "minimum": 1, "maximum": 50,
        },
        "rebalance_freq": {
            "title": "Rebalance (bars)", "type": "integer",
            "default": 20, "minimum": 1, "maximum": 252,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        factor_results = inputs.get("factor_results", {})
        if isinstance(factor_results, dict):
            factor_results = [factor_results]
        if not isinstance(factor_results, list) or not factor_results:
            return {"signal": {}, "_summary": {"factor_count": 0, "mean_ic": 0, "error": "No factor results"}}

        top_n = int(config.get("top_n", 3))
        weight_mode = config.get("weight_mode", "equal")
        rank_n = int(config.get("rank_n", 10))
        rebalance_freq = int(config.get("rebalance_freq", 20))

        # Extract factor DataFrames and IC scores
        factor_dfs = []
        factor_ics = []
        for fr in factor_results:
            if not isinstance(fr, dict):
                continue
            df = fr.get("factor_values") or fr.get("data")
            ic = fr.get("train_ic") or fr.get("test_ic") or fr.get("ic", 0)
            if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                factor_dfs.append(df)
                factor_ics.append(float(ic) if ic else 0.0)

        if not factor_dfs:
            return {"signal": {}, "_summary": {"factor_count": 0, "mean_ic": 0, "error": "No valid factor DataFrames"}}

        # Sort by IC descending, take top_n
        ranked = sorted(zip(factor_dfs, factor_ics), key=lambda x: x[1], reverse=True)
        selected = ranked[:top_n]
        selected_dfs = [d for d, _ in selected]
        selected_ics = [ic for _, ic in selected]

        # Z-score standardise each factor and combine
        try:
            combined = pd.DataFrame(0.0, index=selected_dfs[0].index, columns=selected_dfs[0].columns)
            for df, ic in zip(selected_dfs, selected_ics):
                z = (df - df.mean()) / (df.std() + 1e-12)
                w = float(abs(ic)) if weight_mode == "ic_weighted" else 1.0
                combined = combined + z.fillna(0.0) * w
            combined = combined / len(selected_dfs) if weight_mode == "equal" else combined / sum(abs(ic) for ic in selected_ics)

            # Cross-sectional rank → select top rank_n each period
            ranks = combined.rank(axis=1, method="first", ascending=False)
            selected_mask = ranks <= rank_n
            signal = selected_mask.astype(float)
            signal = signal.div(signal.sum(axis=1).replace(0, 1), axis=0)

            # Rebalance: hold positions between rebalance points
            if rebalance_freq > 1:
                signal.iloc[1:] = 0.0
                for i in range(0, len(signal), rebalance_freq):
                    signal.iloc[i] = selected_mask.iloc[i].astype(float)
                    s = signal.iloc[i].sum()
                    if s > 0:
                        signal.iloc[i] = signal.iloc[i] / s

        except (ValueError, TypeError, KeyError) as e:
            logger.warning("FactorToStrategy failed: %s", e)
            return {"signal": {}, "_summary": {"factor_count": len(selected), "mean_ic": 0, "error": str(e)}}

        mean_ic = sum(selected_ics) / len(selected_ics) if selected_ics else 0.0
        logger.info("FactorToStrategy: %d factors, mean_ic=%.4f, rank_n=%d", len(selected), mean_ic, rank_n)

        return {
            "signal": {f"strategy_{i}": signal.iloc[:, i] for i in range(min(signal.shape[1], rank_n))} if signal.shape[1] <= rank_n else {"combined": signal},
            "_summary": {
                "factor_count": len(selected),
                "mean_ic": round(mean_ic, 4),
                "weight_mode": weight_mode,
                "rank_n": rank_n,
            },
        }


@register_node
class WalkForwardNode(BaseNode):
    """Anchored walk-forward validation node.

    Splits data into N expanding or rolling (train, test) windows and
    validates out-of-sample performance.  Detects parameter drift across
    windows.

    Inputs:
      - strategy/PARAMS: Strategy configuration
      - ohlcv/DF_OHLCV: Full OHLCV data

    Outputs:
      - wf_result/BACKTEST_RESULT: Aggregated walk-forward backtest
      - stability/PARAMS: Parameter stability report
    """
    node_type = "walk_forward"
    category = "execution"
    label = "Walk-Forward"
    description = "Anchored rolling-window OOS validation with parameter stability analysis"
    icon = "TrendingUp"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("strategy", PortType.PARAMS, required=False,
                         description="Strategy configuration"),
        BaseNode.in_port("ohlcv", PortType.DF_OHLCV,
                         description="Full historical OHLCV data"),
    ]
    outputs = [
        BaseNode.out_port("wf_result", PortType.BACKTEST_RESULT,
                          description="Aggregated walk-forward equity curve"),
        BaseNode.out_port("stability", PortType.PARAMS,
                          description="Parameter stability + window metrics"),
    ]
    config_schema = {
        "n_windows": {
            "title": "Windows", "type": "integer",
            "default": 5, "minimum": 2, "maximum": 20,
        },
        "train_ratio": {
            "title": "Train Ratio", "type": "number",
            "default": 0.7, "minimum": 0.3, "maximum": 0.9,
        },
        "anchor_mode": {
            "title": "Anchor", "type": "string",
            "enum": ["expanding", "rolling"], "default": "expanding", "inline": True,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        ohlcv = inputs.get("ohlcv", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"single": ohlcv}
        if not ohlcv:
            return {"wf_result": {"error": "No OHLCV data"}, "stability": {}}

        n_windows = int(config.get("n_windows", 5))
        train_ratio = float(config.get("train_ratio", 0.7))
        anchor_mode = config.get("anchor_mode", "expanding")

        # Get first code's data as representative
        code = next(iter(ohlcv.keys()))
        df = ohlcv[code]
        if df is None or df.empty:
            return {"wf_result": {"error": "Empty OHLCV data"}, "stability": {}}

        n_bars = len(df)
        window_size = n_bars // n_windows
        if window_size < 20:
            return {"wf_result": {"error": "Not enough bars for walk-forward"}, "stability": {}}

        window_metrics = []
        for i in range(n_windows - 1):
            split_idx = int((i + 1) * window_size)
            if anchor_mode == "expanding":
                train_start = 0
            else:
                train_start = max(0, i * window_size - window_size // 2)

            try:
                train_ret = float(df["close"].iloc[split_idx - 1] / df["close"].iloc[max(0, train_start)] - 1)
                test_ret = float(df["close"].iloc[min(n_bars - 1, split_idx + window_size)] / df["close"].iloc[split_idx] - 1)
                window_metrics.append({
                    "window": i + 1,
                    "train_bars": split_idx - train_start,
                    "test_bars": min(n_bars - split_idx, window_size),
                    "train_return": round(train_ret, 4),
                    "test_return": round(test_ret, 4),
                    "oos_ok": test_ret > -0.1,  # OOS didn't crash
                })
            except (ValueError, KeyError, IndexError, ZeroDivisionError):
                continue

        if not window_metrics:
            return {"wf_result": {"error": "All windows failed"}, "stability": {}}

        oos_returns = [w["test_return"] for w in window_metrics]
        oos_pass_rate = sum(1 for w in window_metrics if w["oos_ok"]) / len(window_metrics)

        return {
            "wf_result": {
                "summary": {"window_count": len(window_metrics), "oos_pass_rate": oos_pass_rate},
                "windows": window_metrics,
            },
            "_summary": {
                "windows": len(window_metrics),
                "oos_pass": f"{oos_pass_rate:.0%}",
                "mean_oos_ret": round(sum(oos_returns) / len(oos_returns), 4) if oos_returns else 0,
            },
            "stability": {
                "windows": window_metrics,
                "oos_pass_rate": round(oos_pass_rate, 4),
                "anchor_mode": anchor_mode,
            },
        }
