"""Tests for RiskPipeline — gap detection, daily loss, intraday checks."""

from __future__ import annotations

import pytest

from src.trading.risk_pipeline import RiskPipeline, RiskConfig


def _make_risk(config: dict | None = None) -> RiskPipeline:
    c = RiskConfig(**(config or {}))
    return RiskPipeline(c, initial_capital=100_000)


class TestCheckGap:
    def test_stop_loss_gap_long(self):
        r = _make_risk({"stop_loss_pct": 5.0})
        reason, price = r.check_gap("A", 1, 100.0, 105.0, 93.0)
        assert reason == "gap_stop"
        assert price == 93.0

    def test_stop_loss_gap_short(self):
        r = _make_risk({"stop_loss_pct": 5.0})
        reason, price = r.check_gap("A", -1, 100.0, 95.0, 108.0)
        assert reason == "gap_stop"
        assert price == 108.0

    def test_take_profit_gap_long(self):
        r = _make_risk({"take_profit_pct": 10.0})
        reason, price = r.check_gap("A", 1, 100.0, 105.0, 115.0)
        assert reason == "gap_target"
        assert price == 115.0

    def test_take_profit_gap_short(self):
        r = _make_risk({"take_profit_pct": 10.0})
        reason, price = r.check_gap("A", -1, 100.0, 95.0, 85.0)
        assert reason == "gap_target"
        assert price == 85.0

    def test_trailing_stop_gap_long(self):
        r = _make_risk({"stop_loss_pct": 10.0, "trailing_stop_pct": 5.0})
        r._trailing_highs["A"] = 110.0  # price ran up to 110
        r.check_position("A", 1, 100.0, 110.0, "2024-01-02")  # registers the high
        reason, price = r.check_gap("A", 1, 100.0, 110.0, 103.0)
        # trailing stop = 110 * (1 - 0.05) = 104.5, open 103 < 104.5 → triggered
        assert reason == "gap_trail"
        assert price == 103.0

    def test_no_gap(self):
        r = _make_risk({"stop_loss_pct": 5.0, "take_profit_pct": 10.0})
        reason, price = r.check_gap("A", 1, 100.0, 105.0, 102.0)
        assert reason is None
        assert price is None

    def test_invalid_inputs_return_none(self):
        r = _make_risk()
        assert r.check_gap("A", 1, -1, 100, 100) == (None, None)
        assert r.check_gap("A", 1, 100, -1, 100) == (None, None)
        assert r.check_gap("A", 1, 100, 100, -1) == (None, None)

    def test_stop_priority_over_target(self):
        r = _make_risk({"stop_loss_pct": 5.0, "take_profit_pct": 10.0})
        reason, _ = r.check_gap("A", 1, 100.0, 105.0, 90.0)
        assert reason == "gap_stop"

    def test_stop_priority_over_trail(self):
        r = _make_risk({"stop_loss_pct": 5.0, "trailing_stop_pct": 10.0})
        r._trailing_highs["A"] = 110.0
        r.check_position("A", 1, 100.0, 110.0, "2024-01-02")
        # Gap down triggers both stop (95) and trail (110 * 0.9 = 99)
        # Stop has priority
        reason, _ = r.check_gap("A", 1, 100.0, 110.0, 93.0)
        assert reason == "gap_stop"


class TestCheckDailyLoss:
    def test_no_loss_allowed(self):
        r = _make_risk({"max_daily_loss_pct": 3.0})
        assert not r.check_daily_loss()

    def test_exceeds_threshold(self):
        r = _make_risk({"max_daily_loss_pct": 3.0})
        r.accumulate_daily(-4000, "2024-01-02")
        assert r.check_daily_loss()  # 4000 > 3000

    def test_below_threshold(self):
        r = _make_risk({"max_daily_loss_pct": 3.0})
        r.accumulate_daily(-2000, "2024-01-02")
        assert not r.check_daily_loss()  # 2000 < 3000

    def test_dynamic_equity_updates_threshold(self):
        r = _make_risk({"max_daily_loss_pct": 10.0})
        r.accumulate_daily(-5000, "2024-01-02")
        # With initial 100k, threshold = 10000 → 5000 < 10000 → not triggered
        assert not r.check_daily_loss()
        # With equity = 30000, threshold = 3000 → 5000 > 3000 → triggered
        assert r.check_daily_loss(equity=30_000)

    def test_resets_on_new_day(self):
        r = _make_risk({"max_daily_loss_pct": 3.0})
        r.accumulate_daily(-4000, "2024-01-02")
        assert r.check_daily_loss()
        r.accumulate_daily(1000, "2024-01-03")  # new day
        assert not r.check_daily_loss()
        assert r.daily_pnl == 1000


