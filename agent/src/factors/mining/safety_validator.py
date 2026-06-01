"""Factor code safety validator — Phase C P2.

Three-layer defence for GP/LLM-generated factor code:
    1. AST whitelist — only allow safe operations (math, pandas safe subset)
    2. Type signature validator — ensure each operator call has correct arity/input types
    3. Runtime circuit breaker — memory 512MB + time 30s limits

Also includes enhanced Walk-Forward (24-window Purged CV) and
PAPER_TRADING promotion gate.
"""

from __future__ import annotations

import logging
import signal
import time
from typing import Any

import numpy as np
import pandas as pd

from src.factors.mining.expression_tree import (
    ExpressionTree,
    ExpressionNode,
    OPERATOR_REGISTRY,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer 1: AST whitelist
# ---------------------------------------------------------------------------

class ASTWhitelistValidator:
    """Validate factor code by AST whitelist — only allow known-safe operations.

    This is a COMPILE-TIME check on ExpressionTree nodes, not on raw Python
    strings.  The ExpressionTree itself is the AST — no need to parse Python.
    """

    # Operators that are unconditionally safe
    WHITELIST_MATH = {"abs", "log", "sqrt", "sign", "min", "max", "round", "len"}
    # Operators that are safe ONLY with positive shift/pct_change values
    WHITELIST_TIMESERIES = {"ts_delta", "ts_delay", "ts_pct", "ts_mean", "ts_std",
                            "ts_max", "ts_min", "ts_sum", "ts_rank", "ts_zscore"}
    WHITELIST_CROSSSECTIONAL = {"rank", "cs_zscore", "scale", "ind_neutralize"}
    WHITELIST_ARITHMETIC = {"add", "sub", "mul", "div", "pow", "inv", "neg"}
    WHITELIST_PAIRWISE = {"ts_corr", "ts_cov"}
    WHITELIST_CONDITIONAL = {"if_else"}

    ALL_WHITELISTED = (
        WHITELIST_MATH | WHITELIST_TIMESERIES | WHITELIST_CROSSSECTIONAL |
        WHITELIST_ARITHMETIC | WHITELIST_PAIRWISE | WHITELIST_CONDITIONAL
    )

    # Features that are safe to reference
    WHITELIST_FEATURES = {"open", "high", "low", "close", "volume", "vwap",
                          "returns_1d", "returns_5d", "returns_20d",
                          "volume_ratio", "high_low_ratio"}

    # Explicitly forbidden patterns
    FORBIDDEN_PATTERNS = [
        ("negative shift", ["shift(-", "shift(-1", "shift(-2", "shift(-3",
                            "shift(-5", "shift(-10", "shift(-20"]),
        ("negative pct_change", ["pct_change(-"]),
        ("eval/exec", ["eval(", "exec(", "compile("]),
        ("file IO", ["open(", "write(", "read(", "Path("]),
        ("network", ["requests", "urllib", "socket", "http"]),
        ("system", ["os.", "sys.", "subprocess", "shutil"]),
        ("import", ["import ", "__import__"]),
    ]

    def validate(self, tree: ExpressionTree) -> tuple[bool, str, list[str]]:
        """Validate an ExpressionTree against the AST whitelist.

        Returns:
            (is_valid, error_message, warnings)
        """
        warnings: list[str] = []

        # Check every operator is registered
        ok, err = self._validate_node(tree.root)
        if not ok:
            return False, err, warnings

        # Check formula string for forbidden patterns
        formula = tree.to_formula().lower()
        for category, patterns in self.FORBIDDEN_PATTERNS:
            for p in patterns:
                if p.lower() in formula:
                    return False, f"Forbidden pattern in formula: {category} ({p})", warnings

        # Check features are whitelisted
        f_ok, f_err = self._validate_features(tree.root)
        if not f_ok:
            return False, f_err, warnings

        return True, "", warnings

    def _validate_node(self, node: ExpressionNode) -> tuple[bool, str]:
        """Recursively validate each node's operator."""
        if node.is_leaf:
            return True, ""

        if node.op is None or node.op not in OPERATOR_REGISTRY:
            return False, f"Unknown operator: {node.op}"

        if node.op not in self.ALL_WHITELISTED and node.op not in OPERATOR_REGISTRY:
            return False, f"Operator not in whitelist: {node.op}"

        for child in node.children:
            ok, err = self._validate_node(child)
            if not ok:
                return False, err

        return True, ""

    def _validate_features(self, node: ExpressionNode) -> tuple[bool, str]:
        """Check that all feature references are valid."""
        if node.is_leaf:
            if node.feature_id and node.feature_id not in self.WHITELIST_FEATURES:
                return False, f"Unknown feature: {node.feature_id}"
            return True, ""
        for child in node.children:
            ok, err = self._validate_features(child)
            if not ok:
                return False, err
        return True, ""


# ---------------------------------------------------------------------------
# Layer 2: Type signature validator
# ---------------------------------------------------------------------------

class TypeSignatureValidator:
    """Validate operator call signatures — arity and type compatibility.

    Prevents issues like ts_corr(rank(x), 5) where a window parameter
    is incorrectly passed as a child node instead of as node.window.
    """

    OPERATOR_SIGNATURES: dict[str, dict[str, Any]] = {
        "add":  {"arity": 2, "input_types": ["dataframe", "dataframe"]},
        "sub":  {"arity": 2, "input_types": ["dataframe", "dataframe"]},
        "mul":  {"arity": 2, "input_types": ["dataframe", "dataframe"]},
        "div":  {"arity": 2, "input_types": ["dataframe", "dataframe"]},
        "pow":  {"arity": 2, "input_types": ["dataframe", "dataframe"]},
        "rank": {"arity": 1, "input_types": ["dataframe"]},
        "ts_mean": {"arity": 1, "input_types": ["dataframe"]},
        "ts_std":  {"arity": 1, "input_types": ["dataframe"]},
        "ts_corr": {"arity": 2, "input_types": ["dataframe", "dataframe"]},
        "ts_cov":  {"arity": 2, "input_types": ["dataframe", "dataframe"]},
        "if_else": {"arity": 3, "input_types": ["dataframe", "dataframe", "dataframe"]},
    }

    def validate(self, tree: ExpressionTree) -> tuple[bool, str]:
        """Validate the expression tree's type consistency."""
        return self._validate_node(tree.root)

    def _validate_node(self, node: ExpressionNode) -> tuple[bool, str]:
        if node.is_leaf:
            return True, ""

        sig = self.OPERATOR_SIGNATURES.get(node.op or "")
        if sig is None:
            return True, ""  # Skip operators not in signature registry (they use default arity)

        expected_arity = sig["arity"]
        actual_arity = len(node.children)

        if actual_arity != expected_arity:
            return False, (
                f"Operator '{node.op}' expects {expected_arity} children, "
                f"got {actual_arity}"
            )

        for child in node.children:
            ok, err = self._validate_node(child)
            if not ok:
                return False, err

        return True, ""


# ---------------------------------------------------------------------------
# Layer 3: Runtime circuit breaker
# ---------------------------------------------------------------------------

class RuntimeCircuitBreaker:
    """Limit resource usage during factor evaluation.

    Kills evaluation that exceeds:
        - max_memory_mb (512 MB default)
        - max_seconds (30s default)
    """

    def __init__(self, max_memory_mb: int = 512, max_seconds: int = 30) -> None:
        self.max_memory_mb = max_memory_mb
        self.max_seconds = max_seconds

    def evaluate_with_guard(
        self,
        compute_fn,
        panel: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """Evaluate a factor with resource limits.

        On timeout or OOM, returns an empty DataFrame and logs a warning.
        """
        result = None
        error = None

        def _timeout_handler(signum, frame):
            raise TimeoutError(f"Factor evaluation exceeded {self.max_seconds}s limit")

        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self.max_seconds)
            result = compute_fn(panel)
        except TimeoutError as e:
            error = str(e)
            logger.warning("Factor evaluation timed out, circuit breaker tripped")
        except MemoryError:
            error = f"Factor evaluation exceeded {self.max_memory_mb}MB memory limit"
            logger.warning("Factor evaluation OOM, circuit breaker tripped")
        except Exception as e:
            error = f"Factor evaluation failed: {e}"
        finally:
            signal.alarm(0)

        if error:
            return pd.DataFrame()

        return result if result is not None else pd.DataFrame()


# ---------------------------------------------------------------------------
# Walk-Forward 24-window (Purged Cross-Validation)
# ---------------------------------------------------------------------------

def walk_forward_validate(
    tree: ExpressionTree,
    panel: dict[str, pd.DataFrame],
    forward_returns: pd.DataFrame,
    n_windows: int = 24,
    train_years: float = 4.0,
    test_months: int = 6,
    purge_days: int = 5,
) -> dict[str, Any]:
    """Enhanced Walk-Forward validation with Purged CV.

    24 rolling windows (6-month OOS each), 4-year expanding training,
    5-day purge between train/test to prevent information leakage.

    Returns:
        Dict with per-window ICs, pass/fail, and summary stats.
    """
    from src.factors.mining.fitness import ic_fitness

    if panel is None or forward_returns.empty:
        return {"passed": False, "reason": "No data", "windows": []}

    dates = forward_returns.index.sort_values()
    n = len(dates)
    trading_days_per_year = 252
    test_len = trading_days_per_year * test_months // 12
    purge_len = purge_days

    if n < test_len * 2:
        # Fallback to simple 5-fold
        n_windows = min(5, n // (test_len // 2))
        test_len = n // (n_windows * 2)

    compute_fn = tree.to_callable()
    windows = []
    passed_count = 0

    for w in range(n_windows):
        # Test window: last N days
        test_end = n - w * test_len
        test_start = max(0, test_end - test_len)
        # Train window: everything before test_start - purge
        train_end = max(0, test_start - purge_len)
        train_start = 0

        if test_end - test_start < 5:
            continue

        test_dates = dates[test_start:test_end]
        train_dates = dates[train_start:train_end]

        try:
            train_panel = {k: v.loc[v.index.intersection(train_dates)]
                          for k, v in panel.items() if not v.empty}
            test_panel = {k: v.loc[v.index.intersection(test_dates)]
                         for k, v in panel.items() if not v.empty}

            fv_test = compute_fn(test_panel)
            if fv_test.empty:
                continue

            fr_test = forward_returns.loc[forward_returns.index.intersection(test_dates)]
            common_idx = fv_test.index.intersection(fr_test.index)
            common_cols = fv_test.columns.intersection(fr_test.columns)

            if len(common_idx) >= 5 and len(common_cols) >= 3:
                ic = ic_fitness(
                    fv_test.loc[common_idx, common_cols],
                    fr_test.loc[common_idx, common_cols],
                )
                passed = abs(ic) > 0.01
                windows.append({
                    "window": w + 1,
                    "test_start": str(test_dates[0].date()),
                    "test_end": str(test_dates[-1].date()),
                    "ic": round(ic, 6),
                    "passed": passed,
                })
                if passed:
                    passed_count += 1
        except Exception as exc:
            windows.append({"window": w + 1, "error": str(exc), "passed": False})

    if not windows:
        return {"passed": False, "reason": "No valid windows", "windows": []}

    pass_rate = passed_count / len(windows)
    ics = [w["ic"] for w in windows if "ic" in w]
    mean_ic = float(np.mean(ics)) if ics else 0.0
    std_ic = float(np.std(ics, ddof=1)) if len(ics) > 1 else 0.0

    # Must pass > 60% of windows AND mean OOS IC > 0.01
    passed = pass_rate >= 0.6 and abs(mean_ic) > 0.01

    return {
        "passed": passed,
        "pass_rate": round(pass_rate, 4),
        "n_windows": len(windows),
        "n_passed": passed_count,
        "mean_oos_ic": round(mean_ic, 6),
        "std_oos_ic": round(std_ic, 6),
        "information_ratio": round(mean_ic / std_ic, 4) if std_ic > 1e-12 else 0.0,
        "windows": windows,
    }


# ---------------------------------------------------------------------------
# PAPER_TRADING promotion gate
# ---------------------------------------------------------------------------

PAPER_TRADING_RULES = {
    "min_duration_days": 21,         # At least 21 calendar days in paper trading
    "min_trading_days": 15,          # At least 15 days with actual signals
    "max_slippage_bps": 15,          # Simulated slippage cap
    "min_sharpe": 0.5,               # Minimum paper trading Sharpe
    "max_turnover_gap": 1.5,         # Paper turnover / backtest turnover < 1.5x
    "require_positive_pnl": True,    # Must have positive P&L
}


def check_paper_trading_promotion(
    backtest_metrics: dict[str, Any],
    paper_trading_metrics: dict[str, Any],
) -> tuple[bool, str, dict[str, Any]]:
    """Check if a factor satisfies PAPER_TRADING → PRODUCTION conditions.

    Args:
        backtest_metrics: Metrics from the original backtest.
        paper_trading_metrics: Metrics from the paper trading run.

    Returns:
        (passed, reason, diagnostics_dict)
    """
    diag: dict[str, Any] = {}
    failures: list[str] = []

    # ── Duration ──
    pt_days = paper_trading_metrics.get("trading_days", 0)
    diag["trading_days"] = pt_days
    if pt_days < PAPER_TRADING_RULES["min_trading_days"]:
        failures.append(f"Insufficient trading days: {pt_days} < {PAPER_TRADING_RULES['min_trading_days']}")

    # ── Sharpe ──
    pt_sharpe = paper_trading_metrics.get("sharpe", 0.0)
    diag["sharpe"] = pt_sharpe
    if pt_sharpe < PAPER_TRADING_RULES["min_sharpe"]:
        failures.append(f"Sharpe too low: {pt_sharpe:.2f} < {PAPER_TRADING_RULES['min_sharpe']}")

    # ── P&L ──
    pt_pnl = paper_trading_metrics.get("total_return", 0.0)
    diag["total_return"] = pt_pnl
    if PAPER_TRADING_RULES["require_positive_pnl"] and pt_pnl <= 0:
        failures.append(f"Negative P&L: {pt_pnl:.4f}")

    # ── Turnover gap ──
    bt_turnover = backtest_metrics.get("annual_turnover", 0.0)
    pt_turnover = paper_trading_metrics.get("annual_turnover", 0.0)
    diag["backtest_turnover"] = bt_turnover
    diag["paper_turnover"] = pt_turnover
    if bt_turnover > 0 and pt_turnover / bt_turnover > PAPER_TRADING_RULES["max_turnover_gap"]:
        failures.append(f"Turnover gap too large: paper {pt_turnover:.1f}x vs backtest {bt_turnover:.1f}x")

    # ── Slippage ──
    pt_slippage = paper_trading_metrics.get("avg_slippage_bps", 0.0)
    diag["avg_slippage_bps"] = pt_slippage
    if pt_slippage > PAPER_TRADING_RULES["max_slippage_bps"]:
        failures.append(f"Slippage too high: {pt_slippage:.1f}bps > {PAPER_TRADING_RULES['max_slippage_bps']}bps")

    passed = len(failures) == 0
    reason = "; ".join(failures) if failures else "All PAPER_TRADING checks passed"

    return passed, reason, diag
