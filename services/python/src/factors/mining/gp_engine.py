"""Genetic Programming Evolution Engine.

Orchestrates the evolution of alpha factor expressions through:
    - Hybrid population initialisation (skeletons + mutation + random)
    - Multiplicative composite fitness (IC × cost × orthogonality × A-share × stability × complexity)
    - Tiered operator unlocking (basic → advanced → alternative)
    - Tournament selection + elitism
    - Subtree crossover + point mutation
    - FactorKB integration (auto-register + formula dedup)
    - FDR multiple testing correction (Benjamini-Yekutieli, every generation)
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
    get_allowed_operators,
)
from src.factors.mining.fitness import (
    compute_forward_returns,
    rank_ic_fitness,
)
from src.factors.mining.enhanced_fitness import (
    composite_fitness,
    apply_fdr_correction,
    apply_by_correction,
)
from src.factors.mining.hybrid_init import (
    hybrid_initialize_population,
    get_default_skeletons,
)
from src.factors.mining.factor_kb import (
    FactorKnowledgeBase,
    FactorEntry,
    FactorStatus,
    get_kb,
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
    # ── Legacy fitness config (kept for backward compat) ──
    fitness_metric: Literal["ic_mean", "rank_ic", "sharpe", "composite"] = "composite"
    complexity_penalty: Literal["aic", "bic", "none"] = "bic"
    train_start: str = "2024-01-01"   # within free source range (~2-3yr lookback)
    train_end: str = "2025-12-31"
    test_start: str = "2025-01-01"    # last year for OOS validation
    test_end: str = "2025-12-31"
    universe: list[str] = Field(default_factory=list, description="Stock codes to include")
    max_workers: int = Field(default=4, ge=1, le=16)
    # ── Walk-forward validation ──
    walk_forward_windows: int = Field(default=5, ge=1, le=24, description="Number of rolling OOS windows for fitness evaluation")
    oos_stability_weight: float = Field(default=0.5, ge=0.0, le=2.0, description="Penalty weight on std of OOS IC (higher = prefer stable factors)")
    # ── P0: Tiered operators ──
    use_tiered_operators: bool = Field(default=True, description="Progressively unlock operators by tier")
    # ── P0: Hybrid initialization ──
    use_hybrid_init: bool = Field(default=True, description="Use skeleton-seeded hybrid initialization")
    skeleton_ratio: float = Field(default=0.30, ge=0.0, le=1.0, description="Fraction from direct skeleton copies")
    mutant_ratio: float = Field(default=0.40, ge=0.0, le=1.0, description="Fraction from skeleton mutations")
    # ── P0: FactorKB integration ──
    use_kb: bool = Field(default=True, description="Auto-register factors to Knowledge Base with dedup")
    kb_user_id: int = Field(default=1, description="User ID for KB tenant isolation")
    # ── P0: FDR correction ──
    fdr_alpha: float = Field(default=0.05, ge=0.01, le=0.20, description="FDR threshold for BH/BY correction")
    # [P0-05 fix] Use Benjamini-Yekutieli instead of BH when candidates are
    # tested on the same data (correlated p-values). BY controls FDR under
    # arbitrary dependence.
    use_by_correction: bool = Field(default=True, description="Use BY (more conservative) instead of BH for FDR")

    # ── P1-06 fix: Walk-forward OOS evaluation in core fitness path ──
    use_walk_forward_oos: bool = Field(default=True, description="Use rolling OOS windows for IC in core fitness")


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
    """Orchestrates genetic programming evolution for alpha factor discovery.

    P0 upgrades:
    - Multiplicative composite fitness (IC × cost × orthogonality × …)
    - Hybrid skeleton-seeded initialization
    - FactorKB auto-registration with formula dedup
    - FDR correction every generation
    - Tiered operator unlocking
    """

    def __init__(
        self,
        config: GPEvolutionConfig,
        data_provider: Any | None = None,
        kb: FactorKnowledgeBase | None = None,
    ) -> None:
        self.config = config
        self.rng = random.Random()
        self._data_provider = data_provider

        # ── P0: FactorKB ──
        self._kb = kb if kb is not None else (get_kb(user_id=config.kb_user_id) if config.use_kb else None)

        # ── P0: Skeletons (shared across runs) ──
        self._skeletons: list[ExpressionTree] | None = None

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

        # ── P0: Core factor values for orthogonality checks ──
        self._core_factor_values: dict[str, pd.DataFrame] = {}

        # Elite lineage tracking: formula_hash -> {first_seen_gen, last_seen_gen, best_fitness, representative}
        self._elite_tracker: dict[str, dict[str, Any]] = {}

        # ── P0: KB registration stats ──
        self._kb_new_registrations: int = 0
        self._kb_duplicates_avoided: int = 0

        # [P0-02 fix] Thread-safe KB access — prevents data races when
        # evaluate_population() runs workers in parallel via ThreadPoolExecutor.
        self._kb_lock = threading.Lock()

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

        When the primary source returns data that doesn't cover the
        requested date range, walks the market fallback chain to find a
        source with better coverage — matching the behaviour of
        ``backtest/runner.py``.
        """
        try:
            from backtest.data_store import get_data_store
            store = get_data_store()
        except (ImportError, ModuleNotFoundError, RuntimeError) as e:
            logger.warning("DataStore unavailable, using mock data: %s", e)
            self.data_source = "mock"
            self.data_source_detail = f"DataStore import failed: {e}"
            self._emit_progress("data_source", {"source": "mock", "detail": self.data_source_detail})
            self._load_mock_data()
            return

        universe = self.config.universe
        if not universe:
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

            # ── Coverage fallback: when primary source returns data but it
            # doesn't cover the train_start (e.g. mootdx free server only
            # keeps ~3 months), walk the fallback chain to find a source
            # with better coverage.  Without this, the train panel ends up
            # empty and all individuals get fitness=0.
            # TODO(P5-task8): This uses the loader registry for bulk multi-symbol
            # fetch with fallback-chain walking and coverage checking —
            # significantly more complex than a single fetch_bars() call.
            # Migrate when DataService supports bulk fetch + fallback chains.
            # TODO(P6): migrate data coverage check to Go gRPC DataService
            from backtest.loaders.registry import (
                FALLBACK_CHAINS, LOADER_REGISTRY, _ensure_registered,
            )
            try:
                from backtest.runner import _data_covers_range, _detect_market
            except ImportError:
                _data_covers_range = lambda dm, start: True  # noqa: E731
                _detect_market = lambda sym: "equity_cn"  # noqa: E731

            _ensure_registered()
            needs_fallback = not _data_covers_range(data_map, train_start)
            if needs_fallback and universe:
                market = _detect_market(universe[0])
                for fb_name in FALLBACK_CHAINS.get(market, []):
                    if fb_name not in LOADER_REGISTRY:
                        continue
                    try:
                        fb_loader = LOADER_REGISTRY[fb_name]()
                    except (ImportError, ModuleNotFoundError, TypeError, ValueError):
                        continue
                    if not fb_loader.is_available():
                        continue
                    try:
                        fb_data_map = fb_loader.fetch(
                            universe, full_start, full_end, interval="1D",
                        )
                    except (ValueError, KeyError, IOError, OSError, RuntimeError):
                        continue
                    if fb_data_map and _data_covers_range(fb_data_map, train_start):
                        logger.info(
                            "GP data: switched from primary to %s (better coverage)", fb_name,
                        )
                        data_map = fb_data_map
                        break
                    elif fb_data_map and not data_map:
                        data_map = fb_data_map
                if needs_fallback and not _data_covers_range(data_map, train_start):
                    logger.warning(
                        "GP data: all sources have insufficient coverage for train_start=%s. "
                        "Train panel may be empty.", train_start,
                    )

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

            # If train panel is empty after all the fallback attempts,
            # the requested date range is simply not available from any
            # configured source.  Fall back to mock data with a clear
            # reason so the user can adjust dates.
            if train_bars < 10 or n_stocks < 2:
                logger.warning(
                    "GP data: train panel too small (bars=%d, stocks=%d) after "
                    "fallback chain.  Falling to mock data.  Try shorter date "
                    "range or enable more data sources.", train_bars, n_stocks,
                )
                self.data_source = "mock"
                self.data_source_detail = (
                    f"Train panel too small ({train_bars} bars × {n_stocks} stocks). "
                    f"Requested {train_start}→{train_end}. "
                    f"Available data only covers {full_start}→{full_end} with limited depth. "
                    f"Try a more recent date range (e.g. last 2 years) or enable "
                    f"eastmoney/tushare for long history."
                )
                self._emit_progress("data_source", {"source": "mock", "detail": self.data_source_detail})
                self._load_mock_data()
                return

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
        except (ValueError, KeyError, IOError, OSError, TypeError, RuntimeError, ImportError) as e:
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
    # P0: Core factor loading + KB registration
    # ------------------------------------------------------------------

    def _load_core_factors(self) -> None:
        """Load core factor values from KB for orthogonality checks.

        Core factors are the top-N approved/production factors in KB.
        Their values are evaluated on the current train panel so they
        can be used as regressors in the orthogonality penalty.
        """
        if self._kb is None or not self.config.use_kb:
            return

        core_entries = self._kb.get_top_core_factors(n=50)
        if not core_entries:
            logger.debug("No core factors in KB for orthogonality checks")
            return

        self._core_factor_values = {}
        for entry in core_entries[:30]:  # Use top 30 for regression
            try:
                fn = entry.tree.to_callable()
                fv = fn(self._train_panel)
                if not fv.empty:
                    self._core_factor_values[entry.alpha_id] = fv
            except (ValueError, KeyError, TypeError, IndexError, ZeroDivisionError, RuntimeError):
                continue

        if self._core_factor_values:
            logger.info("Loaded %d core factors from KB for orthogonality checks",
                        len(self._core_factor_values))

    def _register_to_kb(
        self,
        ind: GPIndividual,
        generation: int,
        source: str = "gp_engine",
    ) -> FactorEntry | None:
        """Register a GP individual to the FactorKB.

        Formula dedup is automatic — if the same formula_hash already
        exists, the existing entry is returned instead.

        Args:
            ind: GP individual to register.
            generation: Current generation number.
            source: Origin label for KB.

        Returns:
            The FactorEntry (new or existing), or None if KB is disabled.
        """
        if self._kb is None or not self.config.use_kb:
            return None

        detail = getattr(ind, "_fitness_detail", {})
        components = detail.get("components", {})
        ortho = detail.get("orthogonality", {})

        entry, is_new = self._kb.register(
            tree=ind.tree,
            name=f"gp_gen{generation}_{ind.tree.formula_hash[:8]}",
            theme=[],
            semantic_tags=[],
            source=source,
            economic_rationale=f"GP evolution generation {generation}",
            data_source_version=self.data_source,
            train_ic=detail.get("rank_ic", 0.0),
            test_ic=ind.test_ic,
            test_ir=ind.test_ir,
            sharpe=0.0,
            max_drawdown=0.0,
            oos_ic_per_window=ind.oos_ic_per_window,
            orthogonality_score=components.get("orthogonality_penalty", 0.0),
            max_corr_with_core=ortho.get("max_corr_with_core", 0.0),
        )

        if is_new:
            self._kb_new_registrations += 1
            # Auto-transition to VALIDATING if IC passes threshold
            if abs(ind.test_ic) > 0.01:
                try:
                    self._kb.transition_status(
                        entry.alpha_id, FactorStatus.VALIDATING,
                        reason=f"Auto-validated from GP gen {generation}",
                    )
                except ValueError:
                    pass
        else:
            self._kb_duplicates_avoided += 1

        return entry

    def initialize_population(self) -> None:
        """Generate initial population.

        P0: Uses hybrid initialization (skeletons + mutants + random) when
        ``use_hybrid_init=True``.  Falls back to ramped half-and-half otherwise.

        P0: When tiered operators are enabled, skeletons are filtered to only
        use operators available at generation 0 (basic tier).
        """
        if self.config.use_hybrid_init:
            if self._skeletons is None:
                self._skeletons = get_default_skeletons()
                # Also extract skeletons from KB if available
                if self._kb and len(self._kb) > 0:
                    from src.factors.mining.hybrid_init import extract_skeletons_from_zoo
                    kb_skeletons = extract_skeletons_from_zoo(top_n=5)
                    for sk in kb_skeletons:
                        if sk.formula_hash not in {s.formula_hash for s in self._skeletons}:
                            self._skeletons.append(sk)
                logger.info("Loaded %d factor skeletons for hybrid init", len(self._skeletons))

            trees = hybrid_initialize_population(
                population_size=self.config.population_size,
                rng=self.rng,
                skeletons=self._skeletons,
                skeleton_ratio=self.config.skeleton_ratio,
                mutant_ratio=self.config.mutant_ratio,
                random_ratio=round(1.0 - self.config.skeleton_ratio - self.config.mutant_ratio, 2),
            )
            self._population = [GPIndividual(tree=t) for t in trees]
            logger.info(
                "Hybrid init: %d individuals (%.0f%% skeleton, %.0f%% mutant, %.0f%% random)",
                len(self._population),
                self.config.skeleton_ratio * 100,
                self.config.mutant_ratio * 100,
                (1.0 - self.config.skeleton_ratio - self.config.mutant_ratio) * 100,
            )
        else:
            self._population = []
            for _ in range(self.config.population_size):
                tree = ExpressionTree.random(rng=self.rng, max_depth=3)
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
        # [P2-02 fix] Non-overlapping sequential walk-forward windows.
        # Previously rolling windows shared training/OOS data across windows
        # (window w's OOS was included in window w+1's training), which made
        # OOS IC values correlated and invalidated the t-test in FDR.
        #
        # Now each window's training data is strictly BEFORE its OOS data,
        # and OOS windows are non-overlapping and sequential.
        oos_size = max(5, n // (n_windows + 1))

        for w in range(n_windows):
            oos_start = n - (n_windows - w) * oos_size
            oos_end = min(n, oos_start + oos_size)
            # Training: expanding window ending where OOS begins
            train_end = oos_start
            train_start = max(0, oos_start - oos_size * 4)

            if train_end - train_start >= 10 and oos_end - oos_start >= 5:
                windows.append((
                    all_dates[train_start:train_end],
                    all_dates[oos_start:oos_end],
                ))

        return windows or [(all_dates[: max(10, int(n * 0.8))], all_dates[max(10, int(n * 0.8)) :])]

    def _evaluate_individual(self, ind: GPIndividual) -> float:
        """Evaluate a single individual's fitness.

        Uses ``composite_fitness()`` for a multiplicative composite score
        that incorporates rank IC, A-share cost penalty, orthogonality
        check against KB core factors, cross-time stability, and
        complexity discount.

        Also tracks OOS IC per window for FDR correction and checks the
        KB for duplicate formulas before evaluating.

        Args:
            ind: The GP individual to evaluate.  Its ``train_fitness``,
                ``oos_ic_per_window``, and ``_fitness_detail`` attributes
                are set in-place.

        Returns:
            The composite fitness score (float).  Returns ``0.0`` when the
            factor cannot be computed (e.g., invalid expression,
            insufficient data, or KB dedup hit with matching provenance).
        """
        # ── P0: KB dedup check (skip evaluation if duplicate) ──
        if self._kb is not None and self.config.use_kb:
            fhash = ind.tree.formula_hash
            # [P0-02 fix] Thread-safe KB access with provenance validation
            with self._kb_lock:
                existing = self._kb.get_by_hash(fhash)
                if existing is not None:
                    # [P0-03 fix] Verify data provenance — KB metrics are only
                    # valid if they came from the same data source and a
                    # compatible date range.  Otherwise re-evaluate.
                    if self._kb_provenance_matches(existing):
                        ind.train_fitness = abs(existing.test_ic)
                        ind.test_ic = existing.test_ic
                        ind.test_ir = existing.test_ir
                        ind.oos_ic_per_window = existing.oos_ic_per_window
                        self._kb_duplicates_avoided += 1
                        return float(ind.train_fitness)
                    else:
                        logger.debug(
                            "KB entry %s has mismatched provenance — re-evaluating",
                            fhash[:12],
                        )

        try:
            compute_fn = ind.tree.to_callable()
            factor_values = compute_fn(self._train_panel)
        except (ValueError, KeyError, TypeError, IndexError, ZeroDivisionError, RuntimeError):
            ind.train_fitness = 0.0
            return 0.0

        if factor_values.empty or self._train_returns is None:
            ind.train_fitness = 0.0
            return 0.0

        common_idx = factor_values.index.intersection(self._train_returns.index)
        common_cols = factor_values.columns.intersection(self._train_returns.columns)

        if len(common_idx) < 10 or len(common_cols) < 3:
            ind.train_fitness = 0.0
            return 0.0

        fv = factor_values.loc[common_idx, common_cols]
        fr = self._train_returns.loc[common_idx, common_cols]

        # ── P1-06 fix: Walk-forward OOS evaluation ──
        # When use_walk_forward_oos is enabled, compute true OOS IC from
        # rolling windows rather than reusing in-sample IC.
        oos_ic_windows: list[float] = []
        if self.config.use_walk_forward_oos and len(common_idx) >= 40:
            oos_ic_windows = self._compute_oos_ic_windows(fv, fr)
            if not oos_ic_windows:
                oos_ic_windows = []  # fall through to single-window below

        # ── P0: Composite fitness (multiplicative) ──
        result = composite_fitness(
            tree=ind.tree,
            factor_values=fv,
            forward_returns=fr,
            panel=self._train_panel,
            core_factors=self._core_factor_values if self._core_factor_values else None,
        )

        fitness = result["fitness"]
        ind.train_fitness = float(fitness)
        # [P1-06 fix] Use true OOS windows when available, otherwise fall back
        # to the single in-sample IC for backward compatibility.
        ind.oos_ic_per_window = oos_ic_windows if oos_ic_windows else [result["rank_ic"]]

        # ── P0: Store component scores for diagnostics ──
        ind._fitness_detail = result

        return float(fitness)

    def _evaluate_individual_wf(self, ind: GPIndividual) -> tuple[float, list[float]]:
        """Walk-forward fitness evaluation using rank IC in each OOS window.

        Splits the training period into sequential OOS windows, evaluates the
        individual's factor values on each window via ``rank_ic_fitness``,
        and derives a fitness score as ``mean_IC - oos_stability_weight * std_IC``.

        Args:
            ind: The GP individual to evaluate.

        Returns:
            A tuple of ``(fitness, window_ics)`` where:
            - *fitness* is ``mean_IC - oos_stability_weight * std_IC``.
            - *window_ics* is the list of per-window OOS IC values.

        Note:
            Retained for backward compatibility.  The primary fitness path is
            now ``_evaluate_individual`` which uses ``composite_fitness``
            directly.  Returns ``(0.0, [])`` when insufficient data is available.
        """
        windows = self._get_walk_forward_windows()

        if not windows or self._train_returns is None:
            return 0.0, []

        compute_fn = ind.tree.to_callable()
        window_ics: list[float] = []

        for train_idx, oos_idx in windows:
            if len(train_idx) < 10 or len(oos_idx) < 5:
                continue

            try:
                oos_panel_slice = {
                    k: v.loc[v.index.intersection(oos_idx)] if not v.empty else v
                    for k, v in self._train_panel.items()
                }
                fv = compute_fn(oos_panel_slice)
                if fv.empty:
                    continue

                oos_returns = self._train_returns.loc[self._train_returns.index.intersection(oos_idx)]
                common_idx = fv.index.intersection(oos_returns.index)
                common_cols = fv.columns.intersection(oos_returns.columns)

                if len(common_idx) >= 5 and len(common_cols) >= 3:
                    ic = float(rank_ic_fitness(
                        fv.loc[common_idx, common_cols],
                        oos_returns.loc[common_idx, common_cols],
                    ))
                    window_ics.append(ic)
            except (ValueError, KeyError, TypeError, IndexError, ZeroDivisionError):
                continue

        if not window_ics:
            return 0.0, []

        mean_ic = float(np.mean(window_ics))
        std_ic = float(np.std(window_ics, ddof=1)) if len(window_ics) > 1 else 0.0
        fitness = mean_ic - self.config.oos_stability_weight * std_ic

        return float(fitness), window_ics

    # ── KB provenance validation ──────────────────────────────────────

    def _kb_provenance_matches(self, kb_entry) -> bool:
        """[P0-03 fix] Check whether a KB entry's metrics are valid for the
        current run's data configuration.

        Returns False (force re-evaluation) if:
        - The data source has changed (e.g., mock vs real)
        - The training date range is substantially different
        - The universe size differs by more than 20%
        """
        # Always re-evaluate if data source changed
        kb_source = kb_entry.data_source_version if hasattr(kb_entry, "data_source_version") else ""
        if kb_source and self.data_source_detail and kb_source != self.data_source_detail:
            return False

        # Check date range overlap
        kb_train_range = kb_entry.train_date_range if hasattr(kb_entry, "train_date_range") else ""
        if kb_train_range and hasattr(self, "_train_panel") and self._train_panel:
            # Extract date range from current train panel
            close_df = self._train_panel.get("close")
            if close_df is not None and len(close_df) > 0:
                current_start = str(close_df.index[0])[:10]
                current_end = str(close_df.index[-1])[:10]
                current_range = f"{current_start}/{current_end}"
                if kb_train_range != current_range:
                    return False

        return True

    # ── Walk-forward OOS IC computation ───────────────────────────────

    def _compute_oos_ic_windows(
        self,
        factor_values: pd.DataFrame,
        forward_returns: pd.DataFrame,
    ) -> list[float]:
        """[P1-06 fix] Compute true OOS ICs from rolling walk-forward windows.

        Splits the data into n expanding or rolling windows, computes the
        factor on each training window, and evaluates IC on the held-out
        OOS window.  Returns a list of OOS IC values.
        """
        from src.factors.mining.fitness import rank_ic_fitness

        n_total = len(factor_values)
        if n_total < 60:
            return []

        n_windows = min(self.config.walk_forward_windows, max(2, n_total // 30))
        window_size = n_total // (n_windows + 1)
        if window_size < 20:
            return []

        oos_ics: list[float] = []
        for w in range(n_windows):
            train_end = n_total - (n_windows - w) * window_size
            train_start = max(0, train_end - window_size * 3)  # 3x lookback
            oos_start = train_end
            oos_end = min(n_total, oos_start + window_size)

            if oos_end - oos_start < 5 or train_end - train_start < 20:
                continue

            oos_fv = factor_values.iloc[oos_start:oos_end]
            oos_fr = forward_returns.iloc[oos_start:oos_end]

            common_idx = oos_fv.index.intersection(oos_fr.index)
            common_cols = oos_fv.columns.intersection(oos_fr.columns)
            if len(common_idx) < 5 or len(common_cols) < 3:
                continue

            try:
                ic_val = float(rank_ic_fitness(
                    oos_fv.loc[common_idx, common_cols],
                    oos_fr.loc[common_idx, common_cols],
                ))
                if np.isfinite(ic_val):
                    oos_ics.append(ic_val)
            except (ValueError, KeyError, TypeError, IndexError, ZeroDivisionError):
                continue

        return oos_ics

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
                    except (concurrent.futures.TimeoutError, concurrent.futures.CancelledError, RuntimeError, ValueError) as e:
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
        """Tournament selection algorithm.

        Randomly samples ``k`` individuals without replacement and returns
        the index of the one with the highest fitness.

        Args:
            fitnesses: List of fitness values, aligned with the population.
            k: Tournament size. Defaults to ``config.tournament_size``.

        Returns:
            Index of the winning individual in the population list.

        Note:
            If the population is smaller than ``k``, the tournament is
            drawn from the entire population.
        """
        k = k or self.config.tournament_size
        candidates = self.rng.sample(range(len(self._population)), min(k, len(self._population)))
        best_idx = max(candidates, key=lambda i: fitnesses[i])
        return best_idx

    # ------------------------------------------------------------------
    # Evolution loop
    # ------------------------------------------------------------------

    def _get_allowed_ops_for_gen(self, generation: int) -> list[str] | None:
        """Return allowed operators for the current generation, or None if
        tiered operators are disabled (all operators allowed)."""
        if not self.config.use_tiered_operators:
            return None
        return get_allowed_operators(generation, self.config.generations)

    def _mutate_with_tier_guard(
        self,
        child_tree: ExpressionTree,
        generation: int,
    ) -> ExpressionTree:
        """Tier-aware mutation with allowed-operator filtering.

        Attempts to mutate the tree up to 10 times until a valid result is
        produced that uses only operators unlocked at the current generation
        tier. Falls back to returning the original tree if no valid mutation
        is found within the retry budget.

        Args:
            child_tree: The expression tree to mutate.
            generation: Current generation number (determines which operator
                tiers are unlocked).

        Returns:
            A mutated tree using only tier-allowed operators, or the original
            tree if no valid mutation was found within the retry budget.

        Note:
            When tiered operators are disabled
            (``use_tiered_operators=False``), this falls through to standard
            ``child_tree.mutate()`` without operator filtering.
        """
        allowed_ops = self._get_allowed_ops_for_gen(generation)
        if allowed_ops is None:
            # All operators allowed — standard mutation
            return child_tree.mutate(rng=self.rng, rate=self.config.mutation_prob)

        # Tiered mode: mutate, then validate operators
        for _attempt in range(10):
            mutant = child_tree.mutate(rng=self.rng, rate=self.config.mutation_prob)
            if _tree_uses_only_allowed_ops(mutant.root, set(allowed_ops)):
                return mutant
        # Fallback: return original
        return child_tree

    def evolve(self, fitnesses: list[float], generation: int = 0) -> list[GPIndividual]:
        """Produce the next generation through selection, crossover, mutation, elitism.

        P0: When ``use_tiered_operators=True``, mutations are filtered to only
        use operators unlocked at the current generation's progress.
        """
        new_pop: list[GPIndividual] = []

        # Elitism
        if self.config.elitism_count > 0:
            sorted_idx = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True)
            for idx in sorted_idx[: self.config.elitism_count]:
                new_pop.append(GPIndividual(
                    tree=ExpressionTree(self._population[idx].tree.root.copy()),
                    train_fitness=fitnesses[idx],
                ))

        allowed_ops = self._get_allowed_ops_for_gen(generation)

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

            # Mutation (P0: tier-aware)
            if self.rng.random() < self.config.mutation_prob:
                child_tree = self._mutate_with_tier_guard(child_tree, generation)

            # P0: Validate operators when tiered mode is active
            if allowed_ops is not None and not _tree_uses_only_allowed_ops(child_tree.root, set(allowed_ops)):
                # Replace with random tree using only allowed ops
                child_tree = _random_tree_with_ops(self.rng, allowed_ops)

            # Complexity guard
            if child_tree.complexity() > MAX_COMPLEXITY:
                child_tree = ExpressionTree.random(rng=self.rng, max_depth=2)

            new_pop.append(GPIndividual(tree=child_tree))

        return new_pop[: self.config.population_size]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, individual: GPIndividual) -> dict[str, float]:
        """Out-of-sample validation on the test set using walk-forward windows.

        Evaluates the individual's factor values on the configured test
        period, splitting data into rolling OOS windows.  Falls back to a
        single evaluation when test data is insufficient for walk-forward.

        Args:
            individual: The GP individual to validate.  Its
                ``oos_ic_per_window`` attribute is updated in-place.

        Returns:
            A dict with keys:
            - ``ic``: Mean IC across all test OOS windows.
            - ``ir``: Annualised information ratio
              (``mean_IC / std_IC * sqrt(252)``).
            - ``oos_ic_per_window``: List of per-window IC values for this
              individual.
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
            except (ValueError, KeyError, TypeError, IndexError, ZeroDivisionError):
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
            except (ValueError, KeyError, TypeError, IndexError, ZeroDivisionError):
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
        """Apply FDR multiple testing correction (supports BH and BY procedures).

        For each individual, derives a raw p-value from a one-sample t-test
        on its OOS IC windows, then applies the Benjamini-Hochberg (BH) or
        Benjamini-Yekutieli (BY) procedure depending on
        ``config.use_by_correction``.

        Sets ``adjusted_p_value`` and ``is_statistically_significant``
        in-place on every individual.

        Args:
            individuals: List of GP individuals whose OOS IC windows are used
                to compute p-values.

        Note:
            BY controls FDR under arbitrary dependence and is the default
            (``config.use_by_correction=True``) — appropriate when all GP
            candidates are tested on the same dataset, which makes IC values
            correlated across individuals.
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

        # Choose procedure
        if self.config.use_by_correction:
            # Benjamini-Yekutieli: controls FDR under arbitrary dependence
            harmonic = sum(1.0 / i for i in range(1, n_tests + 1))
            divisor_factor = harmonic
        else:
            # Benjamini-Hochberg (original)
            divisor_factor = 1.0

        sorted_idx = np.argsort(p_values)
        adjusted = np.ones(n_tests)
        for rank, idx in enumerate(sorted_idx):
            adjusted[idx] = min(1.0, p_values[idx] * n_tests * divisor_factor / (rank + 1.0))
        # Ensure monotonicity
        for i in range(n_tests - 1, 0, -1):
            adjusted[sorted_idx[i - 1]] = min(adjusted[sorted_idx[i - 1]], adjusted[sorted_idx[i]])

        for i, ind in enumerate(individuals):
            ind.adjusted_p_value = round(float(adjusted[i]), 6)
            ind.is_statistically_significant = float(adjusted[i]) < self.config.fdr_alpha

    # ------------------------------------------------------------------
    # SSE progress
    # ------------------------------------------------------------------

    def _emit_progress(self, event_type: str, data: dict[str, Any]) -> None:
        """Push a progress event to the SSE queue for live frontend updates.

        Args:
            event_type: A string label for the event (e.g., ``"progress"``,
                ``"data_source"``, ``"generation_complete"``, ``"done"``).
            data: Dictionary of event payload fields.  Merged with
                ``{"type": event_type}`` before enqueuing.
        """
        self._progress_queue.put({"type": event_type, **data})

    def _get_generation_diversity(self, fitnesses: list[float]) -> float:
        """Measure population diversity as the standard deviation of fitness.

        Args:
            fitnesses: List of fitness values for the current population.

        Returns:
            Population standard deviation (``ddof=1``) of the fitness values.
            Returns ``0.0`` when fewer than two fitness values are available.
        """
        if len(fitnesses) < 2:
            return 0.0
        return float(np.std(fitnesses, ddof=1))

    def _get_fitness_distribution(self, fitnesses: list[float], n_bins: int = 10) -> dict[str, Any]:
        """Compute fitness distribution histogram for frontend visualization.

        Bins finite fitness values and returns a histogram along with
        summary statistics (min, max, median, quartiles).

        Args:
            fitnesses: List of fitness values for the current population.
            n_bins: Desired number of histogram bins (clamped to a reasonable
                fraction of the available data size).

        Returns:
            A dict with keys ``bins``, ``counts``, ``min``, ``max``,
            ``median``, ``q25``, ``q75``.  Non-finite values are filtered
            before binning.  Returns an empty/default dict when no finite
            fitness values exist.
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

        [P1-03 fix] Uses ``ind.tree.formula_hash`` (canonical, insensitive to
        operand ordering in commutative operators) instead of ``ind.formula``
        (display string, which varies with operand order).  Two formulas that
        differ only in the order of ``add``/``mul`` operands are the same
        mathematical expression and should be tracked as one elite.
        """
        sorted_ind = sorted(individuals, key=lambda ind: ind.train_fitness, reverse=True)
        for rank, ind in enumerate(sorted_ind[:top_n]):
            # [P1-03 fix] Use canonical formula_hash, not display formula string
            formula_hash = ind.tree.formula_hash
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
                    "formula_hash": formula_hash,
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

        P0 upgrades:
        - Hybrid skeleton-seeded initialization
        - Multiplicative composite fitness with orthogonality checks
        - FactorKB auto-registration with formula dedup
        - FDR correction every generation (not just final)
        - Tiered operator unlocking
        - KB mining guidance for future runs

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

        # ── P0: Load core factors from KB for orthogonality checks ──
        self._load_core_factors()

        # Initialize population
        self._emit_progress("progress", {"stage": "init_population", "message": "Initializing population..."})
        self.initialize_population()

        total_generations = self.config.generations
        best_overall: GPIndividual | None = None
        best_overall_fitness = float("-inf")

        # ── P0: Track all-time candidates for FDR ──
        all_time_candidates: list[GPIndividual] = []

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

            try:
                fitnesses = self.evaluate_population()
            except (ValueError, RuntimeError, MemoryError) as e:
                logger.exception("Evaluate population failed at generation %d — skipping", gen + 1)
                self._emit_progress("generation_error", {
                    "generation": gen + 1,
                    "error": f"Evaluation failed: {str(e)[:120]}",
                    "total_generations": total_generations,
                })
                # Evolve anyway with flat fitness so the run can continue
                fitnesses = [0.0] * len(self._population)

            # ── P0: FDR correction on this generation ──
            # Build candidate dicts for FDR
            gen_candidates = []
            for ind in self._population:
                gen_candidates.append({
                    "individual": ind,
                    "rank_ic": getattr(ind, "_fitness_detail", {}).get("rank_ic", 0.0),
                    "oos_ic_per_window": ind.oos_ic_per_window,
                })
            # [P0-05 fix] Use BY (Benjamini-Yekutieli) when configured —
            # controls FDR under arbitrary dependence, appropriate when all
            # candidates in a generation share the same training data.
            if self.config.use_by_correction:
                apply_by_correction(gen_candidates, ic_key="rank_ic", alpha=self.config.fdr_alpha)
            else:
                apply_fdr_correction(gen_candidates, ic_key="rank_ic", alpha=self.config.fdr_alpha)
            # Apply FDR results back to individuals
            for gc in gen_candidates:
                gc["individual"].adjusted_p_value = gc.get("fdr_adjusted_p_value", 1.0)
                gc["individual"].is_statistically_significant = gc.get("fdr_significant", False)

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

            # ── P0: Auto-register top individuals to KB ──
            sorted_pop = sorted(
                self._population, key=lambda ind: ind.train_fitness, reverse=True,
            )
            for rank, ind in enumerate(sorted_pop[:5]):
                if ind.train_fitness > 0 and ind.is_statistically_significant:
                    self._register_to_kb(ind, gen + 1)

            # ── P0: Track for all-time FDR ──
            for ind in sorted_pop[:10]:
                if ind.train_fitness > 0:
                    all_time_candidates.append(ind)

            # Compute fitness distribution for frontend histogram
            fitness_dist = self._get_fitness_distribution(fitnesses)

            # Update elite lineage tracking
            self._update_elite_lineage(self._population, gen + 1)
            elite_summary = self._get_elite_summary()

            # ── P0: Get KB mining guidance every 10 generations ──
            kb_guidance = None
            if self._kb and (gen + 1) % 10 == 0:
                kb_guidance = self._kb.get_mining_guidance()

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
                "kb_registrations": self._kb_new_registrations,
                "kb_duplicates": self._kb_duplicates_avoided,
                "kb_guidance": kb_guidance,
                "tier_allowed_ops": self._get_allowed_ops_for_gen(gen) if self.config.use_tiered_operators else None,
            })

            # Evolve (unless last generation)
            if gen < total_generations - 1:
                try:
                    self._population = self.evolve(fitnesses, generation=gen + 1)
                except (ValueError, RuntimeError) as e:
                    logger.exception("Evolve population failed at generation %d — keeping current population", gen + 1)
                    self._emit_progress("generation_error", {
                        "generation": gen + 1,
                        "error": f"Evolution failed: {str(e)[:120]}",
                        "total_generations": total_generations,
                    })
                    # Keep current population for next generation


        # Final validation of top individuals
        best_individuals: list[GPIndividual] = []
        sorted_pop = sorted(self._population, key=lambda ind: ind.train_fitness, reverse=True)
        top_n = min(10, len(sorted_pop))
        for ind in sorted_pop[:top_n]:
            val = self.validate(ind)
            ind.test_ic = val["ic"]
            ind.test_ir = val["ir"]
            best_individuals.append(ind)

        # ── P0: Final FDR on all-time top candidates ──
        all_time_dicts = [
            {
                "individual": ind,
                "rank_ic": ind.test_ic,
                "oos_ic_per_window": ind.oos_ic_per_window,
            }
            for ind in all_time_candidates[-50:]  # last 50 unique candidates
        ]
        if all_time_dicts:
            if self.config.use_by_correction:
                apply_by_correction(all_time_dicts, ic_key="rank_ic", alpha=self.config.fdr_alpha)
            else:
                apply_fdr_correction(all_time_dicts, ic_key="rank_ic", alpha=self.config.fdr_alpha)

        # Also run BH/BY on final best_individuals for backward compat
        self._compute_bh_correction(best_individuals)

        # Best test IC only from statistically significant factors
        sig = [i for i in best_individuals if i.is_statistically_significant]
        best_test_ic = max((ind.test_ic for ind in sig), default=0.0)
        if best_test_ic == 0.0 and best_individuals:
            best_test_ic = max((ind.test_ic for ind in best_individuals))
        runtime = time.monotonic() - start_time

        # ── P0: KB stats ──
        if self._kb:
            logger.info(
                "FactorKB: %d total factors, %d new this run, %d duplicates avoided",
                len(self._kb), self._kb_new_registrations, self._kb_duplicates_avoided,
            )

        self._emit_progress("done", {
            "status": "completed",
            "best_test_ic": best_test_ic,
            "total_generations": len(self._generation_history),
            "runtime_seconds": round(runtime, 1),
            "significant_count": len(sig),
            "total_candidates": len(best_individuals),
            "data_source": self.data_source,
            "data_source_detail": self.data_source_detail,
            "kb_total": len(self._kb) if self._kb else 0,
            "kb_new": self._kb_new_registrations,
            "kb_duplicates": self._kb_duplicates_avoided,
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
                "kb_registrations": self._kb_new_registrations,
                "kb_duplicates_avoided": self._kb_duplicates_avoided,
            },
        )

    def cancel(self) -> None:
        """Signal the evolution to stop after the current generation."""
        self._cancelled.set()

    def get_progress_queue(self) -> queue.Queue[dict[str, Any]]:
        """Get the SSE progress queue for streaming to frontend."""
        return self._progress_queue


