"""Strategy Version Control REST API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.common import safe_error, validate_path_param
from src.auth.dependencies import require_auth

router = APIRouter(prefix="/strategy-versions", tags=["strategy-versions"])


def _get_user_id(auth: dict) -> int:
    return int(auth["user_id"])


class SaveVersionRequest(BaseModel):
    strategy_id: int = Field(...)
    code: str = Field(...)
    title: str = ""
    change_note: str = ""


class DiffRequest(BaseModel):
    from_version: int
    to_version: int


@router.get("/{strategy_id}")
async def list_versions(strategy_id: int, auth: dict = Depends(require_auth)):
    from src.services.version_control import VersionControlService
    svc = VersionControlService()
    return svc.list_versions(strategy_id)


@router.post("/{strategy_id}")
async def save_version(strategy_id: int, req: SaveVersionRequest, auth: dict = Depends(require_auth)):
    from src.services.version_control import VersionControlService
    user_id = _get_user_id(auth)
    svc = VersionControlService()
    return svc.save_version(strategy_id, user_id, req.code, req.title, req.change_note)


@router.get("/{strategy_id}/{version_num}")
async def get_version(strategy_id: int, version_num: int, auth: dict = Depends(require_auth)):
    from src.services.version_control import VersionControlService
    svc = VersionControlService()
    result = svc.get_version(strategy_id, version_num)
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return result


@router.get("/{strategy_id}/diff/{from_version}/{to_version}")
async def get_diff(strategy_id: int, from_version: int, to_version: int, auth: dict = Depends(require_auth)):
    from src.services.version_control import VersionControlService
    svc = VersionControlService()
    return {"diff": svc.get_diff(strategy_id, from_version, to_version)}


@router.post("/{strategy_id}/revert/{version_num}")
async def revert_version(strategy_id: int, version_num: int, auth: dict = Depends(require_auth)):
    from src.services.version_control import VersionControlService
    user_id = _get_user_id(auth)
    svc = VersionControlService()
    try:
        return svc.revert(strategy_id, user_id, version_num)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
