"""Concurrent workflow execution engine — Kahn + asyncio + Semaphore + ProcessPool.

CPU-bound nodes execute via ProcessPoolExecutor to avoid blocking the event loop.
I/O-bound nodes run on the async loop with per-resource-profile concurrency limits.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import logging
import os
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

# Shared process pool for CPU-bound node execution.
_CPU_POOL = concurrent.futures.ProcessPoolExecutor(
    max_workers=min(os.cpu_count() or 4, 8),
)


class WorkflowEngine:
    """Concurrent DAG execution engine.

    CPU-bound nodes run in a ProcessPoolExecutor to avoid blocking the asyncio
    event loop.  I/O-bound nodes run on the async loop with per-resource-profile
    semaphore limits.

    State is reset at the start of each :meth:`execute` call — the engine
    instance can be reused across multiple workflow runs.
    """

    def __init__(self, max_concurrency: int = 32, continue_on_error: bool = False,
                 default_timeout_seconds: float = 600):
        self._global_sem = Semaphore(max_concurrency)
        self._profile_sems_lock = asyncio.Lock()
        self._profile_sems: Dict[str, Semaphore] = {}
        self.continue_on_error = continue_on_error
        self.default_timeout = default_timeout_seconds
        self._registry = get_node_registry()

        # Per-run state — reset in execute()
        self._results: Dict[str, Dict[str, Any]] = {}
        self._node_status: Dict[str, NodeStatus] = {}
        self._edge_map: Dict[Tuple[str, str], Tuple[str, str]] = {}
        self._progress: Optional[asyncio.Queue] = None
        self._cancelled: bool = False
        self._running_tasks: Dict[str, Task] = {}

    def _reset(self):
        self._results.clear()
        self._node_status.clear()
        self._edge_map.clear()
        self._progress = None
        self._cancelled = False
        self._running_tasks.clear()

    def cancel(self):
        """Cancel all running tasks. Called from stop_workflow."""
        self._cancelled = True
        for t in self._running_tasks.values():
            if not t.done():
                t.cancel()

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

        while ready or self._running_tasks:
            if self._cancelled:
                for t in self._running_tasks.values():
                    if not t.done():
                        t.cancel()
                break

            for nid in ready:
                if nid not in self._running_tasks and nid in node_map:
                    self._running_tasks[nid] = create_task(
                        self._execute_with_limits(nid, node_map[nid]))
            ready.clear()
            if not self._running_tasks:
                break

            done, _ = await wait(
                self._running_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                nid = next((k for k, t in self._running_tasks.items() if t is task), None)
                if nid is None:
                    continue
                del self._running_tasks[nid]

                if self._node_status.get(nid) == NodeStatus.ERROR and not self.continue_on_error:
                    for t in self._running_tasks.values():
                        if not t.done():
                            t.cancel()
                    self._running_tasks.clear()
                    break

                for dnid in downstream.get(nid, []):
                    in_degree[dnid] -= 1
                    if in_degree[dnid] == 0:
                        ready.append(dnid)

        await self._emit("workflow_done", {
            "completed": sum(1 for s in self._node_status.values() if s == NodeStatus.DONE),
            "cancelled": self._cancelled,
        })

        return {nid: NodeRunResult(
            node_id=nid, status=status,
            summary=self._results.get(nid, {}).get("_summary", {}),
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
        # Use set of (source, target) pairs to avoid double-counting multi-port edges
        seen_pairs = set()
        for e in edges:
            if e.source in all_ids and e.target in all_ids:
                pair = (e.source, e.target)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
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
                    visited.add(p)
                    q.append(p)
        return visited

    async def _execute_with_limits(self, nid: str, node: WorkflowNodeData):
        profile = self._registry.get(node.node_type).resource_profile

        # Thread-safe profile semaphore init
        async with self._profile_sems_lock:
            if profile not in self._profile_sems:
                self._profile_sems[profile] = Semaphore(
                    RESOURCE_LIMITS.get(profile, 8))

        async with self._global_sem, self._profile_sems[profile]:
            await self._execute_node(node, self._gather_inputs(nid, node))

    async def _execute_node(self, node: WorkflowNodeData, inputs: dict):
        nid = node.id
        started = datetime.now(timezone.utc)
        self._node_status[nid] = NodeStatus.RUNNING
        await self._emit("node_start", {"node_id": nid, "node_type": node.node_type})

        impl = None  # scoped outside try for cancel handler access

        try:
            impl = self._registry.get_class(node.node_type)()
            profile = self._registry.get(node.node_type).resource_profile

            # Determine timeout: node class attribute > engine default
            timeout = getattr(impl, 'timeout_seconds', None) or self.default_timeout

            # Lifecycle: init + validate
            try:
                await impl.on_init(node.config)
                await impl.on_validate(inputs, node.config)
            except ValueError:
                raise
            except Exception as e:
                logger.warning("Node %s on_init/validate warning: %s", nid, e)

            # CPU-bound nodes run in ProcessPoolExecutor to avoid blocking
            if profile == "cpu_bound":
                outputs = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        _CPU_POOL, _run_cpu_node, node.node_type, inputs, node.config),
                    timeout=timeout)
            else:
                outputs = await asyncio.wait_for(
                    impl.execute(inputs, node.config),
                    timeout=timeout)

            # Cleanup (best-effort)
            try:
                await impl.on_cleanup()
            except Exception:
                pass

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
            await self._emit("node_done", {
                "node_id": nid, "node_type": node.node_type, "duration_ms": duration,
                "outputs_summary": summary})

        except asyncio.CancelledError:
            self._node_status[nid] = NodeStatus.ERROR
            self._results[nid] = {"_error": "Cancelled", "_summary": {}}
            try:
                if impl is not None:
                    await impl.on_cancel()
                    await impl.on_cleanup()
            except Exception:
                pass
            raise

        except asyncio.TimeoutError:
            logger.error("Node %s (%s) timed out after %.0fs", nid, node.node_type, timeout)
            self._node_status[nid] = NodeStatus.ERROR
            self._results[nid] = {"_error": f"Timeout after {timeout}s", "_summary": {}}
            await self._emit("node_error", {
                "node_id": nid,
                "error_message": f"Timeout after {timeout}s",
                "retryable": True})

        except Exception as e:
            logger.exception("Node %s failed", nid)
            self._node_status[nid] = NodeStatus.ERROR
            self._results[nid] = {"_error": str(e), "_summary": {}}
            await self._emit("node_error", {
                "node_id": nid, "error_message": str(e), "retryable": True})

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
                self._progress.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                pass  # Drop event if consumer is too slow
            except Exception:
                pass


# ── ProcessPool helper ──────────────────────────────────────────────────────

def _run_cpu_node(node_type: str, inputs: dict, config: dict) -> dict:
    """Run a CPU-bound node in a subprocess.  Re-imports the registry to get
    a fresh class instance in the child process."""
    from src.workflow.node_registry import get_node_registry
    registry = get_node_registry()
    impl = registry.get_class(node_type)()
    # asyncio.run is safe here because each child process has its own event loop
    return asyncio.run(impl.execute(inputs, config))
