"""Tests for services.signal_brief — daily factor signal brief generator."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure services/python/src/ is on sys.path (conftest.py adds
# services/python/, but we need the src/ sub-directory for the
# "from services.xxx" import style used by service modules).
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from services.signal_brief import SignalBriefGenerator


def _make_factor_df(
    dates: pd.DatetimeIndex,
    stocks: list[str],
    seed: int,
    with_noise: bool = False,
) -> pd.DataFrame:
    """Build a (dates × stocks) DataFrame of synthetic factor values."""
    rng = np.random.default_rng(seed)
    data = rng.normal(0, 1, size=(len(dates), len(stocks)))
    if with_noise:
        data += rng.normal(0, 0.1, size=data.shape)
    return pd.DataFrame(data, index=dates, columns=stocks)


def _make_forward_returns(
    dates: pd.DatetimeIndex,
    stocks: list[str],
    base: np.ndarray | None = None,
    noise_scale: float = 0.5,
    seed: int = 999,
) -> pd.DataFrame:
    """Build a (dates × stocks) DataFrame of forward returns, optionally
    correlated with *base* factor values."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, noise_scale, size=(len(dates), len(stocks)))
    if base is not None:
        data = base * 0.3 + noise  # weak positive correlation
    else:
        data = noise
    return pd.DataFrame(data, index=dates, columns=stocks)


@pytest.mark.unit
class TestComputeCrossSectionalIC:
    """IC computation returns correct per-factor values."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.gen = SignalBriefGenerator()
        self.dates = pd.date_range("2024-01-02", periods=20, freq="B")
        self.stocks = [f"{i:06d}.SZ" for i in range(100001, 100011)]

    def test_ic_sign_matches_correlation_direction(self):
        """Positive-correlation factor gets positive IC, negative gets
        negative IC."""
        # Factor a: positively correlated with returns
        fv_pos = _make_factor_df(self.dates, self.stocks, seed=1)
        fr_pos = _make_forward_returns(
            self.dates, self.stocks, base=fv_pos.values, seed=10
        )

        # Factor b: negatively correlated (invert factor values)
        fv_neg = -fv_pos.copy()
        fr_neg = fr_pos.copy()  # same returns

        ic = self.gen.compute_cross_sectional_ic(
            {"factor_pos": fv_pos, "factor_neg": fv_neg},
            fr_pos,
        )
        assert ic["factor_pos"] > 0.0, f"Expected positive IC, got {ic['factor_pos']}"
        assert ic["factor_neg"] < 0.0, f"Expected negative IC, got {ic['factor_neg']}"

    def test_ic_values_bounded_between_minus_one_and_one(self):
        """All IC values must be within [-1, 1]."""
        fv_a = _make_factor_df(self.dates, self.stocks, seed=2)
        fv_b = _make_factor_df(self.dates, self.stocks, seed=3)
        fr = _make_forward_returns(self.dates, self.stocks, seed=4)
        ic = self.gen.compute_cross_sectional_ic(
            {"factor_a": fv_a, "factor_b": fv_b}, fr
        )
        for name, val in ic.items():
            assert -1.0 <= val <= 1.0, f"{name}: IC={val} outside [-1, 1]"

    def test_too_few_dates_returns_zero(self):
        """Less than 3 aligned dates → IC = 0."""
        short_dates = pd.date_range("2024-01-02", periods=2, freq="B")
        fv = _make_factor_df(short_dates, self.stocks, seed=5)
        fr = _make_forward_returns(short_dates, self.stocks, seed=6)
        ic = self.gen.compute_cross_sectional_ic({"f": fv}, fr)
        assert ic["f"] == 0.0

    def test_too_few_stocks_returns_zero(self):
        """Less than 3 stock columns → IC = 0."""
        few_stocks = ["000001.SZ", "000002.SZ"]
        fv = _make_factor_df(self.dates, few_stocks, seed=7)
        fr = _make_forward_returns(self.dates, few_stocks, seed=8)
        ic = self.gen.compute_cross_sectional_ic({"f": fv}, fr)
        assert ic["f"] == 0.0

    def test_empty_input_returns_zero(self):
        """Empty DataFrame returns IC = 0."""
        ic = self.gen.compute_cross_sectional_ic(
            {"f": pd.DataFrame()}, pd.DataFrame()
        )
        assert ic["f"] == 0.0


@pytest.mark.unit
class TestSelectTopFactors:
    """Top N selection by absolute IC."""

    def test_selects_by_absolute_ic_descending(self):
        gen = SignalBriefGenerator()
        ics = pd.Series({"factor_a": 0.05, "factor_b": -0.08, "factor_c": 0.03})
        top = gen.select_top_factors(ics, n=2)
        assert len(top) == 2
        # factor_b has |IC|=0.08, should be first
        assert top[0][0] == "factor_b"
        assert top[0][1] == -0.08
        assert top[1][0] == "factor_a"

    def test_returns_all_when_n_exceeds_available(self):
        gen = SignalBriefGenerator()
        ics = pd.Series({"x": 0.01, "y": 0.02})
        top = gen.select_top_factors(ics, n=5)
        assert len(top) == 2

    def test_empty_series_returns_empty_list(self):
        gen = SignalBriefGenerator()
        top = gen.select_top_factors(pd.Series(dtype=float), n=3)
        assert top == []


@pytest.mark.unit
class TestRenderMarkdown:
    """Markdown brief generation."""

    def test_full_report_with_signals(self):
        gen = SignalBriefGenerator()
        top = [("momentum_20d", 0.042), ("reversal_5d", -0.038)]
        signals = {
            "momentum_20d": ["600519.SH", "000858.SZ"],
            "reversal_5d": ["601318.SH"],
        }
        md = gen.render_markdown(top, signals, date(2024, 6, 23))
        assert "\U0001f4ca" in md
        assert "2024-06-23" in md
        assert "momentum_20d" in md
        assert "600519.SH" in md
        assert "看多" in md
        assert "看空" in md
        assert "AStockPursue Signal Engine" in md

    def test_report_without_signals(self):
        gen = SignalBriefGenerator()
        top = [("rsi_14", -0.055)]
        md = gen.render_markdown(top, signals=None, target_date=date(2024, 1, 15))
        assert "2024-01-15" in md
        assert "rsi_14" in md
        assert "IC=-0.055" in md

    def test_empty_factors_produces_valid_minimal_brief(self):
        gen = SignalBriefGenerator()
        md = gen.render_markdown([], {}, date(2024, 6, 23))
        assert "\U0001f4ca" in md
        assert "2024-06-23" in md
        assert "AStockPursue Signal Engine" in md
        # Should not have any factor entry
        assert "IC=" not in md

    def test_no_target_date_defaults_to_today(self):
        gen = SignalBriefGenerator()
        md = gen.render_markdown([("f1", 0.01)])
        assert "today" in md
