"""Options Analysis REST API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.common import safe_error
from src.auth.dependencies import require_auth

router = APIRouter(prefix="/options", tags=["options"])


class BSRequest(BaseModel):
    S: float = Field(..., description="Spot price")
    K: float = Field(..., description="Strike price")
    T: float = Field(..., description="Time to expiry (years)")
    r: float = Field(default=0.03, description="Risk-free rate")
    sigma: float = Field(default=0.25, description="Volatility")
    option_type: Literal["call", "put"] = "call"


class IVRequest(BaseModel):
    S: float
    K: float
    T: float
    r: float = 0.03
    market_price: float
    option_type: Literal["call", "put"] = "call"


class BinomialRequest(BaseModel):
    S: float
    K: float
    T: float
    r: float = 0.03
    sigma: float = 0.25
    n_steps: int = Field(default=100, ge=10, le=1000)
    option_type: Literal["call", "put"] = "call"


class VolSurfaceRequest(BaseModel):
    S: float = Field(..., description="Spot/underlying price")
    r: float = Field(default=0.03)


@router.post("/black-scholes")
async def black_scholes_price(req: BSRequest):
    from src.services.options_pricing import OptionsPricingEngine
    result = OptionsPricingEngine.black_scholes(req.S, req.K, req.T, req.r, req.sigma, req.option_type)
    return result.model_dump()


@router.post("/binomial")
async def binomial_price(req: BinomialRequest):
    from src.services.options_pricing import OptionsPricingEngine
    price = OptionsPricingEngine.binomial_tree(req.S, req.K, req.T, req.r, req.sigma, req.n_steps, req.option_type)
    return {"price": price, "method": "binomial_tree", "n_steps": req.n_steps}


@router.post("/implied-volatility")
async def implied_vol(req: IVRequest):
    from src.services.options_pricing import OptionsPricingEngine
    iv = OptionsPricingEngine.implied_volatility(req.S, req.K, req.T, req.r, req.market_price, req.option_type)
    if iv is None:
        raise HTTPException(status_code=400, detail="Implied volatility did not converge")
    return {"implied_vol": iv}


@router.post("/vol-surface")
async def vol_surface(req: VolSurfaceRequest):
    from src.services.options_pricing import OptionsPricingEngine
    surface = OptionsPricingEngine.generate_vol_surface(req.S, req.r)
    return {"points": [s.model_dump() for s in surface], "spot": req.S}


@router.post("/greeks")
async def greeks(req: BSRequest):
    """Get full Greeks analysis for a single option."""
    from src.services.options_pricing import OptionsPricingEngine
    result = OptionsPricingEngine.black_scholes(req.S, req.K, req.T, req.r, req.sigma, req.option_type)
    return result.model_dump()
