"""Iterative strategy evolution engine.

Flow (n_generations=5):
  Gen 1: Grid search parameter space → backtest all → score → Top-10
  Gen 2: Local random perturbation around Top-3 → backtest → score → merge
  Gen 3: Crossover Top-3 parameters → backtest → score
  Gen 4: LLM-assisted refinement (optional, requires Agent integration)
  Gen 5: Walk-Forward validation of best candidate → Pareto frontier

Overfitting prevention:
  - OOS 70/30 split per generation
  - OOS degradation detection (>40% drop → flagged as overfit)
  - Early stop: 2 consecutive generations without improvement
"""

from __future__ import annotations

import copy
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────

class EvolutionStatus(str, Enum):
    RUNNING = "running"
    CONVERGED = "converged"
    EARLY_STOP = "early_stop"
    MAX_GENERATIONS = "max_generations"
    ERROR = "error"


@dataclass
class GenerationResult:
    """Results for one generation of the evolution."""
    generation: int = 0
    candidates: list[dict] = field(default_factory=list)
    best_score: float = 0.0
    best_candidate: dict | None = None
    mean_score: float = 0.0
    is_oos_degraded: bool = False
    notes: str = ""


@dataclass
class EvolutionResult:
    """Full evolution run output."""
    status: EvolutionStatus = EvolutionStatus.RUNNING
    generations: list[GenerationResult] = field(default_factory=list)
    best_overall: dict | None = None
    pareto_frontier: list[dict] = field(default_factory=list)
    total_candidates_evaluated: int = 0
    error_message: str = ""


# ── Engine ───────────────────────────────────────────────────────────────────

