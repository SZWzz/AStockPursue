"""Fitness functions for genetic programming factor mining.

Evaluates how predictive a factor is of future returns using:
    - Cross-sectional rank IC (Information Coefficient)
    - Rank IC (Spearman)
    - Long-short quintile portfolio Sharpe ratio
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)


def compute_forward_returns(
    prices: pd.DataFrame,
    period: int = 1,
) -> pd.DataFrame:
    """Compute forward returns from a price DataFrame.

    Args:
        prices: Wide DataFrame (index=dates, columns=codes) of close prices.
        period: Forward horizon in bars.

    Returns:
        Forward returns of same shape, shifted back for alignment.
    """
    fwd = prices.pct_change(period).shift(-period)
    return fwd.replace([np.inf, -np.inf], np.nan)


def ic_fitness(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
) -> float:
    """Cross-sectional Pearson IC (Information Coefficient).

    For each date, compute Pearson correlation between factor values
    and forward returns across all stocks.  Return the mean IC.

    Args:
        factor_values: Wide DataFrame (index=dates, columns=codes).
        forward_returns: Same shape, aligned with factor_values.

    Returns:
        Mean cross-sectional Pearson IC.  Higher is better.
    """
    if factor_values.empty or forward_returns.empty:
        return 0.0

    # Align dates and columns
    common_dates = factor_values.index.intersection(forward_returns.index)
    common_cols = factor_values.columns.intersection(forward_returns.columns)

    if len(common_dates) < 5 or len(common_cols) < 3:
        return 0.0

    fv = factor_values.loc[common_dates, common_cols]
    fr = forward_returns.loc[common_dates, common_cols]

    ics: list[float] = []
    for i in range(len(common_dates)):
        fv_row = fv.iloc[i]
        fr_row = fr.iloc[i]
        valid = fv_row.notna() & fr_row.notna()
        if valid.sum() < 3:
            continue
        try:
            corr, _ = sp_stats.pearsonr(fv_row[valid].to_numpy(dtype=np.float64),
                                         fr_row[valid].to_numpy(dtype=np.float64))
            if not np.isnan(corr):
                ics.append(corr)
        except Exception:
            pass

    return float(np.mean(ics)) if ics else 0.0


def rank_ic_fitness(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
) -> float:
    """Spearman (rank) IC — more robust to outliers than Pearson IC.

    Returns:
        Mean cross-sectional Spearman rank correlation.
    """
    if factor_values.empty or forward_returns.empty:
        return 0.0

    common_dates = factor_values.index.intersection(forward_returns.index)
    common_cols = factor_values.columns.intersection(forward_returns.columns)

    if len(common_dates) < 5 or len(common_cols) < 3:
        return 0.0

    fv = factor_values.loc[common_dates, common_cols]
    fr = forward_returns.loc[common_dates, common_cols]

    rank_ics: list[float] = []
    for i in range(len(common_dates)):
        fv_row = fv.iloc[i]
        fr_row = fr.iloc[i]
        valid = fv_row.notna() & fr_row.notna()
        if valid.sum() < 3:
            continue
        try:
            corr, _ = sp_stats.spearmanr(fv_row[valid].to_numpy(dtype=np.float64),
                                          fr_row[valid].to_numpy(dtype=np.float64))
            if not np.isnan(corr):
                rank_ics.append(corr)
        except Exception:
            pass

    return float(np.mean(rank_ics)) if rank_ics else 0.0


def sharpe_fitness(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_quantiles: int = 5,
) -> float:
    """Long-short quintile portfolio Sharpe ratio.

    Each day, stocks are sorted into n_quantiles by factor value.
    The top quantile is bought, the bottom quantile is sold.
    Returns the annualized Sharpe of the long-short daily return.

    Args:
        factor_values: Wide DataFrame (index=dates, columns=codes).
        forward_returns: Same shape.
        n_quantiles: Number of quantile groups (default 5).

    Returns:
        Annualized Sharpe ratio (assuming 252 trading days).
    """
    if factor_values.empty or forward_returns.empty:
        return 0.0

    common_dates = factor_values.index.intersection(forward_returns.index)
    common_cols = factor_values.columns.intersection(forward_returns.columns)

    if len(common_dates) < 20 or len(common_cols) < n_quantiles:
        return 0.0

    fv = factor_values.loc[common_dates, common_cols]
    fr = forward_returns.loc[common_dates, common_cols]

    daily_ls_returns: list[float] = []

    for i in range(len(common_dates)):
        fv_row = fv.iloc[i]
        fr_row = fr.iloc[i]
        valid = fv_row.notna() & fr_row.notna()
        if valid.sum() < n_quantiles:
            daily_ls_returns.append(0.0)
            continue

        try:
            ranks = fv_row[valid].rank(method="average", na_option="keep")
            top_mask = ranks >= ranks.quantile(1.0 - 1.0 / n_quantiles)
            bottom_mask = ranks <= ranks.quantile(1.0 / n_quantiles)

            top_ret = fr_row[valid][top_mask].mean()
            bottom_ret = fr_row[valid][bottom_mask].mean()

            if pd.notna(top_ret) and pd.notna(bottom_ret):
                daily_ls_returns.append(float(top_ret - bottom_ret))
            else:
                daily_ls_returns.append(0.0)
        except Exception:
            daily_ls_returns.append(0.0)

    arr = np.array(daily_ls_returns, dtype=np.float64)
    mean_ret = float(np.mean(arr))
    std_ret = float(np.std(arr, ddof=1))

    if std_ret <= 1e-12:
        return 0.0

    annual_sharpe = (mean_ret / std_ret) * np.sqrt(252)
    return float(annual_sharpe)


def complexity_penalty(
    n_nodes: int,
    n_samples: int,
    method: Literal["aic", "bic", "none"] = "bic",
) -> float:
    """Compute complexity penalty for a factor expression.

    AIC: penalty = 2 * n_nodes
    BIC: penalty = n_nodes * ln(n_samples)

    The penalty is subtracted from fitness so simpler trees
    are preferred when predictive power is equal.

    Args:
        n_nodes: Number of nodes in the expression tree.
        n_samples: Number of observations (trading days * stocks).
        method: 'aic', 'bic', or 'none'.

    Returns:
        Penalty value (larger = more penalized).
    """
    if method == "none":
        return 0.0
    if method == "aic":
        return 2.0 * n_nodes
    if method == "bic":
        return n_nodes * np.log(max(n_samples, 100))
    return 0.0


def evaluate_fitness(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_nodes: int = 0,
    n_samples: int = 0,
    metric: Literal["ic_mean", "rank_ic", "sharpe"] = "ic_mean",
    penalty: Literal["aic", "bic", "none"] = "bic",
) -> float:
    """Unified fitness evaluation.

    Returns fitness = raw_score - complexity_penalty.
    """
    if metric == "sharpe":
        raw = sharpe_fitness(factor_values, forward_returns)
    elif metric == "rank_ic":
        raw = rank_ic_fitness(factor_values, forward_returns)
    else:
        raw = ic_fitness(factor_values, forward_returns)

    p = complexity_penalty(n_nodes, n_samples, penalty)
    return raw - p


def ic_decay(
    factor_values: pd.DataFrame,
    prices: pd.DataFrame,
    horizons: list[int] | None = None,
) -> dict[str, Any]:
    """Compute IC decay curve — how predictive power falls off with horizon.

    For each horizon h, compute forward h-period returns and evaluate IC.
    The half-life is the horizon at which IC drops below 50% of the 1-period IC.

    Args:
        factor_values: Wide DataFrame (index=dates, columns=codes) of factor values.
        prices: Wide DataFrame of close prices (same shape).
        horizons: List of forward horizons to evaluate. Defaults to [1,3,5,10,20].

    Returns:
        Dict with horizons, ic_per_horizon, half_life, and decay_rate.
    """
    if horizons is None:
        horizons = [1, 3, 5, 10, 20]

    if factor_values.empty or prices.empty:
        return {"horizons": horizons, "ic_per_horizon": [0.0] * len(horizons),
                "half_life": None, "decay_rate": 0.0}

    ics: list[float] = []
    for h in horizons:
        fwd_returns = compute_forward_returns(prices, period=h)
        ic = ic_fitness(factor_values, fwd_returns)
        ics.append(round(float(ic), 6))

    # Estimate half-life: find where IC crosses 50% of max(1-period, 0.01)
    ic_1 = max(abs(ics[0]), 0.001) if ics else 0.001
    half_threshold = ic_1 / 2.0
    half_life = None
    decay_rate = 0.0

    for i, (h, ic) in enumerate(zip(horizons, ics)):
        if abs(ic) < half_threshold:
            if i > 0:
                # Linear interpolation
                prev_h = horizons[i - 1]
                prev_ic = abs(ics[i - 1])
                curr_ic = abs(ic)
                if prev_ic > half_threshold:
                    frac = (prev_ic - half_threshold) / max(prev_ic - curr_ic, 1e-12)
                    half_life = round(prev_h + frac * (h - prev_h), 1)
            else:
                half_life = float(h)
            break

    # Decay rate: average % drop per horizon step
    if len(ics) >= 2:
        drops = []
        for i in range(1, len(ics)):
            prev = max(abs(ics[i - 1]), 1e-6)
            drops.append((prev - abs(ics[i])) / prev)
        decay_rate = round(float(np.mean(drops)) if drops else 0.0, 4)

    # If IC actually increases with horizon, half_life is beyond max horizon
    if half_life is None and ics:
        half_life = float(horizons[-1]) * 1.5  # signal: decay is slow

    return {
        "horizons": horizons,
        "ic_per_horizon": ics,
        "half_life": half_life,
        "decay_rate": decay_rate,
        "interpretation": _decay_interpretation(half_life),
    }


def _decay_interpretation(half_life: float | None) -> str:
    """Human-readable interpretation of IC half-life."""
    if half_life is None:
        return "Unable to determine decay pattern"
    if half_life <= 2:
        return "Very fast decay — likely microstructural noise, suitable for intraday/HFT only"
    if half_life <= 5:
        return "Fast decay — short-term reversal/momentum, rebalance daily"
    if half_life <= 15:
        return "Moderate decay — medium-frequency alpha, rebalance weekly"
    if half_life <= 40:
        return "Slow decay — sustainable alpha, rebalance monthly"
    return "Very slow decay — structural factor, long-term holding suitable"
