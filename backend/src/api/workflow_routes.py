"""Workflow REST + SSE API — n8n-style node-based quant research pipelines.

Endpoints for managing research projects, workflow DAGs, execution runs,
node-type discovery, and DAG validation.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.auth.dependencies import require_auth
from src.workflow.node_registry import get_node_registry
from src.workflow.schema import (
    NodeRunResult,
    RunStatus,
    WorkflowEdge,
    WorkflowModel,
    WorkflowNodeData,
    WorkflowRun,
    is_compatible,
)
from src.workflow.workflow_engine import WorkflowEngine
from src.workflow.workflow_store import WorkflowStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["workflow"])

_store = WorkflowStore()
_engine = WorkflowEngine()
_running_workflows: dict[str, asyncio.Task] = {}  # workflow_id -> running task
_run_queues: dict[str, asyncio.Queue] = {}         # run_id -> progress queue (for SSE)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_user_id(req=Depends(require_auth)) -> int:
    """Extract user_id from auth dependency."""
    return req.user_id if hasattr(req, "user_id") else req.get("user_id", 0)


# ── Projects ─────────────────────────────────────────────────────────────────

@router.get("/projects")
def list_projects(user_id: int = Depends(_get_user_id)):
    """List all active research projects for the authenticated user."""
    try:
        return _store.list_projects(user_id)
    except Exception:
        logger.exception("Failed to list projects")
        raise HTTPException(status_code=500, detail="An internal error occurred while listing projects")


@router.post("/projects")
def create_project(body: dict, user_id: int = Depends(_get_user_id)):
    """Create a new research project."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Project name is required")
    try:
        return _store.create_project(user_id, name, body.get("description", ""))
    except Exception:
        logger.exception("Failed to create project")
        raise HTTPException(status_code=500, detail="An internal error occurred while creating the project")


@router.get("/projects/{project_id}")
def get_project(project_id: str, user_id: int = Depends(_get_user_id)):
    """Get project metadata.  Currently returns 200 with id or 404."""
    workflows = _store.list_workflows(project_id, user_id)
    return {"id": project_id, "workflow_count": len(workflows)}


@router.put("/projects/{project_id}")
def update_project(project_id: str, body: dict, user_id: int = Depends(_get_user_id)):
    """Update project name/description."""
    ok = _store.update_project(project_id, user_id, body.get("name", ""), body.get("description", ""))
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "ok"}


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user_id: int = Depends(_get_user_id)):
    """Archive a project (soft-delete)."""
    ok = _store.delete_project(project_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "ok"}


# ── Workflows CRUD ───────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/workflows")
def list_workflows(project_id: str, user_id: int = Depends(_get_user_id)):
    """List all workflows in a project."""
    return _store.list_workflows(project_id, user_id)