# ---------------------------------------------------------------------------
# P0: Tiered operator helpers
# ---------------------------------------------------------------------------

def _tree_uses_only_allowed_ops(root: ExpressionNode, allowed_ops: set[str]) -> bool:
    """Check recursively that every operator in the tree is in ``allowed_ops``.

    Leaf nodes (feature references / constants) are always permitted.

    Args:
        root: The root node of the expression (sub)tree to validate.
        allowed_ops: Set of operator keys that are permitted.

    Returns:
        ``True`` if every operator node in the tree uses only keys
        present in *allowed_ops*; ``False`` otherwise.
    """
    if root.is_leaf:
        return True
    if root.op is not None and root.op not in allowed_ops:
        return False
    return all(_tree_uses_only_allowed_ops(c, allowed_ops) for c in root.children)


def _random_tree_with_ops(
    rng: random.Random,
    allowed_ops: list[str],
    max_depth: int = 3,
    max_attempts: int = 100,
) -> ExpressionTree:
    """Generate a random expression tree using only the given operator set.

    Repeatedly generates random trees via ``_random_tree_restricted`` and
    filters for those within the complexity limit.  Falls back to a single
    feature-reference leaf if no valid tree is found within *max_attempts*.

    Args:
        rng: Random number generator instance.
        allowed_ops: List of permitted operator keys (from the tier system).
        max_depth: Maximum tree depth for the generated tree.
        max_attempts: Number of retries before falling back to a leaf.

    Returns:
        An ``ExpressionTree`` using only the supplied operators and
        respecting ``MAX_COMPLEXITY``.
    """
    # Filter the global operator registry to allowed ops
    from src.factors.mining.expression_tree import UNARY_OPS, BINARY_OPS, TERNARY_OPS

    allowed_unary = [o for o in UNARY_OPS if o in allowed_ops]
    allowed_binary = [o for o in BINARY_OPS if o in allowed_ops]
    allowed_ternary = [o for o in TERNARY_OPS if o in allowed_ops]

    if not allowed_unary and not allowed_binary:
        # No operators allowed — fall back to leaf
        return ExpressionTree(ExpressionNode(feature_id=rng.choice(FEATURE_IDS)))

    for _ in range(max_attempts):
        tree = _random_tree_restricted(
            rng, allowed_unary, allowed_binary, allowed_ternary, max_depth,
        )
        if tree.complexity() <= MAX_COMPLEXITY:
            return tree

    return ExpressionTree(ExpressionNode(feature_id=rng.choice(FEATURE_IDS)))


