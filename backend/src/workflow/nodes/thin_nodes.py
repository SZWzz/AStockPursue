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
        "mode": {"title": "Mode", "type": "string", "enum": ["rank", "filter"], "default": "rank"},
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
    description = "Validate strategy + generate deploy config for paper trading"
    icon = "TrendingUp"
    inputs = [
        BaseNode.in_port("strategy_code", PortType.PARAMS),
        BaseNode.in_port("codes", PortType.STOCK_LIST),
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT, required=False),
    ]
    outputs = [BaseNode.out_port("deploy_status", PortType.PARAMS)]
    config_schema = {
        "initial_capital": {"title": "Initial Capital", "type": "number", "default": 1000000},
        "market": {"title": "Market", "type": "string", "enum": ["equity_cn", "equity_us", "equity_hk", "crypto"], "default": "equity_cn"},
        "stop_loss_pct": {"title": "Stop Loss %", "type": "number", "default": 0.05},
        "take_profit_pct": {"title": "Take Profit %", "type": "number", "default": 0.15},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        strategy = inputs.get("strategy_code", {})
        codes = inputs.get("codes", [])
        bt_result = inputs.get("backtest_result")
        code_text = strategy.get("code", "") if isinstance(strategy, dict) else str(strategy)
        strategy_valid = bool(code_text and "generate" in code_text)

        pre_flight_warnings = []
        if bt_result and isinstance(bt_result, dict):
            metrics = bt_result.get("metrics", {})
            if metrics.get("sharpe", 0) < 0.5:
                pre_flight_warnings.append("Low Sharpe ratio")
            if abs(metrics.get("max_drawdown", 0)) > 0.3:
                pre_flight_warnings.append("High max drawdown")

        return {"deploy_status": {
            "ready": strategy_valid,
            "pre_flight_passed": len(pre_flight_warnings) == 0,
            "pre_flight_warnings": pre_flight_warnings,
            "config": {
                "initial_capital": config.get("initial_capital", 1_000_000),
                "market": config.get("market", "equity_cn"),
                "stop_loss_pct": config.get("stop_loss_pct", 0.05),
                "take_profit_pct": config.get("take_profit_pct", 0.15),
                "universe_size": len(codes) if isinstance(codes, list) else 0,
            },
        }}
