"""GP Evolution data models.

Extracted from gp_engine.py to reduce file size and improve testability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    use_by_correction: bool = Field(default=True, description="Use BY (more conservative) instead of BH for FDR")
    # ── P1-06 fix: Walk-forward OOS evaluation in core fitness path ──
    use_walk_forward_oos: bool = Field(default=True, description="Use rolling OOS windows for IC in core fitness")


@dataclass
class GPIndividual:
    """A single individual in the GP population."""

    tree: "ExpressionTree"  # forward reference, resolved at import time
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
    config: dict[str, Any] = field(default_factory=dict)  # summary of run configuration
