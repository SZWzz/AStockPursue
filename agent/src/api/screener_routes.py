"""Smart Stock Screener REST API."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.common import safe_error, validate_path_param
from src.auth.dependencies import require_auth
from src.services.screener_engine import PresetManager, ScreenCondition, ScreenerEngine

router = APIRouter(prefix="/screener", tags=["screener"])


def _get_user_id(auth: dict) -> int:
    return int(auth["user_id"])


class ScreenRunRequest(BaseModel):
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    universe: list[str] = Field(default_factory=list)
    date: str = ""


class BatchRequest(BaseModel):
    action: str = "add_watchlist"  # add_watchlist, export_csv, backtest_basket
    symbols: list[str] = Field(default_factory=list)


@router.get("/presets")
async def list_presets(auth: dict = Depends(require_auth)):
    """List saved screener presets (system + user)."""
    user_id = _get_user_id(auth)
    pm = PresetManager(user_id)
    return pm.list_presets()


@router.post("/presets")
async def save_preset(request: Request, auth: dict = Depends(require_auth)):
    """Save a new screener preset."""
    user_id = _get_user_id(auth)
    body = await request.json()
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    pm = PresetManager(user_id)
    preset_id = pm.save_preset(name, body.get("conditions", []), body.get("universe", []))
    return {"ok": True, "id": preset_id}


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: int, auth: dict = Depends(require_auth)):
    """Delete a screener preset."""
    user_id = _get_user_id(auth)
    pm = PresetManager(user_id)
    if pm.delete_preset(preset_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Preset not found")


@router.post("/run")
async def run_screen(req: ScreenRunRequest, auth: dict = Depends(require_auth)):
    """Execute a stock screen with the given conditions."""
    conditions = [ScreenCondition(**c) for c in req.conditions]
    engine = ScreenerEngine()
    df = engine.execute(conditions, req.universe or None, req.date or None)
    results = df.to_dict(orient="records") if not df.empty else []
    return {"results": results, "count": len(results)}


@router.post("/ai-recommend")
async def ai_recommend(auth: dict = Depends(require_auth)):
    """Get AI-recommended factor combinations for screening."""
    user_id = _get_user_id(auth)
    pm = PresetManager(user_id)
    return pm.ai_recommend()


@router.post("/batch")
async def batch_operation(req: BatchRequest, auth: dict = Depends(require_auth)):
    """Batch operations: add to watchlist, export, backtest."""
    user_id = _get_user_id(auth)
    symbols = req.symbols

    if req.action == "add_watchlist":
        try:
            from src.db.async_pool import async_get_connection
            async with async_get_connection() as conn:
                with conn.cursor() as cur:
                    for sym in symbols:
                        cur.execute(
                            "INSERT INTO vt_watchlist (user_id, symbol, name) VALUES (%s, %s, %s) ON CONFLICT (user_id, symbol) DO NOTHING",
                            (user_id, sym.strip().upper(), sym.strip()),
                        )
            return {"ok": True, "added": len(symbols)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    elif req.action == "backtest_basket":
        return {"ok": True, "message": f"Equal-weight backtest for {len(symbols)} symbols would be created", "symbols": symbols}

    return {"ok": False, "message": "Unknown action"}
