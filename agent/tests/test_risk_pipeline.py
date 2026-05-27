"""Tests for RiskPipeline — stop-loss, take-profit, trailing-stop, daily loss limit."""

import pytest
from src.trading.risk_pipeline import RiskConfig, RiskPipeline


class TestRiskPipeline:
    """Happy-path and boundary tests for the composable risk layer."""

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _pipeline(**overrides) -> RiskPipeline:
        cfg = RiskConfig()
        for k, v in overrides.items():
            setattr(cfg, k, v)
        return RiskPipeline(cfg, initial_capital=100_000.0)

    # ── stop-loss ────────────────────────────────────────────────────

    def test_stop_loss_long(self):
        rp = self._pipeline(stop_loss_pct=5.0)
        reason = rp.check_position("TEST", 1, 100.0, 94.0, "2024-01-02")
        assert reason == "stop_loss"

    def test_stop_loss_not_triggered(self):
        rp = self._pipeline(stop_loss_pct=5.0)
        reason = rp.check_position("TEST", 1, 100.0, 96.0, "2024-01-02")
        assert reason is None

    def test_stop_loss_short(self):
        rp = self._pipeline(stop_loss_pct=5.0)
        reason = rp.check_position("TEST", -1, 100.0, 106.0, "2024-01-02")
        assert reason == "stop_loss"

    # ── take-profit ──────────────────────────────────────────────────

    def test_take_profit_long(self):
        rp = self._pipeline(take_profit_pct=10.0)
        reason = rp.check_position("TEST", 1, 100.0, 111.0, "2024-01-02")
        assert reason == "take_profit"

    def test_take_profit_not_triggered(self):
        rp = self._pipeline(take_profit_pct=10.0)
        reason = rp.check_position("TEST", 1, 100.0, 109.0, "2024-01-02")
        assert reason is None

    # ── trailing-stop ────────────────────────────────────────────────

    def test_trailing_stop_activated(self):
        rp = self._pipeline(trailing_stop_pct=3.0, take_profit_pct=20.0)
        # Price rises to 110 → trailing_high = 110 → stop at 110 * 0.97 = 106.7
        assert rp.check_position("TEST", 1, 100.0, 110.0, "2024-01-02") is None
        # Price drops to 106 → below 106.7 → trailing_stop
        reason = rp.check_position("TEST", 1, 100.0, 106.0, "2024-01-03")
        assert reason == "trailing_stop"

    def test_trailing_stop_disabled(self):
        rp = self._pipeline(trailing_stop_pct=0.0)
        rp.check_position("TEST", 1, 100.0, 110.0, "2024-01-02")
        reason = rp.check_position("TEST", 1, 100.0, 90.0, "2024-01-03")
        # Without trailing, 90.0 triggers stop_loss at 5%, not trailing
        assert reason == "stop_loss"

    # ── daily loss limit ─────────────────────────────────────────────

    def test_daily_loss_not_breached(self):
        rp = self._pipeline(max_daily_loss_pct=3.0)
        # initial_capital=100k, max_daily_loss=3000
        # Simulate daily PnL -2000
        rp._daily_pnl = -2000.0
        assert rp.check_daily_loss() is False

    def test_daily_loss_breached(self):
        rp = self._pipeline(max_daily_loss_pct=3.0)
        rp._daily_pnl = -3500.0
        assert rp.check_daily_loss() is True

    # ── position size ────────────────────────────────────────────────

    def test_position_size_ok(self):
        rp = self._pipeline(max_position_pct=30.0)
        # 30% of 100k = 30k; 20k < 30k
        assert rp.check_position_size(20_000.0, 100_000.0) is True

    def test_position_size_exceeded(self):
        rp = self._pipeline(max_position_pct=30.0)
        assert rp.check_position_size(35_000.0, 100_000.0) is False

    # ── intraday checks ──────────────────────────────────────────────

    def test_intraday_stop_loss_touched(self):
        rp = self._pipeline(stop_loss_pct=5.0)
        # Long at 100, bar low=94 (< 95 stop) → stop_loss at open
        reason, exec_price = rp.check_position_intraday(
            "TEST", 1, 100.0, bar_open=98.0, bar_high=99.0, bar_low=94.0, bar_close=96.0,
        )
        assert reason == "stop_loss"
        assert exec_price is not None

    def test_intraday_no_trigger(self):
        rp = self._pipeline(stop_loss_pct=5.0)
        reason, exec_price = rp.check_position_intraday(
            "TEST", 1, 100.0, bar_open=98.0, bar_high=102.0, bar_low=97.0, bar_close=101.0,
        )
        assert reason is None
        assert exec_price is None

    def test_intraday_take_profit_touched(self):
        rp = self._pipeline(take_profit_pct=10.0)
        # Long at 100, bar high=111 (> 110 target) → take_profit
        reason, exec_price = rp.check_position_intraday(
            "TEST", 1, 100.0, bar_open=105.0, bar_high=111.0, bar_low=104.0, bar_close=110.0,
        )
        assert reason == "take_profit"
        assert exec_price is not None

    # ── priority: stop > trail > target ──────────────────────────────

    def test_intraday_priority_stop_over_target(self):
        rp = self._pipeline(stop_loss_pct=5.0, take_profit_pct=10.0)
        # Both touched: low=93 (<95 stop), high=112 (>110 target) → stop wins
        reason, _ = rp.check_position_intraday(
            "TEST", 1, 100.0, bar_open=100.0, bar_high=112.0, bar_low=93.0, bar_close=105.0,
        )
        assert reason == "stop_loss"

    # ── edge cases ───────────────────────────────────────────────────

    def test_zero_entry_price(self):
        rp = self._pipeline()
        assert rp.check_position("TEST", 1, 0.0, 100.0, "2024-01-02") is None

    def test_negative_entry_price(self):
        rp = self._pipeline()
        assert rp.check_position("TEST", 1, -10.0, 100.0, "2024-01-02") is None

    def test_intraday_zero_entry(self):
        rp = self._pipeline()
        reason, price = rp.check_position_intraday(
            "TEST", 1, 0.0, 100.0, 105.0, 95.0, 100.0,
        )
        assert reason is None
        assert price is None
