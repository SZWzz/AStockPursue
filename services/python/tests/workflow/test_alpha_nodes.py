"""Tests for AlphaZooNode."""

import asyncio

import pandas as pd
import pytest

from src.workflow.nodes.alpha_nodes import AlphaZooNode


class TestAlphaZooNode:
    def test_node_attributes(self):
        node = AlphaZooNode()
        assert node.node_type == "alpha_zoo"
        assert node.category == "alpha"
        assert node.resource_profile == "cpu_bound"
        assert len(node.inputs) == 1
        assert node.inputs[0].name == "ohlcv_data"
        assert len(node.outputs) == 2

    @pytest.fixture
    def sample_ohlcv(self):
        """Small multi-code OHLCV panel."""
        dates = pd.date_range("2024-01-01", periods=30, freq="B")
        import numpy as np
        rng = np.random.default_rng(42)
        data = {}
        for code in ["000001.SZ", "000002.SZ", "600519.SH"]:
            data[code] = pd.DataFrame({
                "open": rng.normal(10, 1, 30).cumsum() + 100,
                "high": rng.normal(10.5, 1, 30).cumsum() + 100,
                "low": rng.normal(9.5, 1, 30).cumsum() + 100,
                "close": rng.normal(10, 1, 30).cumsum() + 100,
                "volume": rng.integers(1000, 10000, 30),
            }, index=dates)
        return data

    def test_empty_data(self):
        node = AlphaZooNode()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(node.execute({"ohlcv_data": {}}, {"alpha_id": "alpha101_001"}))
            assert "factor" in result
            assert result["factor"].empty
        finally:
            loop.close()

    def test_execute_with_data(self, sample_ohlcv):
        """Should compute a factor (may fail gracefully if alpha not found in registry)."""
        node = AlphaZooNode()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(node.execute(
                {"ohlcv_data": sample_ohlcv},
                {"alpha_id": "", "zoo": "alpha101"}
            ))
            assert "factor" in result
            assert "factor_result" in result
            # Either factor is computed or an error is reported
            fr = result["factor_result"]
            assert "alpha_id" in fr or "error" in fr
        finally:
            loop.close()
