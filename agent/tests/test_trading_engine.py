"""Tests for TradingEngine core pipeline and BarResult."""

import numpy as np
import pandas as pd
import pytest
from src.trading.engine import TradingEngine, BarResult


class MockSignalAdapter:
    """Returns equal-weight signals for all codes."""
    mode = "batch"

    def init_batch(self, data_map):
        return data_map

    def on_bar_batch(self, bar, data_map, *, skip_append=False):
        n = len(bar)
        w = 1.0 / n if n > 0 else 0.0
        return {code: w for code in bar}

    def generate(self, bar):
        return self.on_bar_batch(bar, {})


class MockMarketEngine:
    """Minimal market engine that always allows trades."""
    def __init__(self, config):
        self.config = config
        self.capital = config.get("initial_capital", 100_000.0)
        self.positions = {}
        self.trades = []
        self.equity_snapshots = []
        self._active_symbol = None
        self.default_leverage = 1.0

    def on_bar(self, code, bar, timestamp):
        pass

    def can_execute(self, symbol, direction, bar):
        return True

    def round_size(self, raw_size, price):
        return max(int(raw_size), 0)

    def calc_commission(self, size, price, direction, is_open):
        return max(size * price * 0.00025, 5.0)

    def apply_slippage(self, price, direction):
        return price * (1.0 + direction * 0.001)

    def _calc_margin(self, symbol, size, price, leverage):
        return size * price / leverage

    def _open_position(self, symbol, direction, size, price, timestamp, leverage):
        from backtest.models import Position
        pos = Position(symbol=symbol, direction=direction, entry_price=price,
                       entry_time=timestamp, size=size, leverage=leverage)
        self.positions[symbol] = pos
        self.capital -= size * price * 0.00025  # commission
        return pos

    def _calc_pnl(self, symbol, direction, size, entry_price, current_price):
        return direction * size * (current_price - entry_price)

    def get_summary(self):
        return {"equity": self.capital, "positions": len(self.positions)}


def _make_bar(codes, prices=None):
    """Create a bar dict for testing."""
    if prices is None:
        prices = {c: 100.0 for c in codes}
    return {
        c: pd.Series({"open": p, "high": p * 1.01, "low": p * 0.99,
                       "close": p * 1.005, "volume": 10000}, name=pd.Timestamp("2024-01-02"))
        for c, p in prices.items()
    }


class TestBarResult:
    def test_bars_field_populated(self):
        engine = TradingEngine(
            config={"codes": ["A"], "initial_capital": 100_000},
            signal_adapter=MockSignalAdapter(),
            market_engine=MockMarketEngine({"codes": ["A"], "initial_capital": 100_000}),
        )
        bar = _make_bar(["A"])
        result = engine.on_bar(bar, pd.Timestamp("2024-01-02"))
        assert "A" in result.bars
        assert result.bars["A"]["open"] > 0
        assert result.bars["A"]["close"] > 0

    def test_bars_field_multiple_codes(self):
        engine = TradingEngine(
            config={"codes": ["A", "B"], "initial_capital": 100_000},
            signal_adapter=MockSignalAdapter(),
            market_engine=MockMarketEngine({"codes": ["A", "B"], "initial_capital": 100_000}),
        )
        bar = _make_bar(["A", "B"])
        result = engine.on_bar(bar, pd.Timestamp("2024-01-02"))
        assert "A" in result.bars
        assert "B" in result.bars


class TestTradingEngine:
    def test_initialize_stores_data_map(self):
        engine = TradingEngine(
            config={"codes": ["A"], "initial_capital": 100_000},
            signal_adapter=MockSignalAdapter(),
            market_engine=MockMarketEngine({"codes": ["A"], "initial_capital": 100_000}),
        )
        df = pd.DataFrame({"open": [100], "high": [101], "low": [99],
                            "close": [100.5], "volume": [5000]},
                           index=[pd.Timestamp("2024-01-01")])
        engine.initialize({"A": df})
        assert engine.last_bar_time is not None
        assert engine._bar_idx > 0

    def test_get_bars_returns_ohlcv(self):
        engine = TradingEngine(
            config={"codes": ["A"], "initial_capital": 100_000},
            signal_adapter=MockSignalAdapter(),
            market_engine=MockMarketEngine({"codes": ["A"], "initial_capital": 100_000}),
        )
        df = pd.DataFrame({
            "open":  [100, 101],
            "high":  [102, 103],
            "low":   [98, 99],
            "close": [101, 102],
            "volume":[5000, 6000],
        }, index=[pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")])
        engine.initialize({"A": df})
        bars = engine.get_bars(["A"])
        assert len(bars["A"]) == 2
        assert bars["A"][0]["open"] == 100.0
        assert bars["A"][1]["close"] == 102.0

    def test_get_bars_limit(self):
        engine = TradingEngine(
            config={"codes": ["A"], "initial_capital": 100_000},
            signal_adapter=MockSignalAdapter(),
            market_engine=MockMarketEngine({"codes": ["A"], "initial_capital": 100_000}),
        )
        rows = []
        for i in range(10):
            rows.append({"open": 100+i, "high": 101+i, "low": 99+i, "close": 100.5+i, "volume": 5000})
        df = pd.DataFrame(rows, index=pd.date_range("2024-01-01", periods=10, freq="D"))
        engine.initialize({"A": df})
        bars = engine.get_bars(["A"], limit=3)
        assert len(bars["A"]) == 3

    def test_get_bars_unknown_code(self):
        engine = TradingEngine(
            config={"codes": ["A"], "initial_capital": 100_000},
            signal_adapter=MockSignalAdapter(),
            market_engine=MockMarketEngine({"codes": ["A"], "initial_capital": 100_000}),
        )
        bars = engine.get_bars(["UNKNOWN"])
        assert "UNKNOWN" not in bars or len(bars.get("UNKNOWN", [])) == 0

    def test_on_bar_updates_indices(self):
        engine = TradingEngine(
            config={"codes": ["A"], "initial_capital": 100_000},
            signal_adapter=MockSignalAdapter(),
            market_engine=MockMarketEngine({"codes": ["A"], "initial_capital": 100_000}),
        )
        bar = _make_bar(["A"])
        ts = pd.Timestamp("2024-01-02")
        result = engine.on_bar(bar, ts)
        assert result.equity > 0
        assert engine.last_bar_time == ts
        assert engine._bar_idx == 1

    def test_on_bar_equity_computation(self):
        engine = TradingEngine(
            config={"codes": ["A"], "initial_capital": 100_000},
            signal_adapter=MockSignalAdapter(),
            market_engine=MockMarketEngine({"codes": ["A"], "initial_capital": 100_000}),
        )
        bar = _make_bar(["A"])
        result = engine.on_bar(bar, pd.Timestamp("2024-01-02"))
        assert result.equity > 0
        assert result.capital > 0
        # With no open positions, equity ≈ capital
        assert abs(result.equity - result.capital) < 1.0
