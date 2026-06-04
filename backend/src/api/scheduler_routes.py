"""Scheduled Tasks REST API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.common import safe_error, validate_path_param
from src.auth.dependencies import require_auth
from src.services.scheduler_engine import ScheduledTask, get_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def _get_user_id(auth: dict) -> int:
    return int(auth["user_id"])


class CreateTaskRequest(BaseModel):
    name: str
    task_type: str = "auto_backtest"
    cron_expression: str = "0 9 * * 1-5"
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateTaskRequest(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None


@router.get("/tasks")
async def list_tasks(auth: dict = Depends(require_auth)):
    user_id = _get_user_id(auth)
    scheduler = get_scheduler()
    tasks = scheduler.list_tasks(user_id)
    return {"tasks": [t.model_dump() for t in tasks], "total": len(tasks)}


@router.post("/tasks")
async def create_task(req: CreateTaskRequest, auth: dict = Depends(require_auth)):
    user_id = _get_user_id(auth)
    task = ScheduledTask(
        user_id=user_id,
        name=req.name,
        task_type=req.task_type,  # type: ignore[arg-type]
        cron_expression=req.cron_expression,
        config=req.config,
    )
    task_id = get_scheduler().add_task(user_id, task)
    return {"ok": True, "task_id": task_id}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, auth: dict = Depends(require_auth)):
    validate_path_param(task_id, "task_id")
    task = get_scheduler().get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump()


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, req: UpdateTaskRequest, auth: dict = Depends(require_auth)):
    validate_path_param(task_id, "task_id")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    task = get_scheduler().update_task(task_id, updates)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True, "task": task.model_dump()}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, auth: dict = Depends(require_auth)):
    validate_path_param(task_id, "task_id")
    if get_scheduler().remove_task(task_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str, auth: dict = Depends(require_auth)):
    validate_path_param(task_id, "task_id")
    if get_scheduler().pause_task(task_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str, auth: dict = Depends(require_auth)):
    validate_path_param(task_id, "task_id")
    if get_scheduler().resume_task(task_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_id}/run-now")
async def run_task_now(task_id: str, auth: dict = Depends(require_auth)):
    validate_path_param(task_id, "task_id")
    try:
        execution = get_scheduler().run_now(task_id)
        return execution.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.get("/tasks/{task_id}/history")
async def get_task_history(task_id: str, limit: int = 20, auth: dict = Depends(require_auth)):
    validate_path_param(task_id, "task_id")
    executions = get_scheduler().get_execution_history(task_id, limit)
    return {"executions": [e.model_dump() for e in executions], "total": len(executions)}
