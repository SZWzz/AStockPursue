"""Performance Attribution REST API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.common import safe_error
from src.auth.dependencies import require_auth

router = APIRouter(prefix="/attribution", tags=["attribution"])


class AttributionRequest(BaseModel):
    run_id: str = Field(...)


class FactorAttributionRequest(BaseModel):
    run_id: str = Field(...)
    factors: list[str] = Field(default_factory=list)


class SectorAttributionRequest(BaseModel):
    run_id: str
    classification: Literal["sw", "gics"] = "sw"


@router.post("/brinson")
async def compute_brinson(req: AttributionRequest):
    try:
        from src.services.attribution_engine import AttributionEngine
        engine = AttributionEngine()
        return engine.brinson(req.run_id).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.post("/factor")
async def compute_factor(req: FactorAttributionRequest):
    try:
        from src.services.attribution_engine import AttributionEngine
        engine = AttributionEngine()
        return engine.factor_attribution(req.run_id, req.factors or None).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.post("/sector")
async def compute_sector(req: SectorAttributionRequest):
    try:
        from src.services.attribution_engine import AttributionEngine
        engine = AttributionEngine()
        return engine.sector_attribution(req.run_id, req.classification).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.post("/time-series-decomposition")
async def compute_decomposition(req: AttributionRequest):
    try:
        from src.services.attribution_engine import AttributionEngine
        engine = AttributionEngine()
        return engine.time_series_decomposition(req.run_id).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.post("/full")
async def compute_full_report(req: AttributionRequest):
    try:
        from src.services.attribution_engine import AttributionEngine
        engine = AttributionEngine()
        return engine.full_report(req.run_id).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))
