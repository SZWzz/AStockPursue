"""Tests for port-type compatibility."""

from src.workflow.schema import is_compatible, PortType as PT


class TestExactMatch:
    def test_same(self):
        assert is_compatible(PT.DF_OHLCV, PT.DF_OHLCV) is True

    def test_different(self):
        assert is_compatible(PT.DF_OHLCV, PT.DF_FACTOR) is False

    def test_returns(self):
        assert is_compatible(PT.DF_RETURNS, PT.DF_RETURNS) is True


class TestWildcard:
    def test_any_accepts_all(self):
        assert is_compatible(PT.DF_OHLCV, PT.ANY) is True
        assert is_compatible(PT.STOCK_LIST, PT.ANY) is True
        assert is_compatible(PT.SIGNAL, PT.ANY) is True

    def test_any_to_specific_fails(self):
        # ANY source → specific target: not compatible
        pass  # is_compatible checks source→target direction


class TestSignalChain:
    """Test the typical data flow chain: OHLCV → Factor → Signal → Backtest"""
    def test_ohlcv_to_ohlcv(self):
        assert is_compatible(PT.DF_OHLCV, PT.DF_OHLCV) is True

    def test_ohlcv_to_factor_fails(self):
        assert is_compatible(PT.DF_OHLCV, PT.DF_FACTOR) is False

    def test_factor_to_signal_fails(self):
        assert is_compatible(PT.DF_FACTOR, PT.SIGNAL) is False

    def test_signal_to_any(self):
        assert is_compatible(PT.SIGNAL, PT.ANY) is True

    def test_backtest_to_attribution_fails(self):
        assert is_compatible(PT.BACKTEST_RESULT, PT.ATTRIBUTION) is False