@router.post("/projects/{project_id}/workflows")
def create_workflow(project_id: str, body: dict, user_id: int = Depends(_get_user_id)):
    """Create a new empty workflow."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Workflow name is required")
    try:
        wf_id = _store.create_workflow(project_id, user_id, name, body.get("description", ""))
        return {"id": wf_id}
    except Exception:
        logger.exception("Failed to create workflow")
        raise HTTPException(status_code=500, detail="An internal error occurred while creating the workflow")


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str, user_id: int = Depends(_get_user_id)):
    """Get full workflow definition (nodes + edges + viewport)."""
    wf = _store.get_workflow(workflow_id, user_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf.to_dict()


@router.put("/workflows/{workflow_id}")
def save_workflow(workflow_id: str, body: dict, user_id: int = Depends(_get_user_id)):
    """Save a workflow (full overwrite of nodes/edges/viewport).

    Rejected if the workflow is locked (execution in progress).
    """
    existing = _store.get_workflow(workflow_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if existing.is_locked:
        # Stale lock detection
        if workflow_id not in _running_workflows:
            logger.warning("Workflow %s is locked but has no running task — auto-unlocking", workflow_id)
            _store.unlock(workflow_id)
            existing.is_locked = False
        else:
            raise HTTPException(status_code=423, detail="Workflow is locked during execution")

    # Update from body
    existing.name = body.get("name", existing.name)
    existing.description = body.get("description", existing.description)
    if "nodes" in body:
        existing.nodes = [WorkflowNodeData.from_dict(n) for n in body["nodes"]]
    if "edges" in body:
        existing.edges = [WorkflowEdge.from_dict(e) for e in body["edges"]]
    if "viewport" in body:
        existing.viewport = body["viewport"]

    _store.save_workflow(existing)
    return {"status": "ok", "updated_at": existing.updated_at}


@router.delete("/workflows/{workflow_id}")
def delete_workflow(workflow_id: str, user_id: int = Depends(_get_user_id)):
    """Delete a workflow."""
    ok = _store.delete_workflow(workflow_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"status": "ok"}


@router.post("/workflows/{workflow_id}/duplicate")
def duplicate_workflow(workflow_id: str, body: dict, user_id: int = Depends(_get_user_id)):
    """Clone a workflow."""
    new_name = body.get("name", "Copy")
    new_id = _store.duplicate_workflow(workflow_id, user_id, new_name)
    if not new_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"id": new_id}


# ── Execution ────────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, body: dict, user_id: int = Depends(_get_user_id)):
    """Run a workflow (or up to a specific target node).

    Takes a snapshot of the current DAG, locks the workflow, and executes
    concurrently.  Returns the run id; progress is streamed via SSE.
    """
    wf = _store.get_workflow(workflow_id, user_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.is_locked:
        # Stale lock detection: if no active task is running for this workflow, auto-unlock
        if workflow_id not in _running_workflows:
            logger.warning("Workflow %s is locked but has no running task — auto-unlocking", workflow_id)
            _store.unlock(workflow_id)
            wf.is_locked = False
        else:
            raise HTTPException(status_code=423, detail="Workflow is already running")

    target_node_id = body.get("target_node_id")

    # Lock + snapshot + create run
    try:
        _store.lock(workflow_id)
        run_id = _store.create_run(
            workflow_id=workflow_id,
            user_id=user_id,
            snapshot_nodes=wf.nodes,
            snapshot_edges=wf.edges,
            target_node_id=target_node_id,
        )
    except Exception:
        _store.unlock(workflow_id)
        raise

    # Start execution in background
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    task = asyncio.create_task(
        _execute_and_persist(run_id, wf.nodes, wf.edges, target_node_id, queue)
    )
    _running_workflows[workflow_id] = task

    # Dashboard activity log
    try:
        from src.api.dashboard_routes import log_activity
        log_activity(f"Workflow {wf.name or workflow_id[:8]} started ({len(wf.nodes)} nodes)", user_id)
    except Exception:
        pass

    return {"run_id": run_id, "status": "running"}


@router.post("/workflows/{workflow_id}/run/{node_id}")
async def run_single_node(workflow_id: str, node_id: str, body: dict, user_id: int = Depends(_get_user_id)):
    """Execute a single node with manually-supplied inputs (for debugging)."""
    wf = _store.get_workflow(workflow_id, user_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    target_node = None
    for n in wf.nodes:
        if n.id == node_id:
            target_node = n
            break
    if not target_node:
        raise HTTPException(status_code=404, detail="Node not found in workflow")

    inputs = body.get("inputs", {})
    try:
        result = await _engine.execute_single_node(target_node, inputs)
        return {"node_id": node_id, "result": result.get("_summary", {}), "error": result.get("_error", "")}
    except Exception:
        logger.exception("Single node execution failed")
        raise HTTPException(status_code=500, detail="An internal error occurred during node execution")


@router.post("/workflows/{workflow_id}/stop")
def stop_workflow(workflow_id: str, user_id: int = Depends(_get_user_id)):
    """Cancel a running workflow — cancels the engine task AND unlocks."""
    task = _running_workflows.pop(workflow_id, None)
    if task and not task.done():
        _engine.cancel()
        task.cancel()
    _store.unlock(workflow_id)
    return {"status": "ok"}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    """Get run status and per-node results."""
    run = _store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.to_dict()


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, auth: dict = Depends(require_auth)):
    """SSE progress stream for a workflow run.

    Replays existing results from DB, then bridges the engine's progress queue
    to the SSE stream.  Falls back to a standalone queue if the engine queue
    is not available (e.g. after server restart).
    """
    run = _store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Try to find the engine's live queue from the running workflow
    engine_queue: Optional[asyncio.Queue] = None
    if run.workflow_id and run.workflow_id in _running_workflows:
        # Queue is stored alongside the task — we need to reconstruct it.
        # For now, create a fresh queue and poll for results.
        pass  # engine_queue accessed via _engine._progress in subclasses; see below

    fallback_queue: asyncio.Queue = asyncio.Queue()

    async def event_generator():
        # Replay existing results from DB (summary only, no raw data)
        if run:
            has_results = False
            for nid, result in run.node_results.items():
                if result.status in ("done", "cached"):
                    has_results = True
                    compact = {}
                    for k, v in (result.summary or {}).items():
                        if isinstance(v, dict):
                            compact[k] = f"{{...{len(v)} keys}}" if len(v) > 3 else v
                        elif isinstance(v, (list, tuple)):
                            compact[k] = f"[...{len(v)} items]"
                        elif isinstance(v, str) and len(v) > 100:
                            compact[k] = v[:100] + "..."
                        else:
                            compact[k] = v
                    yield f"event: node_done\ndata: {json.dumps({'node_id': nid, 'node_type': 'completed', 'duration_ms': result.duration_ms, 'outputs_summary': compact}, default=str)}\n\n"
            # Signal completion after replay
            if has_results:
                yield f"event: workflow_done\ndata: {{}}\n\n"

        # Stream live events or send heartbeats
        try:
            while True:
                msg = await asyncio.wait_for(fallback_queue.get(), timeout=5)
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], default=str)}\n\n"
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_id}/node/{node_id}")
def get_node_result(run_id: str, node_id: str):
    """Get detailed output for a specific node in a run."""
    run = _store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    result = run.node_results.get(node_id)
    if not result:
        raise HTTPException(status_code=404, detail="Node result not found")
    return result.to_dict()


# ── Node registry ────────────────────────────────────────────────────────────

@router.get("/node-types")
def list_node_types():
    """Return all available node type definitions (for the palette UI)."""
    registry = get_node_registry()
    definitions = registry.list_all()
    return [d.to_dict() for d in definitions]


@router.get("/node-types/{node_type}")
def get_node_type(node_type: str):
    """Get the definition for a specific node type."""
    try:
        registry = get_node_registry()
        return registry.get(node_type).to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown node type: {node_type}")


# ── ExpressionTree → Workflow converter ────────────────────────────────────────


@router.post("/tree-to-workflow")
def tree_to_workflow(body: dict, user_id: int = Depends(_get_user_id)):
    """Convert an ExpressionTree dict to workflow {nodes, edges}.

    Request body::

        {"tree": {...}, "name": "alpha101_001"}

    Returns::

        {"nodes": [...], "edges": [...]}
    """
    from src.factors.mining.expression_tree import ExpressionTree
    from src.workflow.tree_converter import expression_tree_to_workflow

    tree_dict = body.get("tree")
    if not tree_dict:
        raise HTTPException(status_code=400, detail="Missing 'tree' field")

    name = body.get("name", "Factor")
    try:
        tree = ExpressionTree.from_dict(tree_dict)
        result = expression_tree_to_workflow(tree, name=name)
        return result
    except ValueError as e:
        logger.warning("tree_to_workflow invalid input: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid expression tree: {e}")
    except Exception:
        logger.exception("tree_to_workflow failed")
        raise HTTPException(status_code=500, detail="An internal error occurred during tree conversion")


# ── Strategy templates ────────────────────────────────────────────────────────


@router.get("/templates")
def list_templates():
    """List all available strategy templates."""
    from src.workflow.templates import TEMPLATES
    return [{"id": t["id"], "name": t["name"], "description": t["description"]} for t in TEMPLATES]


@router.get("/templates/{template_id}")
def get_template(template_id: str):
    """Get a specific template's {nodes, edges} for canvas insertion."""
    from src.workflow.templates import load_template
    result = load_template(template_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    return result


@router.post("/match-template")
def match_strategy_template(body: dict, user_id: int = Depends(_get_user_id)):
    """Analyse Python strategy code and find the best matching template.

    Request::

        {"code": "class SignalEngine: ..."}

    Returns::

        {"template_id": "dual_ma_crossover", "name": "Dual MA Crossover",
         "score": 0.85, "nodes": [...], "edges": [...]}
    """
    from src.workflow.templates import match_template

    code = body.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="Missing 'code' field")

    result = match_template(code)
    if not result:
        return {"template_id": None, "name": None, "score": 0.0,
                "message": "No template matched — strategy may be too complex or custom"}

    template, score = result
    return {
        "template_id": template["id"],
        "name": template["name"],
        "description": template["description"],
        "score": round(score, 3),
        "nodes": template["nodes"],
        "edges": template["edges"],
    }


