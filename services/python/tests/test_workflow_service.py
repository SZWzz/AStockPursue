"""Tests for WorkflowService gRPC servicer."""
from src.gen import workflow_pb2
from src.grpc.workflow_service import WorkflowServiceServicer


class TestWorkflowService:
    def test_execute_workflow_not_found(self):
        servicer = WorkflowServiceServicer()
        req = workflow_pb2.WorkflowRequest(
            workflow_id="nonexistent",
            params={},
        )
        resp = servicer.ExecuteWorkflow(req, None)
        assert resp.error != "" or resp.status == "error"

    def test_get_node_result_not_found(self):
        servicer = WorkflowServiceServicer()
        req = workflow_pb2.NodeQuery(
            workflow_id="nonexistent",
            node_id="nonexistent",
        )
        resp = servicer.GetNodeResult(req, None)
        assert resp.error != ""
