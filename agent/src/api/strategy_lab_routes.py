"""Strategy Lab HTTP routes — direct access to the original backtest engine.

Routes:
    POST /strategy-lab/backtest     — run strategy against backtest engine
    POST /strategy-lab/save         — save strategy code
    GET  /strategy-lab/list         — list saved strategies
    GET  /strategy-lab/{id}         — get strategy info + code
    POST /strategy-lab/delete/{id}  — delete strategy
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.lab.repository import IndicatorRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-lab", tags=["strategy-lab"])

_repo: IndicatorRepository | None = None


def _get_repo() -> IndicatorRepository:
    global _repo
    if _repo is None:
        from pathlib import Path
        from src.config.paths import get_runtime_root
        _repo = IndicatorRepository(base_dir=get_runtime_root() / "strategies")
    return _repo


# ── Models ──────────────────────────────────────────────────────────────────


class StrategySaveRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=200_000)
    strategy_id: str | None = None
    filename: str | None = None


class StrategyBacktestRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=200_000)
    codes: list[str] = Field(..., min_length=1, max_length=20)
    source: str = Field(default="auto", max_length=20)
    start_date: str = Field(default="2024-01-01")
    end_date: str = Field(default="2025-12-31")
    interval: str = Field(default="1D", pattern=r"^(1m|5m|15m|30m|1H|4H|1D)$")
    initial_cash: float = Field(default=100_000.0, ge=1000.0)
    leverage: float = Field(default=1.0, ge=1.0, le=20.0)
    extra_fields: list[str] | None = None


class BacktestResponse(BaseModel):
    success: bool
    error: str | None = None
    run_id: str | None = None


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/list")
async def list_strategies():
    repo = _get_repo()
    items = repo.list()
    return {
        "strategies": [
            {
                "id": i.id,
                "name": i.name,
                "description": i.description,
                "param_count": i.param_count,
                "created_at": i.created_at,
                "updated_at": i.updated_at,
            }
            for i in items
        ]
    }


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    repo = _get_repo()
    info = repo.get(strategy_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    code = repo.get_code(strategy_id) or ""
    return {
        "id": info.id,
        "name": info.name,
        "description": info.description,
        "code": code,
        "created_at": info.created_at,
        "updated_at": info.updated_at,
    }


@router.post("/save")
async def save_strategy(req: StrategySaveRequest):
    repo = _get_repo()
    try:
        info = repo.save(code=req.code, indicator_id=req.strategy_id, filename=req.filename)
        return {
            "id": info.id,
            "name": info.name,
            "description": info.description,
            "created_at": info.created_at,
            "updated_at": info.updated_at,
        }
    except Exception as e:
        logger.exception("Failed to save strategy")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete/{strategy_id}")
async def delete_strategy(strategy_id: str):
    repo = _get_repo()
    if repo.delete(strategy_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")


@router.post("/backtest", response_model=BacktestResponse)
async def backtest_strategy(req: StrategyBacktestRequest):
    from src.lab.strategy_backtest_bridge import run_strategy_backtest

    try:
        result = run_strategy_backtest(
            code=req.code,
            codes=req.codes,
            start_date=req.start_date,
            end_date=req.end_date,
            source=req.source,
            interval=req.interval,
            initial_cash=req.initial_cash,
            leverage=req.leverage,
            extra_fields=req.extra_fields,
        )
        return BacktestResponse(**result)
    except Exception as e:
        logger.exception("Strategy backtest failed")
        return BacktestResponse(success=False, error=str(e))


@router.get("/template/default")
async def get_default_template():
    from src.lab.strategy_backtest_bridge import DEFAULT_SIGNAL_ENGINE_TEMPLATE

    return {"code": DEFAULT_SIGNAL_ENGINE_TEMPLATE}
