"""Shared fixtures for workflow tests."""

from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortDirection, PortType, WorkflowEdge, WorkflowNodeData


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    import numpy as np; rng = np.random.default_rng(42)
    return pd.DataFrame({
        "open": rng.normal(10, 1, 100).cumsum() + 100,
        "high": rng.normal(10.5, 1, 100).cumsum() + 100,
        "low": rng.normal(9.5, 1, 100).cumsum() + 100,
        "close": rng.normal(10, 1, 100).cumsum() + 100,
        "volume": rng.integers(1000, 10000, 100),
    }, index=dates)


@pytest.fixture
def sample_factor_df() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    codes = [f"{i:06d}.SZ" for i in range(1, 11)]
    import numpy as np; rng = np.random.default_rng(42)
    return pd.DataFrame(rng.normal(0, 1, (50, 10)), index=dates, columns=codes)


@pytest.fixture
def sample_nodes() -> list[WorkflowNodeData]:
    return [
        WorkflowNodeData(id="n1", node_type="data_source", label="Load Data"),
        WorkflowNodeData(id="n2", node_type="compute", label="Compute Alpha"),
        WorkflowNodeData(id="n3", node_type="output", label="Export"),
    ]


@pytest.fixture
def sample_edges() -> list[WorkflowEdge]:
    return [
        WorkflowEdge(id="e1", source="n1", source_port="data", target="n2", target_port="input"),
        WorkflowEdge(id="e2", source="n2", source_port="result", target="n3", target_port="input"),
    ]


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Mock nodes for testing ────────────────────────────────────────────────────

@register_node
class MockDataNode(BaseNode):
    node_type = "data_source"; category = "data"; label = "Mock Data Source"; icon = "Database"
    inputs = []
    outputs = [NodePort(name="data", port_type=PortType.DF_OHLCV, direction=PortDirection.OUTPUT, required=False)]

    async def execute(self, inputs: dict, config: dict) -> dict:
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        import numpy as np; rng = np.random.default_rng(42)
        df = pd.DataFrame({
            "open": rng.normal(10, 1, 10).cumsum() + 100,
            "close": rng.normal(10, 1, 10).cumsum() + 100,
            "volume": rng.integers(1000, 10000, 10),
        }, index=dates)
        return {"data": df}


@register_node
class MockComputeNode(BaseNode):
    node_type = "compute"; category = "alpha"; label = "Mock Compute"; icon = "Calculator"
    inputs = [NodePort(name="input", port_type=PortType.DF_OHLCV, direction=PortDirection.INPUT, required=True)]
    outputs = [NodePort(name="result", port_type=PortType.DF_FACTOR, direction=PortDirection.OUTPUT, required=False)]

    async def execute(self, inputs: dict, config: dict) -> dict:
        ohlcv = inputs.get("input")
        if ohlcv is None:
            return {"result": pd.DataFrame()}
        factor = (ohlcv["close"] - ohlcv["close"].mean()) / ohlcv["close"].std()
        return {"result": pd.DataFrame({"factor": factor.values}, index=ohlcv.index)}


@register_node
class MockOutputNode(BaseNode):
    node_type = "output"; category = "output"; label = "Mock Output"; icon = "FileOutput"
    inputs = [NodePort(name="input", port_type=PortType.DF_FACTOR, direction=PortDirection.INPUT, required=True)]
    outputs = [NodePort(name="summary", port_type=PortType.ANY, direction=PortDirection.OUTPUT, required=False)]

    async def execute(self, inputs: dict, config: dict) -> dict:
        data = inputs.get("input")
        rows = data.shape[0] if hasattr(data, "shape") else 0
        return {"summary": {"rows": rows}}
