"""Thin wrapper nodes — Screener and PaperTrading."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

# TODO(P5): migrate to Go gRPC equivalents:
#   - engines → EngineService (not yet exposed)
#   - risk → RiskService (not yet exposed)
#   - brokers → BrokerService (not yet exposed)

logger = logging.getLogger(__name__)


@register_node
class ScreenerNode(BaseNode):
    node_type = "screener"; category = "filter"; label = "Screener"
    description = "Filter stocks by factor values (rank/filter modes)"
    icon = "Filter"
    quick_tool_route = "/screener"
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
        from src.services.screener_engine import ScreenerEngine

        codes = inputs.get("codes", [])
        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)
        if not codes:
            return {"filtered_codes": [], "scores": pd.DataFrame()}

        factor_data = inputs.get("factor_data")
        top_n = int(config.get("top_n", 20))

        if factor_data is not None and isinstance(factor_data, pd.DataFrame) and not factor_data.empty:
            filtered, score_df = ScreenerEngine.rank_in_memory(
                factor_data, codes=codes, top_n=top_n, ascending=False,
            )
        else:
            filtered, score_df = list(codes)[:top_n], pd.DataFrame()

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
                from src.go_http import run_backtest

                capital = float(config.get("initial_capital", 1_000_000))
                interval = config.get("interval", "1D")
                duration = int(config.get("duration_days", 30))

                # Build backtest config for Go API
                bt_config = {
                    "symbols": list(codes),
                    "start_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "end_date": (pd.Timestamp.now() + pd.Timedelta(days=duration)).strftime("%Y-%m-%d"),
                    "frequency": interval.lower(),
                    "initial_cash": capital,
                }

                bt_resp = run_backtest(bt_config)

                if "error" in bt_resp:
                    result["simulation"] = {"error": bt_resp["error"]}
                else:
                    result["simulation"] = {
                        "mode": "paper_trading_go",
                        "final_equity": round(bt_resp.get("final_equity", capital), 2),
                        "total_return": round(bt_resp.get("total_return", 0), 4),
                        "sharpe": round(bt_resp.get("sharpe_ratio", 0), 4),
                        "max_drawdown": round(bt_resp.get("max_drawdown", 0), 4),
                        "total_trades": bt_resp.get("total_trades", 0),
                        "win_rate": round(bt_resp.get("win_rate", 0), 4),
                    }

            except Exception as e:
                logger.exception("PaperTrading simulation via Go API failed")
                result["simulation"] = {"error": str(e)}

        return {"deploy_status": result}
