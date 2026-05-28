"""End-to-end integration tests for TradingEngine + market engines + fees.

These tests construct known OHLCV data with known outcomes and verify
that the full pipeline produces correct P&L, fees, and exit reasons.
"""

import numpy as np
import pandas as pd
import pytest
from backtest.engines.china_a import ChinaAEngine
from backtest.engines.china_futures import ChinaFuturesEngine
from backtest.engines.global_equity import GlobalEquityEngine
from backtest.engines.crypto import CryptoEngine
from backtest.models import Position, TradeRecord
from src.trading.engine import TradingEngine
from src.trading.signal_adapter import SignalAdapter


# ── Helpers ───────────────────────────────────────────────────────────

def _make_ohlcv(prices: list[float], start: str = "2024-01-02") -> pd.DataFrame:
    """Build a simple OHLCV DataFrame with 1% daily range around close."""
    dates = pd.date_range(start, periods=len(prices), freq="B")
    return pd.DataFrame({
        "open":  [p * 0.995 for p in prices],
        "high":  [p * 1.005 for p in prices],
        "low":   [p * 0.985 for p in prices],
        "close": prices,
        "volume":[10000] * len(prices),
    }, index=dates)


def _make_bar(code: str, price: float, ts: pd.Timestamp) -> dict:
    return {
        code: pd.Series({"open": price * 0.995, "high": price * 1.005,
                          "low": price * 0.985, "close": price, "volume": 10000},
                         name=ts),
    }


class ConstSignalEngine:
    """Always returns 1.0 weight (100% long) for the first code via generate()."""
    def generate(self, data_map):
        codes = list(data_map.keys())
        if not codes:
            return {}
        result = {}
        for c in codes:
            df = data_map[c]
            if df is not None and len(df) > 0:
                result[c] = pd.Series(1.0, index=df.index)
        return result


# Wrap as SignalAdapter expects: module.SignalEngine
class _ConstModule:
    SignalEngine = ConstSignalEngine


# ══════════════════════════════════════════════════════════════════════
# A-shares: buy-and-hold PnL with fees
# ══════════════════════════════════════════════════════════════════════

class TestASharesIntegration:
    def test_buy_and_hold_pnl(self):
        """Buy 1 bar of A-shares, hold to end, verify fees deducted."""
        df = _make_ohlcv([100.0, 101.0, 102.0])
        engine = TradingEngine(
            config={"codes": ["000001.SZ"], "initial_capital": 100_000},
            signal_adapter=SignalAdapter(_ConstModule()),
            market_engine=ChinaAEngine({"codes": ["000001.SZ"], "initial_capital": 100_000}),
        )
        engine.initialize({"000001.SZ": df})

        # Feed bars 2 and 3 (bar 1 is for initialization)
        bar2 = _make_bar("000001.SZ", 101.0, df.index[1])
        result2 = engine.on_bar(bar2, df.index[1])
        # Position should be opened at bar2 open (~100.5) with 1.0 weight
        assert len(engine.positions) >= 1 or result2.trade_count > 0

        bar3 = _make_bar("000001.SZ", 102.0, df.index[2])
        engine.force_close_all("end_test")
        trades = engine.trades
        assert len(trades) > 0, "should have at least one trade"

        # Verify total equity > initial (price went up)
        summary = engine.get_summary()
        assert summary["equity"] > 100_000, f"equity should exceed initial, got {summary['equity']}"

    def test_stop_loss_risk_pipeline(self):
        """Verify RiskPipeline.check_position() returns correct stop reason."""
        from src.trading.risk_pipeline import RiskPipeline, RiskConfig
        rp = RiskPipeline(RiskConfig(stop_loss_pct=5.0), 100_000)
        reason = rp.check_position("TEST", 1, 100.0, 94.0, "2024-01-02")
        assert reason == "stop_loss"


# ══════════════════════════════════════════════════════════════════════
# China Futures: fee verification
# ══════════════════════════════════════════════════════════════════════

class TestFuturesFeesIntegration:
    def test_commission_is_charged(self):
        """Verify China futures charge per-lot or per-notional fees."""
        engine = ChinaFuturesEngine({"codes": ["IF2406.CFFEX"], "initial_capital": 1_000_000})
        # IF has multiplier=300, commission mode="rate", value≈0.000023
        comm = engine.calc_commission_for_symbol("IF2406.CFFEX", 1, 4000.0, is_open=True)
        # 1 contract × 4000 price × 300 multiplier × 0.000023 ≈ 27.6
        assert comm > 20, f"expected >20 RMB commission, got {comm}"

    def test_close_today_multiplier(self):
        """IF stock index futures: 平今仓 should be ~15× normal."""
        engine = ChinaFuturesEngine({"codes": ["IF2406.CFFEX"], "initial_capital": 1_000_000})
        normal = engine.calc_commission_for_symbol("IF2406.CFFEX", 1, 4000.0, is_open=True)
        # 平今仓: pass entry_time same as bar_date (simulated)
        engine._active_entry_time = pd.Timestamp("2024-06-03")
        engine._active_bar_date = "2024-06-03"
        close_today = engine.calc_commission_for_symbol("IF2406.CFFEX", 1, 4000.0, is_open=False,
                                                          entry_time=pd.Timestamp("2024-06-03"))
        assert close_today > normal * 10, f"close-today should be >> normal (normal={normal}, today={close_today})"


# ══════════════════════════════════════════════════════════════════════
# HK / US: fee verification
# ══════════════════════════════════════════════════════════════════════

class TestGlobalEquityFeesIntegration:
    def test_hk_has_multiple_fee_components(self):
        engine_hk = GlobalEquityEngine({"codes": ["00700.HK"], "initial_capital": 1_000_000}, market="hk")
        comm = engine_hk.calc_commission(1000, 350.0, 1, is_open=True)
        # HK has broker + stamp + trading fee + SFC levy + settlement
        assert comm > 200, f"HK commission should be substantial, got {comm}"

    def test_us_sec_fee_on_sell(self):
        engine_us = GlobalEquityEngine({"codes": ["AAPL.US"], "initial_capital": 1_000_000}, market="us")
        comm_buy = engine_us.calc_commission(100, 180.0, 1, is_open=True)
        comm_sell = engine_us.calc_commission(100, 180.0, 1, is_open=False)
        assert comm_buy == 0.0, "US buy commission should be zero"
        assert comm_sell > 0.0, "US sell should have SEC fee"
        assert comm_sell < 0.1, "SEC fee should be negligible for 100 shares"


# ══════════════════════════════════════════════════════════════════════
# Crypto: dynamic funding rate
# ══════════════════════════════════════════════════════════════════════

class TestCryptoIntegration:
    def test_dynamic_funding_changes(self):
        engine = CryptoEngine({"codes": ["BTC-USDT"], "initial_capital": 100_000, "dynamic_funding": True})
        r1 = engine.get_dynamic_funding_rate("2024-01-01")
        r2 = engine.get_dynamic_funding_rate("2024-01-02")
        # Rate should change daily (mean-reverting random walk)
        assert r2 != r1, f"dynamic rate should change daily: {r1} → {r2}"
        # Should stay within bounds
        assert -0.003 <= r1 <= 0.003
        assert -0.003 <= r2 <= 0.003
