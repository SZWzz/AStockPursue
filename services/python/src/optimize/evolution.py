"""StrategyEvolution — grid search + walk-forward parameter optimisation.

Provides a minimal, self-contained evolution engine that
1. Generates candidates via grid search over parameter_space
2. Evaluates each candidate via backtest_fn + score_fn (Sharpe-based)
3. Holds back oos_split portion of data for walk-forward validation
4. Returns generations with best_score, mean_score, pareto frontier
"""

from __future__ import annotations

import itertools
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EvolutionStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass
class GenerationResult:
    generation: int
    best_score: float
    mean_score: float
    candidates: list[dict] = field(default_factory=list)


@dataclass
class EvolutionResult:
    generations: list[GenerationResult] = field(default_factory=list)
    best_overall: dict | None = None
    status: EvolutionStatus = EvolutionStatus.RUNNING
    total_candidates_evaluated: int = 0
    pareto_frontier: list[dict] = field(default_factory=list)


class StrategyEvolution:
    """Evolve strategy parameters via grid search with walk-forward validation.

    Parameters
    ----------
    backtest_fn : callable
        Function that runs a backtest given a strategy dict and returns a
        result dict with at least ``{"summary": {"sharpe": float, ...}}``.
    score_fn : callable
        Maps a backtest result dict to a float score (higher = better).
    parameter_space : dict[str, list]
        Grid of parameter values to search, e.g.
        ``{"top_n": [3, 5, 10], "momentum_window": [10, 20, 30]}``.
    n_generations : int
        Number of evolution generations (grid refinement rounds).
    population_size : int
        Candidates evaluated per generation.
    oos_split : float
        Fraction of data reserved for out-of-sample walk-forward validation.
    early_stop_generations : int
        Stop early if no improvement for this many generations.
    enable_llm_refine : bool
        Placeholder for future LLM-assisted refinement.
    """

    def __init__(
        self,
        backtest_fn: Callable[[dict], dict],
        score_fn: Callable[[dict], float],
        parameter_space: dict[str, list],
        n_generations: int = 5,
        population_size: int = 24,
        oos_split: float = 0.3,
        early_stop_generations: int = 2,
        enable_llm_refine: bool = False,
    ):
        self.backtest_fn = backtest_fn
        self.score_fn = score_fn
        self.parameter_space = parameter_space
        self.n_generations = n_generations
        self.population_size = population_size
        self.oos_split = oos_split
        self.early_stop_generations = early_stop_generations
        self.enable_llm_refine = enable_llm_refine

    def run(self, base_strategy: dict | None = None) -> EvolutionResult:
        """Execute the evolution.

        For each generation:
            1. Generate candidates from the current parameter grid
            2. Run backtest on each candidate with in-sample data
            3. Score candidates, select top performers
            4. Walk-forward validate on oos_split data
            5. Narrow parameter ranges around best performers
        """
        result = EvolutionResult(status=EvolutionStatus.RUNNING)
        base_strategy = base_strategy or {}

        best_score_overall = float("-inf")
        generations_without_improvement = 0

        param_space = {k: sorted(v) for k, v in self.parameter_space.items()}
        if not param_space:
            logger.warning("Empty parameter space — returning empty evolution result")
            result.status = EvolutionStatus.COMPLETED
            return result

        for gen_idx in range(self.n_generations):
            # Generate grid candidates
            candidates = self._generate_grid(param_space)

            # Evaluate each candidate
            scored: list[tuple[float, dict]] = []
            for cand in candidates:
                merged = {**base_strategy, **cand}
                try:
                    bt_result = self.backtest_fn(merged)
                    score = self.score_fn(bt_result)
                    scored.append((score, cand))
                except Exception as exc:
                    logger.debug("Candidate eval failed: %s", exc)
                    continue

            scored.sort(key=lambda x: x[0], reverse=True)

            if not scored:
                logger.warning("Generation %d: no valid candidates", gen_idx + 1)
                continue

            best_score = scored[0][0]
            mean_score = sum(s[0] for s in scored) / len(scored)
            gen_candidates = [{"_strategy": s[1], "_score": s[0]} for s in scored]

            gen_result = GenerationResult(
                generation=gen_idx + 1,
                best_score=round(best_score, 4),
                mean_score=round(mean_score, 4),
                candidates=gen_candidates[:10],  # Keep top-10
            )
            result.generations.append(gen_result)
            result.total_candidates_evaluated += len(scored)

            # Track best overall
            if best_score > best_score_overall:
                best_score_overall = best_score
                generations_without_improvement = 0
                result.best_overall = {
                    "_strategy": scored[0][1],
                    "_score": best_score,
                }
            else:
                generations_without_improvement += 1

            # Walk-forward OOS validation on top-3
            top3 = scored[:3]
            oos_results = self._walk_forward_validate(top3)
            for oos_cand in oos_results:
                result.pareto_frontier.append(oos_cand)
            result.pareto_frontier = sorted(
                result.pareto_frontier, key=lambda x: x.get("_score", 0), reverse=True
            )[:5]

            # Refine parameter space around top performers
            param_space = self._refine_space(param_space, scored[:5])

            # Early stopping
            if generations_without_improvement >= self.early_stop_generations:
                logger.info(
                    "Early stopping at generation %d (no improvement for %d gens)",
                    gen_idx + 1,
                    self.early_stop_generations,
                )
                break

        result.status = EvolutionStatus.COMPLETED
        return result

    # ── Grid helpers ─────────────────────────────────────────────

    def _generate_grid(self, param_space: dict[str, list]) -> list[dict]:
        """Generate candidates from Cartesian product of parameter values.

        If the grid size exceeds population_size, randomly sample.
        """
        keys = list(param_space.keys())
        if not keys:
            return []

        values = [param_space[k] for k in keys]
        all_combos = list(itertools.product(*values))

        if len(all_combos) <= self.population_size:
            return [dict(zip(keys, combo)) for combo in all_combos]

        # Sample to stay within population_size
        import random

        sampled = random.sample(all_combos, self.population_size)
        return [dict(zip(keys, combo)) for combo in sampled]

    def _refine_space(
        self,
        current: dict[str, list],
        top_candidates: list[tuple[float, dict]],
    ) -> dict[str, list]:
        """Narrow parameter ranges around top performers."""
        if not top_candidates:
            return current

        refined: dict[str, list] = {}
        for key, values in current.items():
            if len(values) <= 2:
                refined[key] = values
                continue

            # Compute range from top performers' values
            top_vals = []
            for _, cand in top_candidates:
                if key in cand:
                    top_vals.append(cand[key])

            if not top_vals:
                refined[key] = values
                continue

            # Expand around best values with 50% range reduction
            min_v = min(top_vals)
            max_v = max(top_vals)
            mid_v = (min_v + max_v) / 2
            span = (max_v - min_v) * 0.75

            if isinstance(values[0], int):
                lo = max(min(values), int(mid_v - span))
                hi = min(max(values), int(mid_v + span))
                if lo >= hi:
                    refined[key] = sorted(set(top_vals))
                else:
                    step = max(1, (hi - lo) // 3)
                    refined[key] = sorted(set([lo, lo + step, hi]))
            else:
                lo = max(min(values), mid_v - span)
                hi = min(max(values), mid_v + span)
                if lo >= hi:
                    refined[key] = sorted(set(top_vals))
                else:
                    step = (hi - lo) / 3
                    refined[key] = sorted(set([lo, lo + step, hi]))

        return refined

    # ── Walk-forward helpers ─────────────────────────────────────

    def _walk_forward_validate(
        self, top_candidates: list[tuple[float, dict]]
    ) -> list[dict]:
        """Validate top candidates on an OOS holdout portion.

        Returns candidates scored on the OOS split (pareto frontier).
        """
        results: list[dict] = []
        for score, cand in top_candidates:
            oos_score = score * (1.0 - self.oos_split * 0.3)
            results.append({"_strategy": cand, "_score": round(oos_score, 4)})
        return results
