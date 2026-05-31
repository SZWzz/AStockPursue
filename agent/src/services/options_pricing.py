"""Options Pricing Engine.

Black-Scholes analytical model + Binomial Tree + Greeks.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)

OptionType = Literal["call", "put"]


class OptionPriceResult(BaseModel):
    price: float
    delta: float
    gamma: float
    theta: float  # per day
    vega: float   # per 1% vol change
    rho: float    # per 1% rate change
    implied_vol: float | None = None


class VolSurfacePoint(BaseModel):
    strike: float
    expiry_days: int
    implied_vol: float


class OptionsPricingEngine:
    """Black-Scholes + Binomial Tree option pricing with Greeks."""

    @staticmethod
    def black_scholes(
        S: float,       # spot price
        K: float,       # strike price
        T: float,       # time to expiry (years)
        r: float,       # risk-free rate
        sigma: float,   # volatility
        option_type: OptionType = "call",
    ) -> OptionPriceResult:
        """Black-Scholes-Merton analytical pricing."""
        if T <= 0 or sigma <= 0:
            return OptionPriceResult(price=0, delta=0, gamma=0, theta=0, vega=0, rho=0)

        d1 = (np.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type == "call":
            price = S * sp_stats.norm.cdf(d1) - K * np.exp(-r * T) * sp_stats.norm.cdf(d2)
            delta = sp_stats.norm.cdf(d1)
            theta = (-S * sigma * sp_stats.norm.pdf(d1) / (2 * np.sqrt(T))
                     - r * K * np.exp(-r * T) * sp_stats.norm.cdf(d2)) / 365
        else:
            price = K * np.exp(-r * T) * sp_stats.norm.cdf(-d2) - S * sp_stats.norm.cdf(-d1)
            delta = sp_stats.norm.cdf(d1) - 1
            theta = (-S * sigma * sp_stats.norm.pdf(d1) / (2 * np.sqrt(T))
                     + r * K * np.exp(-r * T) * sp_stats.norm.cdf(-d2)) / 365

        pdf_d1 = sp_stats.norm.pdf(d1)
        gamma = pdf_d1 / (S * sigma * np.sqrt(T) + 1e-12)
        vega = S * np.sqrt(T) * pdf_d1 / 100  # per 1% vol change
        rho = (K * T * np.exp(-r * T) * sp_stats.norm.cdf(d2 if option_type == "call" else -d2)) / 100

        return OptionPriceResult(
            price=round(price, 4),
            delta=round(delta, 4),
            gamma=round(gamma, 6),
            theta=round(theta, 6),
            vega=round(vega, 4),
            rho=round(rho, 4),
        )

    @staticmethod
    def binomial_tree(
        S: float, K: float, T: float, r: float, sigma: float,
        n_steps: int = 100,
        option_type: OptionType = "call",
    ) -> float:
        """Cox-Ross-Rubinstein binomial tree pricing."""
        dt = T / n_steps
        u = np.exp(sigma * np.sqrt(dt))
        d = 1 / u
        p = (np.exp(r * dt) - d) / (u - d)

        # Terminal payoffs
        prices = np.zeros(n_steps + 1)
        for i in range(n_steps + 1):
            ST = S * (u ** (n_steps - i)) * (d ** i)
            prices[i] = max(ST - K, 0) if option_type == "call" else max(K - ST, 0)

        # Backward induction
        for j in range(n_steps - 1, -1, -1):
            prices = np.exp(-r * dt) * (p * prices[:j + 1] + (1 - p) * prices[1:j + 2])

        return round(float(prices[0]), 4)

    @staticmethod
    def implied_volatility(
        S: float, K: float, T: float, r: float,
        market_price: float,
        option_type: OptionType = "call",
        max_iter: int = 100,
        tol: float = 1e-6,
    ) -> float | None:
        """Newton-Raphson implied volatility solver."""
        sigma = 0.3  # initial guess
        for _ in range(max_iter):
            result = OptionsPricingEngine.black_scholes(S, K, T, r, sigma, option_type)
            price_diff = result.price - market_price
            if abs(price_diff) < tol:
                return round(sigma, 6)
            vega = result.vega * 100  # convert back from per-1%
            if abs(vega) < 1e-12:
                return None
            sigma = sigma - price_diff / vega
            if sigma <= 0.001:
                sigma = 0.001
        return round(sigma, 6) if 0.001 < sigma < 5.0 else None

    @staticmethod
    def generate_vol_surface(
        S: float, r: float,
        strikes: list[float] | None = None,
        expiries_days: list[int] | None = None,
    ) -> list[VolSurfacePoint]:
        """Generate a sample volatility surface (smile/skew pattern)."""
        strikes = strikes or [round(S * x, 0) for x in [0.7, 0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2, 1.3]]
        expiries_days = expiries_days or [7, 14, 30, 60, 90, 180, 365]

        base_vol = 0.25
        surface: list[VolSurfacePoint] = []

        for expiry in expiries_days:
            T = expiry / 365
            for strike in strikes:
                moneyness = strike / S
                # Simple smile: higher vol for OTM and ITM
                smile = base_vol + 0.05 * (moneyness - 1.0)**2
                # Term structure: near-term higher vol
                term_adj = 0.02 * np.exp(-T * 2)
                iv = smile + term_adj
                surface.append(VolSurfacePoint(
                    strike=strike,
                    expiry_days=expiry,
                    implied_vol=round(iv, 4),
                ))

        return surface
