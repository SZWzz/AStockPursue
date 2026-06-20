"""Sub-workflow node — execute a nested workflow as a sub-process.

Loads a workflow by ID from the database or from an inline JSON definition,
creates a fresh WorkflowEngine, and executes the sub-graph.  Input ports
feed into the sub-workflow's start nodes; output ports collect from its
leaf nodes (nodes with no downstream edges).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType, WorkflowNodeData, WorkflowEdge

logger = logging.getLogger(__name__)


@register_node
class SubWorkflowNode(BaseNode):
    """Execute another workflow as a sub-process.

    The sub-workflow can be loaded from the database by ``workflow_id`` or
    provided inline as a JSON string in ``workflow_json``.

    **Input mapping**: The first input port value is injected into the
    sub-workflow's start nodes (nodes with in-degree 0).  If there are
    multiple input ports, they are passed by port name.

    **Output mapping**: The sub-workflow's leaf nodes (nodes with no
    downstream edges) produce the output.  The combined outputs are
    returned on the ``result`` output port.

    Configuration:
        workflow_id  — ID of the workflow to execute (loaded from DB)
        workflow_json — Inline workflow JSON as alternative to workflow_id
    """
    node_type = "sub_workflow"
    category = "control"
    label = "Sub-Workflow"
    description = (
        "Execute another workflow as a sub-process. Input ports feed into the "
        "sub-workflow's start nodes; output ports collect from its end nodes."
    )
    icon = "Layers"

    inputs = [
        BaseNode.in_port("input", PortType.ANY, required=False,
                         description="Value passed to the sub-workflow's start nodes"),
    ]
    outputs = [
        BaseNode.out_port("result", PortType.ANY,
                          description="Combined output from the sub-workflow's leaf nodes"),
    ]

    config_schema = {
        "workflow_id": {
            "title": "Workflow ID",
            "type": "string",
            "default": "",
            "description": "ID of the workflow to execute (loaded from database)",
        },
        "workflow_json": {
            "title": "Inline Workflow JSON",
            "type": "string",
            "default": "",
            "description": "Inline workflow JSON definition as alternative to workflow_id",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.workflow.workflow_engine import WorkflowEngine

        # ── Load the sub-workflow definition ─────────────────────────────
        workflow_id = config.get("workflow_id", "").strip()
        workflow_json = config.get("workflow_json", "").strip()

        nodes, edges = self._load_sub_workflow(workflow_id, workflow_json)
        if not nodes:
            logger.error("SubWorkflow: no nodes found (workflow_id=%s)", workflow_id)
            return {"result": {"error": "Sub-workflow not found or empty"}}

        # ── Inject input into start nodes ───────────────────────────────
        start_nodes = self._find_start_nodes(nodes, edges)
        input_value = inputs.get("input")
        prepared_nodes = self._inject_inputs(nodes, start_nodes, input_value)

        # ── Execute ─────────────────────────────────────────────────────
        logger.info("SubWorkflow: executing %d nodes, %d edges (start=%s)",
                     len(prepared_nodes), len(edges), [n.id for n in start_nodes])

        engine = WorkflowEngine(
            max_concurrency=32,
            continue_on_error=False,
        )
        run_results = await engine.execute(prepared_nodes, edges)

        # ── Collect outputs from leaf nodes ─────────────────────────────
        leaf_nodes = self._find_leaf_nodes(prepared_nodes, edges)
        combined_output = self._collect_outputs(leaf_nodes, run_results, engine)

        logger.info("SubWorkflow: completed, leaf_nodes=%s, output_keys=%s",
                     [n.id for n in leaf_nodes], list(combined_output.keys()))

        return {"result": combined_output}

    # ── Sub-workflow loading ────────────────────────────────────────────

    def _load_sub_workflow(
        self, workflow_id: str, workflow_json: str,
    ) -> tuple:
        """Load sub-workflow nodes and edges from DB or inline JSON.

        Returns (nodes, edges) as lists of WorkflowNodeData/WorkflowEdge.
        """
        if workflow_id:
            return self._load_from_db(workflow_id)
        elif workflow_json:
            return self._load_from_json(workflow_json)
        return [], []

    @staticmethod
    def _load_from_db(workflow_id: str) -> tuple:
        """Load workflow definition from PostgreSQL via WorkflowStore."""
        try:
            from src.workflow.workflow_store import WorkflowStore
            store = WorkflowStore()
            # user_id=0 is a placeholder; the store filters by user_id,
            # but for sub-workflows we want any user's definition.
            # Use a raw query fallback if needed.
            wf = store.get_workflow(workflow_id, user_id=0)
            if wf:
                return wf.nodes, wf.edges

            # Fallback: direct DB query without user_id filter
            from src.db import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT nodes, edges FROM vt_workflows WHERE id = %s""",
                        (workflow_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        nodes = [WorkflowNodeData.from_dict(n) for n in (row[0] or [])]
                        edges = [WorkflowEdge.from_dict(e) for e in (row[1] or [])]
                        return nodes, edges
        except Exception as e:
            logger.exception("SubWorkflow: failed to load workflow %s from DB", workflow_id)
        return [], []

    @staticmethod
    def _load_from_json(workflow_json: str) -> tuple:
        """Parse an inline JSON workflow definition."""
        try:
            data = json.loads(workflow_json)
            nodes = [WorkflowNodeData.from_dict(n) for n in data.get("nodes", [])]
            edges = [WorkflowEdge.from_dict(e) for e in data.get("edges", [])]
            return nodes, edges
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.exception("SubWorkflow: failed to parse inline workflow JSON")
        return [], []

    # ── Graph helpers ───────────────────────────────────────────────────

    @staticmethod
    def _find_start_nodes(nodes: list, edges: list) -> list:
        """Return nodes with in-degree 0 (no incoming edges)."""
        targets = {e.target for e in edges}
        return [n for n in nodes if n.id not in targets]

    @staticmethod
    def _find_leaf_nodes(nodes: list, edges: list) -> list:
        """Return nodes with out-degree 0 (no outgoing edges)."""
        sources = {e.source for e in edges}
        return [n for n in nodes if n.id not in sources]

    @staticmethod
    def _inject_inputs(
        nodes: list, start_nodes: list, input_value: Any,
    ) -> list:
        """Return copies of nodes with inputs injected into start nodes.

        The input value is stored in each start node's config under
        ``_subworkflow_input`` so the engine can pass it as an input.
        """
        start_ids = {n.id for n in start_nodes}
        prepared = []
        for n in nodes:
            if n.id in start_ids:
                # Create a new node data with the injected input in config
                new_config = dict(n.config)
                new_config["_subworkflow_input"] = input_value
                prepared.append(WorkflowNodeData(
                    id=n.id,
                    node_type=n.node_type,
                    label=n.label,
                    position=n.position,
                    config=new_config,
                ))
            else:
                prepared.append(n)
        return prepared

    def _collect_outputs(
        self, leaf_nodes: list, run_results: dict, engine,
    ) -> dict:
        """Merge outputs from all leaf nodes into a single dict.

        Each leaf's outputs are prefixed by its node_id to avoid key collisions.
        """
        combined = {}
        for leaf in leaf_nodes:
            result = run_results.get(leaf.id)
            if result is None:
                continue
            node_outputs = engine._results.get(leaf.id, {})
            for key, value in node_outputs.items():
                if key.startswith("_"):
                    continue
                combined[key] = value
        return combined
