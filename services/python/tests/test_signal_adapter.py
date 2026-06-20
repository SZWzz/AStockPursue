"""Tests for SignalAdapter — mode detection, batch path, look-ahead prevention."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.trading.signal_adapter import SignalAdapter


class TestSignalAdapterMode:
    def test_batch_mode_for_generate_only(self):
        adapter = SignalAdapter(engine=SimpleSignalEngine())
        assert adapter.mode == "batch"

    def test_tick_mode_for_tick_handler(self):
        adapter = SignalAdapter(engine=TickSignalEngine())
        assert adapter.mode == "tick"

    def test_requires_engine_or_module(self):
        with pytest.raises(ValueError, match="signal_module or engine"):
            SignalAdapter()


class SimpleSignalEngine:
    """Minimal strategy that only implements generate()."""
    def generate(self, data_map):
        return {code: pd.Series(1.0, index=df.index) for code, df in data_map.items()}


class TickSignalEngine:
    """Minimal strategy that implements TickHandler protocol."""
    def on_init(self, data_map):
        return {}

    def on_bar(self, bar, state):
        return {code: 1.0 for code in bar}


class TestBatchMode:
    def test_on_bar_batch_returns_weights(self):
        adapter = SignalAdapter(engine=SimpleSignalEngine())
        data_map = {
            "A": pd.DataFrame({"close": [100, 101]}, index=pd.date_range("2024-01-01", periods=2)),
        }
        bar = {"A": pd.Series({"close": 102}, name=pd.Timestamp("2024-01-03"))}
        weights = adapter.on_bar_batch(bar, data_map)
        assert "A" in weights
        assert abs(weights["A"] - 1.0) < 1e-9

    def test_on_bar_batch_appends_bar_when_not_skipped(self):
        adapter = SignalAdapter(engine=SimpleSignalEngine())
        data_map = {
            "A": pd.DataFrame({"close": [100]}, index=[pd.Timestamp("2024-01-01")]),
        }
        bar = {"A": pd.Series({"close": 101}, name=pd.Timestamp("2024-01-02"))}
        adapter.on_bar_batch(bar, data_map, skip_append=False)
        assert len(data_map["A"]) == 2

    def test_on_bar_batch_skips_append_when_requested(self):
        adapter = SignalAdapter(engine=SimpleSignalEngine())
        data_map = {
            "A": pd.DataFrame({"close": [100]}, index=[pd.Timestamp("2024-01-01")]),
        }
        bar = {"A": pd.Series({"close": 101}, name=pd.Timestamp("2024-01-02"))}
        adapter.on_bar_batch(bar, data_map, skip_append=True)
        assert len(data_map["A"]) == 1  # unchanged

    def test_look_ahead_prevention(self):
        """The strategy must NOT see the current bar's data."""
        seen_max_date = []

        class TrackingEngine:
            def generate(self, data_map):
                for code, df in data_map.items():
                    seen_max_date.append(df.index.max())
                return {code: pd.Series(1.0, index=df.index) for code, df in data_map.items()}

        adapter = SignalAdapter(engine=TrackingEngine())
        data_map = {
            "A": pd.DataFrame({"close": [100, 101]}, index=pd.date_range("2024-01-01", periods=2)),
        }
        # Current bar is 2024-01-03
        bar = {"A": pd.Series({"close": 102}, name=pd.Timestamp("2024-01-03"))}
        adapter.on_bar_batch(bar, data_map, skip_append=True)

        # generate() was called BEFORE appending, so max date seen should be 2024-01-02
        assert len(seen_max_date) == 1
        assert seen_max_date[0] == pd.Timestamp("2024-01-02")

    def test_filters_nan_and_zero_weights(self):
        class NanEngine:
            def generate(self, data_map):
                return {
                    "A": pd.Series([np.nan], index=data_map["A"].index),
                    "B": pd.Series([0.0], index=data_map["B"].index),
                    "C": pd.Series([0.5], index=data_map["C"].index),
                }

        adapter = SignalAdapter(engine=NanEngine())
        data_map = {
            "A": pd.DataFrame({"close": [100]}, index=[pd.Timestamp("2024-01-01")]),
            "B": pd.DataFrame({"close": [200]}, index=[pd.Timestamp("2024-01-01")]),
            "C": pd.DataFrame({"close": [300]}, index=[pd.Timestamp("2024-01-01")]),
        }
        bar = {"A": None, "B": None, "C": None}
        weights = adapter.on_bar_batch(bar, data_map, skip_append=True)
        # C should be the only entry (A is NaN, B is 0)
        assert "C" in weights
        assert "A" not in weights
        assert "B" not in weights


class TestGetWeights:
    def test_get_weights_batch_mode(self):
        adapter = SignalAdapter(engine=SimpleSignalEngine())
        data_map = {
            "A": pd.DataFrame({"close": [100]}, index=[pd.Timestamp("2024-01-01")]),
        }
        bar = {"A": pd.Series({"close": 101}, name=pd.Timestamp("2024-01-02"))}
        weights = adapter.get_weights(bar, data_map=data_map)
        assert "A" in weights

    def test_get_weights_tick_mode(self):
        adapter = SignalAdapter(engine=TickSignalEngine())
        bar = {"A": pd.Series({"close": 101})}
        weights = adapter.get_weights(bar, tick_state={})
        assert "A" in weights