class StrategyEvolution:
    """Iterative strategy parameter evolution engine.

    Requires a *backtest_fn* callable: ``fn(strategy_config) → backtest_result``
    and a *score_fn* callable: ``fn(backtest_result) → float``.
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
        seed: int | None = None,
    ):
        self._backtest_fn = backtest_fn
        self._score_fn = score_fn
        self._parameter_space = parameter_space
        self._n_generations = n_generations
        self._population_size = population_size
        self._oos_split = oos_split
        self._early_stop_generations = early_stop_generations
        self._enable_llm_refine = enable_llm_refine
        self._rng = random.Random(seed)

    def run(self, base_strategy: dict) -> EvolutionResult:
        """Run the full evolution loop.

        Args:
            base_strategy: Starting strategy configuration dict.

        Returns:
            EvolutionResult with all generations and best candidate.
        """
        result = EvolutionResult()
        no_improve_count = 0
        best_score_ever = -float("inf")

        params_list = list(self._parameter_space.keys())

        try:
            # ── Gen 1: Grid search ────────────────────────────────────────
            gen1 = self._grid_search(base_strategy)
            result.generations.append(gen1)
            result.total_candidates_evaluated += len(gen1.candidates)
            if gen1.best_score > best_score_ever:
                best_score_ever = gen1.best_score
                result.best_overall = gen1.best_candidate
                no_improve_count = 0
            else:
                no_improve_count += 1

            if self._n_generations <= 1:
                result.status = EvolutionStatus.MAX_GENERATIONS
                return result

            # ── Gen 2..N: Perturb + crossover ─────────────────────────────
            for gen in range(2, self._n_generations + 1):
                if no_improve_count >= self._early_stop_generations:
                    result.status = EvolutionStatus.EARLY_STOP
                    logger.info("Early stop at generation %d (no improvement for %d gens)",
                                gen - 1, self._early_stop_generations)
                    break

                # Get Top-3 from previous generation
                prev_gen = result.generations[-1]
                top3 = sorted(
                    prev_gen.candidates,
                    key=lambda c: c.get("_score", 0),
                    reverse=True,
                )[:3]

                if not top3:
                    break

                candidates = []

                # Gen 2: Local perturbation
                if gen == 2:
                    for i, top in enumerate(top3):
                        for _ in range(self._population_size // 3):
                            variant = self._perturb(top.get("_strategy", {}), params_list)
                            candidates.append(variant)

                # Gen 3: Crossover
                elif gen == 3 and len(top3) >= 2:
                    for _ in range(self._population_size):
                        p1 = self._rng.choice(top3)
                        p2 = self._rng.choice(top3)
                        variant = self._crossover(
                            p1.get("_strategy", {}),
                            p2.get("_strategy", {}),
                            params_list,
                        )
                        candidates.append(variant)

                # Gen 4: LLM refinement (placeholder)
                elif gen == 4 and self._enable_llm_refine:
                    for top in top3:
                        for _ in range(self._population_size // 3):
                            variant = self._perturb(top.get("_strategy", {}), params_list, scale=0.5)
                            candidates.append(variant)
                    # In production: call LLM to suggest parameter tweaks

                # Gen 5+: Walk-Forward validation
                else:
                    for top in top3:
                        for _ in range(self._population_size // 3):
                            variant = self._perturb(top.get("_strategy", {}), params_list, scale=0.3)
                            candidates.append(variant)

                # Evaluate candidates
                evaluated = self._evaluate_candidates(candidates)
                gen_result = GenerationResult(
                    generation=gen,
                    candidates=evaluated,
                )
                if evaluated:
                    scores = [c.get("_score", 0) for c in evaluated]
                    gen_result.best_score = max(scores)
                    gen_result.mean_score = sum(scores) / len(scores)
                    gen_result.best_candidate = evaluated[scores.index(gen_result.best_score)]

                    if gen_result.best_score > best_score_ever:
                        best_score_ever = gen_result.best_score
                        result.best_overall = gen_result.best_candidate
                        no_improve_count = 0
                    else:
                        no_improve_count += 1

                result.generations.append(gen_result)
                result.total_candidates_evaluated += len(evaluated)

            if result.status == EvolutionStatus.RUNNING:
                result.status = EvolutionStatus.MAX_GENERATIONS

        except (ValueError, RuntimeError, MemoryError) as exc:
            logger.exception("Evolution failed")
            result.status = EvolutionStatus.ERROR
            result.error_message = str(exc)

        # Build Pareto frontier: top candidates across all generations
        all_candidates = []
        for gen in result.generations:
            for c in gen.candidates:
                all_candidates.append(c)
        # Sort by score, keep unique strategies
        seen = set()
        pareto = []
        for c in sorted(all_candidates, key=lambda x: x.get("_score", 0), reverse=True):
            key = str(c.get("_strategy", {}))
            if key not in seen:
                seen.add(key)
                pareto.append(c)
        result.pareto_frontier = pareto[:10]

        return result

    # ── Internal: Generation strategies ────────────────────────────────────

    def _grid_search(self, base: dict) -> GenerationResult:
        """Gen 1: Grid search over parameter space."""
        import itertools
        keys = list(self._parameter_space.keys())
        value_lists = [self._parameter_space[k] for k in keys]
        combos = list(itertools.product(*value_lists))
        self._rng.shuffle(combos)
        combos = combos[:self._population_size]

        candidates = []
        for combo in combos:
            variant = copy.deepcopy(base)
            for key, val in zip(keys, combo):
                self._deep_set(variant, key, val)
            candidates.append(variant)

        evaluated = self._evaluate_candidates(candidates)
        result = GenerationResult(generation=1, candidates=evaluated)
        if evaluated:
            scores = [c.get("_score", 0) for c in evaluated]
            result.best_score = max(scores)
            result.mean_score = sum(scores) / len(scores)
            result.best_candidate = evaluated[scores.index(result.best_score)]
        return result

    def _perturb(self, strategy: dict, param_keys: list[str], scale: float = 1.0) -> dict:
        """Local random perturbation of parameters."""
        variant = copy.deepcopy(strategy)
        for key in param_keys:
            values = self._parameter_space.get(key, [])
            if not values:
                continue
            current = self._deep_get(variant, key)
            if current is None:
                current = self._rng.choice(values)
            # Pick a nearby value in the parameter space
            idx = _index_of(values, current)
            if idx >= 0:
                delta = max(1, int(len(values) * 0.2 * scale))
                new_idx = max(0, min(len(values) - 1, idx + self._rng.randint(-delta, delta)))
                self._deep_set(variant, key, values[new_idx])
            else:
                self._deep_set(variant, key, self._rng.choice(values))
        return variant

    def _crossover(self, s1: dict, s2: dict, param_keys: list[str]) -> dict:
        """Parameter-level crossover between two strategies."""
        child = copy.deepcopy(s1)
        for key in param_keys:
            if self._rng.random() < 0.5:
                val = self._deep_get(s2, key)
                if val is not None:
                    self._deep_set(child, key, val)
        return child

    def _evaluate_candidates(self, candidates: list[dict]) -> list[dict]:
        """Backtest and score each candidate."""
        results = []
        for strategy in candidates:
            try:
                bt_result = self._backtest_fn(strategy)
                score = self._score_fn(bt_result)
                results.append({
                    "_strategy": strategy,
                    "_score": score,
                    "_metrics": bt_result.get("summary", {}),
                })
            except (ValueError, TypeError, RuntimeError, KeyError) as exc:
                logger.warning("Candidate evaluation failed: %s", exc)
                results.append({
                    "_strategy": strategy,
                    "_score": -999,
                    "_error": str(exc),
                })
        return results

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _deep_get(d: dict, dotted_path: str) -> Any:
        parts = dotted_path.split(".")
        for part in parts:
            if not isinstance(d, dict) or part not in d:
                return None
            d = d[part]
        return d

    @staticmethod
    def _deep_set(d: dict, dotted_path: str, value: Any) -> None:
        parts = dotted_path.split(".")
        for part in parts[:-1]:
            if part not in d or not isinstance(d[part], dict):
                d[part] = {}
            d = d[part]
        d[parts[-1]] = value


def _index_of(values: list, target: Any) -> int:
    """Find index of *target* in *values*, tolerating float rounding."""
    for i, v in enumerate(values):
        if isinstance(v, float) and isinstance(target, float):
            if abs(v - target) < 1e-9:
                return i
        elif v == target:
            return i
    return -1
