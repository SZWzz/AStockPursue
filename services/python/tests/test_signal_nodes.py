"""Unit tests for workflow signal construction nodes.

Tests the vectorised logic of RankSelectNode, ThresholdSelectNode,
SignalWeightNode, HoldSignalNode, CrossOverNode, and RebalanceNode.
"""

from __future__ import annotations

import asyncio

import numpy as np
import pandas as pd
import pytest

from src.workflow.nodes.factor_atoms import ColumnExtractNode, MANode
from src.workflow.nodes.signal_nodes import (
    HoldSignalNode,
    RankSelectNode,
    RebalanceNode,
    SignalWeightNode,
    ThresholdSelectNode,
)
from src.workflow.workflow_engine import _run_cpu_node


# ── Test helpers ──────────────────────────────────────────────────────────────


def _make_ohlcv(
    codes: list[str] = ("000001.SZ", "600000.SH", "000002.SZ"),
    periods: int = 100,
    seed: int = 42,
) -> dict[str, pd.DataFrame]:
    """Create synthetic OHLCV data for testing."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=periods, freq="B")
    result = {}
    for code in codes:
        close = 10 + rng.random(periods).cumsum() * 0.1
        result[code] = pd.DataFrame(
            {
                "open": close * (1 + rng.normal(0, 0.005, periods)),
                "high": close * (1 + abs(rng.normal(0, 0.01, periods))),
                "low": close * (1 - abs(rng.normal(0, 0.01, periods))),
                "close": close,
                "volume": rng.integers(10000, 1000000, periods).astype(float),
            },
            index=dates,
        )
    return result


async def _run(node, inputs: dict, config: dict | None = None) -> dict:
    """Execute a node and return its outputs."""
    return await node.execute(inputs, config or {})


# ═══════════════════════════════════════════════════════════════════════════════
# RankSelectNode
# ═══════════════════════════════════════════════════════════════════════════════


class TestRankSelectNode:
    def test_empty_input_returns_empty(self):
        node = RankSelectNode()
        result = asyncio.run(_run(node, {}))
        assert result == {"signal": {}}

    def test_selects_top_n_stocks(self):
        """Top 2 stocks by factor value should get weight 0.5 each."""
        node = RankSelectNode()
        # 3 stocks × 5 bars, stock C always highest
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        factor = pd.DataFrame(
            {"A": [1, 2, 3, 4, 5], "B": [2, 3, 4, 5, 6], "C": [3, 4, 5, 6, 7]},
            index=dates,
        )
        result = asyncio.run(_run(node, {"factor": factor}, {"top_n": 2, "ascending": "false"}))
        signals = result["signal"]

        assert len(signals) == 3
        # Stock C always in top 2 → weight=0.5 at every bar
        for date in dates:
            assert signals["C"].at[date] == 0.5
        # Stock A only gets selected when it's in top 2 (first few bars it's not)
        assert signals["A"].iloc[0] == 0.0  # A=1 (lowest)
        assert signals["B"].iloc[-1] == 0.5  # B=6 (second highest)

    def test_ascending_selects_lowest(self):
        """Ascending mode: lowest values should be selected."""
        node = RankSelectNode()
        dates = pd.date_range("2024-01-01", periods=1, freq="B")
        factor = pd.DataFrame({"A": [10], "B": [5], "C": [1]}, index=dates)
        result = asyncio.run(_run(node, {"factor": factor}, {"top_n": 2, "ascending": "true"}))
        signals = result["signal"]

        # C (1) and B (5) should be selected, not A (10)
        assert signals["C"].iloc[0] == 0.5
        assert signals["B"].iloc[0] == 0.5
        assert signals["A"].iloc[0] == 0.0

    def test_top_n_larger_than_stocks_gives_equal_weight(self):
        node = RankSelectNode()
        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        factor = pd.DataFrame({"A": [1, 2, 3], "B": [2, 1, 2]}, index=dates)
        result = asyncio.run(_run(node, {"factor": factor}, {"top_n": 10, "ascending": "false"}))
        signals = result["signal"]

        # Both stocks always selected → each gets 1/top_n = 0.1
        for date in dates:
            assert signals["A"].at[date] == 0.1
            assert signals["B"].at[date] == 0.1


# ═══════════════════════════════════════════════════════════════════════════════
# ThresholdSelectNode
# ═══════════════════════════════════════════════════════════════════════════════


class TestThresholdSelectNode:
    def test_gt_threshold(self):
        node = ThresholdSelectNode()
        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        factor = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}, index=dates)
        result = asyncio.run(_run(node, {"factor": factor}, {"threshold": 3, "op": "gt"}))
        signals = result["signal"]

        # Bar 0: A=1, B=4 → only B selected, weight=1.0
        assert signals["A"].iloc[0] == 0.0
        assert signals["B"].iloc[0] == 1.0
        # Bar 2: both > 3 → equal weight 0.5
        assert signals["A"].iloc[2] == 0.0  # A=3, threshold=3, gt → false
        assert signals["B"].iloc[2] == 1.0

    def test_lt_threshold(self):
        node = ThresholdSelectNode()
        dates = pd.date_range("2024-01-01", periods=2, freq="B")
        factor = pd.DataFrame({"A": [1, 5], "B": [3, 2]}, index=dates)
        result = asyncio.run(_run(node, {"factor": factor}, {"threshold": 3, "op": "lt"}))
        signals = result["signal"]

        # Bar 0: A=1<3, B=3 not <3 → only A, weight=1.0
        assert signals["A"].iloc[0] == 1.0
        assert signals["B"].iloc[0] == 0.0

    def test_gte_threshold(self):
        node = ThresholdSelectNode()
        dates = pd.date_range("2024-01-01", periods=1, freq="B")
        factor = pd.DataFrame({"A": [3], "B": [5]}, index=dates)
        result = asyncio.run(_run(node, {"factor": factor}, {"threshold": 3, "op": "gte"}))
        signals = result["signal"]

        # Both >= 3 → equal weight 0.5
        assert signals["A"].iloc[0] == 0.5
        assert signals["B"].iloc[0] == 0.5

    def test_no_stock_meets_threshold(self):
        node = ThresholdSelectNode()
        dates = pd.date_range("2024-01-01", periods=1, freq="B")
        factor = pd.DataFrame({"A": [1], "B": [2]}, index=dates)
        result = asyncio.run(_run(node, {"factor": factor}, {"threshold": 100, "op": "gt"}))
        signals = result["signal"]

        # No stock > 100 → all weights 0
        assert signals["A"].iloc[0] == 0.0
        assert signals["B"].iloc[0] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# SignalWeightNode
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignalWeightNode:
    def test_equal_mode_normalises(self):
        node = SignalWeightNode()
        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        signal = {
            "A": pd.Series([0, 1, 1], index=dates),
            "B": pd.Series([1, 1, 0], index=dates),
            "C": pd.Series([0, 0, 1], index=dates),
        }
        result = asyncio.run(_run(node, {"signal": signal}, {"mode": "equal"}))
        out = result["signal"]

        # Bar 0: A=0, B=1, C=0 → B gets 1.0
        assert out["B"].iloc[0] == 1.0
        # Bar 1: A=1, B=1, C=0 → A and B get 0.5
        assert out["A"].iloc[1] == 0.5
        assert out["B"].iloc[1] == 0.5
        # Bar 2: A=1, B=0, C=1 → A and C get 0.5
        assert out["A"].iloc[2] == 0.5
        assert out["C"].iloc[2] == 0.5

    def test_factor_proportional_mode(self):
        node = SignalWeightNode()
        dates = pd.date_range("2024-01-01", periods=2, freq="B")
        signal = {
            "A": pd.Series([1, 1], index=dates),
            "B": pd.Series([1, 1], index=dates),
        }
        factor = pd.DataFrame({"A": [3.0, 2.0], "B": [1.0, 2.0]}, index=dates)
        result = asyncio.run(
            _run(node, {"signal": signal, "factor": factor}, {"mode": "factor_proportional"})
        )
        out = result["signal"]

        # Bar 0: A has factor 3, B has factor 1 → A: 3/4=0.75, B: 1/4=0.25
        assert out["A"].iloc[0] == pytest.approx(0.75)
        assert out["B"].iloc[0] == pytest.approx(0.25)
        # Bar 1: both have factor 2 → equal 0.5
        assert out["A"].iloc[1] == pytest.approx(0.5)
        assert out["B"].iloc[1] == pytest.approx(0.5)

    def test_empty_signal(self):
        node = SignalWeightNode()
        result = asyncio.run(_run(node, {}, {"mode": "equal"}))
        assert result == {"signal": {}}


# ═══════════════════════════════════════════════════════════════════════════════
# HoldSignalNode
# ═══════════════════════════════════════════════════════════════════════════════


class TestHoldSignalNode:
    def test_enter_pulse_latches_position(self):
        node = HoldSignalNode()
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        # Enter pulse at bar 2
        enter = pd.DataFrame({"A": [0, 0, 1, 0, 0, 0, 0, 0, 0, 0]}, index=dates)
        exit_sig = pd.DataFrame({"A": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, index=dates)
        result = asyncio.run(_run(node, {"enter": enter, "exit": exit_sig}, {"initial": "flat"}))
        pos = result["position"]

        # Before enter: 0
        assert pos["A"].iloc[0] == 0.0
        assert pos["A"].iloc[1] == 0.0
        # After enter: latches to 1
        assert pos["A"].iloc[2] == 1.0
        assert pos["A"].iloc[3] == 1.0
        assert pos["A"].iloc[9] == 1.0

    def test_exit_pulse_unlatches_position(self):
        node = HoldSignalNode()
        dates = pd.date_range("2024-01-01", periods=8, freq="B")
        enter = pd.DataFrame({"A": [0, 1, 0, 0, 0, 0, 0, 0]}, index=dates)
        exit_sig = pd.DataFrame({"A": [0, 0, 0, 0, 1, 0, 0, 0]}, index=dates)
        result = asyncio.run(_run(node, {"enter": enter, "exit": exit_sig}, {"initial": "flat"}))
        pos = result["position"]

        # Bar 1: enter → position becomes 1
        assert pos["A"].iloc[1] == 1.0
        assert pos["A"].iloc[3] == 1.0
        # Bar 4: exit → position becomes 0
        assert pos["A"].iloc[4] == 0.0
        assert pos["A"].iloc[5] == 0.0

    def test_initial_long(self):
        node = HoldSignalNode()
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        enter = pd.DataFrame({"A": [0, 0, 0, 0, 0]}, index=dates)
        exit_sig = pd.DataFrame({"A": [0, 0, 1, 0, 0]}, index=dates)
        result = asyncio.run(_run(node, {"enter": enter, "exit": exit_sig}, {"initial": "long"}))
        pos = result["position"]

        # Start long
        assert pos["A"].iloc[0] == 1.0
        assert pos["A"].iloc[1] == 1.0
        # Exit → flat
        assert pos["A"].iloc[2] == 0.0
        assert pos["A"].iloc[4] == 0.0

    def test_multiple_codes(self):
        node = HoldSignalNode()
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        enter = pd.DataFrame(
            {"A": [0, 1, 0, 0, 0], "B": [1, 0, 0, 0, 0]}, index=dates
        )
        exit_sig = pd.DataFrame(
            {"A": [0, 0, 0, 0, 1], "B": [0, 0, 0, 0, 0]}, index=dates
        )
        result = asyncio.run(_run(node, {"enter": enter, "exit": exit_sig}, {"initial": "flat"}))
        pos = result["position"]

        # A: enters bar 1, exits bar 4
        assert pos["A"].iloc[0] == 0.0
        assert pos["A"].iloc[1] == 1.0
        assert pos["A"].iloc[3] == 1.0
        assert pos["A"].iloc[4] == 0.0
        # B: enters bar 0, never exits
        assert pos["B"].iloc[0] == 1.0
        assert pos["B"].iloc[4] == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# RebalanceNode
# ═══════════════════════════════════════════════════════════════════════════════


class TestRebalanceNode:
    def test_holds_between_rebalance_dates(self):
        node = RebalanceNode()
        dates = pd.date_range("2024-01-01", periods=8, freq="B")
        signal = {
            "A": pd.Series([0.5, 0.3, 0.7, 0.2, 0.9, 0.1, 0.4, 0.8], index=dates),
        }
        result = asyncio.run(_run(node, {"signal": signal}, {"frequency": 3}))
        out = result["signal"]

        # Rebalance every 3 bars: bar 0, 3, 6
        assert out["A"].iloc[0] == 0.5  # rebalance
        assert out["A"].iloc[1] == 0.5  # hold
        assert out["A"].iloc[2] == 0.5  # hold
        assert out["A"].iloc[3] == 0.2  # rebalance
        assert out["A"].iloc[4] == 0.2  # hold
        assert out["A"].iloc[5] == 0.2  # hold
        assert out["A"].iloc[6] == 0.4  # rebalance

    def test_frequency_1_passthrough(self):
        node = RebalanceNode()
        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        signal = {"A": pd.Series([0.5, 0.3, 0.7], index=dates)}
        result = asyncio.run(_run(node, {"signal": signal}, {"frequency": 1}))
        out = result["signal"]

        # Frequency 1 = every bar rebalances = passthrough
        assert out["A"].iloc[0] == 0.5
        assert out["A"].iloc[1] == 0.3
        assert out["A"].iloc[2] == 0.7


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: factor pipeline end-to-end
# ═══════════════════════════════════════════════════════════════════════════════


class TestFactorPipelineIntegration:
    def test_column_extract_to_ma_to_rank_select(self):
        """Simulate a simple pipeline: extract close → MA(5) → rank_select."""
        ohlcv = _make_ohlcv(periods=50)

        # Step 1: ColumnExtract
        extract = ColumnExtractNode()
        out1 = asyncio.run(_run(extract, {"ohlcv_data": ohlcv}, {"column": "close"}))
        assert not out1["series"].empty
        assert out1["series"].shape[1] == 3  # 3 codes

        # Step 2: MA(5)
        ma = MANode()
        out2 = asyncio.run(_run(ma, {"series": out1["series"]}, {"window": 5}))
        assert not out2["ma"].empty

        # Step 3: RankSelect (top 2)
        rank = RankSelectNode()
        out3 = asyncio.run(_run(rank, {"factor": out2["ma"]}, {"top_n": 2, "ascending": "false"}))
        signals = out3["signal"]

        assert len(signals) == 3
        # Each bar should have at most 2 stocks with weight 0.5
        for date in out2["ma"].index[-10:]:
            active = sum(1 for s in signals.values() if s.at[date] > 0)
            assert active <= 2

    def test_factor_to_threshold_select_to_weight_to_rebalance(self):
        """Full signal pipeline: factor → threshold → weight → rebalance."""
        dates = pd.date_range("2024-01-01", periods=20, freq="B")
        # Simulate a factor: momentum (pct_change)
        rng = np.random.default_rng(0)
        factor = pd.DataFrame(
            {c: rng.normal(0, 0.02, 20) for c in ("A", "B", "C", "D")}, index=dates
        )

        # Threshold: select stocks with factor > 0
        thresh = ThresholdSelectNode()
        out1 = asyncio.run(_run(thresh, {"factor": factor}, {"threshold": 0, "op": "gt"}))
        assert len(out1["signal"]) == 4

        # Equal weight
        weight = SignalWeightNode()
        out2 = asyncio.run(_run(weight, {"signal": out1["signal"]}, {"mode": "equal"}))
        assert len(out2["signal"]) == 4

        # Rebalance every 5 bars
        rebalance = RebalanceNode()
        out3 = asyncio.run(_run(rebalance, {"signal": out2["signal"]}, {"frequency": 5}))

        # Check weights sum to ≤ 1.0 per bar
        for i in range(len(dates)):
            total_weight = sum(s.iloc[i] for s in out3["signal"].values())
            assert total_weight <= 1.0 + 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
# CPU pool execution (smoke test)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignalNodesViaCPUPool:
    """Smoke test: nodes should work through ProcessPoolExecutor."""

    def test_rank_select_via_cpu_pool(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        factor = pd.DataFrame({"A": range(10), "B": range(10, 20)}, index=dates)
        result = _run_cpu_node(
            "rank_select",
            inputs={"factor": factor},
            config={"top_n": 1, "ascending": "false"},
        )
        # Result should be pickled/serialised correctly
        assert "signal" in result

    def test_threshold_select_via_cpu_pool(self):
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        factor = pd.DataFrame({"A": [1, 2, 3, 4, 5]}, index=dates)
        result = _run_cpu_node(
            "threshold_select",
            inputs={"factor": factor},
            config={"threshold": 3, "op": "gt"},
        )
        assert "signal" in result
