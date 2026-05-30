"""Random search parameter optimization.

Samples parameter combinations uniformly from defined ranges.
Best for 4-10 parameters where grid search is infeasible.

Usage::

    from src.optimize.random_search import RandomSearchOptimizer

    opt = RandomSearchOptimizer()
    config = {
        ...
        "params": {
            "ma_short": {"min": 5, "max": 30, "type": "int"},
            "ma_long":  {"min": 20, "max": 200, "type": "int"},
            "atr_mult": {"min": 1.0, "max": 5.0, "type": "float"},
        },
        "n_iter": 200,
    }
    results = opt.run(config, strategy_code)
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np

from src.optimize.grid_search import _OBJECTIVE_FNS, _inject_params, GridSearchOptimizer

logger = logging.getLogger(__name__)


class RandomSearchOptimizer(GridSearchOptimizer):
    """Random search over continuous/discrete parameter spaces.

    Extends GridSearchOptimizer, overriding the grid generation with random sampling.
    """

    def run(
        self,
        config: dict[str, Any],
        strategy_code: str,
    ) -> list[dict[str, Any]]:
        params_def = config.get("params", {})
        if not params_def:
            raise ValueError("config must contain 'params'")

        n_iter = config.get("n_iter", 100)
        objective_fn = _OBJECTIVE_FNS.get(config.get("objective", "sharpe_ratio"), _OBJECTIVE_FNS["sharpe_ratio"])
        rng = np.random.default_rng(config.get("seed", 42))

        # Pre-compute param spec
        param_specs = {}
        for name, p in params_def.items():
            ptype = p.get("type", "float")
            if "values" in p:
                param_specs[name] = {"type": "choice", "values": list(p["values"])}
            elif all(k in p for k in ("min", "max")):
                param_specs[name] = {
                    "type": ptype,
                    "min": p["min"],
                    "max": p["max"],
                }
            else:
                raise ValueError(f"Param {name}: need 'values' or ('min','max')")

        results = []
        best = None
        best_score = float("-inf")

        for i in range(n_iter):
            params = {}
            for name, spec in param_specs.items():
                if spec["type"] == "choice":
                    params[name] = rng.choice(spec["values"])
                elif spec["type"] == "int":
                    params[name] = int(rng.integers(spec["min"], spec["max"] + 1))
                else:  # float
                    params[name] = float(rng.uniform(spec["min"], spec["max"]))

            metrics = self._run_single(config, strategy_code, params)
            if metrics is None:
                continue

            score = objective_fn(metrics)
            result = {"params": params, "metrics": metrics, "score": score}
            results.append(result)

            if score > best_score:
                best_score = score
                best = result

            if self._progress_cb:
                self._progress_cb(i + 1, n_iter, best)

        results.sort(key=lambda r: r["score"], reverse=True)
        return results
