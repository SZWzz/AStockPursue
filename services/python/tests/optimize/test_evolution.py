"""Tests for src.optimize.evolution — strategy parameter evolution via grid search."""

from __future__ import annotations

import pytest

from src.optimize.evolution import (
    EvolutionResult,
    EvolutionStatus,
    GenerationResult,
    StrategyEvolution,
)


@pytest.mark.unit
class TestEvolutionStatus:
    def test_enum_values(self):
        assert EvolutionStatus.RUNNING.value == "running"
        assert EvolutionStatus.COMPLETED.value == "completed"
        assert EvolutionStatus.STOPPED.value == "stopped"

    def test_enum_membership(self):
        statuses = list(EvolutionStatus)
        assert len(statuses) == 3


@pytest.mark.unit
class TestGenerationResult:
    def test_dataclass_fields(self):
        gr = GenerationResult(generation=1, best_score=0.85, mean_score=0.72)
        assert gr.generation == 1
        assert gr.best_score == 0.85
        assert gr.mean_score == 0.72
        assert gr.candidates == []

    def test_dataclass_with_candidates(self):
        gr = GenerationResult(
            generation=2,
            best_score=0.9,
            mean_score=0.8,
            candidates=[{"_strategy": {"top_n": 5}, "_score": 0.9}],
        )
        assert len(gr.candidates) == 1


@pytest.mark.unit
class TestEvolutionResult:
    def test_dataclass_fields(self):
        result = EvolutionResult()
        assert result.generations == []
        assert result.best_overall is None
        assert result.status == EvolutionStatus.RUNNING
        assert result.total_candidates_evaluated == 0
        assert result.pareto_frontier == []

    def test_dataclass_custom_values(self):
        gen = GenerationResult(generation=1, best_score=1.0, mean_score=0.9)
        result = EvolutionResult(
            generations=[gen],
            best_overall={"_strategy": {"top_n": 5}, "_score": 1.0},
            status=EvolutionStatus.COMPLETED,
            total_candidates_evaluated=10,
            pareto_frontier=[{"_strategy": {"top_n": 5}, "_score": 0.85}],
        )
        assert len(result.generations) == 1
        assert result.best_overall is not None
        assert result.status == EvolutionStatus.COMPLETED
        assert result.total_candidates_evaluated == 10


@pytest.mark.unit
class TestStrategyEvolutionInit:
    def test_default_parameters(self):
        def bt(s):
            return {"sharpe": 1.0}

        def score(r):
            return r.get("sharpe", 0)

        evo = StrategyEvolution(bt, score, parameter_space={"top_n": [3, 5]})
        assert evo.n_generations == 5
        assert evo.population_size == 24
        assert evo.oos_split == 0.3
        assert evo.early_stop_generations == 2
        assert evo.enable_llm_refine is False

    def test_custom_parameters(self):
        def bt(s):
            return {"sharpe": 1.0}

        def score(r):
            return r.get("sharpe", 0)

        evo = StrategyEvolution(
            bt, score,
            parameter_space={"window": [10, 20]},
            n_generations=3,
            population_size=8,
            oos_split=0.2,
            early_stop_generations=1,
            enable_llm_refine=True,
        )
        assert evo.n_generations == 3
        assert evo.population_size == 8
        assert evo.oos_split == 0.2
        assert evo.early_stop_generations == 1
        assert evo.enable_llm_refine is True


@pytest.mark.unit
class TestGenerateGrid:
    def _make_evo(self, population_size=24):
        def bt(s):
            return {"sharpe": 1.0}

        def score(r):
            return r.get("sharpe", 0)

        return StrategyEvolution(bt, score, parameter_space={}, population_size=population_size)

    def test_produces_cartesian_product(self):
        evo = self._make_evo()
        space = {"a": [1, 2, 3], "b": [10, 20]}
        candidates = evo._generate_grid(space)
        assert len(candidates) == 6  # 3 x 2
        # Each candidate should have both keys
        for c in candidates:
            assert "a" in c
            assert "b" in c

    def test_capped_at_population_size(self):
        evo = self._make_evo(population_size=5)
        space = {
            "a": list(range(10)),
            "b": list(range(10)),
        }  # 100 combinations
        candidates = evo._generate_grid(space)
        assert len(candidates) <= 5

    def test_single_param_still_works(self):
        evo = self._make_evo()
        space = {"window": [5, 10, 20]}
        candidates = evo._generate_grid(space)
        assert len(candidates) == 3

    def test_empty_space_returns_empty(self):
        evo = self._make_evo()
        candidates = evo._generate_grid({})
        assert candidates == []


