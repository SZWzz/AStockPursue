"""Strategy comparison API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.common import safe_error
from src.auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compare", tags=["compare"])


class StatisticalTestRequest(BaseModel):
    run_id_a: str = Field(...)
    run_id_b: str = Field(...)
    benchmark: str | None = None


class FactorRegressionRequest(BaseModel):
    run_id: str
    factors: list[str] = Field(default_factory=list)


@router.post("/statistical-tests")
async def run_statistical_tests(req: StatisticalTestRequest):
    """Run statistical comparison tests between two backtest runs."""
    try:
        from src.services.statistical_tests import StatisticalTestEngine

        engine = StatisticalTestEngine()
        result = engine.compute_all(req.run_id_a, req.run_id_b)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.get("/equity-overlay/{run_id_a}/{run_id_b}")
async def get_equity_overlay(run_id_a: str, run_id_b: str):
    """Get overlaid equity curves for two runs."""
    equity_a, equity_b = [], []
    try:
        from src.db.backtest_store import get_backtest_run

        run_a = get_backtest_run(run_id_a)
        if run_a:
            equity_a = run_a.get("equity", [])

        run_b = get_backtest_run(run_id_b)
        if run_b:
            equity_b = run_b.get("equity", [])
    except Exception:
        logger.debug("Failed to load equity overlay for runs %s / %s", run_id_a, run_id_b)
        pass

    return {"equity_a": equity_a, "equity_b": equity_b}


@router.post("/factor-regression")
async def factor_regression(req: FactorRegressionRequest):
    """Run factor regression on strategy returns (CAPM/FF3)."""
    try:
        from src.services.statistical_tests import StatisticalTestEngine

        engine = StatisticalTestEngine()
        capm = engine.capm_regression(engine._load_returns(req.run_id))
        return {"capm": capm}
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))
