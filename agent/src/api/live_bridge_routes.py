"""Live Trading Bridge REST API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.common import safe_error, validate_path_param
from src.auth.dependencies import require_auth

router = APIRouter(prefix="/live-bridge", tags=["live-bridge"])


def _get_user_id(auth: dict) -> int:
    return int(auth["user_id"])


class PromoteRequest(BaseModel):
    run_id: str = Field(...)
    override_checks: bool = False


@router.post("/preflight/{run_id}")
async def preflight_check(run_id: str, auth: dict = Depends(require_auth)):
    validate_path_param(run_id, "run_id")
    user_id = _get_user_id(auth)
    from src.services.live_bridge import LiveBridge, LiveBridgeConfig
    bridge = LiveBridge()
    result = bridge.pre_flight_check(run_id, user_id)
    return result.model_dump()


@router.post("/promote")
async def promote_to_live(req: PromoteRequest, auth: dict = Depends(require_auth)):
    validate_path_param(req.run_id, "run_id")
    user_id = _get_user_id(auth)
    from src.services.live_bridge import LiveBridge
    bridge = LiveBridge()
    result = bridge.promote(req.run_id, user_id, req.override_checks)
    return result