@pytest.mark.unit
class TestRun:
    def test_run_completes_and_returns_evolution_result(self):
        def bt(s):
            return {"sharpe": 1.5, "total_return": 0.2}

        def score(r):
            return r.get("sharpe", 0)

        evo = StrategyEvolution(
            bt, score,
            parameter_space={"top_n": [3, 5, 10], "momentum_window": [10, 20]},
            n_generations=3,
            population_size=10,
        )
        result = evo.run()
        assert isinstance(result, EvolutionResult)
        assert result.status == EvolutionStatus.COMPLETED
        assert len(result.generations) > 0
        assert result.total_candidates_evaluated > 0

    def test_run_score_fn_receives_backtest_result(self):
        """Verify score_fn is called with backtest result dict."""
        scores_received = []

        def bt(s):
            return {"sharpe": 1.2}

        def score(r):
            scores_received.append(r)
            return r["sharpe"]

        evo = StrategyEvolution(
            bt, score,
            parameter_space={"x": [1, 2]},
            n_generations=1,
            population_size=10,
        )
        evo.run()
        assert len(scores_received) > 0
        for s in scores_received:
            assert "sharpe" in s

    def test_run_early_stopping(self):
        """Verify early stopping when no improvement."""
        call_count = [0]

        def bt(s):
            # Same result every time — no improvement
            return {"sharpe": 1.0}

        def score(r):
            call_count[0] += 1
            return 1.0

        evo = StrategyEvolution(
            bt, score,
            parameter_space={"x": [1, 2]},
            n_generations=10,  # Would run 10 gens but stops early
            population_size=8,
            early_stop_generations=2,
        )
        result = evo.run()
        # Should not complete all 10 generations
        assert len(result.generations) < 10

    def test_run_oos_validation_adds_pareto_frontier(self):
        def bt(s):
            return {"sharpe": 1.5}

        def score(r):
            return r["sharpe"]

        evo = StrategyEvolution(
            bt, score,
            parameter_space={"top_n": [3, 5, 10]},
            n_generations=1,
            population_size=10,
            oos_split=0.3,
        )
        result = evo.run()
        assert len(result.pareto_frontier) > 0
        for entry in result.pareto_frontier:
            assert "_strategy" in entry
            assert "_score" in entry

    def test_run_empty_parameter_space(self):
        def bt(s):
            return {"sharpe": 1.0}

        def score(r):
            return 1.0

        evo = StrategyEvolution(bt, score, parameter_space={})
        result = evo.run()
        assert result.status == EvolutionStatus.COMPLETED
        assert result.generations == []


@pytest.mark.unit
class TestRefineSpace:
    def _make_evo(self):
        def bt(s):
            return {"sharpe": 1.0}

        def score(r):
            return 1.0

        return StrategyEvolution(bt, score, parameter_space={})

    def test_narrows_ranges_around_best(self):
        evo = self._make_evo()
        current = {"window": [10, 20, 30, 40, 50]}
        top = [(0.9, {"window": 25}), (0.85, {"window": 30})]
        refined = evo._refine_space(current, top)
        assert "window" in refined
        # Should be narrowed
        vals = refined["window"]
        assert len(vals) <= len(current["window"])

    def test_preserves_small_spaces(self):
        evo = self._make_evo()
        current = {"mode": ["a", "b"]}
        top = [(0.9, {"mode": "a"})]
        refined = evo._refine_space(current, top)
        # Small space (len <= 2) should be preserved
        assert refined["mode"] == current["mode"]

    def test_empty_top_candidates_returns_original(self):
        evo = self._make_evo()
        current = {"window": [10, 20, 30]}
        refined = evo._refine_space(current, [])
        assert refined == current


@pytest.mark.unit
class TestWalkForwardValidate:
    def test_modifies_scores_with_oos_discount(self):
        def bt(s):
            return {"sharpe": 1.0}

        def score(r):
            return 1.0

        evo = StrategyEvolution(bt, score, parameter_space={}, oos_split=0.3)
        top = [(2.0, {"x": 1}), (1.8, {"x": 2})]
        result = evo._walk_forward_validate(top)
        assert len(result) == 2
        # oos_score = score * (1 - oos_split * 0.3) = score * 0.91
        expected = 2.0 * (1.0 - 0.3 * 0.3)
        assert result[0]["_score"] == pytest.approx(expected, rel=1e-6)
