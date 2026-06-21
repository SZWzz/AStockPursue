"""Tests for workflow schema models."""

from src.workflow.schema import (
    NodePort, PortDirection, PortType, NodeDefinition,
    WorkflowEdge, WorkflowNodeData, WorkflowRun, NodeRunResult,
    NodeStatus, RunStatus,
)


class TestNodePort:
    def test_create(self):
        p = NodePort(name="data", port_type=PortType.DF_OHLCV, direction=PortDirection.INPUT)
        assert p.name == "data" and p.required is True

    def test_roundtrip(self):
        p = NodePort(name="x", port_type=PortType.SIGNAL, direction=PortDirection.OUTPUT, required=False)
        d = p.to_dict()
        r = NodePort.from_dict(d)
        assert r.name == p.name and r.port_type == p.port_type

    def test_from_json_style(self):
        d = {"name": "x", "port_type": "df_ohlcv", "direction": "input", "required": True, "description": ""}
        p = NodePort.from_dict(d)
        assert p.direction == PortDirection.INPUT


class TestNodeDefinition:
    def test_create(self):
        d = NodeDefinition(node_type="test", category="data", label="Test", inputs=[NodePort(name="in", port_type=PortType.ANY, direction=PortDirection.INPUT)])
        assert d.to_dict()["node_type"] == "test"


class TestWorkflowNodeData:
    def test_roundtrip(self):
        n = WorkflowNodeData(id="n1", node_type="compute", label="Test", config={"k": "v"})
        d = n.to_dict()
        r = WorkflowNodeData.from_dict(d)
        assert r.id == n.id and r.node_type == n.node_type


class TestWorkflowEdge:
    def test_roundtrip(self):
        e = WorkflowEdge(id="e1", source="a", source_port="x", target="b", target_port="y")
        d = e.to_dict()
        r = WorkflowEdge.from_dict(d)
        assert r.source == "a" and r.target == "b"


class TestNodeRunResult:
    def test_roundtrip(self):
        r = NodeRunResult(node_id="n1", status=NodeStatus.DONE, duration_ms=100, summary={"k": "v"})
        d = r.to_dict()
        r2 = NodeRunResult.from_dict(d)
        assert r2.status == NodeStatus.DONE and r2.duration_ms == 100


class TestWorkflowRun:
    def test_roundtrip(self):
        r = WorkflowRun(workflow_id="w1", user_id=1, status=RunStatus.PENDING, snapshot_nodes=[], snapshot_edges=[])
        d = r.to_dict()
        r2 = WorkflowRun.from_dict(d)
        assert r2.workflow_id == "w1"
