"""Cross-asset correlation computation — single source of truth.

Used by:
  - GET /correlation API endpoint
  - CorrelationNode (workflow)
  - CrowdingNode (workflow)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """Stateless correlation computation engine.

    All methods are pure functions of their inputs — no internal state,
    no data fetching.  Data loading and normalization are the caller's
    responsibility.
    """

    # ── Panel construction ────────────────────────────────────────────────

    @staticmethod
    def build_panel_from_ohlcv(
        ohlcv_data: dict[str, pd.DataFrame],
        column: str = "close",
    ) -> pd.DataFrame:
        """Extract a single column from OHLCV data and align into a wide panel.

        Args:
            ohlcv_data: {code: DataFrame with OHLCV columns}.
            column: Which price column to extract (default: "close").

        Returns:
            DataFrame with codes as columns, dates as index, forward-filled.
        """
        if isinstance(ohlcv_data, pd.DataFrame):
            ohlcv_data = {"panel": ohlcv_data}

        series_map: dict[str, pd.Series] = {}
        for code, df in ohlcv_data.items():
            if not isinstance(df, pd.DataFrame):
                continue
            if column not in df.columns:
                continue
            series_map[code] = df[column]

        if not series_map:
            return pd.DataFrame()

        panel = pd.DataFrame(series_map).ffill()
        return panel

    # ── Correlation matrix ────────────────────────────────────────────────

    @staticmethod
    def compute_matrix(
        panel: pd.DataFrame,
        method: str = "pearson",
        lookback: int = 0,
        min_overlap_pct: float = 0.5,
    ) -> tuple[pd.DataFrame, dict]:
        """Compute pairwise correlation matrix from a price/factor panel.

        Args:
            panel: Wide DataFrame (dates × codes).
            method: "pearson" or "spearman".
            lookback: Number of most recent rows to use (0 = full history).
            min_overlap_pct: Minimum overlap ratio for a column to be kept.

        Returns:
            (corr_df, summary_dict).  corr_df is a square DataFrame of
            correlation coefficients.
        """
        if panel is None or panel.empty:
            return pd.DataFrame(), {"n_assets": 0, "error": "No data"}

        # Slice lookback
        if lookback > 0 and len(panel) > lookback:
            panel = panel.iloc[-lookback:]

        # Drop columns with too little overlap
        min_obs = max(2, int(len(panel) * min_overlap_pct))
        panel = panel.dropna(axis=1, thresh=min_obs)

        if panel.shape[1] < 2:
            return pd.DataFrame(), {
                "n_assets": panel.shape[1],
                "labels": list(panel.columns),
                "error": "Insufficient data after overlap filter",
            }

        # Compute
        if method == "spearman":
            corr_df = panel.corr(method="spearman")
        else:
            corr_df = panel.corr(method="pearson")

        summary = CorrelationEngine._build_summary(corr_df, method, lookback)
        return corr_df, summary

    @staticmethod
    def _build_summary(
        corr_df: pd.DataFrame,
        method: str,
        lookback: int,
    ) -> dict:
        """Build summary statistics from a correlation matrix."""
        labels = list(corr_df.columns)

        # Upper triangle (excluding diagonal)
        upper_tri = corr_df.where(
            np.triu(np.ones(corr_df.shape, dtype=bool), k=1)
        )
        values = upper_tri.values.flatten()
        values = values[~np.isnan(values)]

        return {
            "n_assets": len(labels),
            "mean_corr": round(float(np.mean(values)), 4) if len(values) > 0 else None,
            "max_corr": round(float(np.max(values)), 4) if len(values) > 0 else None,
            "min_corr": round(float(np.min(values)), 4) if len(values) > 0 else None,
            "method": method,
            "lookback_days": lookback,
        }

    # ── Crowding detection ────────────────────────────────────────────────

    @staticmethod
    def find_crowded_pairs(
        corr_df: pd.DataFrame,
        threshold: float = 0.75,
        top_n: int = 10,
    ) -> dict:
        """Detect highly-correlated factor pairs (crowding risk).

        Args:
            corr_df: Factor correlation matrix.
            threshold: Correlation threshold above which a pair is "crowded".
            top_n: Maximum number of pairs to return.

        Returns:
            {crowded_pairs, overall_score, warning, ...}
        """
        cols = list(corr_df.columns)
        if len(cols) < 2:
            return {
                "crowded_pairs": [],
                "overall_score": 0.0,
                "warning": None,
                "total_pairs": 0,
                "total_factors": len(cols),
            }

        crowded_pairs = []
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                val = float(corr_df.iloc[i, j])
                if abs(val) >= threshold:
                    crowded_pairs.append({
                        "factor_a": cols[i],
                        "factor_b": cols[j],
                        "correlation": round(val, 4),
                    })

        crowded_pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)
        crowded_pairs = crowded_pairs[:top_n]

        n_total_pairs = len(cols) * (len(cols) - 1) // 2
        overall_score = len(crowded_pairs) / max(n_total_pairs, 1)

        warning = None
        if overall_score > 0.30:
            warning = "HIGH: Over 30% of factor pairs are highly correlated — crowded trade risk is elevated"
        elif overall_score > 0.15:
            warning = "MODERATE: 15-30% of pairs correlated — monitor for concentration"
        elif overall_score > 0.05:
            warning = "LOW: Minor crowding detected"

        return {
            "crowded_pairs": crowded_pairs,
            "overall_score": round(overall_score, 4),
            "overall_score_pct": round(overall_score * 100, 1),
            "warning": warning,
            "threshold": threshold,
            "total_pairs": n_total_pairs,
            "total_factors": len(cols),
        }

    # ── Legacy compatibility ──────────────────────────────────────────────

    @staticmethod
    def compute_from_returns(
        returns_df: pd.DataFrame,
        method: str = "pearson",
        window: int = 90,
    ) -> tuple[list[str], list[list[float]]]:
        """Compute correlation from an aligned returns DataFrame.

        Compatible with backtest/correlation.py's _rolling_correlation_matrix.

        Args:
            returns_df: DataFrame of aligned returns (dates × codes).
            method: "pearson" or "spearman".
            window: Trailing rows to include.

        Returns:
            (labels, matrix) tuple for JSON serialization.
        """
        if returns_df.empty:
            return [], []

        if len(returns_df) > window:
            returns_df = returns_df.iloc[-window:]

        if len(returns_df) < 2:
            return list(returns_df.columns), []

        if method == "spearman":
            corr_df = returns_df.corr(method="spearman")
        else:
            corr_df = returns_df.corr(method="pearson")

        # Fill NaN diagonals
        corr_df = corr_df.fillna(0.0)
        arr = corr_df.to_numpy(dtype=float, copy=True)
        np.fill_diagonal(arr, 1.0)
        corr_df = pd.DataFrame(arr, index=corr_df.index, columns=corr_df.columns)

        labels = list(corr_df.columns)
        matrix = corr_df.values.tolist()
        return labels, matrix
