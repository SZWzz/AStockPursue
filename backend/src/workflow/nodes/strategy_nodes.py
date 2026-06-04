"""Strategy, Backtest, and adapter classes — the execution pipeline."""

from __future__ import annotations

import logging
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

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
    outputs = [BaseNode.out_port("signal", PortType.SIGNAL)]
    config_schema = {
        "strategy_template": {"title": "Template", "type": "string", "enum": ["momentum_top5", "custom"], "default": "momentum_top5"},
        "custom_code": {"title": "Custom Code", "type": "string", "default": ""},
        "top_n": {"title": "Top N", "type": "integer", "default": 5, "minimum": 1, "maximum": 50},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        ohlcv = inputs.get("ohlcv_data", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}
        if not ohlcv:
            return {"signal": {}}

        template = config.get("strategy_template", "momentum_top5")
        code = config.get("custom_code", "") if template == "custom" else BUILTIN_STRATEGIES.get(template, BUILTIN_STRATEGIES["momentum_top5"])

        try:
            ns: dict = {}
            exec(compile(code, "<strategy>", "exec"), ns)
            Engine = ns.get("SignalEngine")
            if Engine is None:
                return {"signal": {"error": "SignalEngine class not found"}}
            engine = Engine(top_n=int(config.get("top_n", 5)))
            signals = engine.generate(ohlcv)
        except Exception as e:
            logger.exception("Strategy failed")
            return {"signal": {"error": str(e)}}

        return {"signal": signals}


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
            except Exception:
                pass
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
        BaseNode.in_port("signal", PortType.SIGNAL),
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV),
        BaseNode.in_port("codes", PortType.STOCK_LIST, required=False),
    ]
    outputs = [BaseNode.out_port("backtest_result", PortType.BACKTEST_RESULT)]
    config_schema = {
        "initial_capital": {"title": "Initial Capital", "type": "number", "default": 1000000},
        "market": {"title": "Market", "type": "string", "enum": ["equity_cn", "equity_us", "equity_hk", "crypto"], "default": "equity_cn"},
        "interval": {"title": "Interval", "type": "string", "enum": ["1D", "1H", "4H", "1W"], "default": "1D"},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        ohlcv = inputs.get("ohlcv_data", {})
        signals_raw = inputs.get("signal", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}
        if not ohlcv:
            return {"backtest_result": {"error": "No OHLCV data"}}
        if not signals_raw:
            return {"backtest_result": {"error": "No trading signals"}}

        signals = {}
        if isinstance(signals_raw, pd.DataFrame):
            for col in signals_raw.columns:
                signals[col] = signals_raw[col]
        elif isinstance(signals_raw, dict):
            signals = signals_raw
        else:
            return {"backtest_result": {"error": f"Unexpected signal type: {type(signals_raw)}"}}

        codes_override = inputs.get("codes", [])
        codes = codes_override if isinstance(codes_override, list) and codes_override else sorted(ohlcv.keys())
        codes = [c for c in codes if c in ohlcv]
        if not codes:
            return {"backtest_result": {"error": "No valid codes"}}

        market = config.get("market", "equity_cn")
        interval = config.get("interval", "1D")
        initial_capital = float(config.get("initial_capital", 1_000_000))

        bt_config = {"codes": codes, "initial_capital": initial_capital, "interval": interval, "engine": market}
        loader = InMemoryLoader(ohlcv)
        sig_engine = StaticSignalEngine(signals)
        market_engine = self._mk_engine(market, initial_capital)

        try:
            from src.trading.backtest_driver import BacktestDriver
            driver = BacktestDriver()
            with tempfile.TemporaryDirectory() as td:
                metrics = driver.run(
                    config=bt_config, loader=loader, signal_engine=sig_engine,
                    run_dir=Path(td), market_engine=market_engine,
                    bars_per_year={"1D": 252, "1H": 1512, "4H": 378, "1W": 52}.get(interval, 252),
                )
        except Exception as e:
            logger.exception("Backtest failed")
            return {"backtest_result": {"error": str(e)}}

        summary = {k: round(metrics.get(k, 0), 4) for k in ["total_return", "annual_return", "sharpe", "max_drawdown", "win_rate"]}
        summary["trade_count"] = metrics.get("trade_count", 0)
        logger.info("Backtest: sharpe=%.2f", summary["sharpe"])
        return {"backtest_result": {"metrics": metrics, "summary": summary}}

    @staticmethod
    def _mk_engine(market: str, capital: float):
        cfg = {"initial_capital": capital}
        if market == "equity_cn":
            from backtest.engines.china_a import ChinaAEngine; return ChinaAEngine(config=cfg)
        elif market in ("equity_us", "equity_hk"):
            from backtest.engines.global_equity import GlobalEquityEngine; return GlobalEquityEngine(config=cfg)
        elif market == "crypto":
            from backtest.engines.crypto import CryptoEngine; return CryptoEngine(config=cfg)
        else:
            from backtest.engines.china_a import ChinaAEngine; return ChinaAEngine(config=cfg)
