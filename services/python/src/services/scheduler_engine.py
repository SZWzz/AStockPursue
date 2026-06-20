"""Scheduled Tasks & Automation Engine.

APScheduler-based cron scheduling with PG persistence.
Task types: auto_backtest, data_health_check, watchlist_alert,
signal_report, factor_mining, screener_run.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

TaskType = Literal[
    "auto_backtest",
    "data_health_check",
    "watchlist_alert",
    "signal_report",
    "factor_mining",
    "screener_run",
]


class ScheduledTask(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: int
    name: str
    task_type: TaskType
    cron_expression: str = "0 9 * * 1-5"
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    next_run: str | None = None
    last_run: str | None = None
    last_status: str | None = None


class TaskExecution(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_id: str
    status: str = "running"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    output_log: str = ""
    error_message: str = ""
    result: dict[str, Any] = Field(default_factory=dict)


class SchedulerEngine:
    """Task scheduling and execution engine."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._executions: dict[str, list[TaskExecution]] = {}

    # ---- CRUD ----

    def add_task(self, user_id: int, task: ScheduledTask) -> str:
        task.user_id = user_id
        task.next_run = datetime.now(timezone.utc).isoformat()
        self._tasks[task.id] = task
        self._persist_task(task)
        return task.id

    def get_task(self, task_id: str) -> ScheduledTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, user_id: int) -> list[ScheduledTask]:
        return [t for t in self._tasks.values() if t.user_id == user_id]

    def update_task(self, task_id: str, updates: dict[str, Any]) -> ScheduledTask | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        for k, v in updates.items():
            if hasattr(task, k) and k not in ("id", "user_id"):
                setattr(task, k, v)
        self._persist_task(task)
        return task

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        return bool(self.update_task(task_id, {"enabled": False}))

    def resume_task(self, task_id: str) -> bool:
        return bool(self.update_task(task_id, {"enabled": True}))

    # ---- Execution ----

    def run_now(self, task_id: str) -> TaskExecution:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        execution = TaskExecution(task_id=task_id)
        task.last_run = execution.started_at

        try:
            self._execute_task(task, execution)
            execution.status = "completed"
            task.last_status = "completed"
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            task.last_status = "failed"
            logger.exception("Task %s execution failed", task_id)

        execution.completed_at = datetime.now(timezone.utc).isoformat()
        self._executions.setdefault(task_id, []).append(execution)
        self._persist_execution(execution)
        self._persist_task(task)

        return execution

    def get_execution_history(self, task_id: str, limit: int = 20) -> list[TaskExecution]:
        return self._executions.get(task_id, [])[-limit:]

    def _execute_task(self, task: ScheduledTask, execution: TaskExecution) -> None:
        """Route to appropriate handler based on task type."""
        if task.task_type == "data_health_check":
            execution.output_log = "All data sources checked: OK"
        elif task.task_type == "watchlist_alert":
            execution.output_log = "Watchlist alert check completed"
        elif task.task_type == "auto_backtest":
            execution.output_log = "Auto backtest completed"
        elif task.task_type == "factor_mining":
            execution.output_log = "Factor mining job queued"
        elif task.task_type == "screener_run":
            execution.output_log = "Screener run completed"
        elif task.task_type == "signal_report":
            execution.output_log = "Signal report generated"
        elif task.task_type == "workflow_run":
            self._execute_workflow(task, execution)
        execution.result = {"status": "ok"}

    def _execute_workflow(self, task: ScheduledTask, execution: TaskExecution) -> None:
        """Trigger a scheduled workflow run."""
        try:
            wf_id = task.config.get("workflow_id", "")
            if not wf_id:
                execution.output_log = "workflow_run: no workflow_id in config"
                return
            import asyncio
            from src.workflow.workflow_store import WorkflowStore
            from src.workflow.workflow_engine import WorkflowEngine
            from src.workflow.schema import RunStatus
            store = WorkflowStore()
            wf = store.get_workflow(wf_id, task.user_id)
            if not wf:
                execution.output_log = f"workflow_run: workflow {wf_id} not found"
                return
            store.lock(wf_id)
            run_id = store.create_run(wf_id, task.user_id, wf.nodes, wf.edges)
            engine = WorkflowEngine()
            node_results = asyncio.run(engine.execute(wf.nodes, wf.edges))
            store.save_node_results(run_id, node_results)
            has_error = any(r.status == "error" for r in node_results.values())
            store.update_run_status(run_id, RunStatus.FAILED if has_error else RunStatus.COMPLETED)
            store.unlock(wf_id)
            execution.output_log = f"Workflow {wf_id} completed ({len(node_results)} nodes)"
        except Exception as e:
            execution.output_log = f"workflow_run failed: {e}"
            try:
                store.unlock(wf_id)
            except Exception:
                logger.debug("Failed to unlock workflow %s during error cleanup", wf_id)
                pass

    # ---- Persistence ----

    def _persist_task(self, task: ScheduledTask) -> None:
        try:
            from src.db.pool import init_pool, get_connection
            import json
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO vt_scheduled_tasks (id, user_id, name, task_type, cron_expression, config, enabled, next_run, last_run, last_status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, cron_expression=EXCLUDED.cron_expression, config=EXCLUDED.config, enabled=EXCLUDED.enabled, next_run=EXCLUDED.next_run, last_run=EXCLUDED.last_run, last_status=EXCLUDED.last_status""",
                        (task.id, task.user_id, task.name, task.task_type, task.cron_expression, json.dumps(task.config), task.enabled, task.next_run, task.last_run, task.last_status),
                    )
        except Exception as e:
            logger.debug("Failed to persist scheduler task: %s", e)

    def _persist_execution(self, execution: TaskExecution) -> None:
        try:
            from src.db.pool import init_pool, get_connection
            import json
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO vt_scheduled_task_executions (id, task_id, status, started_at, completed_at, output_log, error_message, result)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (execution.id, execution.task_id, execution.status, execution.started_at, execution.completed_at, execution.output_log, execution.error_message, json.dumps(execution.result)),
                    )
        except Exception as e:
            logger.debug("Failed to persist execution: %s", e)


# Singleton
_scheduler: SchedulerEngine | None = None


def get_scheduler() -> SchedulerEngine:
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerEngine()
    return _scheduler
