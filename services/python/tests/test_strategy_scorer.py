"""Tests for StrategyScorer — multi-factor strategy scoring."""

import pytest
from src.services.strategy_scorer import StrategyScorer, ScoreResult, DEFAULT_WEIGHTS


class TestStrategyScorer:
    """Unit tests for strategy scoring logic."""

    def test_empty_backtest(self):
        scorer = StrategyScorer()
        result = scorer.score({"metrics": {}, "summary": {}})
        assert isinstance(result, ScoreResult)
        assert 0 <= result.overall <= 100
        assert result.grade in ("A", "B", "C", "D", "E")

    def test_good_strategy_scores_high(self):
        scorer = StrategyScorer()
        bt = {
            "metrics": {
                "total_return": 0.50,
                "annual_return": 0.35,
                "sharpe": 2.5,
                "max_drawdown": -0.10,
                "win_rate": 0.65,
                "profit_factor": 2.2,
                "trade_count": 50,
            },
            "summary": {},
            "equity_curve": [
                {"equity": 100000 + i * 200} for i in range(100)
            ],
        }
        result = scorer.score(bt)
        assert result.overall > 60, f"Expected high score, got {result.overall}"
        assert result.grade in ("A", "B")

    def test_poor_strategy_scores_low(self):
        scorer = StrategyScorer()
        bt = {
            "metrics": {
                "total_return": -0.30,
                "annual_return": -0.25,
                "sharpe": -1.0,
                "max_drawdown": -0.50,
                "win_rate": 0.25,
                "profit_factor": 0.5,
                "trade_count": 3,
            },
            "summary": {},
        }
        result = scorer.score(bt)
        assert result.overall < 40, f"Expected low score, got {result.overall}"

    def test_trade_count_penalty(self):
        scorer = StrategyScorer()
        bt_base = {
            "metrics": {
                "total_return": 0.20, "annual_return": 0.15,
                "sharpe": 1.5, "max_drawdown": -0.10,
                "win_rate": 0.55, "profit_factor": 1.5,
            },
            "summary": {},
        }

        # Few trades ⇒ penalty
        bt_few = {**bt_base, "metrics": {**bt_base["metrics"], "trade_count": 3}}
        result_few = scorer.score(bt_few)

        bt_many = {**bt_base, "metrics": {**bt_base["metrics"], "trade_count": 30}}
        result_many = scorer.score(bt_many)

        assert result_few.overall < result_many.overall, \
            f"Few trades ({result_few.overall}) should score lower than many ({result_many.overall})"

    def test_rank_sorts_descending(self):
        scorer = StrategyScorer()
        candidates = [
            {"name": "A", "score": {"overall": 80}},
            {"name": "B", "score": {"overall": 60}},
            {"name": "C", "score": {"overall": 90}},
        ]
        ranked = scorer.rank(candidates)
        assert ranked[0]["name"] == "C"
        assert ranked[0]["rank"] == 1
        assert ranked[2]["name"] == "B"
        assert ranked[2]["rank"] == 3

    def test_custom_weights(self):
        # Ensure total weight sums to ~1.0 by normalising
        raw = {"total_return": 0.50, "annual_return": 0.10, "sharpe_ratio": 0.05,
               "profit_factor": 0.10, "win_rate": 0.05, "max_drawdown": 0.15,
               "equity_stability": 0.05}
        scorer = StrategyScorer(weights=raw)
        bt = {
            "metrics": {
                "total_return": 1.0, "annual_return": 0.50,
                "sharpe": 0.0, "max_drawdown": -0.20,
                "win_rate": 0.50, "profit_factor": 1.5,
                "trade_count": 20,
            },
            "summary": {},
        }
        result = scorer.score(bt)
        assert result.overall > 0

    def test_grade_thresholds(self):
        scorer = StrategyScorer()
        # Exceptional strategy → A
        grade_a = scorer.score(_make_bt(total_return=1.0, sharpe=3.0, max_dd=-0.05, win_rate=0.75, trades=100))
        assert grade_a.grade == "A", f"Expected A, got {grade_a.grade} ({grade_a.overall})"
        # Good strategy → B or C (depends on weight distribution)
        grade_b = scorer.score(_make_bt(total_return=0.5, sharpe=2.0, max_dd=-0.10, win_rate=0.60, trades=50))
        assert grade_b.grade in ("A", "B"), f"Expected A/B, got {grade_b.grade} ({grade_b.overall})"
        # Mediocre strategy → C/D/E
        grade_c = scorer.score(_make_bt(total_return=0.05, sharpe=0.3, max_dd=-0.30, win_rate=0.40, trades=10))
        assert grade_c.grade in ("C", "D", "E"), f"Expected C/D/E, got {grade_c.grade} ({grade_c.overall})"
        # Terrible strategy → E
        grade_e = scorer.score(_make_bt(total_return=-0.50, sharpe=-2.0, max_dd=-0.70, win_rate=0.20, trades=2))
        assert grade_e.grade == "E", f"Expected E, got {grade_e.grade} ({grade_e.overall})"


def _make_bt(
    total_return: float = 0.1, sharpe: float = 1.0, max_dd: float = -0.15,
    win_rate: float = 0.50, trades: int = 20,
) -> dict:
    """Build a minimal backtest result with realistic metric values."""
    return {
        "metrics": {
            "total_return": total_return,
            "annual_return": total_return * 0.8,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "profit_factor": max(0.3, sharpe * 0.6 + 0.5),
            "trade_count": trades,
        },
        "summary": {},
    }
