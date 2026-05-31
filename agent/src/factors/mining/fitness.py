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
