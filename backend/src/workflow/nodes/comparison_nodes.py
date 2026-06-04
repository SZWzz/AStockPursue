"""Backtest comparison node — statistical tests between two backtest results."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class ComparisonNode(BaseNode):
    node_type = "comparison"; category = "analysis"; label = "Compare"
    description = (
        "Compare two backtest results with statistical tests: "
        "paired t-test, bootstrap, CAPM regression, White's Reality Check."
    )
    icon = "GitCompare"
    inputs = [
        BaseNode.in_port("backtest_a", PortType.BACKTEST_RESULT,
                         description="First backtest result"),
        BaseNode.in_port("backtest_b", PortType.BACKTEST_RESULT,
                         description="Second backtest result"),
    ]
    outputs = [
        BaseNode.out_port("comparison_report", PortType.COMPARISON_RESULT,
                          description="Comparison report with test results and verdict"),
    ]
    config_schema = {
        "tests": {
            "title": "Tests", "type": "string",
            "enum": ["all", "paired_t", "bootstrap", "capm", "whites"],
            "default": "all",
        },
        "bootstrap_samples": {
            "title": "Bootstrap Samples", "type": "integer", "default": 10000,
            "minimum": 1000, "maximum": 100000,
        },
        "rolling_window": {
            "title": "Rolling Window", "type": "integer", "default": 252,
            "minimum": 20, "maximum": 1260,
            "description": "Days for rolling window Sharpe comparison",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        bt_a = inputs.get("backtest_a", {})
        bt_b = inputs.get("backtest_b", {})

        if isinstance(bt_a, dict) and bt_a.get("error"):
            return {"comparison_report": {"error": f"Backtest A error: {bt_a['error']}"}}
        if isinstance(bt_b, dict) and bt_b.get("error"):
            return {"comparison_report": {"error": f"Backtest B error: {bt_b['error']}"}}

        tests_wanted = config.get("tests", "all")
        n_bootstrap = int(config.get("bootstrap_samples", 10000))
        roll_window = int(config.get("rolling_window", 252))

        # ── Extract metrics ───────────────────────────────────────────────────
        metrics_a = self._get_metrics(bt_a)
        metrics_b = self._get_metrics(bt_b)

        # ── Extract equity curves (daily returns) ─────────────────────────────
        equity_a = self._get_equity(bt_a)
        equity_b = self._get_equity(bt_b)

        returns_a = None
        returns_b = None
        if equity_a is not None and len(equity_a) > 1:
            returns_a = np.diff(equity_a) / (equity_a[:-1] + 1e-9)
        if equity_b is not None and len(equity_b) > 1:
            returns_b = np.diff(equity_b) / (equity_b[:-1] + 1e-9)

        report: Dict[str, Any] = {
            "metrics_a": metrics_a,
            "metrics_b": metrics_b,
            "winner": {},
        }

        # ── Simple metric delta ───────────────────────────────────────────────
        for key in ["sharpe", "total_return", "annual_return", "max_drawdown", "win_rate"]:
            a_val = metrics_a.get(key)
            b_val = metrics_b.get(key)
            if a_val is not None and b_val is not None:
                report["winner"][key] = "A" if a_val > b_val else "B" if b_val > a_val else "tie"

        # ── Run statistical tests ─────────────────────────────────────────────
        if returns_a is not None and returns_b is not None and len(returns_a) > 1 and len(returns_b) > 1:
            min_len = min(len(returns_a), len(returns_b))
            ra = np.array(returns_a[:min_len])
            rb = np.array(returns_b[:min_len])

            try:
                from src.services.statistical_tests import StatisticalTestEngine
                engine = StatisticalTestEngine()

                if tests_wanted in ("all", "paired_t"):
                    report["paired_t"] = engine.paired_t_test(ra, rb)

                if tests_wanted in ("all", "bootstrap"):
                    report["bootstrap"] = engine.bootstrap_ci(ra, rb, n=n_bootstrap)

                if tests_wanted in ("all", "whites"):
                    report["whites"] = engine.whites_reality_check(ra, rb)

                if tests_wanted in ("all", "capm"):
                    report["capm"] = engine.capm_regression(ra, rb)

                if tests_wanted in ("all", "rolling_sharpe"):
                    report["rolling_sharpe"] = engine.rolling_window_sharpe(ra, rb, window=roll_window)

            except ImportError:
                # Fallback: basic tests without the engine
                report["_fallback"] = True
                report["paired_t"] = self._simple_paired_t(ra, rb)
                report["bootstrap"] = self._simple_bootstrap(ra, rb, n=n_bootstrap)
        else:
            report["_no_returns"] = True
            report["note"] = "No return series available — showing metric deltas only"

        logger.info("Compare: winner=%s", {k: v for k, v in report.get("winner", {}).items() if v != "tie"})
        return {"comparison_report": report}

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_metrics(bt_result: Any) -> Dict[str, float]:
        if isinstance(bt_result, dict):
            m = bt_result.get("metrics", {})
            if isinstance(m, dict):
                return {k: float(v) for k, v in m.items() if isinstance(v, (int, float))}
            s = bt_result.get("summary", {})
            if isinstance(s, dict):
                return {k: float(v) for k, v in s.items() if isinstance(v, (int, float))}
        return {}

    @staticmethod
    def _get_equity(bt_result: Any):
        if isinstance(bt_result, dict):
            eq = bt_result.get("equity_curve") or bt_result.get("equity")
            if eq is not None:
                if isinstance(eq, list):
                    return np.array(eq, dtype=float)
                if hasattr(eq, "__array__"):
                    return np.asarray(eq, dtype=float)
        return None

    @staticmethod
    def _simple_paired_t(ra: np.ndarray, rb: np.ndarray) -> dict:
        diff = ra - rb
        n = len(diff)
        if n < 2:
            return {"error": "Too few observations"}
        mean_diff = float(np.mean(diff))
        std_diff = float(np.std(diff, ddof=1))
        t_stat = mean_diff / (std_diff / np.sqrt(n) + 1e-9)
        return {"mean_diff": round(mean_diff, 6), "t_stat": round(t_stat, 4), "n": n}

    @staticmethod
    def _simple_bootstrap(ra: np.ndarray, rb: np.ndarray, n: int = 10000) -> dict:
        diff = ra - rb
        if len(diff) < 2:
            return {"error": "Too few observations"}
        rng = np.random.default_rng(42)
        boot_means = np.array([np.mean(rng.choice(diff, size=len(diff), replace=True)) for _ in range(n)])
        prob_a_better = float(np.mean(boot_means > 0))
        ci_lower = float(np.percentile(boot_means, 2.5))
        ci_upper = float(np.percentile(boot_means, 97.5))
        return {
            "prob_a_better_than_b": round(prob_a_better, 4),
            "sharpe_diff_ci95": [round(ci_lower, 6), round(ci_upper, 6)],
            "n_bootstrap": n,
        }
