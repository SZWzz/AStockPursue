"""Enhanced multiplicative composite fitness for GP factor mining.

Builds on ``fitness.py``, adding A-share-specific penalties, orthogonality
checks, cross-source stability, and FDR multiple testing correction.

**Design principle**: multiplicative composite — a single bad dimension
zeros out the entire fitness.  No amount of IC can compensate for 500x
annual turnover or 100% redundancy with existing factors.

Formula:
    fitness = rank_ic
            × cost_penalty
            × orthogonality_penalty
            × a_share_penalty
            × cross_source_stability
            × complexity_discount
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.factors.mining.expression_tree import ExpressionTree
from src.factors.mining.fitness import (
    compute_forward_returns,
    ic_fitness,
    rank_ic_fitness,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# A-share trading cost constants
# ---------------------------------------------------------------------------

# [P0-04 fix] Commission: 万三 = 3 bps per side (not 0.3 bps).
# Previously 0.3 was 10x too low, making high-turnover strategies appear far
# more profitable than in reality.
# Stamp duty: 5 bps on sell only (千分之一，仅卖出)
# Total round-trip cost per trade in bps
A_SHARE_COMMISSION_BPS = 3.0   # 佣金 万三 = 3 bps
A_SHARE_STAMP_DUTY_BPS = 5.0   # 印花税 千一（仅卖出）
A_SHARE_ROUNDTRIP_COST_BPS = A_SHARE_COMMISSION_BPS * 2 + A_SHARE_STAMP_DUTY_BPS  # = 11 bps

# Annual cost thresholds
MAX_ACCEPTABLE_ANNUAL_COST_BPS = 500  # > 500bps annual cost → penalty → 0


# ---------------------------------------------------------------------------
# Turnover estimation
# ---------------------------------------------------------------------------

def estimate_daily_turnover(factor_values: pd.DataFrame) -> float:
    """Estimate daily turnover from factor value rank changes.

    Turnover = fraction of stocks that change quantile group each day.
    A factor that ranks stocks identically every day has 0 turnover.
    A factor that randomly re-ranks every day approaches 1.0.

    Args:
        factor_values: Wide DataFrame (index=dates, columns=codes).

    Returns:
        Estimated daily turnover rate (0.0 — 1.0).
    """
    if factor_values.empty or factor_values.shape[1] < 2:
        return 0.0

    # Rank stocks cross-sectionally each day
    ranks = factor_values.rank(axis=1, pct=True, na_option="keep")

    # Day-to-day rank change (L1 distance in rank space)
    rank_changes = ranks.diff(periods=1).abs()
    if rank_changes.empty or rank_changes.shape[0] < 2:
        return 0.0

    # Mean absolute rank change across all dates and stocks
    # Multiplied by 0.5 because max L1 distance is 2.0
    mean_change = float(rank_changes.mean(skipna=True).mean(skipna=True) * 0.5)

    return round(min(1.0, max(0.0, mean_change)), 4)


def estimate_annual_turnover(factor_values: pd.DataFrame, trading_days: int = 252) -> float:
    """Annualised turnover estimate from daily rank turnover.

    Annual turnover = daily turnover × trading_days.
    A value of 100 means the portfolio turns over 100× per year
    (roughly rebalanced every 2.5 days).
    """
    daily = estimate_daily_turnover(factor_values)
    return round(daily * trading_days, 2)


# ---------------------------------------------------------------------------
# A-share cost penalty
# ---------------------------------------------------------------------------

def a_share_cost_penalty(
    factor_values: pd.DataFrame,
    max_annual_cost_bps: float = MAX_ACCEPTABLE_ANNUAL_COST_BPS,
) -> float:
    """Multiplicative penalty for trading costs exceeding acceptable levels.

    Returns 1.0 for low-turnover factors, decays to 0.0 for extreme turnover.

    Args:
        factor_values: Wide DataFrame of factor values.
        max_annual_cost_bps: Annual cost (bps) at which penalty → 0.

    Returns:
        Penalty multiplier in [0.0, 1.0].
    """
    annual_turnover = estimate_annual_turnover(factor_values)
    annual_cost_bps = annual_turnover * A_SHARE_ROUNDTRIP_COST_BPS

    if annual_cost_bps <= 0:
        return 1.0

    # Linear decay: 0 cost → 1.0, max_cost → 0.0
    penalty = 1.0 - annual_cost_bps / max_annual_cost_bps
    return round(float(np.clip(penalty, 0.0, 1.0)), 4)


# ---------------------------------------------------------------------------
# Orthogonality penalty (residual IC)
# ---------------------------------------------------------------------------

def orthogonality_penalty(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    core_factors: dict[str, pd.DataFrame] | None = None,
    min_residual_ic: float = 0.01,
) -> tuple[float, float, dict[str, Any]]:
    """Penalise factors that are redundant with existing core factors.

    Regresses the new factor onto the core factors.  The residual
    (unexplained component) is evaluated for independent predictive power.
    A factor fully explained by existing factors gets penalty → 0.

    Args:
        factor_values: Wide DataFrame of the new factor's values.
        forward_returns: Forward returns aligned with factor_values.
        core_factors: Dict of core factor name → Wide DataFrame.
        min_residual_ic: Threshold below which the factor is considered
            fully redundant and gets penalty = 0.

    Returns:
        (penalty, residual_ic, diagnostics_dict)
        penalty in [0.0, 1.0], higher = more independent.
    """
    if core_factors is None or len(core_factors) == 0:
        return 1.0, 0.0, {"n_core_factors": 0, "note": "no core factors to check against"}

    # Align indices and columns
    common_idx = factor_values.index
    common_cols = factor_values.columns

    # Stack → long form for regression
    fv_stacked = factor_values.stack().dropna()
    if len(fv_stacked) < 100:
        return 1.0, 0.0, {"n_samples": len(fv_stacked), "note": "insufficient samples"}

    # Build core factor matrix
    core_data: dict[str, pd.Series] = {}
    for name, cf in core_factors.items():
        cf_aligned = cf.reindex(index=common_idx, columns=common_cols)
        cf_stacked = cf_aligned.stack().dropna()
        common = fv_stacked.index.intersection(cf_stacked.index)
        if len(common) >= 100:
            core_data[name] = cf_stacked.loc[common]

    if len(core_data) < 2:
        return 1.0, 0.0, {"n_core_factors": len(core_data), "note": "too few core factors with overlapping data"}

    # Build regression matrix X from core factors
    X_parts = []
    common_idx_all = fv_stacked.index
    for cf_series in core_data.values():
        common_idx_all = common_idx_all.intersection(cf_series.index)
        X_parts.append(cf_series)

    if len(common_idx_all) < 100:
        return 1.0, 0.0, {"n_samples": len(common_idx_all), "note": "insufficient overlapping samples"}

    X = pd.concat([s.loc[common_idx_all] for s in X_parts], axis=1)
    X.columns = list(core_data.keys())
    y = fv_stacked.loc[common_idx_all]

    # Drop rows with NaN
    valid = X.notna().all(axis=1) & y.notna()
    X_clean = X[valid]
    y_clean = y[valid]

    if len(X_clean) < 100:
        return 1.0, 0.0, {"n_samples": len(X_clean), "note": "insufficient clean samples"}

    # OLS regression: y ~ X
    try:
        from numpy.linalg import lstsq
        coef, residuals, rank, _ = lstsq(X_clean.values, y_clean.values, rcond=None)
    except Exception as exc:
        logger.debug("Orthogonality regression failed: %s", exc)
        return 1.0, 0.0, {"error": str(exc)}

    # Residual IC: predict forward returns with the residual
    y_pred = X_clean.values @ coef
    residual = y_clean.values - y_pred

    # Align residuals with forward returns for IC computation
    residual_series = pd.Series(residual, index=y_clean.index)

    # Compute residual IC
    fr_stacked = forward_returns.stack().dropna()
    common_fr = residual_series.index.intersection(fr_stacked.index)
    if len(common_fr) < 50:
        return 1.0, 0.0, {"n_common_fwd": len(common_fr), "note": "insufficient forward returns overlap"}

    residual_df = residual_series.loc[common_fr].unstack()
    fr_df = fr_stacked.loc[common_fr].unstack()

    residual_ic = ic_fitness(residual_df, fr_df)

    # R² of the regression — compute manually from residuals to handle
    # rank-deficient cases where lstsq returns an empty residuals array.
    ss_total = float(np.sum((y_clean.values - y_clean.values.mean()) ** 2))
    ss_residual = float(np.sum(residual ** 2))
    r_squared = 1.0 - ss_residual / max(ss_total, 1e-12)
    incremental_r2 = max(0.0, 1.0 - r_squared)

    # Penalty: if residual IC is below threshold → fully redundant → 0
    if abs(residual_ic) < min_residual_ic:
        return 0.0, float(residual_ic), {
            "n_core_factors": len(core_data),
            "r_squared": round(r_squared, 4),
            "incremental_r2": round(incremental_r2, 4),
            "residual_ic": round(residual_ic, 6),
            "max_corr_with_core": round(float(np.max(np.abs(coef))), 4),
            "note": "fully redundant — residual IC below threshold",
        }

    # Scale penalty by incremental R²: more independent → higher penalty value
    penalty = min(1.0, incremental_r2 * 3.0)

    return round(penalty, 4), round(float(residual_ic), 6), {
        "n_core_factors": len(core_data),
        "r_squared": round(r_squared, 4),
        "incremental_r2": round(incremental_r2, 4),
        "residual_ic": round(residual_ic, 6),
        "max_corr_with_core": round(float(np.max(np.abs(coef))), 4),
    }


# ---------------------------------------------------------------------------
# A-share specific penalties
# ---------------------------------------------------------------------------

def a_share_specific_penalty(
    factor_values: pd.DataFrame,
    panel: dict[str, pd.DataFrame] | None = None,
    tree: ExpressionTree | None = None,
) -> float:
    """Penalties specific to A-share market microstructure.

    Checks:
    1. Small-cap extreme exposure: > 80% weight in bottom 20% market cap → ×0.7
    2. Intraday signal pattern: if factor flips sign day-to-day → ×0.5 (T+1 risk)
    3. Extreme turnover: > 200x annualised → ×0.3

    Args:
        factor_values: Wide DataFrame of factor values.
        panel: Optional panel dict with 'close' for cap estimation.
        tree: Optional expression tree for formula pattern checks.

    Returns:
        Penalty multiplier in [0.0, 1.0].
    """
    penalty = 1.0

    # ── 1. Small-cap extreme exposure ──
    if panel and "close" in panel:
        if has_small_cap_extreme_exposure(factor_values, panel):
            penalty *= 0.7

    # ── 2. Intraday / high-frequency pattern ──
    if tree and is_intraday_pattern(tree):
        penalty *= 0.5

    # ── 3. Extreme annual turnover ──
    annual_turnover = estimate_annual_turnover(factor_values)
    if annual_turnover > 200:
        penalty *= 0.3

    return round(penalty, 4)


def has_small_cap_extreme_exposure(
    factor_values: pd.DataFrame,
    panel: dict[str, pd.DataFrame],
    bottom_quantile: float = 0.2,
    max_weight_threshold: float = 0.8,
) -> bool:
    """Check if factor is excessively exposed to the smallest-cap stocks.

    Uses close × volume as a rough market cap proxy.
    """
    if "close" not in panel or "volume" not in panel:
        return False

    close = panel["close"]
    volume = panel["volume"]

    try:
        # Rough cap proxy: close × volume
        cap_proxy = (close * volume).reindex_like(factor_values)

        # For each date, rank stocks by cap proxy
        cap_ranks = cap_proxy.rank(axis=1, pct=True, na_option="keep")

        # Bottom quantile by cap
        bottom_mask = cap_ranks <= bottom_quantile

        # Factor ranks
        fv_ranks = factor_values.rank(axis=1, pct=True, na_option="keep")

        # Top quantile of factor (what the strategy would buy)
        top_factor_mask = fv_ranks >= 0.8

        # Overlap: fraction of top-factor stocks that are bottom-cap
        overlap = (bottom_mask & top_factor_mask).sum(axis=1) / top_factor_mask.sum(axis=1).clip(lower=1)
        mean_overlap = float(overlap.mean(skipna=True))

        return mean_overlap > max_weight_threshold
    except Exception:
        return False


def is_intraday_pattern(tree: ExpressionTree) -> bool:
    """Heuristic: detect if the factor likely captures intraday patterns.

    Checks for very short rolling windows (≤3) combined with daily
    frequency features — suggests the factor relies on patterns that
    can't be traded under T+1 settlement.
    """
    def _check_node(node) -> bool:
        if hasattr(node, "window") and node.window and node.window <= 3:
            # Short window + fast features
            if node.feature_id in ("returns_1d", "high_low_ratio"):
                return True
        for child in getattr(node, "children", []):
            if _check_node(child):
                return True
        return False

    try:
        return _check_node(tree.root)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Cross-source stability
# ---------------------------------------------------------------------------

def cross_source_stability(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_folds: int = 5,
) -> float:
    """Estimate stability by computing IC across time folds.

    A factor with stable IC across folds gets a higher multiplier.
    High variance in IC suggests overfitting to specific market regimes.

    Returns:
        Stability multiplier in [0.3, 1.0].
    """
    if factor_values.empty or forward_returns.empty:
        return 0.5

    common_idx = factor_values.index.intersection(forward_returns.index)
    if len(common_idx) < n_folds * 5:
        return 0.5

    fold_size = len(common_idx) // n_folds
    ics: list[float] = []

    for f in range(n_folds):
        start = f * fold_size
        end = (f + 1) * fold_size if f < n_folds - 1 else len(common_idx)
        fold_idx = common_idx[start:end]
        ic = ic_fitness(
            factor_values.loc[fold_idx],
            forward_returns.loc[fold_idx],
        )
        if not np.isnan(ic):
            ics.append(ic)

    if len(ics) < 2:
        return 0.5

    mean_ic = np.mean(ics)
    std_ic = np.std(ics, ddof=1)

    if abs(mean_ic) < 1e-6:
        return 0.3

    cv = std_ic / max(abs(mean_ic), 1e-6)  # coefficient of variation
    stability = max(0.3, 1.0 - cv)

    return round(float(stability), 4)


# ---------------------------------------------------------------------------
# Complexity discount (BIC-style, multiplicative)
# ---------------------------------------------------------------------------

def complexity_discount(
    n_nodes: int,
    n_samples: int = 0,
) -> float:
    """Multiplicative complexity discount.

    Uses BIC-style penalty: discount = exp(-k × ln(n) / n × scaling).
    Simpler trees are preferred when predictive power is equal.

    Args:
        n_nodes: Number of nodes in the expression tree.
        n_samples: Number of observations (trading days × stocks).

    Returns:
        Discount multiplier in (0.0, 1.0].
    """
    n = max(n_samples, 100)
    # BIC-style: penalty proportional to k × ln(n) / n
    # Scaling factor 5 makes the discount meaningful for typical sample sizes
    discount = np.exp(-n_nodes * np.log(n) / n * 5)
    return round(float(np.clip(discount, 0.1, 1.0)), 4)


# ---------------------------------------------------------------------------
# Composite fitness (the main entry point)
# ---------------------------------------------------------------------------

def composite_fitness(
    tree: ExpressionTree,
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    *,
    panel: dict[str, pd.DataFrame] | None = None,
    core_factors: dict[str, pd.DataFrame] | None = None,
    ic_threshold: float = 0.001,
) -> dict[str, Any]:
    """Enhanced multiplicative composite fitness for GP factor evaluation.

    Fitness = rank_ic
            × cost_penalty
            × orthogonality_penalty
            × a_share_penalty
            × stability
            × complexity_discount

    **Multiplicative design**: a single bad dimension → fitness ≈ 0.
    No amount of IC can compensate for extreme turnover or full redundancy.

    Args:
        tree: The factor's expression tree.
        factor_values: Evaluated factor values (wide DataFrame).
        forward_returns: Forward returns aligned with factor_values.
        panel: Optional OHLCV panel for cap/turnover estimation.
        core_factors: Optional dict of core factor values for orthogonality check.
        ic_threshold: Minimum Rank IC to avoid returning 0.0.

    Returns:
        Dict with fitness and all sub-component scores for debugging.
    """
    n_samples = (len(factor_values) * len(factor_values.columns)
                 if not factor_values.empty else 100)

    # ── 1. Base signal: Rank IC (robust to outliers) ──
    rank_ic = rank_ic_fitness(factor_values, forward_returns)

    # Soft threshold: when IC is near zero, still return a tiny proportional
    # fitness so tournament selection has a gradient.  Without this, every
    # individual below 0.001 gets fitness=0.0, selection becomes random,
    # and the population collapses to a single degenerate formula.
    if abs(rank_ic) <= ic_threshold:
        tiny_fitness = abs(rank_ic) * 0.1  # e.g. IC=0.0009 → fitness=0.00009
        return {
            "fitness": max(tiny_fitness, 1e-8),
            "rank_ic": round(rank_ic, 6),
            "reason": "IC below threshold (soft fallback)",
            "components": {},
        }

    # ── 2. Trading cost penalty ──
    cost_pen = a_share_cost_penalty(factor_values)
    # Clamp cost penalty to a tiny minimum instead of returning 0.0
    if cost_pen <= 0.0:
        cost_pen = 1e-8

    # ── 3. Orthogonality penalty ──
    ortho_pen, residual_ic, ortho_diag = orthogonality_penalty(
        factor_values, forward_returns, core_factors,
    )
    # Clamp to tiny minimum instead of hard-zero cutoff
    if ortho_pen <= 0.0:
        ortho_pen = 1e-8

    # ── 4. A-share specific penalties ──
    ashare_pen = a_share_specific_penalty(factor_values, panel, tree)

    # ── 5. Cross-time stability ──
    stability = cross_source_stability(factor_values, forward_returns)

    # ── 6. Complexity discount ──
    complexity = tree.complexity()
    cmp_discount = complexity_discount(complexity, n_samples)

    # ── Multiplicative composite ──
    fitness = (
        abs(rank_ic)
        * cost_pen
        * ortho_pen
        * ashare_pen
        * stability
        * cmp_discount
    )

    annual_turnover = estimate_annual_turnover(factor_values)

    return {
        "fitness": round(float(fitness), 6),
        "rank_ic": round(rank_ic, 6),
        "annual_turnover": annual_turnover,
        "annual_cost_bps": round(annual_turnover * A_SHARE_ROUNDTRIP_COST_BPS, 2),
        "complexity": complexity,
        "components": {
            "cost_penalty": cost_pen,
            "orthogonality_penalty": ortho_pen,
            "a_share_penalty": ashare_pen,
            "stability": stability,
            "complexity_discount": cmp_discount,
        },
        "orthogonality": ortho_diag,
    }


# ---------------------------------------------------------------------------
# FDR multiple testing correction (Benjamini-Hochberg)
# ---------------------------------------------------------------------------

def apply_fdr_correction(
    candidates: list[dict[str, Any]],
    ic_key: str = "rank_ic",
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    """Apply Benjamini-Hochberg FDR correction to a list of factor candidates.

    In GP evolution, thousands of hypotheses are tested (one per individual
    per generation).  Without FDR correction, ~5% of completely random
    factors will appear significant by chance.

    Each candidate dict must have the ic_key field.  The function adds
    ``fdr_adjusted_p_value`` and ``fdr_significant`` fields.

    Args:
        candidates: List of candidate dicts with ``ic_key`` and ``oos_ic_std`` or
            ``oos_ic_per_window`` fields for p-value estimation.
        ic_key: Key for the IC value in each candidate dict.
        alpha: FDR threshold (default 0.05).

    Returns:
        The same list with FDR fields added (mutated in-place + returned).
    """
    n = len(candidates)
    if n == 0:
        return candidates

    from scipy import stats as sp_stats

    # Compute raw p-values from IC t-statistics
    p_values: list[float] = []
    for c in candidates:
        ic = c.get(ic_key, 0.0)
        # Use OOS IC per window if available for t-test
        oos_ics = c.get("oos_ic_per_window", [])
        if oos_ics and len(oos_ics) >= 2:
            mean_ic = np.mean(oos_ics)
            std_ic = np.std(oos_ics, ddof=1)
            if std_ic > 1e-12 and len(oos_ics) > 1:
                t_stat = mean_ic / (std_ic / np.sqrt(len(oos_ics)))
                p_val = float(sp_stats.t.sf(abs(t_stat), df=len(oos_ics) - 1))
            else:
                p_val = 1.0
        else:
            # Fallback: use IC directly with a rough estimate
            ic_std = c.get("oos_ic_std", 0.01)
            if ic_std > 1e-12:
                t_stat = abs(ic) / ic_std
                p_val = float(sp_stats.t.sf(t_stat, df=20))
            else:
                p_val = 1.0 if abs(ic) < 0.01 else 0.01
        p_values.append(max(p_val, 1e-15))

    # Benjamini-Hochberg procedure
    sorted_idx = np.argsort(p_values)
    adjusted = np.ones(n)

    for rank, idx in enumerate(sorted_idx):
        adjusted[idx] = min(1.0, p_values[idx] * n / (rank + 1.0))

    # Enforce monotonicity
    for i in range(n - 1, 0, -1):
        adjusted[sorted_idx[i - 1]] = min(
            adjusted[sorted_idx[i - 1]], adjusted[sorted_idx[i]]
        )

    for i, c in enumerate(candidates):
        c["fdr_raw_p_value"] = round(p_values[i], 6)
        c["fdr_adjusted_p_value"] = round(float(adjusted[i]), 6)
        c["fdr_significant"] = bool(float(adjusted[i]) < alpha)
        c["fdr_method"] = "BH"

    return candidates


# ---------------------------------------------------------------------------
# FDR Benjamini-Yekutieli correction (controls FDR under arbitrary dependence)
# ---------------------------------------------------------------------------

def apply_by_correction(
    candidates: list[dict[str, Any]],
    ic_key: str = "rank_ic",
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    """[P0-05 fix] Apply Benjamini-Yekutieli FDR correction.

    Unlike Benjamini-Hochberg (which assumes independence or PRDS), the BY
    procedure controls the FDR under *arbitrary* dependence structures.  This
    is the correct choice when all candidates in a GP generation are tested
    on the same dataset — their IC values (and derived p-values) are
    correlated by construction, which makes BH too liberal.

    The BY threshold replaces the BH rank-divisor ``k`` with ``k * H_m``
    where ``H_m = sum(1/i for i in 1..m)`` ≈ ``ln(m) + 0.577`` (harmonic
    number).  This makes BY uniformly more conservative than BH.

    Args:
        candidates: List of candidate dicts with ``ic_key`` and
            ``oos_ic_per_window`` fields.
        ic_key: Key for the IC value in each candidate dict.
        alpha: FDR threshold (default 0.05).

    Returns:
        The same list with FDR fields added (mutated in-place + returned).
    """
    n = len(candidates)
    if n == 0:
        return candidates

    from scipy import stats as sp_stats

    # Harmonic number H_n = 1 + 1/2 + ... + 1/n
    harmonic = sum(1.0 / i for i in range(1, n + 1))

    # Compute raw p-values (same logic as BH)
    p_values: list[float] = []
    for c in candidates:
        ic = c.get(ic_key, 0.0)
        oos_ics = c.get("oos_ic_per_window", [])
        if oos_ics and len(oos_ics) >= 2:
            mean_ic = float(np.mean(oos_ics))
            std_ic = float(np.std(oos_ics, ddof=1))
            if std_ic > 1e-12 and len(oos_ics) > 1:
                t_stat = mean_ic / (std_ic / np.sqrt(len(oos_ics)))
                p_val = float(sp_stats.t.sf(abs(t_stat), df=len(oos_ics) - 1))
            else:
                p_val = 1.0
        else:
            # [P0-05 fix] Improved fallback: use a more conservative prior
            # when no OOS windows are available.  Default to p=1.0 (no
            # significance) rather than the arbitrary heuristic.
            ic_std = c.get("oos_ic_std", 0.01)
            if ic_std > 1e-12:
                t_stat = abs(ic) / ic_std
                p_val = float(sp_stats.t.sf(t_stat, df=5))
            else:
                p_val = 1.0
        p_values.append(max(p_val, 1e-15))

    # Benjamini-Yekutieli procedure
    sorted_idx = np.argsort(p_values)
    adjusted = np.ones(n)

    for rank, idx in enumerate(sorted_idx):
        adjusted[idx] = min(1.0, p_values[idx] * n * harmonic / (rank + 1.0))

    # Enforce monotonicity
    for i in range(n - 1, 0, -1):
        adjusted[sorted_idx[i - 1]] = min(
            adjusted[sorted_idx[i - 1]], adjusted[sorted_idx[i]]
        )

    for i, c in enumerate(candidates):
        c["fdr_raw_p_value"] = round(p_values[i], 6)
        c["fdr_adjusted_p_value"] = round(float(adjusted[i]), 6)
        c["fdr_significant"] = bool(float(adjusted[i]) < alpha)
        c["fdr_method"] = "BY"

    return candidates