class TestCheckPositionIntraday:
    def test_stop_touched_long(self):
        r = _make_risk({"stop_loss_pct": 5.0, "use_intraday_stop": True})
        reason, price = r.check_position_intraday("A", 1, 100.0, 101.0, 102.0, 94.0, 101.0)
        # stop at 95, low 94 → touched
        assert reason == "stop_loss"
        # open 101 > stop 95 → no gap → exec at stop
        assert price == 95.0

    def test_stop_touched_short(self):
        r = _make_risk({"stop_loss_pct": 5.0, "use_intraday_stop": True})
        reason, price = r.check_position_intraday("A", -1, 100.0, 99.0, 108.0, 98.0, 106.0)
        # stop at 105, high 108 → touched
        assert reason == "stop_loss"

    def test_target_touched_long(self):
        r = _make_risk({"take_profit_pct": 10.0, "use_intraday_stop": True})
        reason, price = r.check_position_intraday("A", 1, 100.0, 101.0, 115.0, 100.0, 112.0)
        # target at 110, high 115 → touched
        assert reason == "take_profit"
        # open 101 < target 110 → no gap → exec at target price
        assert abs(price - 110.0) < 1e-9

    def test_trailing_stop_touched(self):
        r = _make_risk({"trailing_stop_pct": 5.0, "use_intraday_stop": True})
        r._trailing_highs["A"] = 120.0
        reason, _ = r.check_position_intraday("A", 1, 100.0, 115.0, 122.0, 112.0, 118.0)
        # trailing_highs updated to 122. trail at 122 * 0.95 = 115.9. low 112 → touched
        assert reason == "trailing_stop"

    def test_no_touch(self):
        r = _make_risk({"stop_loss_pct": 5.0, "take_profit_pct": 10.0, "use_intraday_stop": True})
        reason, price = r.check_position_intraday("A", 1, 100.0, 101.0, 104.0, 99.0, 102.0)
        assert reason is None
        assert price is None

    def test_invalid_inputs(self):
        r = _make_risk({"use_intraday_stop": True})
        assert r.check_position_intraday("A", 1, -1, 100, 100, 100, 100) == (None, None)
        assert r.check_position_intraday("A", 1, 100, -1, 100, 100, 100) == (None, None)


class TestCheckPosition:
    def test_stop_loss_long(self):
        r = _make_risk({"stop_loss_pct": 5.0})
        assert r.check_position("A", 1, 100.0, 93.0, "2024-01-02") == "stop_loss"

    def test_stop_loss_short(self):
        r = _make_risk({"stop_loss_pct": 5.0})
        assert r.check_position("A", -1, 100.0, 107.0, "2024-01-02") == "stop_loss"

    def test_take_profit_long(self):
        r = _make_risk({"take_profit_pct": 10.0})
        assert r.check_position("A", 1, 100.0, 112.0, "2024-01-02") == "take_profit"

    def test_trailing_stop(self):
        r = _make_risk({"trailing_stop_pct": 5.0, "take_profit_pct": 50.0})
        # First call registers the high
        assert r.check_position("A", 1, 100.0, 120.0, "2024-01-02") is None
        assert r._trailing_highs["A"] == 120.0
        # Price drops below trail threshold (120 * 0.95 = 114)
        assert r.check_position("A", 1, 100.0, 110.0, "2024-01-03") == "trailing_stop"

    def test_no_exit(self):
        r = _make_risk({"stop_loss_pct": 5.0, "take_profit_pct": 10.0})
        assert r.check_position("A", 1, 100.0, 103.0, "2024-01-02") is None


class TestOnPositionClosed:
    def test_cleans_up_trailing_highs(self):
        r = _make_risk({"trailing_stop_pct": 5.0})
        r._trailing_highs["A"] = 120.0
        r._trailing_highs["B"] = 200.0
        r.on_position_closed("A")
        assert "A" not in r._trailing_highs
        assert "B" in r._trailing_highs

    def test_no_error_for_missing_symbol(self):
        r = _make_risk()
        r.on_position_closed("UNKNOWN")  # should not raise


class TestCheckPositionSize:
    def test_within_limit(self):
        r = _make_risk({"max_position_pct": 30.0})
        assert r.check_position_size(25_000, 100_000)

    def test_exceeds_limit(self):
        r = _make_risk({"max_position_pct": 30.0})
        assert not r.check_position_size(35_000, 100_000)

    def test_exact_limit(self):
        r = _make_risk({"max_position_pct": 30.0})
        assert r.check_position_size(30_000, 100_000)
