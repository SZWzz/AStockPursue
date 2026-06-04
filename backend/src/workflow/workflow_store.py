"""
PostgreSQL persistence layer for workflow projects, DAG definitions,
execution runs, and node-output cache metadata.

All methods are async-friendly and use the shared PG connection pool via
:func:`src.db.pool.get_connection`.

Design note
-----------
Raw DataFrames are NEVER stored in JSONB columns.  The ``vt_workflow_node_cache``
table holds only :class:`DataArtifactRef` metadata (storage_path, schema_hash,
row_count, summary).  The actual data lives in Parquet files under
``backend/cache/workflow/``, managed by :class:`SharedStorage`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.db.pool import get_connection
from src.workflow.schema import (
    NodeRunResult,
    RunStatus,
    WorkflowEdge,
    WorkflowModel,
    WorkflowNodeData,
    WorkflowRun,
)

logger = logging.getLogger(__name__)


class WorkflowStore:
    """CRUD operations for workflow entities backed by PostgreSQL."""

    # ── Projects ────────────────────────────────────────────────────────────

    def list_projects(self, user_id: int) -> List[Dict[str, Any]]:
        """Return all active projects for a user."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, name, description, status, created_at, updated_at
                       FROM vt_workflow_projects
                       WHERE user_id = %s AND status = 'active'
                       ORDER BY updated_at DESC""",
                    (user_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "name": r[1],
                        "description": r[2],
                        "status": r[3],
                        "created_at": r[4].isoformat() if r[4] else "",
                        "updated_at": r[5].isoformat() if r[5] else "",
                    }
                    for r in rows
                ]

    def create_project(self, user_id: int, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new research project."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO vt_workflow_projects (user_id, name, description)
                       VALUES (%s, %s, %s)
                       RETURNING id, name, description, status, created_at, updated_at""",
                    (user_id, name, description),
                )
                r = cur.fetchone()
                return {
                    "id": r[0],
                    "name": r[1],
                    "description": r[2],
                    "status": r[3],
                    "created_at": r[4].isoformat() if r[4] else "",
                    "updated_at": r[5].isoformat() if r[5] else "",
                }

    def update_project(self, project_id: str, user_id: int, name: str = "", description: str = "") -> bool:
        """Update project metadata.  Returns True if updated."""
        fields = []
        params: List[Any] = []
        if name:
            fields.append("name = %s")
            params.append(name)
        if description:
            fields.append("description = %s")
            params.append(description)
        if not fields:
            return False
        fields.append("updated_at = now()")
        params.extend([project_id, user_id])

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE vt_workflow_projects SET {', '.join(fields)} WHERE id = %s AND user_id = %s",
                    params,
                )
                return cur.rowcount > 0

    def delete_project(self, project_id: str, user_id: int) -> bool:
        """Archive a project (soft-delete).  Returns True if archived."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE vt_workflow_projects SET status = 'archived', updated_at = now()
                       WHERE id = %s AND user_id = %s""",
                    (project_id, user_id),
                )
                return cur.rowcount > 0

    # ── Workflows ───────────────────────────────────────────────────────────

    def list_workflows(self, project_id: str, user_id: int) -> List[Dict[str, Any]]:
        """Return workflow summaries for a project."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, name, description, is_locked, created_at, updated_at
                       FROM vt_workflows
                       WHERE project_id = %s AND user_id = %s
                       ORDER BY updated_at DESC""",
                    (project_id, user_id),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "name": r[1],
                        "description": r[2],
                        "is_locked": r[3],
                        "created_at": r[4].isoformat() if r[4] else "",
                        "updated_at": r[5].isoformat() if r[5] else "",
                    }
                    for r in rows
                ]

    def get_workflow(self, workflow_id: str, user_id: int) -> Optional[WorkflowModel]:
        """Fetch a full workflow definition (nodes + edges + viewport)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, project_id, user_id, name, description,
                              nodes, edges, viewport, is_locked, created_at, updated_at
                       FROM vt_workflows
                       WHERE id = %s AND user_id = %s""",
                    (workflow_id, user_id),
                )
                r = cur.fetchone()
                if not r:
                    return None
                return WorkflowModel(
                    id=r[0],
                    project_id=r[1] or "",
                    user_id=r[2],
                    name=r[3],
                    description=r[4] or "",
                    nodes=[WorkflowNodeData.from_dict(n) for n in (r[5] or [])],
                    edges=[WorkflowEdge.from_dict(e) for e in (r[6] or [])],
                    viewport=r[7] if r[7] else {"x": 0, "y": 0, "zoom": 1},
                    is_locked=r[8] or False,
                    created_at=r[9].isoformat() if r[9] else "",
                    updated_at=r[10].isoformat() if r[10] else "",
                )

    def create_workflow(self, project_id: str, user_id: int, name: str, description: str = "") -> str:
        """Create an empty workflow and return its id."""
        empty_nodes = json.dumps([])
        empty_edges = json.dumps([])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO vt_workflows (project_id, user_id, name, description, nodes, edges)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (project_id, user_id, name, description, empty_nodes, empty_edges),
                )
                return cur.fetchone()[0]

    def save_workflow(self, workflow: WorkflowModel) -> bool:
        """Persist a workflow definition (full overwrite of nodes/edges/viewport)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE vt_workflows
                       SET name = %s, description = %s, nodes = %s, edges = %s, viewport = %s,
                           updated_at = now()
                       WHERE id = %s AND user_id = %s""",
                    (
                        workflow.name,
                        workflow.description,
                        json.dumps([n.to_dict() for n in workflow.nodes]),
                        json.dumps([e.to_dict() for e in workflow.edges]),
                        json.dumps(workflow.viewport),
                        workflow.id,
                        workflow.user_id,
                    ),
                )
                return cur.rowcount > 0

    def delete_workflow(self, workflow_id: str, user_id: int) -> bool:
        """Delete a workflow.  Returns True if deleted."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM vt_workflows WHERE id = %s AND user_id = %s",
                    (workflow_id, user_id),
                )
                return cur.rowcount > 0

    def duplicate_workflow(self, workflow_id: str, user_id: int, new_name: str) -> Optional[str]:
        """Clone a workflow with a new name.  Returns the new workflow id."""
        existing = self.get_workflow(workflow_id, user_id)
        if not existing:
            return None
        new_id = self.create_workflow(
            project_id=existing.project_id,
            user_id=user_id,
            name=new_name,
            description=f"Copy of {existing.name}",
        )
        existing.id = new_id
        self.save_workflow(existing)
        return new_id

    def lock(self, workflow_id: str) -> None:
        """Lock a workflow — prevents structural edits during execution."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_workflows SET is_locked = TRUE, updated_at = now() WHERE id = %s",
                    (workflow_id,),
                )

    def unlock(self, workflow_id: str) -> None:
        """Unlock a workflow after execution completes."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_workflows SET is_locked = FALSE, updated_at = now() WHERE id = %s",
                    (workflow_id,),
                )

    # ── Runs ────────────────────────────────────────────────────────────────

    def create_run(
        self,
        workflow_id: str,
        user_id: int,
        snapshot_nodes: List[WorkflowNodeData],
        snapshot_edges: List[WorkflowEdge],
        target_node_id: Optional[str] = None,
    ) -> str:
        """Create a new execution run with a full DAG snapshot.  Returns run id."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO vt_workflow_runs
                       (workflow_id, user_id, status, target_node_id,
                        snapshot_nodes, snapshot_edges, started_at)
                       VALUES (%s, %s, 'running', %s, %s, %s, now())
                       RETURNING id""",
                    (
                        workflow_id,
                        user_id,
                        target_node_id,
                        json.dumps([n.to_dict() for n in snapshot_nodes]),
                        json.dumps([e.to_dict() for e in snapshot_edges]),
                    ),
                )
                return cur.fetchone()[0]

    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Fetch run status, snapshot, and node results."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, workflow_id, user_id, status, target_node_id,
                              snapshot_nodes, snapshot_edges, node_results,
                              started_at, finished_at, created_at
                       FROM vt_workflow_runs WHERE id = %s""",
                    (run_id,),
                )
                r = cur.fetchone()
                if not r:
                    return None
                return WorkflowRun(
                    id=r[0],
                    workflow_id=r[1] or "",
                    user_id=r[2],
                    status=RunStatus(r[3]) if r[3] else RunStatus.PENDING,
                    target_node_id=r[4],
                    snapshot_nodes=[WorkflowNodeData.from_dict(n) for n in (r[5] or [])],
                    snapshot_edges=[WorkflowEdge.from_dict(e) for e in (r[6] or [])],
                    node_results={k: NodeRunResult.from_dict(v) for k, v in (r[7] or {}).items()},
                    started_at=r[8].isoformat() if r[8] else "",
                    finished_at=r[9].isoformat() if r[9] else "",
                    created_at=r[10].isoformat() if r[10] else "",
                )

    def list_runs(self, workflow_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent runs for a workflow."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, status, target_node_id, started_at, finished_at, created_at
                       FROM vt_workflow_runs
                       WHERE workflow_id = %s
                       ORDER BY created_at DESC LIMIT %s""",
                    (workflow_id, limit),
                )
                return [
                    {
                        "id": r[0],
                        "status": r[1],
                        "target_node_id": r[2],
                        "started_at": r[3].isoformat() if r[3] else "",
                        "finished_at": r[4].isoformat() if r[4] else "",
                        "created_at": r[5].isoformat() if r[5] else "",
                    }
                    for r in cur.fetchall()
                ]

    def update_run_status(self, run_id: str, status: RunStatus) -> None:
        """Update run status (e.g. to 'completed' or 'failed')."""
        finished = datetime.now(timezone.utc) if status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED) else None
        with get_connection() as conn:
            with conn.cursor() as cur:
                if finished:
                    cur.execute(
                        "UPDATE vt_workflow_runs SET status = %s, finished_at = %s WHERE id = %s",
                        (status.value, finished, run_id),
                    )
                else:
                    cur.execute(
                        "UPDATE vt_workflow_runs SET status = %s WHERE id = %s",
                        (status.value, run_id),
                    )

    def save_node_results(self, run_id: str, node_results: Dict[str, NodeRunResult]) -> None:
        """Persist per-node execution results into the run record."""
        payload = {k: v.to_dict() for k, v in node_results.items()}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_workflow_runs SET node_results = %s WHERE id = %s",
                    (json.dumps(payload), run_id),
                )

    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries.  Returns count of deleted rows."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM vt_workflow_node_cache WHERE expires_at < now()")
                return cur.rowcount
