"""Bayesian optimization for strategy parameters.

Uses scikit-optimize (gp_minimize) if available, otherwise falls back to
random search with a warning.

Usage::

    from src.optimize.bayesian import BayesianOptimizer

    opt = BayesianOptimizer()
    config = {
        ...
        "params": {
            "ma_short": {"min": 5, "max": 50, "type": "int"},
            "ma_long":  {"min": 20, "max": 200, "type": "int"},
        },
        "n_calls": 50,
    }
    results = opt.run(config, strategy_code)
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np

from src.optimize.grid_search import _OBJECTIVE_FNS, _inject_params

logger = logging.getLogger(__name__)


class BayesianOptimizer:
    """Bayesian optimization using Gaussian Process surrogate model.

    Requires ``scikit-optimize`` (``pip install scikit-optimize``).
    Falls back to random search if not installed.
    """

    def __init__(self):
        self._progress_cb: Callable[[int, int, dict], None] | None = None

    def on_progress(self, cb: Callable[[int, int, dict], None]) -> None:
        self._progress_cb = cb

    def run(
        self,
        config: dict[str, Any],
        strategy_code: str,
    ) -> list[dict[str, Any]]:
        params_def = config.get("params", {})
        if not params_def:
            raise ValueError("config must contain 'params'")

        n_calls = config.get("n_calls", 50)
        objective_name = config.get("objective", "sharpe_ratio")
        seed = config.get("seed", 42)

        # Build dimensions and param names
        dims = []
        param_names = []
        param_types = []
        for name, p in params_def.items():
            param_names.append(name)
            if "values" in p:
                values = list(p["values"])
                param_types.append(("choice", values))
                # For skopt: treat as categorical
                dims.append(list(range(len(values))))
            else:
                ptype = p.get("type", "float")
                param_types.append((ptype, (p["min"], p["max"])))
                if ptype == "int":
                    dims.append((p["min"], p["max"]))
                else:
                    dims.append((float(p["min"]), float(p["max"])))

        try:
            from skopt import gp_minimize
            from skopt.space import Categorical, Integer, Real
            _has_skopt = True
        except ImportError:
            logger.warning("scikit-optimize not installed — falling back to random search")
            _has_skopt = False

        if not _has_skopt:
            from src.optimize.random_search import RandomSearchOptimizer
            fallback = RandomSearchOptimizer()
            if self._progress_cb:
                fallback.on_progress(self._progress_cb)
            config["n_iter"] = n_calls
            return fallback.run(config, strategy_code)

        # Build skopt dimensions
        space = []
        for name, p in params_def.items():
            if "values" in p:
                values = list(p["values"])
                space.append(Categorical(values, name=name))
            elif p.get("type") == "int":
                space.append(Integer(int(p["min"]), int(p["max"]), name=name))
            else:
                space.append(Real(float(p["min"]), float(p["max"]), name=name))

        all_results: list[dict] = []
        best_so_far = {"score": float("-inf")}

        def objective(x):
            params = {}
            for i, name in enumerate(param_names):
                spec = param_types[i]
                if spec[0] == "choice":
                    params[name] = spec[1][int(x[i])]
                elif spec[0] == "int":
                    params[name] = int(x[i])
                else:
                    params[name] = float(x[i])

            metrics = _run_single_static(config, strategy_code, params)
            if metrics is None:
                return 1e9  # large penalty

            fn = _OBJECTIVE_FNS.get(objective_name, _OBJECTIVE_FNS["sharpe_ratio"])
            score = fn(metrics)
            # skopt minimizes — negate for maximization
            neg_score = -score

            result = {"params": params, "metrics": metrics, "score": score}
            all_results.append(result)

            if score > best_so_far["score"]:
                best_so_far.update(result)

            if self._progress_cb:
                self._progress_cb(len(all_results), n_calls, best_so_far)

            return neg_score

        gp_minimize(objective, space, n_calls=n_calls, random_state=seed, n_jobs=1)

        all_results.sort(key=lambda r: r["score"], reverse=True)
        return all_results


def _run_single_static(config, strategy_code, params):
    """Static helper for Bayesian optimizer callback (can't use self)."""
    import json
    import tempfile
    from pathlib import Path

    try:
        code = _inject_params(strategy_code, params)
        tmp_dir = Path(tempfile.mkdtemp(prefix="bo_"))
        run_dir = tmp_dir / "run"
        run_dir.mkdir(parents=True)
        (run_dir / "code").mkdir()
        (run_dir / "signal_engine.py").write_text(code, encoding="utf-8")
        (run_dir / "config.json").write_text(json.dumps({
            **{k: v for k, v in config.items() if k != "params"},
        }), encoding="utf-8")

        from backtest.runner import main as run_backtest
        return run_backtest(run_dir)
    except Exception as exc:
        logger.debug("Bayesian run failed for %s: %s", params, exc)
        return None
