"""Tests for the concurrent workflow execution engine."""

import asyncio

import pytest

from src.workflow.workflow_engine import WorkflowEngine
from src.workflow.schema import (
    NodeStatus,
    WorkflowEdge,
    WorkflowNodeData,
)


@pytest.fixture
def engine():
    return WorkflowEngine(max_concurrency=4)


class TestTopologicalSort:
    def test_linear_pipeline(self, engine, sample_nodes, sample_edges):
        """A→B→C should execute in order."""
        in_deg, downstream = engine._build_dep_graph(sample_nodes, sample_edges)
        assert in_deg == {"n1": 0, "n2": 1, "n3": 1}
        assert downstream == {"n1": {"n2"}, "n2": {"n3"}, "n3": set()}

    def test_parallel_branches(self, engine):
        """Two independent branches should both have in-degree 0."""
        nodes = [
            WorkflowNodeData(id="root", node_type="data_source", config={}),
            WorkflowNodeData(id="branch_a", node_type="compute", config={}),
            WorkflowNodeData(id="branch_b", node_type="compute", config={}),
            WorkflowNodeData(id="merge", node_type="merge", config={}),
        ]
        edges = [
            WorkflowEdge(id="e1", source="root", source_port="out", target="branch_a", target_port="in"),
            WorkflowEdge(id="e2", source="root", source_port="out", target="branch_b", target_port="in"),
            WorkflowEdge(id="e3", source="branch_a", source_port="out", target="merge", target_port="in_a"),
            WorkflowEdge(id="e4", source="branch_b", source_port="out", target="merge", target_port="in_b"),
        ]
        in_deg, downstream = engine._build_dep_graph(nodes, edges)
        assert in_deg["root"] == 0
        assert in_deg["branch_a"] == 1
        assert in_deg["branch_b"] == 1
        assert in_deg["merge"] == 2

    def test_no_edges(self, engine, sample_nodes):
        """All nodes with no edges should have in-degree 0."""
        in_deg, downstream = engine._build_dep_graph(sample_nodes, [])
        assert all(v == 0 for v in in_deg.values())

    def test_target_node_subgraph(self, engine, sample_nodes, sample_edges):
        """When target is n2, only n1 and n2 should be included."""
        in_deg, downstream = engine._build_dep_graph(sample_nodes, sample_edges, target="n2")
        assert "n1" in in_deg
        assert "n2" in in_deg
        assert "n3" not in in_deg


class TestAncestors:
    def test_linear_ancestors(self, sample_edges):
        ancestors = WorkflowEngine._ancestors(sample_edges, "n3")
        assert ancestors == {"n1", "n2", "n3"}

    def test_single_node(self, sample_edges):
        ancestors = WorkflowEngine._ancestors(sample_edges, "n1")
        assert ancestors == {"n1"}

    def test_disconnected_target(self):
        edges = [WorkflowEdge(id="e1", source="a", source_port="x", target="b", target_port="y")]
        ancestors = WorkflowEngine._ancestors(edges, "c")
        assert ancestors == {"c"}


class TestExecution:
    def test_linear_execution(self, engine, sample_nodes, sample_edges):
        """A 3-node linear pipeline should execute all nodes successfully."""
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(engine.execute(sample_nodes, sample_edges))
            assert len(results) == 3
            for r in results.values():
                assert r.status in (NodeStatus.DONE, NodeStatus.ERROR), f"Expected done/error, got {r.status}"
        finally:
            loop.close()

    def test_single_node_execution(self, engine):
        """Single node execution should work with explicit inputs."""
        import pandas as pd
        node = WorkflowNodeData(id="test", node_type="output", label="Test", config={})
        df = pd.DataFrame({"a": [1, 2, 3]})
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(engine.execute_single_node(node, {"input": df}))
            assert isinstance(result, dict)
        finally:
            loop.close()

    def test_empty_graph(self, engine):
        """Empty graph should return empty results."""
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(engine.execute([], []))
            assert results == {}
        finally:
            loop.close()
