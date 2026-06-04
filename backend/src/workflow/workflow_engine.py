"""Concurrent workflow execution engine — Kahn + asyncio + Semaphore.

Nodes pass data directly in memory (no serialization).  Each call to execute()
starts with clean state.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from asyncio import Semaphore, Task, create_task, wait
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from src.workflow.node_registry import get_node_registry
from src.workflow.schema import (
    NodeRunResult, NodeStatus, RunStatus, WorkflowEdge, WorkflowNodeData,
)

logger = logging.getLogger(__name__)

RESOURCE_LIMITS = {"default": 8, "cpu_bound": 4, "io_bound": 16, "db_bound": 4}


class WorkflowEngine:
    """Concurrent DAG execution engine.

    State is reset at the start of each :meth:`execute` call — the engine
    instance can be reused across multiple workflow runs.
    """

    def __init__(self, max_concurrency: int = 32, continue_on_error: bool = False):
        self._global_sem = Semaphore(max_concurrency)
        self._profile_sems: Dict[str, Semaphore] = {}
        self.continue_on_error = continue_on_error
        self._registry = get_node_registry()

        # Per-run state — reset in execute()
        self._results: Dict[str, Dict[str, Any]] = {}
        self._node_status: Dict[str, NodeStatus] = {}
        self._edge_map: Dict[Tuple[str, str], Tuple[str, str]] = {}
        self._progress: Optional[asyncio.Queue] = None

    def _reset(self):
        self._results.clear()
        self._node_status.clear()
        self._edge_map.clear()
        self._progress = None

    # ── Public API ──────────────────────────────────────────────────────────

    async def execute(
        self, nodes: List[WorkflowNodeData], edges: List[WorkflowEdge],
        target_node_id: Optional[str] = None, progress_queue: Optional[asyncio.Queue] = None,
    ) -> Dict[str, NodeRunResult]:
        self._reset()
        self._progress = progress_queue
        self._node_status = {n.id: NodeStatus.PENDING for n in nodes}
        self._edge_map = {(e.target, e.target_port): (e.source, e.source_port) for e in edges}

        node_map = {n.id: n for n in nodes}
        in_degree, downstream = self._build_dep_graph(nodes, edges, target_node_id)
        ready = [nid for nid, deg in in_degree.items() if deg == 0]
        running_tasks: Dict[str, Task] = {}

        while ready or running_tasks:
            for nid in ready:
                if nid not in running_tasks and nid in node_map:
                    running_tasks[nid] = create_task(self._execute_with_limits(nid, node_map[nid]))
            ready.clear()
            if not running_tasks:
                break

            done, _ = await wait(running_tasks.values(), return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                nid = next((k for k, t in running_tasks.items() if t is task), None)
                if nid is None:
                    continue
                del running_tasks[nid]

                if self._node_status.get(nid) == NodeStatus.ERROR and not self.continue_on_error:
                    for t in running_tasks.values():
                        t.cancel()
                    running_tasks.clear()
                    break

                for dnid in downstream.get(nid, []):
                    in_degree[dnid] -= 1
                    if in_degree[dnid] == 0:
                        ready.append(dnid)

        await self._emit("workflow_done", {"completed": sum(1 for s in self._node_status.values() if s == NodeStatus.DONE)})

        return {nid: NodeRunResult(
            node_id=nid, status=status, summary=self._results.get(nid, {}).get("_summary", {}),
            error_message=self._results.get(nid, {}).get("_error", ""),
            duration_ms=self._results.get(nid, {}).get("_duration_ms", 0),
        ) for nid, status in self._node_status.items()}

    async def execute_single_node(self, node: WorkflowNodeData, inputs: dict) -> dict:
        self._reset()
        self._node_status = {node.id: NodeStatus.PENDING}
        await self._execute_node(node, inputs)
        return self._results.get(node.id, {})

    # ── Internal ────────────────────────────────────────────────────────────

    def _build_dep_graph(self, nodes, edges, target=None):
        all_ids = {n.id for n in nodes}
        in_degree = {n.id: 0 for n in nodes}
        downstream: Dict[str, Set[str]] = {n.id: set() for n in nodes}
        for e in edges:
            if e.source in all_ids and e.target in all_ids:
                in_degree[e.target] += 1
                downstream.setdefault(e.source, set()).add(e.target)
        if target:
            ancestors = self._ancestors(edges, target)
            in_degree = {k: v for k, v in in_degree.items() if k in ancestors}
            downstream = {k: (v & ancestors) for k, v in downstream.items() if k in ancestors}
        return in_degree, downstream

    @staticmethod
    def _ancestors(edges, target: str) -> Set[str]:
        rev: Dict[str, Set[str]] = {}
        for e in edges:
            rev.setdefault(e.target, set()).add(e.source)
        visited, q = {target}, [target]
        while q:
            for p in rev.get(q.pop(0), set()):
                if p not in visited:
                    visited.add(p); q.append(p)
        return visited

    async def _execute_with_limits(self, nid: str, node: WorkflowNodeData):
        profile = self._registry.get(node.node_type).resource_profile
        if profile not in self._profile_sems:
            self._profile_sems[profile] = Semaphore(RESOURCE_LIMITS.get(profile, 8))
        async with self._global_sem, self._profile_sems[profile]:
            await self._execute_node(node, self._gather_inputs(nid, node))

    async def _execute_node(self, node: WorkflowNodeData, inputs: dict):
        nid = node.id
        started = datetime.now(timezone.utc)
        self._node_status[nid] = NodeStatus.RUNNING
        await self._emit("node_start", {"node_id": nid, "node_type": node.node_type})

        try:
            impl = self._registry.get_class(node.node_type)()
            outputs = await impl.execute(inputs, node.config)

            # Build summary from outputs
            summary = {}
            for k, v in outputs.items():
                if isinstance(v, pd.DataFrame):
                    summary[k] = {"type": "DataFrame", "shape": list(v.shape)}
                elif isinstance(v, dict) and not isinstance(v, pd.DataFrame):
                    summary[k] = {sk: sv for sk, sv in list(v.items())[:5]}

            finished = datetime.now(timezone.utc)
            duration = int((finished - started).total_seconds() * 1000)
            self._results[nid] = {"_summary": summary, "_duration_ms": duration, **outputs}
            self._node_status[nid] = NodeStatus.DONE
            await self._emit("node_done", {"node_id": nid, "duration_ms": duration, "outputs_summary": summary})

        except asyncio.CancelledError:
            self._node_status[nid] = NodeStatus.ERROR
            raise
        except Exception as e:
            logger.exception("Node %s failed", nid)
            self._node_status[nid] = NodeStatus.ERROR
            self._results[nid] = {"_error": str(e), "_summary": {}}
            await self._emit("node_error", {"node_id": nid, "error_message": str(e), "retryable": True})

    def _gather_inputs(self, nid: str, node: WorkflowNodeData) -> dict:
        definition = self._registry.get(node.node_type)
        inputs = {}
        for port in definition.inputs:
            upstream = self._edge_map.get((nid, port.name))
            if upstream:
                uid, uport = upstream
                value = self._results.get(uid, {}).get(uport)
                if value is not None:
                    inputs[port.name] = value
        return inputs

    async def _emit(self, event: str, data: dict):
        if self._progress:
            try:
                await self._progress.put({"event": event, "data": data})
            except Exception:
                pass
