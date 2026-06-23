"""Factor validation: syntax, lookahead, stability, predictiveness checks.

Validates AI-discovered factors before promotion to Alpha Zoo.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from src.factors.mining.expression_tree import ExpressionTree

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Complete validation result for a factor candidate."""

    syntax_valid: bool = True
    lookahead_clean: bool = True
    coverage: float = Field(default=0.0, description="Fraction of non-NaN values")
    nan_ratio: float = Field(default=0.0)
    inf_count: int = Field(default=0)
    ic_stability: list[float] = Field(default_factory=list, description="IC per fold")
    max_correlation_with_zoo: float = Field(default=0.0, description="Max correlation with existing factors")
    correlation_details: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether the factor passes all validation checks."""
        return (
            self.syntax_valid
            and self.lookahead_clean
            and self.coverage > 0.5
            and self.nan_ratio < 0.5
            and self.inf_count == 0
        )


class FactorValidator:
    """Validates factor candidates across multiple dimensions."""

    def __init__(self, panel: dict[str, pd.DataFrame] | None = None) -> None:
        self._panel = panel or {}

    def validate_syntax(self, formula: str) -> bool:
        """Check that the formula string is valid Python/pandas."""
        try:
            # Basic check: try parsing as expression tree
            if not formula or not formula.strip():
                return False
            # Try evaluating in a safe context
            import ast
            ast.parse(formula)
            return True
        except SyntaxError:
            return False

    def validate_tree(self, tree: ExpressionTree) -> bool:
        """Validate an expression tree can be compiled and executed."""
        try:
            fn = tree.to_callable()
            if self._panel:
                result = fn(self._panel)
                return isinstance(result, pd.DataFrame)
            return True
        except Exception as e:
            logger.debug("Tree validation failed: %s", e)
            return False

    def validate_lookahead(self, tree: ExpressionTree) -> bool:
        """Check for lookahead bias in the expression tree.

        Currently checks that the formula doesn't use forward-looking
        operations like negative shift.
        """
        formula = tree.to_formula()
        # Check for pct_change with negative period
        if "pct_change(-" in formula:
            return False
        # Check for shift with negative
        if ".shift(-" in formula:
            return False
        return True

    def validate_stability(
        self,
        factor_values: pd.DataFrame,
    ) -> dict[str, Any]:
        """Check data quality: coverage, NaN ratio, infinities.

        Returns:
            Dict with coverage, nan_ratio, inf_count.
        """
        arr = factor_values.to_numpy(dtype=np.float64, na_value=np.nan)
        total = arr.size
        if total == 0:
            return {"coverage": 0.0, "nan_ratio": 1.0, "inf_count": 0}

        nan_count = int(np.isnan(arr).sum())
        inf_count = int(np.isinf(arr).sum())

        return {
            "coverage": round((total - nan_count) / total, 4),
            "nan_ratio": round(nan_count / total, 4),
            "inf_count": inf_count,
        }

    def validate_predictiveness(
        self,
        factor_values: pd.DataFrame,
        forward_returns: pd.DataFrame,
        n_folds: int = 5,
    ) -> dict[str, Any]:
        """Cross-validated IC stability check.

        Splits the time period into n_folds, computes IC per fold,
        and reports stability metrics.

        Returns:
            Dict with ic_per_fold, ic_mean, ic_std, ic_decay.
        """
        from src.factors.mining.fitness import ic_fitness

        if factor_values.empty or forward_returns.empty:
            return {"ic_per_fold": [], "ic_mean": 0.0, "ic_std": 0.0, "ic_decay": []}

        common_idx = factor_values.index.intersection(forward_returns.index)
        if len(common_idx) < n_folds * 5:
            return {"ic_per_fold": [], "ic_mean": 0.0, "ic_std": 0.0, "ic_decay": []}

        fold_size = len(common_idx) // n_folds
        ics: list[float] = []

        for f in range(n_folds):
            start = f * fold_size
            end = (f + 1) * fold_size if f < n_folds - 1 else len(common_idx)
            fold_idx = common_idx[start:end]

            fv_fold = factor_values.loc[fold_idx]
            fr_fold = forward_returns.loc[fold_idx]
            ic = ic_fitness(fv_fold, fr_fold)
            ics.append(ic)

        return {
            "ic_per_fold": ics,
            "ic_mean": round(float(np.mean(ics)), 4) if ics else 0.0,
            "ic_std": round(float(np.std(ics, ddof=1)), 4) if len(ics) > 1 else 0.0,
            "ic_decay": ics,
        }

    def validate_correlation_with_zoo(
        self,
        factor_values: pd.DataFrame,
        existing_factors: dict[str, pd.DataFrame] | None = None,
        max_to_check: int = 50,
    ) -> dict[str, Any]:
        """Check redundancy: correlation with existing Alpha Zoo factors.

        Returns:
            Dict with max_correlation, details per factor.
        """
        if existing_factors is None:
            # Try loading from factor registry
            try:
                from src.factors.registry import get_default_registry
                registry = get_default_registry()
                alpha_ids = registry.list()[:max_to_check]
                existing_factors = {}
                for aid in alpha_ids[:max_to_check]:
                    try:
                        result = registry.compute(aid, self._panel)
                        existing_factors[aid] = result
                    except Exception as e:
                        logger.warning("Factor validation compute failed: %s", e, exc_info=True)
            except Exception:
                existing_factors = {}

        if not existing_factors:
            return {"max_correlation": 0.0, "details": []}

        # Compute cross-sectional rank then correlate
        fv_ranked = factor_values.rank(axis=1, pct=True, na_option="keep")
        details: list[dict[str, Any]] = []
        max_corr = 0.0

        for aid, ef in existing_factors.items():
            try:
                ef_ranked = ef.rank(axis=1, pct=True, na_option="keep")
                common_idx = fv_ranked.index.intersection(ef_ranked.index)
                common_cols = fv_ranked.columns.intersection(ef_ranked.columns)
                if len(common_idx) < 10 or len(common_cols) < 3:
                    continue

                a = fv_ranked.loc[common_idx, common_cols].to_numpy(dtype=np.float64)
                b = ef_ranked.loc[common_idx, common_cols].to_numpy(dtype=np.float64)
                valid = ~np.isnan(a) & ~np.isnan(b)
                if valid.sum() < 10:
                    continue

                corr = float(np.corrcoef(a[valid].ravel(), b[valid].ravel())[0, 1])
                if not np.isnan(corr):
                    abs_corr = abs(corr)
                    if abs_corr > max_corr:
                        max_corr = abs_corr
                    details.append({"factor_id": aid, "correlation": round(corr, 4)})
            except Exception as e:
                logger.warning("Factor correlation computation failed: %s", e, exc_info=True)

        details.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        return {
            "max_correlation": round(max_corr, 4),
            "details": details[:10],
        }

    def full_validation(
        self,
        tree: ExpressionTree,
        factor_values: pd.DataFrame | None = None,
        forward_returns: pd.DataFrame | None = None,
    ) -> ValidationResult:
        """Run all validation checks and return a complete result."""
        result = ValidationResult()

        # Syntax
        result.syntax_valid = self.validate_tree(tree)
        if not result.syntax_valid:
            result.warnings.append("Expression tree compilation failed")

        # Lookahead
        result.lookahead_clean = self.validate_lookahead(tree)
        if not result.lookahead_clean:
            result.warnings.append("Potential lookahead bias detected (negative shift/pct_change)")

        if factor_values is not None:
            # Stability
            stability = self.validate_stability(factor_values)
            result.coverage = stability["coverage"]
            result.nan_ratio = stability["nan_ratio"]
            result.inf_count = stability["inf_count"]
            if result.coverage < 0.5:
                result.warnings.append(f"Low coverage: {result.coverage:.1%}")
            if result.nan_ratio > 0.5:
                result.warnings.append(f"High NaN ratio: {result.nan_ratio:.1%}")
            if result.inf_count > 0:
                result.warnings.append(f"Found {result.inf_count} infinity values")

            # Predictiveness
            if forward_returns is not None:
                pred = self.validate_predictiveness(factor_values, forward_returns)
                result.ic_stability = pred.get("ic_per_fold", [])

            # Correlation with zoo
            corr = self.validate_correlation_with_zoo(factor_values)
            result.max_correlation_with_zoo = corr["max_correlation"]
            result.correlation_details = corr["details"]
            if result.max_correlation_with_zoo > 0.8:
                result.warnings.append(
                    f"Highly correlated with existing factor: r={result.max_correlation_with_zoo:.3f}"
                )

        return result
