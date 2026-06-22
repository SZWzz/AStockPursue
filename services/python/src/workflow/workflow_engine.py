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
    NodeRunResult, NodeStatus, WorkflowEdge, WorkflowNodeData,
)

logger = logging.getLogger(__name__)

RESOURCE_LIMITS = {"default": 8, "cpu_bound": 4, "io_bound": 16, "db_bound": 4}

# Lazy-initialised process pool for CPU-bound node execution.
# Initialised on first use to avoid creating a pool at module import time
# (which can cause issues in some ASGI server configurations where modules
# are imported in non-main threads).
_CPU_POOL: concurrent.futures.ProcessPoolExecutor | None = None
_CPU_POOL_LOCK = asyncio.Lock()


async def _get_cpu_pool() -> concurrent.futures.ProcessPoolExecutor:
    """Return the shared CPU process pool, creating it on first call.

    Uses double-checked locking with an asyncio.Lock to prevent
    multiple concurrent callers from creating duplicate pools.
    """
    global _CPU_POOL
    if _CPU_POOL is not None:
        return _CPU_POOL
    async with _CPU_POOL_LOCK:
        if _CPU_POOL is None:  # double-check under lock
            _CPU_POOL = concurrent.futures.ProcessPoolExecutor(
                max_workers=min(os.cpu_count() or 4, 8),
            )
        return _CPU_POOL


