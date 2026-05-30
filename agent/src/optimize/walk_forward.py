"""Walk-Forward optimization — parameter stability across rolling windows.

Splits historical data into N train/test windows.  For each window:
  1. Optimize parameters on training period
  2. Evaluate with frozen params on test period
  3. Report OOS (out-of-sample) metrics + parameter stability

Usage::

    from src.optimize.walk_forward import WalkForwardAnalyzer

    wf = WalkForwardAnalyzer()
    results = wf.run(config, strategy_code)
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.optimize.grid_search import _OBJECTIVE_FNS, _inject_params

logger = logging.getLogger(__name__)


class WalkForwardAnalyzer:
    """Walk-forward analysis with in-window parameter optimization."""

    def __init__(self):
        self._progress_cb: Callable[[int, int, dict], None] | None = None

    def on_progress(self, cb: Callable[[int, int, dict], None]) -> None:
        self._progress_cb = cb

    def run(
        self,
        config: dict[str, Any],
        strategy_code: str,
        n_windows: int = 5,
        train_ratio: float = 0.7,
        search_method: str = "grid",
    ) -> dict[str, Any]:
        """Run walk-forward analysis.

        Args:
            config: Backtest config with ``params`` key.
            strategy_code: Strategy source code.
            n_windows: Number of rolling windows.
            train_ratio: Fraction of each window used for training (default 0.7).
            search_method: ``"grid"``, ``"random"``, or ``"bayesian"``.

        Returns:
            {windows: [{params, is_metrics, oos_metrics, ...}],
             param_stability: {param: {mean, std}},
             oos_sharpe_mean, oos_sharpe_std,
             consistency_rate (fraction of profitable OOS windows),
             is_oos_correlation (correlation between IS and OOS Sharpe)}.
        """
        start_date = pd.Timestamp(config.get("start_date", "2020-01-01"))
        end_date = pd.Timestamp(config.get("end_date", "2025-12-31"))
        total_days = (end_date - start_date).days
        window_days = total_days // n_windows

        if window_days < 60:
            return {"error": f"Need more data: only {window_days}d per window"}

        windows = []
        objective_fn = _OBJECTIVE_FNS.get(config.get("objective", "sharpe_ratio"), _OBJECTIVE_FNS["sharpe_ratio"])

        for w in range(n_windows):
            w_start = start_date + pd.Timedelta(days=w * window_days)
            w_end = min(start_date + pd.Timedelta(days=(w + 1) * window_days), end_date)
            train_end = w_start + pd.Timedelta(days=int(window_days * train_ratio))

            train_start_str = w_start.strftime("%Y-%m-%d")
            train_end_str = train_end.strftime("%Y-%m-%d")
            test_end_str = w_end.strftime("%Y-%m-%d")

            # Phase 1: Optimize on training data
            train_config = {**config, "start_date": train_start_str, "end_date": train_end_str}
            best_params = self._optimize(train_config, strategy_code, search_method, objective_fn)

            if best_params is None:
                windows.append({"window": w + 1, "error": "optimization failed"})
                continue

            # Phase 2: Evaluate on test data (OOS) with frozen params
            test_config = {**config, "start_date": train_end_str, "end_date": test_end_str}
            oos_metrics = self._evaluate(test_config, strategy_code, best_params)

            # Phase 3: Evaluate on full window (IS) for comparison
            full_config = {**config, "start_date": train_start_str, "end_date": test_end_str}
            is_metrics = self._evaluate(full_config, strategy_code, best_params)

            window_result = {
                "window": w + 1,
                "train_start": train_start_str,
                "train_end": train_end_str,
                "test_end": test_end_str,
                "params": best_params,
                "oos_metrics": oos_metrics,
                "is_metrics": is_metrics,
            }
            windows.append(window_result)

            if self._progress_cb:
                self._progress_cb(w + 1, n_windows, window_result)

        # Aggregate results
        return self._aggregate(windows, objective_fn)

    def _optimize(self, config, code, method, obj_fn):
        """Run optimization on training data."""
        try:
            if method == "grid":
                from src.optimize.grid_search import GridSearchOptimizer
                opt = GridSearchOptimizer()
            elif method == "random":
                from src.optimize.random_search import RandomSearchOptimizer
                opt = RandomSearchOptimizer()
            else:
                from src.optimize.bayesian import BayesianOptimizer
                opt = BayesianOptimizer()

            results = opt.run(config, code)
            if not results:
                return None
            return results[0]["params"]  # best params
        except Exception as exc:
            logger.debug("WF optimize error: %s", exc)
            return None

    def _evaluate(self, config, code, params):
        """Run a single backtest with frozen params."""
        import json, tempfile
        from pathlib import Path

        try:
            injected = _inject_params(code, params)
            tmp_dir = Path(tempfile.mkdtemp(prefix="wf_"))
            run_dir = tmp_dir / "run"
            run_dir.mkdir(parents=True)
            (run_dir / "code").mkdir()
            (run_dir / "signal_engine.py").write_text(injected, encoding="utf-8")
            (run_dir / "config.json").write_text(json.dumps({
                **{k: v for k, v in config.items() if k != "params"},
            }), encoding="utf-8")

            from backtest.runner import main as run_backtest
            return run_backtest(run_dir)
        except Exception as exc:
            logger.debug("WF evaluate error: %s", exc)
            return None

    def _aggregate(self, windows, obj_fn):
        """Compute aggregate walk-forward metrics."""
        valid = [w for w in windows if "error" not in w]
        if not valid:
            return {"error": "no valid windows", "windows": windows}

        oos_sharpes = [obj_fn(w["oos_metrics"]) for w in valid if w.get("oos_metrics")]
        is_sharpes = [obj_fn(w["is_metrics"]) for w in valid if w.get("is_metrics")]
        profitable = sum(1 for w in valid if w.get("oos_metrics", {}).get("total_return", 0) > 0)

        # Parameter stability: for each param, compute mean/std across windows
        param_names = list(valid[0]["params"].keys())
        param_stability = {}
        for pname in param_names:
            vals = [w["params"][pname] for w in valid if pname in w["params"]]
            if vals:
                param_stability[pname] = {
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals)),
                    "values": vals,
                }

        # IS/OOS correlation
        correlation = 0.0
        if len(is_sharpes) == len(oos_sharpes) and len(is_sharpes) > 2:
            correlation = float(np.corrcoef(is_sharpes, oos_sharpes)[0, 1])

        return {
            "n_windows": len(valid),
            "windows": windows,
            "oos_sharpe_mean": round(float(np.mean(oos_sharpes)), 4) if oos_sharpes else 0,
            "oos_sharpe_std": round(float(np.std(oos_sharpes)), 4) if oos_sharpes else 0,
            "is_sharpe_mean": round(float(np.mean(is_sharpes)), 4) if is_sharpes else 0,
            "consistency_rate": round(profitable / len(valid), 4),
            "param_stability": param_stability,
            "is_oos_correlation": round(correlation, 4),
        }
