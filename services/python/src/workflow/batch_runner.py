"""Batch workflow runner — execute the same workflow with different parameter sets.

Generates all parameter combinations from a grid, clones and executes each,
then compares results across runs.  Useful for parameter sensitivity analysis
and strategy optimisation.
"""

from __future__ import annotations

import asyncio
import copy
import itertools
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.workflow.schema import (
    NodeRunResult,
    RunStatus,
    WorkflowEdge,
    WorkflowModel,
    WorkflowNodeData,
    WorkflowRun,
)
from src.workflow.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


@dataclass
class BatchRunItem:
    """Result of a single batch run with its parameter overrides."""
    run_index: int
    params: Dict[str, Any]
    node_results: Dict[str, NodeRunResult] = field(default_factory=dict)
    status: RunStatus = RunStatus.PENDING
    error_message: str = ""
    duration_ms: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_index": self.run_index,
            "params": self.params,
            "status": self.status.value,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "metrics": self.metrics,
            "node_results": {k: v.to_dict() for k, v in self.node_results.items()},
        }


@dataclass
class BatchResult:
    """Aggregated result from a batch run of multiple parameter combinations."""
    batch_id: str = ""
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    runs: List[BatchRunItem] = field(default_factory=list)
    comparison: Dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "total_runs": self.total_runs,
            "completed_runs": self.completed_runs,
            "failed_runs": self.failed_runs,
            "runs": [r.to_dict() for r in self.runs],
            "comparison": self.comparison,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class BatchRunner:
    """Run the same workflow with different parameter sets and compare results.

    Usage::

        runner = BatchRunner()
        result = await runner.run_batch(
            base_workflow=workflow,
            param_grid={
                "alpha.zoo": ["alpha101", "gtja191"],
                "backtest.initial_capital": [500000, 1000000, 2000000],
            },
        )
        print(result.comparison)  # aggregated comparison metrics
    """

    def __init__(self, continue_on_error: bool = True):
        self._engine = WorkflowEngine(continue_on_error=continue_on_error)

    async def run_batch(
        self,
        base_workflow: WorkflowModel,
        param_grid: Dict[str, List[Any]],
        progress_queue: Optional[asyncio.Queue] = None,
    ) -> BatchResult:
        """Run the workflow for every combination of parameters in the grid.

        Args:
            base_workflow: The workflow template to clone for each run.
            param_grid: Keys are ``"node_id.config_key"`` paths, values are
                lists of values to try.  All combinations are generated via
                ``itertools.product``.
            progress_queue: Optional async queue for progress events.

        Returns:
            BatchResult with per-run results and comparison summary.
        """
        import uuid as _uuid

        batch_id = str(_uuid.uuid4())[:12]
        combos = self._generate_combinations(param_grid)
        total = len(combos)

        logger.info("Batch %s: %d parameter combinations", batch_id, total)

        result = BatchResult(
            batch_id=batch_id,
            total_runs=total,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        for idx, combo in enumerate(combos):
            item = BatchRunItem(run_index=idx, params=combo)
            result.runs.append(item)

            try:
                cloned = self._clone_workflow(base_workflow)
                self._apply_params(cloned, combo)

                engine = WorkflowEngine(continue_on_error=False)
                node_results = await engine.execute(
                    nodes=cloned.nodes,
                    edges=cloned.edges,
                    progress_queue=progress_queue,
                )

                item.node_results = node_results
                has_error = any(r.status.value == "error" for r in node_results.values())
                item.status = RunStatus.FAILED if has_error else RunStatus.COMPLETED
                item.metrics = self._extract_metrics(node_results)

                if item.status == RunStatus.COMPLETED:
                    result.completed_runs += 1
                else:
                    result.failed_runs += 1

                logger.info("Batch %s run %d/%d: %s", batch_id, idx + 1, total, item.status.value)

            except Exception as e:
                logger.exception("Batch %s run %d failed", batch_id, idx)
                item.status = RunStatus.FAILED
                item.error_message = str(e)
                result.failed_runs += 1

            # Progress event
            if progress_queue:
                try:
                    progress_queue.put_nowait({
                        "event": "batch_progress",
                        "data": {
                            "batch_id": batch_id,
                            "completed": idx + 1,
                            "total": total,
                            "status": item.status.value,
                        },
                    })
                except asyncio.QueueFull:
                    pass

        result.finished_at = datetime.now(timezone.utc).isoformat()
        result.comparison = self._build_comparison(result.runs)

        logger.info(
            "Batch %s finished: %d/%d succeeded",
            batch_id, result.completed_runs, total,
        )
        return result

    # ── Internal helpers ─────────────────────────────────────────────────

    @staticmethod
    def _generate_combinations(param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Generate all parameter combinations from the grid."""
        if not param_grid:
            return [{}]

        keys = list(param_grid.keys())
        value_lists = [param_grid[k] for k in keys]

        combos = []
        for values in itertools.product(*value_lists):
            combos.append(dict(zip(keys, values)))
        return combos

    @staticmethod
    def _clone_workflow(wf: WorkflowModel) -> WorkflowModel:
        """Deep-clone a workflow to avoid mutating the original."""
        return WorkflowModel(
            id=wf.id,
            project_id=wf.project_id,
            user_id=wf.user_id,
            name=wf.name,
            description=wf.description,
            nodes=[
                WorkflowNodeData(
                    id=n.id, node_type=n.node_type, label=n.label,
                    position=dict(n.position), config=dict(n.config),
                )
                for n in wf.nodes
            ],
            edges=[
                WorkflowEdge(
                    id=e.id, source=e.source, source_port=e.source_port,
                    target=e.target, target_port=e.target_port,
                )
                for e in wf.edges
            ],
            viewport=dict(wf.viewport),
            is_locked=wf.is_locked,
        )

    @staticmethod
    def _apply_params(wf: WorkflowModel, params: Dict[str, Any]) -> None:
        """Apply parameter overrides to a workflow.  Keys are ``node_id.config_key``."""
        node_map = {n.id: n for n in wf.nodes}
        for path, value in params.items():
            parts = path.split(".", 1)
            if len(parts) != 2:
                continue
            node_id, config_key = parts
            node = node_map.get(node_id)
            if node:
                node.config[config_key] = value

    @staticmethod
    def _extract_metrics(node_results: Dict[str, NodeRunResult]) -> Dict[str, Any]:
        """Pull key metrics from node results (backtest, attribution, etc.)."""
        metrics: Dict[str, Any] = {}
        for nid, result in node_results.items():
            if result.status.value != "done":
                continue
            summary = result.summary or {}
            # Backtest metrics
            if "backtest_result" in summary:
                bt = summary["backtest_result"]
                if isinstance(bt, dict):
                    for k in ("sharpe", "total_return", "annual_return", "max_drawdown", "win_rate"):
                        if k in bt:
                            metrics[f"bt_{k}"] = bt[k]
            # Attribution summary
            if "attribution_report" in summary:
                attr = summary["attribution_report"]
                if isinstance(attr, dict) and "summary" in attr:
                    for k, v in attr["summary"].items():
                        metrics[f"attr_{k}"] = v
            # Factor IC
            if "factor_result" in summary:
                fr = summary["factor_result"]
                if isinstance(fr, dict) and "ic_stats" in fr:
                    for k, v in fr["ic_stats"].items():
                        metrics[f"factor_{k}"] = v
        return metrics

    @staticmethod
    def _build_comparison(runs: List[BatchRunItem]) -> Dict[str, Any]:
        """Build a comparison summary across all completed runs."""
        completed = [r for r in runs if r.status == RunStatus.COMPLETED]
        if not completed:
            return {"error": "No completed runs to compare"}

        # Aggregate metrics
        all_metric_keys: set = set()
        for r in completed:
            all_metric_keys.update(r.metrics.keys())

        comparison: Dict[str, Any] = {
            "total_runs": len(runs),
            "completed": len(completed),
            "failed": len(runs) - len(completed),
            "metric_summary": {},
            "best_run": None,
        }

        metric_summary: Dict[str, Dict[str, Any]] = {}
        for key in sorted(all_metric_keys):
            values = [r.metrics[key] for r in completed if key in r.metrics]
            if not values:
                continue
            numeric = [v for v in values if isinstance(v, (int, float))]
            if numeric:
                metric_summary[key] = {
                    "min": round(min(numeric), 6),
                    "max": round(max(numeric), 6),
                    "mean": round(sum(numeric) / len(numeric), 6),
                    "count": len(numeric),
                }
            else:
                metric_summary[key] = {"values": values[:5], "count": len(values)}

        comparison["metric_summary"] = metric_summary

        # Find best run by Sharpe (if available)
        sharpe_key = next((k for k in all_metric_keys if k.endswith("sharpe")), None)
        if sharpe_key:
            best = max(completed, key=lambda r: r.metrics.get(sharpe_key, float("-inf")))
            comparison["best_run"] = {
                "run_index": best.run_index,
                "params": best.params,
                "sharpe": best.metrics.get(sharpe_key),
            }

        return comparison
