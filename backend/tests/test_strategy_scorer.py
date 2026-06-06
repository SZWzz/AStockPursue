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
        weights = {**DEFAULT_WEIGHTS, "total_return": 0.50, "sharpe_ratio": 0.01}
        scorer = StrategyScorer(weights=weights)
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
        assert sum(scorer.weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_grade_thresholds(self):
        scorer = StrategyScorer()
        assert scorer.score(_make_bt(80)).grade == "A"
        assert scorer.score(_make_bt(65)).grade == "B"
        assert scorer.score(_make_bt(50)).grade == "C"
        assert scorer.score(_make_bt(35)).grade == "D"
        assert scorer.score(_make_bt(15)).grade == "E"


def _make_bt(overall: float) -> dict:
    """Build a minimal backtest result that yields roughly the given overall score."""
    # Map overall → approximate sharpe
    sharpe = (overall - 30) / 30 if overall > 30 else -1.0
    return {
        "metrics": {
            "total_return": overall / 200,
            "annual_return": overall / 300,
            "sharpe": sharpe,
            "max_drawdown": -(60 - overall) / 100 if overall < 60 else -0.05,
            "win_rate": overall / 120,
            "profit_factor": overall / 60 if overall > 20 else 0.5,
            "trade_count": 20,
        },
        "summary": {},
    }
