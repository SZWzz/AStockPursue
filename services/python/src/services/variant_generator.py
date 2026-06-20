"""Strategy variant generator — produce candidate variants from a base strategy.

Supports three modes:
  1. grid:  Cartesian product of parameter space → shuffle → truncate
  2. random: Random sampling from parameter space
  3. llm:   LLM-suggested parameters based on regime (Phase 5 integration)
"""

from __future__ import annotations

import copy
import itertools
import logging
import random
from typing import Any

logger = logging.getLogger(__name__)


class VariantGenerator:
    """Generate strategy configuration variants from a parameter space.

    Parameter space format::

        {
            "strategy_config.risk.stop_loss_pct": [0.01, 0.02, 0.03, 0.05],
            "strategy_config.risk.take_profit_pct": [0.03, 0.05, 0.08, 0.10],
            "top_n": [3, 5, 10, 20],
        }

    Each key is a dotted path for deep-set; each value is a list of
    candidate values.
    """

    def generate(
        self,
        base_snapshot: dict,
        parameter_space: dict[str, list],
        method: str = "grid",
        max_variants: int = 24,
        seed: int | None = None,
    ) -> list[dict]:
        """Generate candidate strategy variants.

        Args:
            base_snapshot: Base strategy configuration dict (deep-copied per variant).
            parameter_space: ``{path: [values]}`` mapping.
            method: ``"grid"`` or ``"random"``.
            max_variants: Maximum number of variants to return.
            seed: Random seed for reproducibility.

        Returns:
            List of variant dicts, each a deep copy of *base_snapshot* with
            one combination of parameter overrides applied.  Each variant
            includes a ``_variant_meta`` key with the applied overrides.
        """
        if not parameter_space:
            return [base_snapshot]

        rng = random.Random(seed)

        # Flatten all combinations
        keys = list(parameter_space.keys())
        value_lists = [parameter_space[k] for k in keys]
        all_combos = list(itertools.product(*value_lists))

        if method == "grid":
            rng.shuffle(all_combos)
            combos = all_combos[:max_variants]
        elif method == "random":
            combos = []
            seen = set()
            max_attempts = max_variants * 10
            attempts = 0
            while len(combos) < max_variants and attempts < max_attempts:
                attempts += 1
                combo = tuple(rng.choice(vl) for vl in value_lists)
                if combo not in seen:
                    seen.add(combo)
                    combos.append(combo)
        else:
            raise ValueError(f"Unknown method: {method!r}. Use 'grid' or 'random'.")

        # Build variants
        variants = []
        for combo in combos:
            variant = copy.deepcopy(base_snapshot)
            overrides = {}
            for key, val in zip(keys, combo):
                overrides[key] = val
                _deep_set(variant, key, val)
            variant["_variant_meta"] = {"overrides": overrides, "method": method}
            variants.append(variant)

        logger.info(
            "Generated %d variants from %d-param space (method=%s, max=%d)",
            len(variants), len(keys), method, max_variants,
        )
        return variants


def _deep_set(d: dict, dotted_path: str, value: Any) -> None:
    """Set a nested dict value by dotted path.

    Example: ``_deep_set(d, "a.b.c", 42)`` → ``d["a"]["b"]["c"] = 42``
    """
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        if part not in d or not isinstance(d[part], dict):
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value
