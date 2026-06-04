"""Tests for StrategyNode, BacktestNode, and AttributionNode."""

import asyncio
import pandas as pd
import pytest
from src.workflow.nodes.strategy_nodes import StrategyNode, BacktestNode, BUILTIN_STRATEGIES, InMemoryLoader, StaticSignalEngine
from src.workflow.nodes.analysis_nodes import AttributionNode


@pytest.fixture
def sample_ohlcv():
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    import numpy as np; rng = np.random.default_rng(42)
    data = {}
    for code in ["000001.SZ", "000002.SZ", "600519.SH"]:
        data[code] = pd.DataFrame({
            "open": rng.normal(10, 1, 50).cumsum() + 100,
            "high": rng.normal(10.5, 1, 50).cumsum() + 100,
            "low": rng.normal(9.5, 1, 50).cumsum() + 100,
            "close": rng.normal(10, 1, 50).cumsum() + 100,
            "volume": rng.integers(1000, 10000, 50),
        }, index=dates)
    return data


class TestStrategyNode:
    def test_attributes(self):
        n = StrategyNode()
        assert n.node_type == "strategy"
        assert len(n.inputs) == 2

    def test_empty_data(self):
        n = StrategyNode()
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(n.execute({"ohlcv_data": {}}, {}))
            assert r["signal"] == {}
        finally:
            loop.close()

    def test_momentum_top5(self, sample_ohlcv):
        n = StrategyNode()
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(n.execute({"ohlcv_data": sample_ohlcv}, {"strategy_template": "momentum_top5", "top_n": 2}))
            assert len(r["signal"]) > 0
        finally:
            loop.close()

    def test_builtin_templates(self):
        for name, code in BUILTIN_STRATEGIES.items():
            ns = {}
            exec(compile(code, f"<{name}>", "exec"), ns)
            assert "SignalEngine" in ns


class TestInMemoryLoader:
    def test_fetch(self):
        df = pd.DataFrame({"close": [1, 2, 3]}, index=pd.date_range("2024-01-01", periods=3))
        loader = InMemoryLoader({"TEST": df})
        r = loader.fetch(["TEST"], "2024-01-01", "2024-01-03")
        assert "TEST" in r and len(r["TEST"]) == 3

    def test_missing(self):
        r = InMemoryLoader({}).fetch(["X"], "2024-01-01", "2024-01-03")
        assert r == {}


class TestStaticSignalEngine:
    def test_generate(self):
        dates = pd.date_range("2024-01-01", periods=5)
        df = pd.DataFrame({"close": [1, 2, 3, 4, 5]}, index=dates)
        sigs = {"TEST": pd.Series([0, 0.5, 0.5, 0, 0.5], index=dates)}
        e = StaticSignalEngine(sigs)
        r = e.generate({"TEST": df})
        assert r["TEST"].iloc[1] == 0.5


class TestBacktestNode:
    def test_attributes(self):
        n = BacktestNode()
        assert n.node_type == "backtest"

    def test_empty_data(self):
        n = BacktestNode()
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(n.execute({"ohlcv_data": {}, "signal": {}}, {}))
            assert "error" in r["backtest_result"]
        finally:
            loop.close()

    def test_bars_per_year(self):
        n = BacktestNode()
        assert n._mk_engine("equity_cn", 100000) is not None


class TestAttributionNode:
    def test_attributes(self):
        n = AttributionNode()
        assert n.node_type == "attribution"

    def test_with_metrics(self):
        n = AttributionNode()
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(n.execute({"backtest_result": {"metrics": {"sharpe": 1.5, "max_drawdown": 0.1}}}, {}))
            assert r["attribution_report"]["summary"]["sharpe"] == 1.5
        finally:
            loop.close()
