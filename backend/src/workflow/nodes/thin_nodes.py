"""Thin wrapper nodes — Screener and PaperTrading."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class ScreenerNode(BaseNode):
    node_type = "screener"; category = "filter"; label = "Screener"
    description = "Filter stocks by factor values (rank/filter modes)"
    icon = "Filter"
    resource_profile = "cpu_bound"
    inputs = [
        BaseNode.in_port("codes", PortType.STOCK_LIST),
        BaseNode.in_port("factor_data", PortType.DF_FACTOR, required=False),
    ]
    outputs = [
        BaseNode.out_port("filtered_codes", PortType.STOCK_LIST),
        BaseNode.out_port("scores", PortType.DF_FACTOR),
    ]
    config_schema = {
        "mode": {"title": "Mode", "type": "string", "enum": ["rank", "filter"], "default": "rank", "inline": True},
        "top_n": {"title": "Top N", "type": "integer", "default": 20, "minimum": 1, "maximum": 100},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        codes = inputs.get("codes", [])
        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)
        if not codes:
            return {"filtered_codes": [], "scores": pd.DataFrame()}

        factor_data = inputs.get("factor_data")
        top_n = int(config.get("top_n", 20))

        if factor_data is not None and isinstance(factor_data, pd.DataFrame) and not factor_data.empty:
            try:
                latest = factor_data.iloc[-1] if len(factor_data) > 0 else pd.Series(dtype=float)
                if factor_data.shape[1] > 1:
                    scores = factor_data.mean(axis=1).iloc[-1]
                else:
                    scores = latest
                scores = scores.dropna().sort_values(ascending=False)
                filtered = list(scores.head(top_n).index)
                score_df = pd.DataFrame({"score": scores.values}, index=scores.index)
            except Exception:
                filtered = list(codes)[:top_n]
                score_df = pd.DataFrame()
        else:
            filtered = list(codes)[:top_n]
            score_df = pd.DataFrame()

        logger.info("Screener: %d → %d stocks", len(codes), len(filtered))
        return {"filtered_codes": filtered, "scores": score_df}


@register_node
class PaperTradingNode(BaseNode):
    node_type = "paper_trading"; category = "deploy"; label = "Paper Trading"
    description = (
        "Validate strategy, seed historical data, and run a paper-trading simulation "
        "using LiveDriver with the TradingEngine bar-by-bar pipeline."
    )
    icon = "TrendingUp"; resource_profile = "cpu_bound"
    inputs = [
        BaseNode.in_port("signal", PortType.SIGNAL, required=False,
                         description="Trading signal from StrategyNode"),
        BaseNode.in_port("strategy_code", PortType.PARAMS, required=False,
                         description="Strategy code/config for validation"),
        BaseNode.in_port("codes", PortType.STOCK_LIST,
                         description="Stock codes to trade"),
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV, required=False,
                         description="OHLCV data for seeding historical data"),
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT, required=False),
    ]
    outputs = [
        BaseNode.out_port("deploy_status", PortType.PARAMS,
                          description="Deploy config + pre-flight check + simulation result"),
    ]
    config_schema = {
        "initial_capital": {"title": "Initial Capital", "type": "number", "default": 1000000},
        "market": {"title": "Market", "type": "string", "enum": ["equity_cn", "equity_us", "equity_hk", "crypto"], "default": "equity_cn", "inline": True},
        "interval": {"title": "Interval", "type": "string", "enum": ["1D", "1H", "4H"], "default": "1D", "inline": True},
        "stop_loss_pct": {"title": "Stop Loss %", "type": "number", "default": 0.05, "minimum": 0.0, "maximum": 0.5},
        "take_profit_pct": {"title": "Take Profit %", "type": "number", "default": 0.15, "minimum": 0.0, "maximum": 1.0},
        "mode": {"title": "Mode", "type": "string", "enum": ["validate", "simulate"], "default": "validate", "inline": True,
                 "description": "validate = pre-flight check only; simulate = run paper trading simulation"},
        "duration_days": {"title": "Duration Days", "type": "integer", "default": 30, "minimum": 1, "maximum": 365,
                          "description": "Number of days to simulate in paper trading mode"},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        strategy = inputs.get("strategy_code", {})
        codes = inputs.get("codes", [])
        bt_result = inputs.get("backtest_result")
        signal = inputs.get("signal")
        ohlcv = inputs.get("ohlcv_data", {})
        mode = config.get("mode", "validate")

        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)

        code_text = strategy.get("code", "") if isinstance(strategy, dict) else str(strategy)
        strategy_valid = bool(code_text and "generate" in code_text)

        # ── Pre-flight check ──────────────────────────────────────────────────
        pre_flight_warnings = []
        if bt_result and isinstance(bt_result, dict):
            metrics = bt_result.get("metrics", {})
            if metrics.get("sharpe", 0) < 0.5:
                pre_flight_warnings.append("Low Sharpe ratio")
            if abs(metrics.get("max_drawdown", 0)) > 0.3:
                pre_flight_warnings.append("High max drawdown")

        result = {
            "ready": strategy_valid,
            "pre_flight_passed": len(pre_flight_warnings) == 0,
            "pre_flight_warnings": pre_flight_warnings,
            "config": {
                "initial_capital": config.get("initial_capital", 1_000_000),
                "market": config.get("market", "equity_cn"),
                "interval": config.get("interval", "1D"),
                "stop_loss_pct": config.get("stop_loss_pct", 0.05),
                "take_profit_pct": config.get("take_profit_pct", 0.15),
                "universe_size": len(codes) if isinstance(codes, list) else 0,
            },
        }

        # ── Simulation mode ───────────────────────────────────────────────────
        if mode == "simulate" and signal and codes:
            try:
                from src.trading.engine import TradingEngine
                from src.trading.signal_adapter import SignalAdapter
                from src.trading.risk_pipeline import RiskPipeline, RiskConfig

                capital = float(config.get("initial_capital", 1_000_000))
                market = config.get("market", "equity_cn")
                interval = config.get("interval", "1D")
                duration = int(config.get("duration_days", 30))

                # Build market engine
                engine_cfg = {"initial_capital": capital}
                if market == "equity_cn":
                    from backtest.engines.china_a import ChinaAEngine
                    mkt_engine = ChinaAEngine(config=engine_cfg)
                elif market in ("equity_us", "equity_hk"):
                    from backtest.engines.global_equity import GlobalEquityEngine
                    mkt_engine = GlobalEquityEngine(config=engine_cfg)
                elif market == "crypto":
                    from backtest.engines.crypto import CryptoEngine
                    mkt_engine = CryptoEngine(config=engine_cfg)
                else:
                    from backtest.engines.china_a import ChinaAEngine
                    mkt_engine = ChinaAEngine(config=engine_cfg)

                # Build signal adapter
                from src.workflow.nodes.strategy_nodes import InMemoryLoader, StaticSignalEngine
                sig_engine = StaticSignalEngine(signal if isinstance(signal, dict) else {})
                adapter = SignalAdapter(sig_engine)

                # Risk config
                risk = RiskPipeline(RiskConfig(
                    stop_loss_pct=float(config.get("stop_loss_pct", 0.05)),
                    trailing_stop_pct=None,
                    take_profit_pct=float(config.get("take_profit_pct", 0.15)),
                ))

                engine = TradingEngine(
                    config={"codes": list(codes), "initial_capital": capital, "interval": interval},
                    signal_adapter=adapter,
                    market_engine=mkt_engine,
                    risk_pipeline=risk,
                )

                # Seed with historical data
                if not isinstance(ohlcv, dict) or not ohlcv:
                    result["simulation"] = {"error": "No OHLCV data for seeding"}
                else:
                    engine.initialize(ohlcv)
                    # Run through bars
                    all_bars = self._build_bar_iterator(ohlcv, duration)
                    trade_count = 0
                    for bar, ts in all_bars:
                        bar_result = engine.on_bar(bar, ts)
                        if bar_result:
                            pass  # accumulate results as needed
                    summary = engine.get_summary()
                    result["simulation"] = {
                        "mode": "paper_trading",
                        "bars_processed": len(all_bars) if isinstance(all_bars, list) else duration,
                        "final_equity": round(summary.get("final_equity", capital), 2),
                        "total_return": round(summary.get("total_return", 0), 4),
                        "sharpe": round(summary.get("sharpe", 0), 4),
                        "max_drawdown": round(summary.get("max_drawdown", 0), 4),
                    }

            except ImportError as e:
                result["simulation"] = {"error": f"Trading engine not available: {e}"}
            except Exception as e:
                logger.exception("PaperTrading simulation failed")
                result["simulation"] = {"error": str(e)}

        return {"deploy_status": result}

    @staticmethod
    def _build_bar_iterator(ohlcv: dict, max_days: int):
        """Build (bar_dict, timestamp) iterator from OHLCV data."""
        import pandas as pd

        bars: list = []
        # Collect all unique timestamps
        all_idx = set()
        for df in ohlcv.values():
            if isinstance(df, pd.DataFrame) and not df.empty:
                all_idx.update(df.index)
        if not all_idx:
            # Fallback: generate date range
            end = pd.Timestamp.now()
            start = end - pd.Timedelta(days=max_days)
            all_idx = pd.date_range(start, end, freq="B")  # business days

        sorted_idx = sorted(all_idx)[:max_days]
        for ts in sorted_idx:
            bar = {}
            for code, df in ohlcv.items():
                if isinstance(df, pd.DataFrame) and ts in df.index:
                    bar[code] = df.loc[ts]
            bars.append((bar, ts))
        return bars
