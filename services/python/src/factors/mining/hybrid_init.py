"""Hybrid population initialization for GP factor mining.

Instead of purely random initialization (which produces < 0.1% viable
individuals in the vast search space of 27 operators × 11 features),
we seed the population with known effective factor skeletons and their
mutations.

Strategy (configurable ratios):
    - skeleton_seeds: 30% — known effective factor structures (momentum, value, …)
    - skeleton_mutants: 40% — single-point mutations of skeletons
    - random: 30% — fully random trees (maintains diversity)

Skeletons are expressed as ExpressionTree dicts so they can be loaded
from config or discovered from the Alpha Zoo.
"""

from __future__ import annotations

import logging
import random
from typing import Any

import numpy as np
import pandas as pd

from src.factors.mining.expression_tree import (
    ExpressionNode,
    ExpressionTree,
    FEATURE_IDS,
    MAX_COMPLEXITY,
    MAX_DEPTH,
    OPERATOR_REGISTRY,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known effective factor skeletons
# ---------------------------------------------------------------------------
# Each skeleton is an ExpressionTree dict that captures a proven factor
# structure.  The GP will mutate windows, features, and sub-operators
# while preserving the high-level architecture.
#
# These are architectural templates, not specific parameter values —
# the GP is free to evolve the details.

_A_SHARE_SKELETONS: list[dict[str, Any]] = [
    # ── Momentum skeletons ──
    {
        "name": "price_momentum",
        "description": "Price change over medium window, ranked cross-sectionally",
        "tree": {
            "op": "rank",
            "children": [{
                "op": "ts_delta",
                "children": [{"feature_id": "close"}],
                "window": 20,
            }],
        },
    },
    {
        "name": "volume_weighted_momentum",
        "description": "Price momentum normalized by volume stability",
        "tree": {
            "op": "div",
            "children": [
                {"op": "ts_delta", "children": [{"feature_id": "close"}], "window": 20},
                {"op": "ts_std", "children": [{"feature_id": "volume"}], "window": 20},
            ],
        },
    },
    # ── Mean-reversion / value skeletons ──
    {
        "name": "price_reversal",
        "description": "Short-term reversal: recent losers tend to rebound",
        "tree": {
            "op": "neg",
            "children": [{
                "op": "ts_pct",
                "children": [{"feature_id": "close"}],
                "window": 5,
            }],
        },
    },
    {
        "name": "deviation_from_ma",
        "description": "Price deviation from moving average — mean reversion",
        "tree": {
            "op": "div",
            "children": [
                {"op": "sub", "children": [
                    {"feature_id": "close"},
                    {"op": "ts_mean", "children": [{"feature_id": "close"}], "window": 20},
                ]},
                {"op": "ts_std", "children": [{"feature_id": "close"}], "window": 20},
            ],
        },
    },
    # ── Low-volatility / quality skeletons ──
    {
        "name": "volatility_scaled_return",
        "description": "Return per unit of risk (simple Sharpe-like)",
        "tree": {
            "op": "div",
            "children": [
                {"op": "ts_pct", "children": [{"feature_id": "close"}], "window": 20},
                {"op": "ts_std", "children": [{"feature_id": "close"}], "window": 20},
            ],
        },
    },
    {
        "name": "high_low_range",
        "description": "Daily range as fraction of price — volatility signal",
        "tree": {
            "op": "rank",
            "children": [{
                "op": "div",
                "children": [
                    {"op": "sub", "children": [
                        {"feature_id": "high"},
                        {"feature_id": "low"},
                    ]},
                    {"feature_id": "close"},
                ],
            }],
        },
    },
    # ── Volume / liquidity skeletons ──
    {
        "name": "volume_ratio",
        "description": "Current volume relative to recent average — liquidity signal",
        "tree": {
            "op": "div",
            "children": [
                {"feature_id": "volume"},
                {"op": "ts_mean", "children": [{"feature_id": "volume"}], "window": 20},
            ],
        },
    },
    {
        "name": "turnover_momentum",
        "description": "Volume trend — increasing volume may precede price moves",
        "tree": {
            "op": "ts_delta",
            "children": [{"feature_id": "volume"}],
            "window": 10,
        },
    },
    # ── Composite / interaction skeletons ──
    {
        "name": "volume_confirmed_momentum",
        "description": "Momentum × volume confirmation — stronger signal",
        "tree": {
            "op": "mul",
            "children": [
                {"op": "ts_delta", "children": [{"feature_id": "close"}], "window": 20},
                {"op": "div", "children": [
                    {"feature_id": "volume"},
                    {"op": "ts_mean", "children": [{"feature_id": "volume"}], "window": 20},
                ]},
            ],
        },
    },
    {
        "name": "reversal_with_vol_filter",
        "description": "Reversal signal dampened by high volatility",
        "tree": {
            "op": "div",
            "children": [
                {"op": "neg", "children": [
                    {"op": "ts_pct", "children": [{"feature_id": "close"}], "window": 5},
                ]},
                {"op": "ts_std", "children": [{"feature_id": "close"}], "window": 10},
            ],
        },
    },
]


def get_default_skeletons() -> list[ExpressionTree]:
    """Return the default set of known effective factor skeletons as ExpressionTrees.

    These are architectural templates — the GP will evolve windows,
    features, and sub-operators.
    """
    skeletons: list[ExpressionTree] = []
    for sk in _A_SHARE_SKELETONS:
        try:
            tree = ExpressionTree.from_dict(sk["tree"])
            if tree.complexity() <= MAX_COMPLEXITY:
                skeletons.append(tree)
        except Exception as exc:
            logger.debug("Failed to load skeleton %s: %s", sk.get("name"), exc)
    return skeletons


# ---------------------------------------------------------------------------
# Hybrid initialization
# ---------------------------------------------------------------------------

def hybrid_initialize_population(
    population_size: int,
    rng: random.Random | None = None,
    skeletons: list[ExpressionTree] | None = None,
    skeleton_ratio: float = 0.30,
    mutant_ratio: float = 0.40,
    random_ratio: float = 0.30,
    max_attempts_per_individual: int = 100,
) -> list[ExpressionTree]:
    """Generate an initial GP population using hybrid initialization.

    Ratios (should sum to 1.0):
        skeleton_ratio: Direct copies of known effective structures.
        mutant_ratio: Single-point mutations of skeleton structures.
        random_ratio: Fully random trees (maintains diversity).

    Args:
        population_size: Target population size.
        rng: Random number generator.
        skeletons: Custom skeleton trees (uses defaults if None).
        skeleton_ratio: Fraction from direct skeleton copies.
        mutant_ratio: Fraction from skeleton mutations.
        random_ratio: Fraction from fully random generation.
        max_attempts_per_individual: Max retries per individual to meet
            complexity constraints.

    Returns:
        List of ExpressionTrees for the initial population.
    """
    rng = rng or random.Random()
    skeletons = skeletons or get_default_skeletons()

    n_skeleton = max(0, int(population_size * skeleton_ratio))
    n_mutant = max(0, int(population_size * mutant_ratio))
    n_random = population_size - n_skeleton - n_mutant

    population: list[ExpressionTree] = []

    # ── 1. Skeleton seeds ──
    if skeletons:
        for _ in range(n_skeleton):
            sk = rng.choice(skeletons)
            population.append(ExpressionTree(sk.root.copy()))
    else:
        n_mutant += n_skeleton  # redistribute if no skeletons
        n_skeleton = 0

    # ── 2. Skeleton mutants ──
    if skeletons and n_mutant > 0:
        for _ in range(n_mutant):
            for _attempt in range(max_attempts_per_individual):
                sk = rng.choice(skeletons)
                mutant = sk.mutate(rng=rng, rate=0.3)  # Single-point mutation
                if mutant.complexity() <= MAX_COMPLEXITY:
                    population.append(mutant)
                    break
            else:
                # Fallback: random tree
                population.append(_safe_random_tree(rng))

    # ── 3. Fully random ──
    for _ in range(n_random):
        population.append(_safe_random_tree(rng))

    # Trim or pad to exact population_size
    if len(population) < population_size:
        for _ in range(population_size - len(population)):
            population.append(_safe_random_tree(rng))
    elif len(population) > population_size:
        population = population[:population_size]

    # Shuffle
    rng.shuffle(population)
    return population


def _safe_random_tree(
    rng: random.Random,
    max_depth: int = MAX_DEPTH,
    max_attempts: int = 100,
) -> ExpressionTree:
    """Generate a random tree that satisfies complexity constraints."""
    for _ in range(max_attempts):
        tree = ExpressionTree.random(rng=rng, max_depth=max_depth)
        if tree.complexity() <= MAX_COMPLEXITY:
            return tree
    # Fallback: single feature node
    return ExpressionTree(ExpressionNode(
        feature_id=rng.choice(FEATURE_IDS),
    ))


# ---------------------------------------------------------------------------
# Skeleton discovery from Alpha Zoo
# ---------------------------------------------------------------------------

def extract_skeletons_from_zoo(
    top_n: int = 10,
    min_ic: float = 0.02,
) -> list[ExpressionTree]:
    """Extract effective factor skeletons from the Alpha Zoo registry.

    Survivors in the Zoo with sustained positive IC provide the best
    architectural templates for seeding new GP runs.

    Args:
        top_n: Max number of skeletons to extract.
        min_ic: Minimum IC threshold for inclusion.

    Returns:
        List of ExpressionTree skeletons from the Zoo.
    """
    skeletons: list[ExpressionTree] = []
    try:
        from src.factors.registry import get_default_registry
        registry = get_default_registry()
        alpha_ids = registry.list()

        for aid in alpha_ids[: min(top_n * 3, len(alpha_ids))]:
            try:
                alpha = registry.get(aid)
                meta = getattr(alpha, "meta", {})
                ic = meta.get("ic", meta.get("train_ic", 0.0))
                if abs(ic) < min_ic:
                    continue
                tree_dict = meta.get("expression_json") or meta.get("tree")
                if tree_dict:
                    tree = ExpressionTree.from_dict(tree_dict)
                    if tree.complexity() <= MAX_COMPLEXITY:
                        skeletons.append(tree)
            except Exception:
                continue
            if len(skeletons) >= top_n:
                break
    except ImportError:
        logger.debug("Factor registry not available for skeleton extraction")
    except Exception as exc:
        logger.debug("Failed to extract skeletons from Zoo: %s", exc)

    return skeletons