class WorkflowEngine:
    """Concurrent DAG execution engine.

    CPU-bound nodes run in a ProcessPoolExecutor to avoid blocking the asyncio
    event loop.  I/O-bound nodes run on the async loop with per-resource-profile
    semaphore limits.

    State is reset at the start of each :meth:`execute` call — the engine
    instance can be reused across multiple workflow runs.

    Debug mode:
        When ``debug_mode=True`` is passed to :meth:`execute`, the engine will
        pause before executing any node whose ID is in ``debug_node_ids``.
        It emits a ``node_breakpoint`` event and waits for a ``resume_node()``
        call before continuing.  This allows the frontend to step through
        execution and inspect intermediate results.
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

        # Node-level result cache — survives across execute() calls
        # cache_key → {outputs, node_type, config}
        self._node_cache: Dict[str, Dict[str, Any]] = {}

        # Debug mode state
        self._debug_mode: bool = False
        self._debug_node_ids: Optional[Set[str]] = None
        self._debug_events: Dict[str, asyncio.Event] = {}

    def _reset(self):
        self._results.clear()
        self._node_status.clear()
        self._edge_map.clear()
        self._progress = None
        self._cancelled = False
        self._running_tasks.clear()
        self._debug_mode = False
        self._debug_node_ids = None
        self._debug_events.clear()

    def clear_cache(self):
        """Clear the node result cache (e.g. when data sources change)."""
        self._node_cache.clear()
        logger.info("WorkflowEngine: node cache cleared")

    def cancel(self):
        """Cancel all running tasks. Called from stop_workflow."""
        self._cancelled = True
        for t in self._running_tasks.values():
            if not t.done():
                t.cancel()

    def resume_node(self, node_id: str):
        """Resume execution of a paused debug breakpoint.

        Called by the frontend (or API) after inspecting intermediate results.
        Sets the corresponding asyncio.Event so the waiting coroutine can
        proceed with node execution.
        """
        event = self._debug_events.get(node_id)
        if event is not None:
            event.set()
            logger.debug("WorkflowEngine: resumed node %s", node_id)
        else:
            logger.warning("WorkflowEngine: resume_node(%s) called but no pending event", node_id)

    # ── Public API ──────────────────────────────────────────────────────────

    async def execute(
        self, nodes: List[WorkflowNodeData], edges: List[WorkflowEdge],
        target_node_id: Optional[str] = None, progress_queue: Optional[asyncio.Queue] = None,
        debug_mode: bool = False, debug_node_ids: Optional[Set[str]] = None,
    ) -> Dict[str, NodeRunResult]:
        self._reset()
        self._progress = progress_queue

        # Debug mode setup
        self._debug_mode = debug_mode
        self._debug_node_ids = debug_node_ids or set()
        if debug_mode and self._debug_node_ids:
            logger.info("WorkflowEngine: debug mode enabled, breakpoints at %s", self._debug_node_ids)
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

    async def replay_run(
        self,
        run_id: str,
        target_node_id: Optional[str] = None,
    ) -> Dict[str, NodeRunResult]:
        """Re-execute a workflow from a stored run snapshot.

        Loads the WorkflowRun from the DB, re-runs the captured DAG
        (snapshot_nodes / snapshot_edges), and optionally stops at
        *target_node_id*.  Results are returned but NOT persisted —
        use the normal execute() path for durable runs.
        """
        from src.workflow.workflow_store import WorkflowStore

        store = WorkflowStore()
        run = store.get_run(run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")

        nodes = run.snapshot_nodes
        edges = run.snapshot_edges
        if not nodes:
            raise ValueError(f"Run {run_id} has no snapshot nodes")

        logger.info("Replay: run=%s, nodes=%d, target=%s", run_id, len(nodes), target_node_id)
        return await self.execute(
            nodes=nodes,
            edges=edges,
            target_node_id=target_node_id,
        )

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
        # ── Check cache ──────────────────────────────────────────────────
        inputs = self._gather_inputs(nid, node)
        cache_key = self._compute_cache_key(nid, node, inputs)

        if cache_key in self._node_cache:
            cached = self._node_cache[cache_key]
            # Verify input hashes still match
            current_input_hash = self._hash_inputs(inputs)
            if current_input_hash == cached.get("_input_hash", ""):
                self._results[nid] = {k: v for k, v in cached.items()
                                       if not k.startswith("_")}
                self._results[nid]["_summary"] = cached.get("_summary", {})
                self._results[nid]["_duration_ms"] = 0  # cached
                self._node_status[nid] = NodeStatus.CACHED
                await self._emit("node_cached", {
                    "node_id": nid,
                    "node_type": node.node_type,
                })
                logger.debug("Cache HIT: %s (%s)", nid, node.node_type)
                return

        profile = self._registry.get(node.node_type).resource_profile

        # Thread-safe profile semaphore init
        async with self._profile_sems_lock:
            if profile not in self._profile_sems:
                self._profile_sems[profile] = Semaphore(
                    RESOURCE_LIMITS.get(profile, 8))

        async with self._global_sem, self._profile_sems[profile]:
            await self._execute_node(node, inputs)

        # ── Store in cache after successful execution ────────────────────
        if self._node_status.get(nid) == NodeStatus.DONE:
            self._node_cache[cache_key] = {
                "_input_hash": self._hash_inputs(inputs),
                "_summary": self._results.get(nid, {}).get("_summary", {}),
                **{k: v for k, v in self._results.get(nid, {}).items()
                    if not k.startswith("_")},
            }
            logger.debug("Cache SET: %s (%s)", nid, node.node_type)

    async def _execute_node(self, node: WorkflowNodeData, inputs: dict):
        nid = node.id
        started = datetime.now(timezone.utc)
        self._node_status[nid] = NodeStatus.RUNNING
        await self._emit("node_start", {"node_id": nid, "node_type": node.node_type})

        # ── Debug breakpoint check ──────────────────────────────────────
        if self._debug_mode and nid in self._debug_node_ids:
            await self._handle_breakpoint(nid, node, inputs)

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
            except (TypeError, AttributeError, KeyError, RuntimeError) as e:
                logger.warning("Node %s on_init/validate warning: %s", nid, e)

            # CPU-bound nodes run in ProcessPoolExecutor to avoid blocking
            if profile == "cpu_bound":
                cpu_pool = await _get_cpu_pool()
                outputs = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        cpu_pool, _run_cpu_node, node.node_type, inputs, node.config),
                    timeout=timeout)
            else:
                outputs = await asyncio.wait_for(
                    impl.execute(inputs, node.config),
                    timeout=timeout)

            # Cleanup (best-effort)
            try:
                await impl.on_cleanup()
            except (RuntimeError, TypeError, AttributeError, OSError):
                pass

            # Build summary from outputs — prefer node-provided _summary
            if "_summary" in outputs and isinstance(outputs["_summary"], dict):
                summary = dict(outputs["_summary"])
                outputs = {k: v for k, v in outputs.items() if k != "_summary"}
            else:
                summary = {}
                for k, v in outputs.items():
                    if isinstance(v, pd.DataFrame):
                        summary[k] = {"type": "DataFrame", "shape": list(v.shape)}
                    elif isinstance(v, dict) and not isinstance(v, pd.DataFrame):
                        summary[k] = {sk: sv for sk, sv in list(v.items())[:5] if not isinstance(sv, (pd.DataFrame, dict))}

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
            except (RuntimeError, TypeError, AttributeError, OSError):
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

        except (ValueError, TypeError, KeyError, RuntimeError, AttributeError, IndexError, ZeroDivisionError,
                     concurrent.futures.TimeoutError) as e:
            logger.exception("Node %s failed", nid)
            self._node_status[nid] = NodeStatus.ERROR
            self._results[nid] = {"_error": str(e), "_summary": {}}
            await self._emit("node_error", {
                "node_id": nid, "error_message": str(e), "retryable": True})

    async def _handle_breakpoint(self, nid: str, node: WorkflowNodeData, inputs: dict):
        """Pause execution at a debug breakpoint and wait for resume signal.

        Emits a ``node_breakpoint`` event containing the node's current
        state (id, type, inputs, upstream results) so the frontend can
        display an inspection panel.  Then blocks on an asyncio.Event
        until :meth:`resume_node` is called for this node.
        """
        # Snapshot upstream results for inspection
        upstream_results = {}
        for port_name, value in inputs.items():
            if isinstance(value, pd.DataFrame):
                upstream_results[port_name] = {"type": "DataFrame", "shape": list(value.shape)}
            elif isinstance(value, dict):
                upstream_results[port_name] = {k: v for k, v in list(value.items())[:10]
                                                if not isinstance(v, pd.DataFrame)}
            else:
                upstream_results[port_name] = value

        event = asyncio.Event()
        self._debug_events[nid] = event

        await self._emit("node_breakpoint", {
            "node_id": nid,
            "node_type": node.node_type,
            "node_label": node.label,
            "config": node.config,
            "inputs": upstream_results,
        })

        logger.debug("WorkflowEngine: breakpoint hit at node %s (%s), waiting for resume...",
                      nid, node.node_type)

        # Block until resume_node(nid) is called
        await event.wait()

        # Clean up the event
        self._debug_events.pop(nid, None)
        logger.debug("WorkflowEngine: resumed from breakpoint at node %s", nid)

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

    # ── Cache helpers ──────────────────────────────────────────────────

    def _compute_cache_key(
        self, nid: str, node: WorkflowNodeData, inputs: dict,
    ) -> str:
        """Build a stable cache key from node identity and inputs."""
        try:
            definition = self._registry.get(node.node_type)
            # Include node_type + config + version
            config_str = json.dumps(node.config, sort_keys=True, default=str)
            version = definition.node_type  # Use node_type as version proxy
            key_material = f"{node.node_type}|v{getattr(definition, 'version', 1)}|{config_str}|{self._hash_inputs(inputs)}"
            return hashlib.sha256(key_material.encode()).hexdigest()[:32]
        except Exception:
            # Fallback: unique-per-run key (effectively no cache)
            return f"nocache_{nid}_{datetime.now(timezone.utc).timestamp()}"

    @staticmethod
    def _hash_inputs(inputs: dict) -> str:
        """Compute a stable hash of node input values."""
        if not inputs:
            return "empty"
        try:
            parts = []
            for k in sorted(inputs.keys()):
                v = inputs[k]
                if isinstance(v, pd.DataFrame):
                    # Hash shape + first/last row for stability
                    h = hashlib.sha256()
                    h.update(str(v.shape).encode())
                    if not v.empty:
                        h.update(str(v.index[0]).encode())
                        h.update(str(v.index[-1]).encode())
                        h.update(str(v.iloc[0].values[:5]).encode())
                        h.update(str(v.iloc[-1].values[:5]).encode())
                    parts.append(f"{k}:{h.hexdigest()[:16]}")
                elif isinstance(v, dict):
                    h = hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode())
                    parts.append(f"{k}:{h.hexdigest()[:16]}")
                elif isinstance(v, (list, tuple)):
                    h = hashlib.sha256(str(v).encode())
                    parts.append(f"{k}:{h.hexdigest()[:16]}")
                else:
                    parts.append(f"{k}:{str(v)[:100]}")
            return "|".join(parts)
        except Exception:
            return "hash_error"

    async def _emit(self, event: str, data: dict):
        if self._progress:
            try:
                self._progress.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                pass  # Drop event if consumer is too slow
            except (RuntimeError, TypeError, AttributeError):
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