def _random_tree_restricted(
    rng: random.Random,
    unary_ops: list[str],
    binary_ops: list[str],
    ternary_ops: list[str],
    max_depth: int,
) -> ExpressionTree:
    """Generate a random expression tree from restricted operator sets.

    Recursively builds a tree of up to *max_depth* levels, choosing
    operators from the supplied unary, binary, and ternary lists.  At each
    internal node there is a 30% chance of producing a leaf instead,
    promoting diverse tree shapes.

    Args:
        rng: Random number generator instance.
        unary_ops: List of allowed unary operator keys.
        binary_ops: List of allowed binary operator keys.
        ternary_ops: List of allowed ternary operator keys.
        max_depth: Maximum depth of the generated tree.  At depth 0 a leaf
            is always returned.

    Returns:
        An ``ExpressionTree`` whose nodes use only the supplied operator
        lists.
    """
    from src.factors.mining.expression_tree import WINDOW_OPTIONS

    if max_depth <= 0:
        return ExpressionTree(ExpressionNode(feature_id=rng.choice(FEATURE_IDS)))

    # Choose operator type based on availability
    choices = []
    if unary_ops:
        choices.append("unary")
    if binary_ops:
        choices.append("binary")
    if ternary_ops:
        choices.append("ternary")

    if not choices or rng.random() < 0.3:
        # 30% chance of leaf even when operators are available
        return ExpressionTree(ExpressionNode(
            feature_id=rng.choice(FEATURE_IDS) if rng.random() < 0.8 else None,
            value=round(rng.uniform(-2.0, 2.0), 4) if rng.random() < 0.2 else None,
        ))

    choice = rng.choice(choices)
    if choice == "unary":
        op = rng.choice(unary_ops)
        child = _random_tree_restricted(rng, unary_ops, binary_ops, ternary_ops, max_depth - 1)
        window = rng.choice(WINDOW_OPTIONS) if op.startswith("ts_") else 20
        return ExpressionTree(ExpressionNode(op=op, children=[child.root], window=window))
    elif choice == "binary":
        op = rng.choice(binary_ops)
        left = _random_tree_restricted(rng, unary_ops, binary_ops, ternary_ops, max_depth - 1)
        right = _random_tree_restricted(rng, unary_ops, binary_ops, ternary_ops, max_depth - 1)
        window = rng.choice(WINDOW_OPTIONS) if op.startswith("ts_") else 20
        return ExpressionTree(ExpressionNode(op=op, children=[left.root, right.root], window=window))
    else:
        op = rng.choice(ternary_ops) if ternary_ops else rng.choice(unary_ops)
        cond = _random_tree_restricted(rng, unary_ops, binary_ops, ternary_ops, max_depth - 1)
        t_branch = _random_tree_restricted(rng, unary_ops, binary_ops, ternary_ops, max_depth - 1)
        f_branch = _random_tree_restricted(rng, unary_ops, binary_ops, ternary_ops, max_depth - 1)
        return ExpressionTree(ExpressionNode(op=op, children=[cond.root, t_branch.root, f_branch.root]))
