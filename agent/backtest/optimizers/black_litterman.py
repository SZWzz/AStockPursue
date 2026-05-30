"""Black-Litterman model — Bayesian blending of equilibrium returns with investor views.

Fuses prior (market-cap equilibrium returns via reverse optimization) with
subjective views (e.g. "600519 will outperform by 5%") to produce posterior
expected returns, then feeds into Mean-Variance optimization.

Reference: Black & Litterman (1992), He & Litterman (1999).

Usage::

    from backtest.optimizers.black_litterman import BlackLittermanOptimizer

    bl = BlackLittermanOptimizer()
    weights = bl.optimize(
        cov_matrix,          # N×N covariance matrix (annualized)
        market_caps,         # Market capitalizations (or equal weights)
        risk_aversion=3.0,   # Market risk aversion (2.5–4.0 typical)
        views={              # Investor views (optional)
            "600519": {"return": 0.20, "confidence": 0.6},   # 20% return, 60% confident
            "000858": {"return": 0.10, "confidence": 0.4},
        },
    )
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class BlackLittermanOptimizer:
    """Black-Litterman portfolio optimizer.

    Steps:
      1. Reverse optimization: equilibrium returns = risk_aversion * Σ * w_mkt
      2. View blending: posterior = [(τΣ)^-1 + P^T Ω^-1 P]^-1 * [(τΣ)^-1 Π + P^T Ω^-1 Q]
      3. Mean-Variance optimization on posterior returns
    """

    def __init__(self, tau: float = 0.025):
        """Args:
            tau: Uncertainty scalar for the prior covariance (default 0.025, He & Litterman 1999).
        """
        self.tau = tau

    def equilibrium_returns(
        self,
        cov_matrix: np.ndarray,
        market_weights: np.ndarray,
        risk_aversion: float = 3.0,
    ) -> np.ndarray:
        """Compute equilibrium (implied) excess returns via reverse optimization.

        Π = λ * Σ * w_mkt

        Args:
            cov_matrix: N×N covariance matrix.
            market_weights: Market-cap (or benchmark) weights, length N.
            risk_aversion: Risk aversion coefficient λ (market price of risk).

        Returns:
            Implied equilibrium excess returns, length N.
        """
        return risk_aversion * cov_matrix @ market_weights

    def posterior_returns(
        self,
        cov_matrix: np.ndarray,
        market_weights: np.ndarray,
        views: dict[str, dict],
        symbols: list[str],
        risk_aversion: float = 3.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute posterior (blended) expected returns.

        Args:
            cov_matrix: N×N covariance matrix.
            market_weights: N-vector of market benchmark weights.
            views: {symbol: {return, confidence}} dict. Return is annual excess return.
            symbols: List of symbol names corresponding to cov_matrix indices.
            risk_aversion: Risk aversion coefficient.

        Returns:
            (posterior_returns, posterior_covariance) — N-vectors.
        """
        n = len(symbols)
        pi = self.equilibrium_returns(cov_matrix, market_weights, risk_aversion)

        if not views:
            # No views → posterior = prior
            posterior_cov = cov_matrix + self.tau * cov_matrix
            return pi, posterior_cov

        # Build pick matrix P (K×N) and view vectors Q, Ω
        view_symbols = []
        view_returns = []
        view_confidences = []

        for sym, v in views.items():
            if sym in symbols:
                view_symbols.append(sym)
                view_returns.append(v.get("return", 0.0))
                view_confidences.append(v.get("confidence", 0.5))

        k = len(view_symbols)
        if k == 0:
            posterior_cov = cov_matrix + self.tau * cov_matrix
            return pi, posterior_cov

        P = np.zeros((k, n))
        Q = np.zeros(k)
        omega_diag = np.zeros(k)

        for i, sym in enumerate(view_symbols):
            j = symbols.index(sym)
            P[i, j] = 1.0
            Q[i] = view_returns[i]
            # Ω = P(τΣ)P^T / confidence — scale uncertainty by (1-confidence)
            raw_var = P[i, :] @ (self.tau * cov_matrix) @ P[i, :].T
            # Lower confidence → higher uncertainty (wider diagonal)
            omega_diag[i] = raw_var / max(view_confidences[i], 0.01)

        Omega = np.diag(omega_diag)

        # Black-Litterman formula
        tau_sigma = self.tau * cov_matrix
        tau_sigma_inv = np.linalg.inv(tau_sigma)
        omega_inv = np.linalg.inv(Omega)

        # Posterior covariance
        M = np.linalg.inv(tau_sigma_inv + P.T @ omega_inv @ P)

        # Posterior mean
        posterior_mean = M @ (tau_sigma_inv @ pi + P.T @ omega_inv @ Q)
        posterior_cov = cov_matrix + M  # uncertainty = prior + estimation error

        return posterior_mean, posterior_cov

    def optimize(
        self,
        cov_matrix: np.ndarray,
        market_weights: np.ndarray,
        symbols: list[str],
        views: dict[str, dict] | None = None,
        risk_aversion: float = 3.0,
        max_weight: float = 0.30,
    ) -> dict[str, Any]:
        """Run full Black-Litterman → Mean-Variance pipeline.

        Args:
            cov_matrix: N×N covariance matrix (annualized).
            market_weights: Benchmark weights (N-vector).
            symbols: Asset symbols.
            views: Optional investor views.
            risk_aversion: Risk aversion λ.
            max_weight: Maximum single-asset weight constraint.

        Returns:
            {weights: {symbol: weight}, expected_return, expected_vol, sharpe,
             equilibrium_returns, posterior_returns}
        """
        views = views or {}
        posterior_ret, posterior_cov = self.posterior_returns(
            cov_matrix, market_weights, views, symbols, risk_aversion,
        )
        pi = self.equilibrium_returns(cov_matrix, market_weights, risk_aversion)

        # Mean-Variance: max Sharpe with weight constraints
        n = len(symbols)
        try:
            from scipy.optimize import minimize

            def neg_sharpe(w):
                port_ret = w @ posterior_ret
                port_vol = np.sqrt(w @ posterior_cov @ w)
                return -port_ret / (port_vol + 1e-10)

            constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
            bounds = [(0.0, max_weight) for _ in range(n)]
            x0 = np.ones(n) / n

            result = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
            weights = result.x if result.success else x0
        except Exception:
            # Fallback: equal weight
            weights = np.ones(n) / n

        port_ret = weights @ posterior_ret
        port_vol = np.sqrt(weights @ posterior_cov @ weights)

        return {
            "weights": {s: round(float(w), 4) for s, w in zip(symbols, weights)},
            "expected_return": round(float(port_ret), 4),
            "expected_volatility": round(float(port_vol), 4),
            "expected_sharpe": round(float(port_ret / (port_vol + 1e-10)), 4),
            "equilibrium_returns": {s: round(float(r), 4) for s, r in zip(symbols, pi)},
            "posterior_returns": {s: round(float(r), 4) for s, r in zip(symbols, posterior_ret)},
            "risk_aversion": risk_aversion,
            "tau": self.tau,
        }

    def from_dataframe(
        self,
        returns_df: pd.DataFrame,
        market_caps: dict[str, float] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Convenience: build from a DataFrame of asset returns.

        Args:
            returns_df: T×N DataFrame of daily returns.
            market_caps: {symbol: market_cap} for benchmark weights.
                If None, uses equal weight.
            **kwargs: Passed to ``optimize()``.
        """
        cov = returns_df.cov().values * 252  # annualized
        symbols = list(returns_df.columns)
        n = len(symbols)

        if market_caps:
            caps = np.array([market_caps.get(s, 0) for s in symbols])
            total = caps.sum()
            market_weights = caps / total if total > 0 else np.ones(n) / n
        else:
            market_weights = np.ones(n) / n

        return self.optimize(cov, market_weights, symbols, **kwargs)