# ── AI strategy decomposer ────────────────────────────────────────────────────


@router.post("/decompose-strategy")
def decompose_strategy(body: dict, user_id: int = Depends(_get_user_id)):
    """Use LLM to decompose a Python strategy into workflow {nodes, edges}.

    Request::

        {"code": "class SignalEngine: ..."}

    Returns::

        {"nodes": [...], "edges": [...], "attempts": 1}
        or {"error": "...", "nodes": [], "edges": []}
    """
    from src.workflow.strategy_decomposer import decompose_strategy

    code = body.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="Missing 'code' field")

    result = decompose_strategy(code)
    if "error" in result:
        logger.warning("Strategy decomposition failed: %s", result["error"])
    return result


@router.get("/node-catalog")
def get_node_catalog_endpoint():
    """Return a simplified node catalog for the AI decompose UI."""
    from src.workflow.strategy_decomposer import get_node_catalog
    return get_node_catalog()


# ── Validation ───────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/validate")
def validate_workflow(workflow_id: str, user_id: int = Depends(_get_user_id)):
    """Validate a workflow DAG — type compatibility, cycles, required ports."""
    wf = _store.get_workflow(workflow_id, user_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    errors = []
    registry = get_node_registry()

    # Build node map
    node_map = {n.id: n for n in wf.nodes}

    # Check each edge for type compatibility
    for edge in wf.edges:
        if edge.source not in node_map or edge.target not in node_map:
            errors.append({"edge_id": edge.id, "message": "Edge references unknown node"})
            continue

        try:
            source_def = registry.get(node_map[edge.source].node_type)
            target_def = registry.get(node_map[edge.target].node_type)
        except KeyError as e:
            errors.append({"edge_id": edge.id, "message": f"Unknown node type: {e}"})
            continue

        # Find port types
        source_port_type = None
        for p in source_def.outputs:
            if p.name == edge.source_port:
                source_port_type = p.port_type
                break
        target_port_type = None
        for p in target_def.inputs:
            if p.name == edge.target_port:
                target_port_type = p.port_type
                break

        if source_port_type and target_port_type:
            if not is_compatible(source_port_type, target_port_type):
                errors.append({
                    "edge_id": edge.id,
                    "message": f"Type mismatch: {source_port_type} → {target_port_type}",
                })

    # Check required inputs
    for node in wf.nodes:
        try:
            definition = registry.get(node.node_type)
        except KeyError:
            continue
        for port in definition.inputs:
            if not port.required:
                continue
            connected = any(
                e.target == node.id and e.target_port == port.name
                for e in wf.edges
            )
            if not connected:
                errors.append({
                    "node_id": node.id,
                    "message": f"Required input '{port.name}' is not connected",
                })

    return {"valid": len(errors) == 0, "errors": errors}


@router.post("/validate-connection")
def validate_connection(body: dict):
    """Check whether two port types can be connected."""
    source_type = body.get("source_type", "")
    target_type = body.get("target_type", "")
    return {"compatible": is_compatible(source_type, target_type)}


# ── Suggestions ──────────────────────────────────────────────────────────────

@router.post("/suggest-next")
def suggest_next(body: dict):
    """Given an output port type, suggest compatible downstream node types."""
    source_type = body.get("source_type", "")
    if not source_type:
        raise HTTPException(status_code=422, detail="source_type is required")
    registry = get_node_registry()
    targets = registry.get_compatible_targets(source_type)
    return {
        "source_type": source_type,
        "compatible_nodes": [d.to_dict() for d in targets],
    }


@router.post("/templates/{template_id}/instantiate")
def instantiate_template(template_id: str, body: dict, user_id: int = Depends(_get_user_id)):
    """Instantiate a strategy template into a project (creates a new workflow)."""
    from src.workflow.templates import load_template
    template = load_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

    project_id = body.get("project_id", "")
    name = body.get("name", template["name"])

    # Auto-create project if not provided
    if not project_id:
        try:
            proj = _store.create_project(user_id, name, f"Created from template: {template['name']}")
            project_id = proj["id"]
        except Exception:
            logger.exception("Failed to auto-create project for template")
            raise HTTPException(status_code=500, detail="An internal error occurred while creating the project from template")

    try:
        wf_id = _store.create_workflow(project_id, user_id, name, template["description"])
    except Exception:
        logger.exception("Failed to create workflow from template")
        raise HTTPException(status_code=500, detail="An internal error occurred while creating the workflow from template")

    # Generate nodes from template blueprint
    nodes = template.get("nodes", [])
    edges = template.get("edges", [])
    if nodes:
        body = {"name": name, "description": template["description"], "nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}
        _store.save_workflow(WorkflowModel(
            id=wf_id, project_id=project_id, user_id=user_id, name=name,
            description=template["description"],
            nodes=[WorkflowNodeData.from_dict(n) for n in nodes],
            edges=[WorkflowEdge.from_dict(e) for e in edges],
        ))

    return {"id": wf_id, "project_id": project_id, "name": name}


# ── Scheduled Workflow Runs ──────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/schedule")
def schedule_workflow(workflow_id: str, body: dict, user_id: int = Depends(_get_user_id)):
    """Create a scheduled task that triggers this workflow on a cron schedule."""
    wf = _store.get_workflow(workflow_id, user_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    cron = body.get("cron_expression", "0 9 * * 1-5")
    task_name = body.get("name", f"Workflow: {wf.name}")

    try:
        from src.services.scheduler_engine import SchedulerEngine, ScheduledTask
        import uuid
        task = ScheduledTask(
            id=str(uuid.uuid4()), user_id=user_id, name=task_name,
            task_type="workflow_run", cron_expression=cron,
            config={"workflow_id": workflow_id}, enabled=True,
        )
        SchedulerEngine().create(task)
        return {"status": "ok", "task_id": task.id, "cron": cron}
    except ImportError:
        raise HTTPException(status_code=501, detail="Scheduler engine not available")
    except Exception:
        logger.exception("Failed to schedule workflow")
        raise HTTPException(status_code=500, detail="An internal error occurred while scheduling the workflow")


# ── Version History ───────────────────────────────────────────────────────────

@router.get("/workflows/{workflow_id}/versions")
def list_workflow_versions(workflow_id: str, user_id: int = Depends(_get_user_id)):
    """List version history from run snapshots."""
    runs = _store.list_runs(workflow_id, limit=50)
    return {"workflow_id": workflow_id, "versions": [
        {"run_id": r["id"], "status": r["status"], "started_at": r["started_at"]}
        for r in runs
    ], "count": len(runs)}


@router.post("/workflows/{workflow_id}/versions/{run_id}/restore")
def restore_workflow_version(workflow_id: str, run_id: str, user_id: int = Depends(_get_user_id)):
    """Restore a workflow to the state captured in a previous run."""
    run = _store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    wf = _store.get_workflow(workflow_id, user_id)
    if not wf or wf.is_locked:
        raise HTTPException(status_code=404 if not wf else 423, detail="Not found or locked")
    wf.nodes = run.snapshot_nodes
    wf.edges = run.snapshot_edges
    _store.save_workflow(wf)
    return {"status": "ok", "restored_from_run": run_id}

    return {"status": "ok", "restored_from_run": run_id}


# ── Internal helper ─────────────────────────────────────────────────────────

async def _execute_and_persist(
    run_id: str,
    nodes: list,
    edges: list,
    target_node_id: Optional[str] = None,
    progress_queue: Optional[asyncio.Queue] = None,
):
    """Run the engine and persist results to the DB."""
    try:
        node_results = await _engine.execute(
            nodes=nodes,
            edges=edges,
            target_node_id=target_node_id,
            progress_queue=progress_queue,
        )
        _store.save_node_results(run_id, node_results)

        # Determine overall status
        has_error = any(r.status == "error" for r in node_results.values())
        status = RunStatus.FAILED if has_error else RunStatus.COMPLETED
        _store.update_run_status(run_id, status)

        # Dashboard activity
        try:
            from src.api.dashboard_routes import log_activity
            done = sum(1 for r in node_results.values() if r.status == "done")
            log_activity(
                f"Workflow {run_id[:8]} {status.value}: {done}/{len(node_results)} nodes done",
            )
        except Exception:
            pass
    except asyncio.CancelledError:
        logger.warning("Workflow run %s cancelled", run_id)
        _store.update_run_status(run_id, RunStatus.CANCELLED)
    except Exception as e:
        logger.exception("Workflow run %s failed", run_id)
        _store.update_run_status(run_id, RunStatus.FAILED)
    finally:
        run = _store.get_run(run_id)
        if run and run.workflow_id:
            _running_workflows.pop(run.workflow_id, None)
            _store.unlock(run.workflow_id)
