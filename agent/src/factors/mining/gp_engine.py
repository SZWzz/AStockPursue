"""Genetic Programming Evolution Engine.

Orchestrates the evolution of alpha factor expressions through:
    - Population initialisation (ramped half-and-half)
    - Fitness evaluation (IC / rank-IC / Sharpe + complexity penalty)
    - Tournament selection
    - Subtree crossover + point mutation
    - Elitism preservation
    - SSE progress streaming for live frontend updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from src.factors.mining.expression_tree import (
    ExpressionNode,
    ExpressionTree,
    FEATURE_IDS,
    MAX_COMPLEXITY,
)
from src.factors.mining.fitness import (
    compute_forward_returns,
    evaluate_fitness,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class GPEvolutionConfig(BaseModel):
    """Configuration for a GP evolution run."""

    population_size: int = Field(default=100, ge=10, le=500)
    generations: int = Field(default=50, ge=5, le=200)
    tournament_size: int = Field(default=7, ge=2, le=20)
    crossover_prob: float = Field(default=0.7, ge=0.0, le=1.0)
    mutation_prob: float = Field(default=0.2, ge=0.0, le=1.0)
    elitism_count: int = Field(default=2, ge=0, le=10)
    fitness_metric: Literal["ic_mean", "rank_ic", "sharpe"] = "ic_mean"
    complexity_penalty: Literal["aic", "bic", "none"] = "bic"
    train_start: str = "2023-01-01"
    train_end: str = "2024-12-31"
    test_start: str = "2025-01-01"
    test_end: str = "2025-12-31"
    universe: list[str] = Field(default_factory=list, description="Stock codes to include")
    max_workers: int = Field(default=4, ge=1, le=16)
    # Walk-forward validation
    walk_forward_windows: int = Field(default=3, ge=1, le=10, description="Number of rolling OOS windows for fitness evaluation")
    oos_stability_weight: float = Field(default=0.5, ge=0.0, le=2.0, description="Penalty weight on std of OOS IC (higher = prefer stable factors)")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GPIndividual:
    """A single individual in the GP population."""

    tree: ExpressionTree
    train_fitness: float = 0.0
    test_ic: float = 0.0
    test_ir: float = 0.0
    oos_ic_per_window: list[float] = field(default_factory=list)
    adjusted_p_value: float | None = None
    is_statistically_significant: bool = False

    @property
    def formula(self) -> str:
        return self.tree.to_formula()

    @property
    def complexity(self) -> int:
        return self.tree.complexity()

    def to_dict(self) -> dict[str, Any]:
        return {
            "formula": self.formula,
            "expression_json": self.tree.to_dict(),
            "train_fitness": self.train_fitness,
            "test_ic": self.test_ic,
            "test_ir": self.test_ir,
            "oos_ic_per_window": self.oos_ic_per_window,
            "adjusted_p_value": self.adjusted_p_value,
            "is_statistically_significant": self.is_statistically_significant,
            "complexity": self.complexity,
        }


@dataclass
class GenerationStats:
    """Statistics for one generation of evolution."""

    generation: int
    best_fitness: float
    mean_fitness: float
    std_fitness: float
    best_ic: float
    diversity: float  # mean pairwise tree distance


@dataclass
class GPRunResult:
    """Final result of a GP evolution run."""

    job_id: str
    best_individuals: list[GPIndividual]
    generation_history: list[GenerationStats]
    best_test_ic: float
    runtime_seconds: float
    config: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evolution Engine
# ---------------------------------------------------------------------------

class GPEvolution:
    """Orchestrates genetic programming evolution for alpha factor discovery."""

    def __init__(
        self,
        config: GPEvolutionConfig,
        data_provider: Any | None = None,
    ) -> None:
        self.config = config
        self.rng = random.Random()
        self._data_provider = data_provider

        # Internal state
        self._population: list[GPIndividual] = []
        self._generation_history: list[GenerationStats] = []
        self._train_returns: pd.DataFrame | None = None
        self._test_returns: pd.DataFrame | None = None
        self._train_panel: dict[str, pd.DataFrame] = {}
        self._test_panel: dict[str, pd.DataFrame] = {}

        # Data source tracking
        self.data_source: str = "unknown"  # "real" | "mock"
        self.data_source_detail: str = ""

        # Elite lineage tracking: formula_hash -> {first_seen_gen, last_seen_gen, best_fitness, representative}
        self._elite_tracker: dict[str, dict[str, Any]] = {}

        # SSE progress queue
        self._progress_queue: queue.Queue[dict[str, Any]] = queue.Queue()

        # Cancellation
        self._cancelled = threading.Event()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        """Load OHLCV data for the configured universe from DataStore.

        Sets self.data_source to 'real' on success, 'mock' on fallback.
        Emits data source status via SSE so the frontend can show a badge.
        """
        try:
            from backtest.data_store import get_data_store
            store = get_data_store()
        except Exception as e:
            logger.warning("DataStore unavailable, using mock data: %s", e)
            self.data_source = "mock"
            self.data_source_detail = f"DataStore import failed: {e}"
            self._emit_progress("data_source", {"source": "mock", "detail": self.data_source_detail})
            self._load_mock_data()
            return

        universe = self.config.universe
        if not universe:
            # Default: use some A-share stocks
            universe = [
                "000001.SZ", "000002.SZ", "000858.SZ", "002415.SZ",
                "600000.SH", "600036.SH", "600519.SH", "601318.SH",
                "600276.SH", "300750.SZ",
            ]

        train_start = self.config.train_start
        train_end = self.config.train_end
        test_start = self.config.test_start
        test_end = self.config.test_end

        full_start = min(train_start, test_start)
        full_end = max(train_end, test_end)

        try:
            data_map = store.get_multi_ohlcv(universe, full_start, full_end, interval="1D")

            if not data_map:
                logger.warning("No data returned from DataStore, using mock data")
                self.data_source = "mock"
                self.data_source_detail = f"DataStore returned empty for {len(universe)} symbols"
                self._emit_progress("data_source", {"source": "mock", "detail": self.data_source_detail})
                self._load_mock_data()
                return

            # Build panel: {col_name -> wide DataFrame}
            panels: dict[str, dict[str, pd.DataFrame]] = {"train": {}, "test": {}}
            for col in ["open", "high", "low", "close", "volume"]:
                dfs = []
                for sym in universe:
                    df = data_map.get(sym)
                    if df is not None and col in df.columns:
                        if "date" in df.columns:
                            s = df.set_index("date")[col].rename(sym)
                        else:
                            s = df[col].rename(sym)
                        dfs.append(s)
                if dfs:
                    combined = pd.concat(dfs, axis=1)
                    combined.index = pd.to_datetime(combined.index)
                    combined = combined.sort_index()
                    train_mask = (combined.index >= train_start) & (combined.index <= train_end)
                    test_mask = (combined.index >= test_start) & (combined.index <= test_end)
                    panels["train"][col] = combined[train_mask].astype(np.float64)
                    panels["test"][col] = combined[test_mask].astype(np.float64)

            self._train_panel = panels["train"]
            self._test_panel = panels["test"]

            # Compute forward returns
            if "close" in self._train_panel:
                self._train_returns = compute_forward_returns(self._train_panel["close"], period=1)
            if "close" in self._test_panel:
                self._test_returns = compute_forward_returns(self._test_panel["close"], period=1)

            train_bars = len(self._train_panel.get("close", pd.DataFrame()))
            test_bars = len(self._test_panel.get("close", pd.DataFrame()))
            n_stocks = len(self._train_panel.get("close", pd.DataFrame()).columns) if train_bars > 0 else 0

            self.data_source = "real"
            self.data_source_detail = f"{n_stocks} stocks, train={train_bars} bars, test={test_bars} bars"
            self._emit_progress("data_source", {
                "source": "real",
                "detail": self.data_source_detail,
                "n_stocks": n_stocks,
                "train_bars": train_bars,
                "test_bars": test_bars,
            })

            logger.info("Loaded REAL data: train=%d bars, test=%d bars, %d stocks",
                         train_bars, test_bars, n_stocks)
        except Exception as e:
            logger.warning("Failed to load real data (%s), using mock data", e)
            self.data_source = "mock"
            self.data_source_detail = f"Data loading error: {e}"
            self._emit_progress("data_source", {"source": "mock", "detail": self.data_source_detail})
            self._load_mock_data()

    def _load_mock_data(self) -> None:
        """Generate synthetic OHLCV data for testing/demo purposes."""
        self.data_source = "mock"
        if not self.data_source_detail:
            self.data_source_detail = "Synthetic random-walk data (for demo only)"
        dates_train = pd.date_range(self.config.train_start, self.config.train_end, freq="B")
        dates_test = pd.date_range(self.config.test_start, self.config.test_end, freq="B")
        universe = self.config.universe or [f"STOCK_{i:03d}" for i in range(20)]

        rng = np.random.RandomState(42)
        for period_name, dates in [("train", dates_train), ("test", dates_test)]:
            n = len(dates)
            panel = {}
            close = pd.DataFrame(rng.randn(n, len(universe)).cumsum(axis=0) + 100,
                                index=dates, columns=universe, dtype=np.float64)
            panel["close"] = close
            panel["open"] = close.shift(1).fillna(close) * (1 + rng.randn(n, len(universe)) * 0.005)
            panel["high"] = pd.DataFrame(
                np.maximum(panel["open"].to_numpy(), close.to_numpy()) * (1 + np.abs(rng.randn(n, len(universe))) * 0.01),
                index=dates, columns=universe, dtype=np.float64)
            panel["low"] = pd.DataFrame(
                np.minimum(panel["open"].to_numpy(), close.to_numpy()) * (1 - np.abs(rng.randn(n, len(universe))) * 0.01),
                index=dates, columns=universe, dtype=np.float64)
            panel["volume"] = pd.DataFrame(np.abs(rng.randn(n, len(universe))) * 1e6,
                                           index=dates, columns=universe, dtype=np.float64)

            if period_name == "train":
                self._train_panel = panel
                self._train_returns = compute_forward_returns(panel["close"], period=1)
            else:
                self._test_panel = panel
                self._test_returns = compute_forward_returns(panel["close"], period=1)

    # ------------------------------------------------------------------
    # Population management
    # ------------------------------------------------------------------

    def initialize_population(self) -> None:
        """Generate initial population with ramped half-and-half."""
        self._population = []
        for _ in range(self.config.population_size):
            tree = ExpressionTree.random(rng=self.rng, max_depth=3)
            # Enforce complexity limit
            while tree.complexity() > MAX_COMPLEXITY:
                tree = ExpressionTree.random(rng=self.rng, max_depth=2)
            self._population.append(GPIndividual(tree=tree))

    def _get_walk_forward_windows(self) -> list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
        """Split the train period into in-sample / out-of-sample window pairs.

        Returns list of (train_idx, oos_idx) tuples, where train_idx is the
        index slice used for fitting and oos_idx for evaluation (held-out).
        """
        import numpy as np
        n_windows = max(1, self.config.walk_forward_windows)

        if self._train_returns is None or self._train_returns.empty:
            return [(
                pd.DatetimeIndex([], freq="B"),
                pd.DatetimeIndex([], freq="B"),
            )]

        all_dates = self._train_returns.index.sort_values()
        n = len(all_dates)
        if n < n_windows * 20:
            # Not enough data for walk-forward; use single 80/20 split
            split = max(10, int(n * 0.8))
            return [(all_dates[:split], all_dates[split:])]

        windows: list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]] = []
        # Rolling windows: each window uses ~60% of data for training, next ~20% for OOS
        window_step = max(1, n // (n_windows * 2))

        for w in range(n_windows):
            train_end = n - (n_windows - w) * window_step
            train_start = max(0, train_end - int(window_step * 3))
            oos_end = min(n, train_end + window_step)
            oos_start = train_end

            if train_end - train_start >= 10 and oos_end - oos_start >= 5:
                windows.append((
                    all_dates[train_start:train_end],
                    all_dates[oos_start:oos_end],
                ))

        return windows or [(all_dates[: max(10, int(n * 0.8))], all_dates[max(10, int(n * 0.8)) :])]

    def _evaluate_individual_wf(self, ind: GPIndividual) -> tuple[float, list[float]]:
        """Walk-forward evaluation: compute IC in each window, return (mean_IC - w * std_IC, per_window_ICs)."""
        windows = self._get_walk_forward_windows()

        if not windows or self._train_returns is None:
            return 0.0, []

        from src.factors.mining.fitness import ic_fitness

        compute_fn = ind.tree.to_callable()
        window_ics: list[float] = []

        for train_idx, oos_idx in windows:
            if len(train_idx) < 10 or len(oos_idx) < 5:
                continue

            try:
                # "Fit" = compute factor values on train period
                train_panel_slice = {
                    k: v.loc[v.index.intersection(train_idx)] if not v.empty else v
                    for k, v in self._train_panel.items()
                }
                # "Predict" = compute on OOS period
                oos_panel_slice = {
                    k: v.loc[v.index.intersection(oos_idx)] if not v.empty else v
                    for k, v in self._train_panel.items()
                }

                # Factor values on OOS period
                fv = compute_fn(oos_panel_slice)
                if fv.empty:
                    continue

                oos_returns = self._train_returns.loc[self._train_returns.index.intersection(oos_idx)]
                common_idx = fv.index.intersection(oos_returns.index)
                common_cols = fv.columns.intersection(oos_returns.columns)

                if len(common_idx) >= 5 and len(common_cols) >= 3:
                    ic = ic_fitness(
                        fv.loc[common_idx, common_cols],
                        oos_returns.loc[common_idx, common_cols],
                    )
                    window_ics.append(ic)
            except Exception:
                continue

        if not window_ics:
            return 0.0, []

        mean_ic = float(np.mean(window_ics))
        std_ic = float(np.std(window_ics, ddof=1)) if len(window_ics) > 1 else 0.0
        fitness = mean_ic - self.config.oos_stability_weight * std_ic

        # Also apply complexity penalty
        n_samples = len(self._train_returns) * len(self._train_returns.columns)
        from src.factors.mining.fitness import complexity_penalty
        penalty = complexity_penalty(ind.complexity, max(n_samples, 100), self.config.complexity_penalty)
        fitness -= penalty

        return float(fitness), window_ics

    def _evaluate_individual(self, ind: GPIndividual) -> float:
        """Evaluate a single individual's fitness using walk-forward cross-validation."""
        fitness, window_ics = self._evaluate_individual_wf(ind)
        ind.oos_ic_per_window = window_ics

        # Fallback to traditional single-split if walk-forward gives no signal
        if fitness == 0.0 and window_ics == []:
            try:
                compute_fn = ind.tree.to_callable()
                factor_values = compute_fn(self._train_panel)
                if not factor_values.empty and self._train_returns is not None:
                    common_idx = factor_values.index.intersection(self._train_returns.index)
                    common_cols = factor_values.columns.intersection(self._train_returns.columns)
                    if len(common_idx) >= 10 and len(common_cols) >= 3:
                        n_samples = len(common_idx) * len(common_cols)
                        fitness = evaluate_fitness(
                            factor_values.loc[common_idx, common_cols],
                            self._train_returns.loc[common_idx, common_cols],
                            n_nodes=ind.complexity,
                            n_samples=n_samples,
                            metric=self.config.fitness_metric,
                            penalty=self.config.complexity_penalty,
                        )
            except Exception:
                pass

        ind.train_fitness = float(fitness)
        return float(fitness)

    def evaluate_population(self, parallel: bool = True) -> list[float]:
        """Evaluate all individuals in the population. Returns fitnesses."""
        if not self._population:
            return []

        if parallel and len(self._population) > 10:
            fitnesses: list[float] = [0.0] * len(self._population)
            max_workers = min(self.config.max_workers, len(self._population))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._evaluate_individual, ind): i
                    for i, ind in enumerate(self._population)
                }
                for future in as_completed(futures):
                    i = futures[future]
                    try:
                        fitnesses[i] = future.result(timeout=120)
                    except Exception as e:
                        logger.debug("Fitness eval timed out or failed: %s", e)
                        fitnesses[i] = 0.0
            return fitnesses

        return [self._evaluate_individual(ind) for ind in self._population]

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _tournament_select(
        self,
        fitnesses: list[float],
        k: int | None = None,
    ) -> int:
        """Tournament selection: pick the best among k randomly chosen individuals."""
        k = k or self.config.tournament_size
        candidates = self.rng.sample(range(len(self._population)), min(k, len(self._population)))
        best_idx = max(candidates, key=lambda i: fitnesses[i])
        return best_idx

    # ------------------------------------------------------------------
    # Evolution loop
    # ------------------------------------------------------------------

    def evolve(self, fitnesses: list[float]) -> list[GPIndividual]:
        """Produce the next generation through selection, crossover, mutation, elitism."""
        new_pop: list[GPIndividual] = []

        # Elitism
        if self.config.elitism_count > 0:
            sorted_idx = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True)
            for idx in sorted_idx[: self.config.elitism_count]:
                new_pop.append(GPIndividual(
                    tree=ExpressionTree(self._population[idx].tree.root.copy()),
                    train_fitness=fitnesses[idx],
                ))

        # Fill rest with offspring
        while len(new_pop) < self.config.population_size:
            p1_idx = self._tournament_select(fitnesses)
            p2_idx = self._tournament_select(fitnesses)

            parent1 = self._population[p1_idx]
            parent2 = self._population[p2_idx]

            child_tree: ExpressionTree
            if self.rng.random() < self.config.crossover_prob:
                a, b = parent1.tree.crossover(parent2.tree, rng=self.rng)
                child_tree = a if self.rng.random() < 0.5 else b
            else:
                child_tree = ExpressionTree(parent1.tree.root.copy())

            # Mutation
            if self.rng.random() < self.config.mutation_prob:
                child_tree = child_tree.mutate(rng=self.rng, rate=self.config.mutation_prob)

            # Complexity guard
            if child_tree.complexity() > MAX_COMPLEXITY:
                child_tree = ExpressionTree.random(rng=self.rng, max_depth=2)

            new_pop.append(GPIndividual(tree=child_tree))

        return new_pop[: self.config.population_size]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, individual: GPIndividual) -> dict[str, float]:
        """Validate an individual on the test set using walk-forward windows.

        Returns {ic, ir, oos_ic_per_window}.
        """
        if self._test_returns is None or self._test_returns.empty:
            return {"ic": 0.0, "ir": 0.0, "oos_ic_per_window": []}

        from src.factors.mining.fitness import ic_fitness

        all_dates = self._test_returns.index.sort_values()
        n = len(all_dates)
        n_windows = max(1, self.config.walk_forward_windows)

        if n < n_windows * 10:
            # Not enough test data for walk-forward; single evaluation
            try:
                compute_fn = individual.tree.to_callable()
                factor_values = compute_fn(self._test_panel)
                if factor_values.empty:
                    return {"ic": 0.0, "ir": 0.0, "oos_ic_per_window": []}

                common_idx = factor_values.index.intersection(self._test_returns.index)
                common_cols = factor_values.columns.intersection(self._test_returns.columns)

                if len(common_idx) < 10 or len(common_cols) < 3:
                    return {"ic": 0.0, "ir": 0.0, "oos_ic_per_window": []}

                fv = factor_values.loc[common_idx, common_cols]
                fr = self._test_returns.loc[common_idx, common_cols]
                ic = ic_fitness(fv, fr)
                ic_std = float(np.std([
                    ic_fitness(fv.iloc[i:i+1], fr.iloc[i:i+1])
                    for i in range(min(len(fv), 20))
                ], ddof=1)) if len(fv) > 1 else 1e-12
                ir = ic / ic_std * np.sqrt(252) if ic_std > 1e-12 else 0.0
                return {"ic": ic, "ir": float(ir), "oos_ic_per_window": [ic]}
            except Exception:
                return {"ic": 0.0, "ir": 0.0, "oos_ic_per_window": []}

        # Walk-forward on test set
        window_size = n // (n_windows * 2)
        window_ics: list[float] = []
        compute_fn = individual.tree.to_callable()

        for w in range(n_windows):
            oos_end = n - (n_windows - w - 1) * window_size
            oos_start = max(0, oos_end - window_size)
            if oos_end - oos_start < 5:
                continue

            oos_dates = all_dates[oos_start:oos_end]
            oos_panel = {
                k: v.loc[v.index.intersection(oos_dates)] if not v.empty else v
                for k, v in self._test_panel.items()
            }

            try:
                fv = compute_fn(oos_panel)
                if fv.empty:
                    continue
                oos_ret = self._test_returns.loc[self._test_returns.index.intersection(oos_dates)]
                common_idx = fv.index.intersection(oos_ret.index)
                common_cols = fv.columns.intersection(oos_ret.columns)
                if len(common_idx) >= 5 and len(common_cols) >= 3:
                    window_ics.append(ic_fitness(
                        fv.loc[common_idx, common_cols],
                        oos_ret.loc[common_idx, common_cols],
                    ))
            except Exception:
                continue

        if not window_ics:
            return {"ic": 0.0, "ir": 0.0, "oos_ic_per_window": []}

        mean_ic = float(np.mean(window_ics))
        std_ic = float(np.std(window_ics, ddof=1)) if len(window_ics) > 1 else 1e-12
        ir = mean_ic / std_ic * np.sqrt(252) if std_ic > 1e-12 else 0.0

        individual.oos_ic_per_window = window_ics
        return {"ic": mean_ic, "ir": float(ir), "oos_ic_per_window": window_ics}

    # ------------------------------------------------------------------
    # Multiple testing correction
    # ------------------------------------------------------------------

    def _compute_bh_correction(self, individuals: list[GPIndividual]) -> None:
        """Apply Benjamini-Hochberg correction across all individuals.

        For each individual, compute a p-value from the OOS IC distribution,
        then apply BH procedure at alpha=0.05.  Sets ``adjusted_p_value``
        and ``is_statistically_significant`` on each individual.
        """
        from scipy import stats as sp_stats
        import numpy as np

        n_tests = len(individuals)
        if n_tests == 0:
            return

        # Compute raw p-value for each individual from IC / std(IC across windows)
        p_values: list[float] = []
        for ind in individuals:
            wics = ind.oos_ic_per_window
            if len(wics) < 2 or float(np.std(wics, ddof=1)) < 1e-12:
                p_values.append(1.0)
                continue
            mean_ic = float(np.mean(wics))
            std_ic = float(np.std(wics, ddof=1))
            t_stat = mean_ic / (std_ic / np.sqrt(len(wics)) + 1e-12)
            # One-sided t-test: H0 = IC <= 0
            p_val = float(sp_stats.t.sf(t_stat, df=len(wics) - 1))
            p_values.append(max(p_val, 1e-15))

        # Benjamini-Hochberg procedure
        sorted_idx = np.argsort(p_values)
        adjusted = np.ones(n_tests)
        for rank, idx in enumerate(sorted_idx):
            adjusted[idx] = min(1.0, p_values[idx] * n_tests / (rank + 1.0))
        # Ensure monotonicity
        for i in range(n_tests - 1, 0, -1):
            adjusted[sorted_idx[i - 1]] = min(adjusted[sorted_idx[i - 1]], adjusted[sorted_idx[i]])

        for i, ind in enumerate(individuals):
            ind.adjusted_p_value = round(float(adjusted[i]), 6)
            ind.is_statistically_significant = float(adjusted[i]) < 0.05

    # ------------------------------------------------------------------
    # SSE progress
    # ------------------------------------------------------------------

    def _emit_progress(self, event_type: str, data: dict[str, Any]) -> None:
        """Push a progress event to the SSE queue."""
        self._progress_queue.put({"type": event_type, **data})

    def _get_generation_diversity(self, fitnesses: list[float]) -> float:
        """Measure population diversity as std of fitness."""
        if len(fitnesses) < 2:
            return 0.0
        return float(np.std(fitnesses, ddof=1))

    def _get_fitness_distribution(self, fitnesses: list[float], n_bins: int = 10) -> dict[str, Any]:
        """Compute fitness distribution histogram for frontend visualization.

        Returns bins and counts for a histogram, plus summary stats.
        """
        if not fitnesses:
            return {"bins": [], "counts": [], "min": 0, "max": 0, "median": 0, "q25": 0, "q75": 0}

        arr = np.array(fitnesses, dtype=np.float64)
        finite = arr[np.isfinite(arr)]
        if len(finite) == 0:
            return {"bins": [], "counts": [], "min": 0, "max": 0, "median": 0, "q25": 0, "q75": 0}

        hist, bin_edges = np.histogram(finite, bins=min(n_bins, len(finite) // 3 + 2))
        return {
            "bins": [round(float(e), 6) for e in bin_edges],
            "counts": [int(c) for c in hist],
            "min": round(float(np.min(finite)), 6),
            "max": round(float(np.max(finite)), 6),
            "median": round(float(np.median(finite)), 6),
            "q25": round(float(np.percentile(finite, 25)), 6),
            "q75": round(float(np.percentile(finite, 75)), 6),
        }

    def _update_elite_lineage(self, individuals: list[GPIndividual], generation: int, top_n: int = 5) -> None:
        """Track elite individuals that survive across generations.

        Records each individual's first appearance and updates survival count.
        """
        sorted_ind = sorted(individuals, key=lambda ind: ind.train_fitness, reverse=True)
        for rank, ind in enumerate(sorted_ind[:top_n]):
            formula_hash = ind.formula  # Use formula string as identity key
            if formula_hash in self._elite_tracker:
                entry = self._elite_tracker[formula_hash]
                entry["last_seen_gen"] = generation
                entry["survival_gens"] = generation - entry["first_seen_gen"] + 1
                if ind.train_fitness > entry.get("best_fitness", float("-inf")):
                    entry["best_fitness"] = ind.train_fitness
                    entry["best_ic"] = ind.test_ic
                    entry["expression_json"] = ind.tree.to_dict()
            else:
                self._elite_tracker[formula_hash] = {
                    "formula": ind.formula,
                    "expression_json": ind.tree.to_dict(),
                    "first_seen_gen": generation,
                    "last_seen_gen": generation,
                    "survival_gens": 1,
                    "best_fitness": ind.train_fitness,
                    "best_ic": ind.test_ic,
                    "test_ir": ind.test_ir,
                    "complexity": ind.complexity,
                    "rank": rank + 1,
                }

    def _get_elite_summary(self, min_survival: int = 3, top_n: int = 8) -> list[dict[str, Any]]:
        """Return elite individuals sorted by survival_gens descending."""
        elites = [
            v for v in self._elite_tracker.values()
            if v.get("survival_gens", 0) >= min_survival
        ]
        elites.sort(key=lambda x: (x.get("survival_gens", 0), x.get("best_fitness", 0)), reverse=True)
        return elites[:top_n]

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self) -> GPRunResult:
        """Execute the full GP evolution run.

        Returns:
            GPRunResult with best individuals, generation history, etc.
        """
        job_id = uuid.uuid4().hex[:12]
        start_time = time.monotonic()

        self._emit_progress("started", {"job_id": job_id, "config": self.config.model_dump()})

        # Load data
        self._emit_progress("progress", {"stage": "loading_data", "message": "Loading OHLCV data..."})
        self._load_data()
        self._emit_progress("progress", {"stage": "data_loaded", "message": "Data loaded"})

        # Initialize population
        self._emit_progress("progress", {"stage": "init_population", "message": "Initializing population..."})
        self.initialize_population()

        total_generations = self.config.generations
        best_overall: GPIndividual | None = None
        best_overall_fitness = float("-inf")

        for gen in range(total_generations):
            if self._cancelled.is_set():
                self._emit_progress("done", {"status": "cancelled"})
                break

            gen_start = time.monotonic()

            # Evaluate
            self._emit_progress("progress", {
                "stage": "evaluating",
                "generation": gen + 1,
                "total_generations": total_generations,
                "message": f"Generation {gen + 1}/{total_generations}: evaluating...",
            })

            fitnesses = self.evaluate_population()

            # Record stats
            best_idx = max(range(len(fitnesses)), key=lambda i: fitnesses[i])
            gen_best = self._population[best_idx]
            gen_best.train_fitness = fitnesses[best_idx]
            gen_best_ic: float = 0.0

            # Quick validate best for IC tracking
            val = self.validate(gen_best)
            gen_best.test_ic = val["ic"]
            gen_best.test_ir = val["ir"]
            gen_best_ic = val["ic"]

            if fitnesses[best_idx] > best_overall_fitness:
                best_overall = GPIndividual(
                    tree=ExpressionTree(gen_best.tree.root.copy()),
                    train_fitness=fitnesses[best_idx],
                    test_ic=gen_best.test_ic,
                    test_ir=gen_best.test_ir,
                )
                best_overall_fitness = fitnesses[best_idx]

            diversity = self._get_generation_diversity(fitnesses)
            stats = GenerationStats(
                generation=gen + 1,
                best_fitness=fitnesses[best_idx],
                mean_fitness=float(np.mean(fitnesses)),
                std_fitness=float(np.std(fitnesses, ddof=1)) if len(fitnesses) > 1 else 0.0,
                best_ic=gen_best_ic,
                diversity=diversity,
            )
            self._generation_history.append(stats)

            gen_elapsed = time.monotonic() - gen_start

            # Compute fitness distribution for frontend histogram
            fitness_dist = self._get_fitness_distribution(fitnesses)

            # Update elite lineage tracking
            self._update_elite_lineage(self._population, gen + 1)
            elite_summary = self._get_elite_summary()

            self._emit_progress("generation_complete", {
                "generation": gen + 1,
                "total_generations": total_generations,
                "best_fitness": stats.best_fitness,
                "mean_fitness": stats.mean_fitness,
                "best_ic": stats.best_ic,
                "diversity": stats.diversity,
                "gen_seconds": round(gen_elapsed, 2),
                "best_formula": gen_best.formula,
                "best_expression_json": gen_best.tree.to_dict(),
                "best_complexity": gen_best.complexity,
                "fitness_distribution": fitness_dist,
                "elite_lineage": elite_summary,
                "data_source": self.data_source,
            })

            # Evolve (unless last generation)
            if gen < total_generations - 1:
                self._population = self.evolve(fitnesses)

        # Final validation of top individuals
        best_individuals: list[GPIndividual] = []
        sorted_pop = sorted(self._population, key=lambda ind: ind.train_fitness, reverse=True)
        top_n = min(10, len(sorted_pop))
        for ind in sorted_pop[:top_n]:
            val = self.validate(ind)
            ind.test_ic = val["ic"]
            ind.test_ir = val["ir"]
            best_individuals.append(ind)

        # Apply Benjamini-Hochberg multiple testing correction
        self._compute_bh_correction(best_individuals)

        # Best test IC only from statistically significant factors
        sig = [i for i in best_individuals if i.is_statistically_significant]
        best_test_ic = max((ind.test_ic for ind in sig), default=0.0)
        if best_test_ic == 0.0 and best_individuals:
            best_test_ic = max((ind.test_ic for ind in best_individuals))
        runtime = time.monotonic() - start_time

        self._emit_progress("done", {
            "status": "completed",
            "best_test_ic": best_test_ic,
            "total_generations": len(self._generation_history),
            "runtime_seconds": round(runtime, 1),
            "significant_count": len(sig),
            "total_candidates": len(best_individuals),
            "data_source": self.data_source,
            "data_source_detail": self.data_source_detail,
        })

        return GPRunResult(
            job_id=job_id,
            best_individuals=best_individuals,
            generation_history=self._generation_history,
            best_test_ic=best_test_ic,
            runtime_seconds=runtime,
            config={
                "data_source": self.data_source,
                "data_source_detail": self.data_source_detail,
                "population_size": self.config.population_size,
                "generations": self.config.generations,
            },
        )

    def cancel(self) -> None:
        """Signal the evolution to stop after the current generation."""
        self._cancelled.set()

    def get_progress_queue(self) -> queue.Queue[dict[str, Any]]:
        """Get the SSE progress queue for streaming to frontend."""
        return self._progress_queue
