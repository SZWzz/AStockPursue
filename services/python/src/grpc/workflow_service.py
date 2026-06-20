"""gRPC WorkflowService — workflow execution and node result queries.

Wraps the workflow engine and store behind protobuf contracts.
"""
from __future__ import annotations

import asyncio
import json
import logging

import grpc

from src.gen import workflow_pb2, workflow_pb2_grpc

logger = logging.getLogger(__name__)


def _get_user_id(context: grpc.ServicerContext | None) -> int:
    """Extract user_id from gRPC metadata, defaulting to 0."""
    if context is None:
        return 0
    metadata = dict(context.invocation_metadata() or ())
    raw = metadata.get("x-user-id", "0")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 0


class WorkflowServiceServicer(workflow_pb2_grpc.WorkflowServiceServicer):
    """gRPC implementation of WorkflowService.

    Provides DAG execution and node-result retrieval via protobuf contracts.
    """

    def ExecuteWorkflow(self, request, context):
        """Execute a workflow DAG by ID."""
        workflow_id = request.workflow_id
        params = dict(request.params) if request.params else {}

        if not workflow_id:
            return workflow_pb2.WorkflowResponse(status="error", error="workflow_id required")

        try:
            from src.workflow.workflow_store import WorkflowStore
            from src.workflow.workflow_engine import WorkflowEngine

            user_id = _get_user_id(context)
            store = WorkflowStore()
            wf = store.get_workflow(workflow_id, user_id)
            if wf is None:
                return workflow_pb2.WorkflowResponse(
                    status="error", error=f"workflow {workflow_id} not found"
                )

            engine = WorkflowEngine()
            # Apply params to nodes
            if params:
                for node in getattr(wf, "nodes", []):
                    node_id = node.id if hasattr(node, "id") else None
                    if node_id and node_id in params:
                        config = getattr(node, "config", {}) or {}
                        param_value = params[node_id]
                        if isinstance(param_value, str):
                            try:
                                param_value = json.loads(param_value)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        node.config = {**config, **param_value} if isinstance(param_value, dict) else param_value

            # Bridge async execute into the sync gRPC handler
            result = asyncio.run(engine.execute(
                nodes=getattr(wf, "nodes", []),
                edges=getattr(wf, "edges", []),
            ))
            return workflow_pb2.WorkflowResponse(
                status="completed" if all(
                    r.status.value == "done" for r in result.values()
                ) else "partial",
                error="",
            )

        except Exception as e:
            logger.exception("Workflow execution failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return workflow_pb2.WorkflowResponse(status="error", error=str(e))

    def GetNodeResult(self, request, context):
        """Get the result of a specific node in a workflow run."""
        workflow_id = request.workflow_id
        node_id = request.node_id

        if not workflow_id or not node_id:
            return workflow_pb2.NodeResult(
                node_id=node_id or "", output=b"", error="workflow_id and node_id required"
            )

        try:
            from src.workflow.workflow_store import WorkflowStore

            store = WorkflowStore()
            run = store.get_run(workflow_id)
            if run is None:
                return workflow_pb2.NodeResult(
                    node_id=node_id, output=b"", error=f"run {workflow_id} not found"
                )

            node_results = getattr(run, "node_results", {})
            result = node_results.get(node_id)
            if result is None:
                return workflow_pb2.NodeResult(
                    node_id=node_id, output=b"", error=f"node {node_id} result not found"
                )

            output_bytes = json.dumps(result.to_dict() if hasattr(result, "to_dict") else result).encode("utf-8")
            return workflow_pb2.NodeResult(node_id=node_id, output=output_bytes, error="")

        except Exception as e:
            logger.exception("GetNodeResult failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return workflow_pb2.NodeResult(node_id=node_id, output=b"", error=str(e))
