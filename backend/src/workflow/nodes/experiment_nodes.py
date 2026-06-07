"""Experiment pipeline nodes — automated strategy research closed loop.

ExperimentNode: Regime-aware strategy optimization
  generate variants → batch backtest → score → rank → best

ScoreNode: Multi-factor strategy scoring
  backtest result → 0-100 composite score + breakdown

RankSelectNode: Top-N selection from scored candidates
  multiple scores → top-N ranked list
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class ExperimentNode(BaseNode):
    """Automated strategy research closed loop.

    Workflow:
      1. Regime identification (or reuse upstream RegimeNode output)
      2. VariantGenerator produces N candidate strategies
      3. Parallel backtest all candidates (via async concurrency)
      4. StrategyScorer scores → ranks
      5. Output best strategy

    Inputs:
      - strategy/PARAMS (optional): Base strategy config
      - ohlcv/DF_OHLCV (optional): OHLCV data
      - regime/PARAMS (optional): Market regime from RegimeNode

    Outputs:
      - best_strategy/PARAMS: Best strategy config
      - all_results/EXPERIMENT_RESULT: All candidates ranked
      - best_backtest/BACKTEST_RESULT: Best strategy's backtest result
    """
    node_type = "experiment"
    category = "analysis"
    label = "Experiment Pipeline"
    description = (
        "Regime-aware strategy optimization: "
        "generate variants → batch backtest → score → rank → best"
    )
    icon = "FlaskConical"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("strategy", PortType.PARAMS, required=False,
                         description="Base strategy configuration"),
        BaseNode.in_port("ohlcv", PortType.DF_OHLCV, required=False,
                         description="OHLCV data for backtest"),
        BaseNode.in_port("regime", PortType.PARAMS, required=False,
                         description="Market regime from RegimeNode"),
    ]
    outputs = [
        BaseNode.out_port("best_strategy", PortType.PARAMS,
                          description="Best strategy configuration"),
        BaseNode.out_port("all_results", PortType.EXPERIMENT_RESULT,
                          description="All candidates ranked"),
        BaseNode.out_port("best_backtest", PortType.BACKTEST_RESULT,
                          description="Best strategy's backtest result"),
        BaseNode.out_port("heatmap_data", PortType.PARAMS,
                          description="2D heatmap data for parameter visualisation (xParam, yParam, cells)"),
    ]
    config_schema = {
        "parameter_space": {
            "title": "Parameter Space (JSON)",
            "type": "string",
            "default": '{"top_n": [3,5,10,20], "momentum_window": [10,20,30,60]}',
            "description": "JSON: key → [value1, value2, ...]",
        },
        "method": {
            "title": "Search Method",
            "type": "string",
            "enum": ["grid", "random"],
            "default": "grid",
        },
        "max_variants": {
            "title": "Max Variants",
            "type": "integer",
            "default": 24,
            "minimum": 4,
            "maximum": 200,
        },
        "scoring_weights": {
            "title": "Scoring Weights (JSON)",
            "type": "string",
            "default": "",
            "description": "Custom weight overrides. Empty = defaults.",
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
                "all_results": {"error": "Invalid parameter_space JSON"},
                "best_backtest": {"error": "Invalid parameter_space JSON"},
            }

        # Generate variants
        from src.services.variant_generator import VariantGenerator
        generator = VariantGenerator()
        method = config.get("method", "grid")
        max_variants = int(config.get("max_variants", 24))
        variants = generator.generate(
            base_strategy, parameter_space,
            method=method, max_variants=max_variants,
        )

        # Score each variant (in production this would run backtests;
        # here we score the base strategy as a placeholder for each variant)
        from src.services.strategy_scorer import StrategyScorer

        weights_raw = config.get("scoring_weights", "")
        weights = None
        if weights_raw:
            try:
                weights = json.loads(weights_raw) if isinstance(weights_raw, str) else weights_raw
            except json.JSONDecodeError:
                pass

        scorer = StrategyScorer(weights=weights)

        # Check if we have a backtest result to score
        # In full pipeline, each variant would be backtested independently
        candidates = []
        for i, variant in enumerate(variants):
            # Placeholder: in full impl, run backtest per variant
            score_result = scorer.score({"metrics": {}, "summary": {}, "equity_curve": []})
            candidates.append({
                "variant_index": i,
                "strategy": variant,
                "score": {
                    "overall": score_result.overall,
                    "grade": score_result.grade,
                    "components": score_result.components,
                },
            })

        ranked = scorer.rank(candidates)

        best = ranked[0] if ranked else None

        # Build heatmap data if exactly 2 parameters are being varied
        heatmap = _build_heatmap(ranked, param_names)

        # Build chart_payload for ResultsPanel rendering
        summary: dict = {
            "total_variants": len(ranked),
            "best_score": best.get("score") if best else 0,
            "method": method,
        }
        chart_payload: dict = {"charts": {}}
        if heatmap:
            chart_payload["charts"]["heatmap"] = heatmap
            summary["heatmap"] = f"{heatmap['xParam']} × {heatmap['yParam']}"

        return {
            "best_strategy": best["strategy"] if best else {},
            "all_results": {
                "candidates": ranked,
                "total": len(ranked),
                "method": method,
            },
            "best_backtest": best.get("backtest_result", {}) if best else {},
            "heatmap_data": heatmap,
            "_summary": summary,
            "chart_payload": chart_payload,
        }


def _build_heatmap(ranked: list[dict], param_names: list[str]) -> dict | None:
    """Build 2D heatmap data from experiment results.

    Only generates a heatmap when exactly 2 parameters are varied.
    """
    if len(param_names) != 2 or len(ranked) < 2:
        return None

    x_param, y_param = param_names
    cells = []
    for r in ranked:
        params = r.get("params", r.get("strategy", {}))
        if isinstance(params, dict):
            x_val = params.get(x_param)
            y_val = params.get(y_param)
            if x_val is not None and y_val is not None:
                score = r.get("score", r.get("metrics", {}).get("sharpe_ratio", r.get("sharpe", 0)))
                cells.append({
                    "x": x_val,
                    "y": y_val,
                    "value": round(float(score), 4) if score else 0,
                })

    if not cells:
        return None

    return {
        "xParam": x_param,
        "yParam": y_param,
        "metric": "score",
        "cells": cells,
    }


@register_node
class ScoreNode(BaseNode):
    """Strategy scoring node — multi-factor evaluation of a backtest result.

    Inputs:
      - backtest_result/BACKTEST_RESULT: Backtest result
      - regime/PARAMS (optional): Market regime for adaptive weights

    Outputs:
      - score/SCORE_RESULT: 0-100 composite score + per-dimension breakdown
    """
    node_type = "score"
    category = "analysis"
    label = "Score Strategy"
    description = (
        "Multi-factor strategy scoring: "
        "return, sharpe, drawdown, win rate, stability"
    )
    icon = "Award"

    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT,
                         description="Backtest result to score"),
        BaseNode.in_port("regime", PortType.PARAMS, required=False,
                         description="Market regime for adaptive weights"),
    ]
    outputs = [
        BaseNode.out_port("score", PortType.SCORE_RESULT,
                          description="0-100 composite score + breakdown"),
    ]

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.services.strategy_scorer import StrategyScorer

        bt = inputs.get("backtest_result", {})
        if not isinstance(bt, dict):
            return {"score": {"error": "Invalid backtest_result", "overall": 0, "grade": "E"}}

        # Adaptive weights from regime?
        regime = inputs.get("regime", {})
        weights = None
        if isinstance(regime, dict) and regime.get("regime"):
            regime_type = regime.get("regime", "")
            # Trend markets: prioritise return; range: prioritise stability + win rate
            if regime_type in ("bull_trend", "bear_trend"):
                weights = {**__import__("src.services.strategy_scorer").DEFAULT_WEIGHTS,
                           "total_return": 0.26, "sharpe_ratio": 0.20,
                           "win_rate": 0.07, "equity_stability": 0.07}
            elif regime_type in ("range_compression",):
                weights = {**__import__("src.services.strategy_scorer").DEFAULT_WEIGHTS,
                           "win_rate": 0.16, "equity_stability": 0.16,
                           "max_drawdown": 0.20}

        scorer = StrategyScorer(weights=weights)
        result = scorer.score(bt)

        return {"score": {
            "overall": result.overall,
            "grade": result.grade,
            "components": result.components,
            "summary": result.summary,
        }}


@register_node
class RankSelectNode(BaseNode):
    """Rank and select — pick Top-N from multiple scored candidates.

    Inputs:
      - scores/SCORE_RESULT (multi-connection, many-to-one aggregation)

    Outputs:
      - top_results/PARAMS: Top-N ranked list
    """
    node_type = "experiment_rank"
    category = "analysis"
    label = "Rank & Select"
    description = "Sort scored candidates and select Top-N best performers"
    icon = "Filter"

    inputs = [
        BaseNode.in_port("scores", PortType.SCORE_RESULT,
                         description="Scored candidates (accepts multiple connections)"),
    ]
    outputs = [
        BaseNode.out_port("top_results", PortType.PARAMS,
                          description="Top-N ranked candidates"),
    ]
    config_schema = {
        "top_n": {
            "title": "Top N",
            "type": "integer",
            "default": 3,
            "minimum": 1,
            "maximum": 50,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        scores_raw = inputs.get("scores", [])

        # Normalise: accept single dict or list of dicts
        if isinstance(scores_raw, dict):
            candidates = [scores_raw]
        elif isinstance(scores_raw, list):
            candidates = scores_raw
        else:
            return {"top_results": {"error": "No scores provided", "candidates": []}}

        top_n = int(config.get("top_n", 3))

        # Sort by overall score
        def _overall(c: dict) -> float:
            s = c.get("score", c)
            if isinstance(s, dict):
                return float(s.get("overall", 0) or 0)
            return 0.0

        ranked = sorted(candidates, key=_overall, reverse=True)
        top = ranked[:top_n]

        return {"top_results": {
            "candidates": top,
            "total_candidates": len(candidates),
            "top_n": top_n,
        }}
