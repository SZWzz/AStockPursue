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
    node_type = "comparison"; category = "analysis"; label = "策略对比"
    description = "对比两个回测结果：paired t-test、bootstrap、CAPM 回归、White's Reality Check"
    icon = "GitCompare"
    inputs = [
        BaseNode.in_port("baseline", PortType.BACKTEST_RESULT,
                         description="基准策略回测结果（原有策略/对照）"),
        BaseNode.in_port("candidate", PortType.BACKTEST_RESULT,
                         description="候选策略回测结果（新策略/优化后）"),
    ]
    outputs = [
        BaseNode.out_port("comparison_report", PortType.COMPARISON_RESULT,
                          description="对比报告（统计检验 + 胜负判定）"),
    ]
    config_schema = {
        "tests": {
            "title": "检验方法", "type": "string",
            "enum": ["all", "paired_t", "bootstrap", "capm", "whites"],
            "default": "all",
        },
        "bootstrap_samples": {
            "title": "Bootstrap 样本数", "type": "integer", "default": 10000,
            "minimum": 1000, "maximum": 100000,
        },
        "rolling_window": {
            "title": "滚动窗口(天)", "type": "integer", "default": 252,
            "minimum": 20, "maximum": 1260,
            "description": "滚动窗口 Sharpe 对比的天数",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        bt_baseline = inputs.get("baseline", {})
        bt_candidate = inputs.get("candidate", {})

        if isinstance(bt_baseline, dict) and bt_baseline.get("error"):
            return {"comparison_report": {"error": f"基准策略错误: {bt_baseline['error']}"}}
        if isinstance(bt_candidate, dict) and bt_candidate.get("error"):
            return {"comparison_report": {"error": f"候选策略错误: {bt_candidate['error']}"}}

        tests_wanted = config.get("tests", "all")
        n_bootstrap = int(config.get("bootstrap_samples", 10000))
        roll_window = int(config.get("rolling_window", 252))

        # ── Extract metrics ───────────────────────────────────────────────────
        metrics_a = self._get_metrics(bt_baseline)
        metrics_b = self._get_metrics(bt_candidate)

        # ── Extract equity curves (daily returns) ─────────────────────────────
        equity_a = self._get_equity(bt_baseline)
        equity_b = self._get_equity(bt_candidate)

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
                report["winner"][key] = "基准" if a_val > b_val else "候选" if b_val > a_val else "tie"

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


# ── Consistency Check ────────────────────────────────────────────────────


@register_node
class ConsistencyCheckNode(BaseNode):
    """Compare fast-mode vs simulation-mode backtest results.

    Detects pipeline bugs and look-ahead bias by verifying that both modes
    produce similar results.  Fast mode pre-computes weights; simulation
    mode generates signals bar-by-bar (matches live).  A divergence > threshold
    flags a potential issue.

    Typical wiring::

        [StrategyNode] ─┬─→ [Backtest(mode=fast)] ─┐
                         │                          ├→ [ConsistencyCheck]
                         └─→ [Backtest(mode=sim)]  ─┘
    """

    node_type = "consistency_check"
    category = "validation"
    label = "一致性校验"
    description = "对比快速模式与模拟模式回测结果，发现潜在的前视偏差或管线 bug"
    icon = "CheckCircle"
    resource_profile = "cpu_bound"

    inputs = [
        BaseNode.in_port("fast_result", PortType.BACKTEST_RESULT,
                         description="快速模式回测结果"),
        BaseNode.in_port("sim_result", PortType.BACKTEST_RESULT,
                         description="模拟模式回测结果"),
    ]
    outputs = [
        BaseNode.out_port("consistency_report", PortType.PARAMS,
                          description="偏差报告（含 pass/fail 判定）"),
        BaseNode.out_port("is_consistent", PortType.BOOL,
                          description="两个模式是否在阈值内一致"),
    ]
    config_schema = {
        "return_threshold": {
            "title": "收益偏差阈值",
            "type": "number", "default": 0.01,
            "description": "total_return 最大允许绝对偏差",
        },
        "sharpe_threshold": {
            "title": "Sharpe 偏差阈值",
            "type": "number", "default": 0.1,
            "description": "sharpe_ratio 最大允许绝对偏差",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        def _metrics(r: dict | None) -> dict:
            if isinstance(r, dict):
                return r.get("metrics", r)
            return {}

        fast = _metrics(inputs.get("fast_result"))
        sim = _metrics(inputs.get("sim_result"))

        return_threshold = float(config.get("return_threshold", 0.01))
        sharpe_threshold = float(config.get("sharpe_threshold", 0.1))

        ret_diff = abs(fast.get("total_return", 0) - sim.get("total_return", 0))
        sharpe_diff = abs(fast.get("sharpe_ratio", fast.get("sharpe", 0))
                         - sim.get("sharpe_ratio", sim.get("sharpe", 0)))
        dd_diff = abs(fast.get("max_drawdown", 0) - sim.get("max_drawdown", 0))

        is_consistent = (
            ret_diff <= return_threshold
            and sharpe_diff <= sharpe_threshold
        )

        report = {
            "return_diff": round(ret_diff, 6),
            "sharpe_diff": round(sharpe_diff, 6),
            "drawdown_diff": round(dd_diff, 6),
            "is_consistent": is_consistent,
            "verdict": "PASS" if is_consistent else "FAIL — possible look-ahead bias or pipeline bug",
            "fast_summary": {
                "total_return": fast.get("total_return"),
                "sharpe": fast.get("sharpe_ratio", fast.get("sharpe")),
                "max_drawdown": fast.get("max_drawdown"),
            },
            "sim_summary": {
                "total_return": sim.get("total_return"),
                "sharpe": sim.get("sharpe_ratio", sim.get("sharpe")),
                "max_drawdown": sim.get("max_drawdown"),
            },
        }

        logger.info(
            "ConsistencyCheck: %s (ret_diff=%.4f%%, sharpe_diff=%.4f)",
            "PASS" if is_consistent else "FAIL",
            ret_diff * 100, sharpe_diff,
        )

        return {
            "consistency_report": report,
            "is_consistent": is_consistent,
        }
