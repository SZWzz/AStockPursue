"""Experiment pipeline REST API — run strategy optimisation experiments."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experiment", tags=["experiment"])


@router.post("/generate-variants")
async def generate_variants(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    """Generate strategy variants from a base config and parameter space.

    Request body:
        base_strategy: dict — base strategy configuration
        parameter_space: dict — {path: [values]}
        method: str — "grid" or "random"
        max_variants: int — maximum variants to generate
    """
    from src.services.variant_generator import VariantGenerator

    base = payload.get("base_strategy", {})
    param_space = payload.get("parameter_space", {})
    method = payload.get("method", "grid")
    max_variants = int(payload.get("max_variants", 24))

    generator = VariantGenerator()
    variants = generator.generate(base, param_space, method=method, max_variants=max_variants)

    return {
        "count": len(variants),
        "method": method,
        "variants": variants,
    }


@router.post("/score")
async def score_strategy(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    """Score a strategy from a backtest result.

    Request body:
        backtest_result: dict — backtest output
        weights: dict (optional) — custom scoring weights
    """
    from src.services.strategy_scorer import StrategyScorer

    bt = payload.get("backtest_result", {})
    weights = payload.get("weights")

    scorer = StrategyScorer(weights=weights)
    result = scorer.score(bt)

    return {
        "overall": result.overall,
        "grade": result.grade,
        "components": result.components,
        "summary": result.summary,
    }


@router.post("/detect-regime")
async def detect_regime(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    """Detect market regime from OHLCV data payload.

    Request body:
        ohlcv: list of {time, open, high, low, close, volume} records
        market: str — market identifier
    """
    import pandas as pd
    from src.services.regime_engine import RegimeEngine

    ohlcv_data = payload.get("ohlcv", [])
    market = payload.get("market", "CN_A")

    if not ohlcv_data:
        raise HTTPException(status_code=400, detail="No OHLCV data provided")

    df = pd.DataFrame(ohlcv_data)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")

    engine = RegimeEngine()
    result = engine.detect(df, market=market)

    return result
