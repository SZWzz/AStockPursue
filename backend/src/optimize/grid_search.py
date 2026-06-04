"""Grid search parameter optimization for backtest strategies.

Usage::

    from src.optimize.grid_search import GridSearchOptimizer

    opt = GridSearchOptimizer()
    config = {
        "codes": ["600519.SH"],
        "start_date": "2024-01-01",
        "end_date": "2025-12-31",
        "source": "auto",
        "interval": "1D",
        "initial_cash": 100000,
        "params": {
            "ma_short": {"values": [5, 10, 15, 20]},
            "ma_long":  {"values": [30, 50, 80, 120]},
        },
        "objective": "sharpe_ratio",
    }
    results = opt.run(config, strategy_code)
"""

from __future__ import annotations

import itertools
import json
import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import pandas as pd

logger = logging.getLogger(__name__)

_OBJECTIVE_FNS: dict[str, Callable] = {
    "sharpe_ratio": lambda m: m.get("sharpe_ratio", 0),
    "calmar_ratio": lambda m: m.get("calmar_ratio", 0),
    "profit_factor": lambda m: m.get("profit_factor", 0),
    "total_return": lambda m: m.get("total_return", 0),
    "win_rate": lambda m: m.get("win_rate", 0),
    "sortino_ratio": lambda m: m.get("sortino_ratio", 0),
}


class GridSearchOptimizer:
    """Exhaustive grid search over discrete parameter values.

    Best for 2-3 parameters with small value sets (4-6 values each).
    """

    def __init__(self):
        self._progress_cb: Callable[[int, int, dict], None] | None = None

    def on_progress(self, cb: Callable[[int, int, dict], None]) -> None:
        """Register a progress callback: cb(completed, total, best_so_far)."""
        self._progress_cb = cb

    def run(
        self,
        config: dict[str, Any],
        strategy_code: str,
    ) -> list[dict[str, Any]]:
        """Run grid search.

        Args:
            config: Backtest config with ``params`` key containing param grids.
                Each param has ``values`` (list) or ``range`` (min, max, step).
            strategy_code: Python strategy source code with ``# @param`` markers.

        Returns:
            List of {params, metrics} sorted by objective descending.
        """
        params_def = config.get("params", {})
        if not params_def:
            raise ValueError("config must contain 'params' with parameter grids")

        # Build grid
        param_names = list(params_def.keys())
        param_values = []
        for name in param_names:
            p = params_def[name]
            if "values" in p:
                param_values.append(list(p["values"]))
            elif all(k in p for k in ("min", "max", "step")):
                vals = []
                v = p["min"]
                while v <= p["max"]:
                    vals.append(v)
                    v += p["step"]
                param_values.append(vals)
            else:
                raise ValueError(f"Param {name} must have 'values' or ('min','max','step')")

        total = 1
        for v in param_values:
            total *= len(v)
        logger.info("Grid search: %d params, %d combinations", len(param_names), total)

        objective_fn = _OBJECTIVE_FNS.get(config.get("objective", "sharpe_ratio"), _OBJECTIVE_FNS["sharpe_ratio"])

        results = []
        best = None
        best_score = float("-inf")

        for idx, combo in enumerate(itertools.product(*param_values)):
            param_dict = dict(zip(param_names, combo))
            metrics = self._run_single(config, strategy_code, param_dict)

            if metrics is None:
                continue

            score = objective_fn(metrics)
            result = {"params": param_dict, "metrics": metrics, "score": score}
            results.append(result)

            if score > best_score:
                best_score = score
                best = result

            if self._progress_cb:
                self._progress_cb(idx + 1, total, best)

        results.sort(key=lambda r: r["score"], reverse=True)
        return results

    def _run_single(
        self,
        config: dict,
        strategy_code: str,
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Run a single backtest with given parameters."""
        try:
            # Inject params into strategy code
            code = _inject_params(strategy_code, params)

            tmp_dir = Path(tempfile.mkdtemp(prefix="gs_"))
            run_dir = tmp_dir / "run"
            run_dir.mkdir(parents=True)
            (run_dir / "code").mkdir()
            (run_dir / "signal_engine.py").write_text(code, encoding="utf-8")
            (run_dir / "config.json").write_text(json.dumps({
                **{k: v for k, v in config.items() if k != "params"},
                "optimizer_params": params,
            }), encoding="utf-8")

            from backtest.runner import main as run_backtest
            metrics = run_backtest(run_dir)
            return metrics
        except Exception as exc:
            logger.debug("Grid search run failed for %s: %s", params, exc)
            return None


def _inject_params(code: str, params: dict[str, Any]) -> str:
    """Replace # @param markers in strategy code with actual values."""
    import re
    for name, value in params.items():
        pattern = rf'(#\s*@param\s+{name}\s*[=\:]\s*).*'
        replacement = rf'\g<1>{value}'
        code = re.sub(pattern, replacement, code)

        # Also replace self.<name> = <default> patterns
        pattern2 = rf'(self\.{name}\s*=\s*).*'
        if isinstance(value, (int, float)):
            replacement2 = rf'\g<1>{value}'
            code = re.sub(pattern2, replacement2, code)

    return code
