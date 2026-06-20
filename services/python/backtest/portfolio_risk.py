"""Portfolio-level risk metrics — VaR, CVaR, Kelly, concentration.

Usage::

    from backtest.portfolio_risk import (
        historical_var, parametric_var, cvar, kelly_fraction,
        max_drawdown_circuit, sector_concentration,
    )
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ── VaR / CVaR ────────────────────────────────────────────────────────────────

def historical_var(returns: np.ndarray | pd.Series, confidence: float = 0.95) -> float:
    """Value at Risk — historical simulation method.

    Args:
        returns: Array of period returns (fractional).
        confidence: Confidence level (default 0.95).

    Returns:
        VaR as a positive number (e.g. 0.02 = 2% loss at given confidence).
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    returns = np.asarray(returns)
    return float(-np.percentile(returns, (1 - confidence) * 100))


def parametric_var(returns: np.ndarray | pd.Series, confidence: float = 0.95) -> float:
    """Value at Risk — parametric method (assumes normal distribution).

    VaR = -(μ - z_α * σ)
    """
    from scipy.stats import norm
    if isinstance(returns, pd.Series):
        returns = returns.values
    returns = np.asarray(returns)
    mu = float(np.mean(returns))
    sigma = float(np.std(returns, ddof=1))
    z = norm.ppf(1 - confidence)
    return float(-(mu - z * sigma))


def cvar(returns: np.ndarray | pd.Series, confidence: float = 0.95) -> float:
    """Conditional Value at Risk (Expected Shortfall).

    Average loss beyond VaR threshold.
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    returns = np.asarray(returns)
    var_threshold = -historical_var(returns, confidence)
    tail = returns[returns <= -var_threshold]
    if len(tail) == 0:
        return 0.0
    return float(-np.mean(tail))


# ── Kelly Criterion ───────────────────────────────────────────────────────────

def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly fraction for optimal position sizing.

    f* = (p * b - q) / b
    where p = win_rate, q = 1-p, b = avg_win / avg_loss

    Args:
        win_rate: Fraction of winning trades (0-1).
        avg_win: Average winning trade amount (positive).
        avg_loss: Average losing trade amount (positive).

    Returns:
        Optimal fraction of capital to risk per trade.  Commonly used at
        half-Kelly (f* / 2) for safety.
    """
    if avg_loss <= 0 or win_rate <= 0:
        return 0.0
    b = avg_win / avg_loss
    q = 1 - win_rate
    f = (win_rate * b - q) / b
    return max(0.0, min(f, 1.0))


def half_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Half-Kelly — conservative position sizing."""
    return kelly_fraction(win_rate, avg_win, avg_loss) / 2


# ── Drawdown circuit breaker ──────────────────────────────────────────────────

def max_drawdown_circuit(
    current_drawdown: float,
    max_allowed: float = 0.20,
    current_positions: int = 0,
) -> dict[str, Any]:
    """Check if drawdown circuit breaker should trigger.

    Args:
        current_drawdown: Current drawdown as negative fraction (e.g. -0.15).
        max_allowed: Maximum allowed drawdown before stopping (default 20%).
        current_positions: Number of open positions.

    Returns:
        {tripped: bool, action: str, message: str}
    """
    dd_abs = abs(current_drawdown)

    if dd_abs >= max_allowed and current_positions > 0:
        return {
            "tripped": True,
            "action": "close_all",
            "message": f"Drawdown {dd_abs:.1%} exceeded limit {max_allowed:.1%} — closing all positions",
        }
    elif dd_abs >= max_allowed * 0.8:
        return {
            "tripped": True,
            "action": "no_new_entries",
            "message": f"Drawdown {dd_abs:.1%} approaching limit {max_allowed:.1%} — blocking new entries",
        }
    return {"tripped": False, "action": "none", "message": ""}


# ── Sector concentration ──────────────────────────────────────────────────────

def sector_concentration(
    positions: dict[str, float],       # {symbol: market_value}
    sector_map: dict[str, str],         # {symbol: sector_name}
    max_sector_pct: float = 0.30,
) -> dict[str, Any]:
    """Check sector concentration limits.

    Args:
        positions: Current position market values by symbol.
        sector_map: Symbol → sector mapping.
        max_sector_pct: Maximum allowed percentage in one sector (default 30%).

    Returns:
        {violations: [{sector, pct, message}], total_concentration_score}
    """
    if not positions:
        return {"violations": [], "total_concentration_score": 0.0}

    total_value = sum(positions.values())
    if total_value <= 0:
        return {"violations": [], "total_concentration_score": 0.0}

    sector_values: dict[str, float] = {}
    for symbol, value in positions.items():
        sector = sector_map.get(symbol, "Unknown")
        sector_values[sector] = sector_values.get(sector, 0) + value

    violations = []
    for sector, value in sector_values.items():
        pct = value / total_value
        if pct > max_sector_pct:
            violations.append({
                "sector": sector,
                "pct": pct,
                "message": f"Sector {sector} at {pct:.1%} exceeds limit {max_sector_pct:.1%}",
            })

    # Herfindahl-Hirschman Index for concentration
    weights = [v / total_value for v in sector_values.values()]
    hhi = sum(w * w for w in weights)

    return {
        "violations": violations,
        "total_concentration_score": hhi,
        "sector_breakdown": {k: v / total_value for k, v in sector_values.items()},
    }


# ── Portfolio risk report ─────────────────────────────────────────────────────

def portfolio_risk_report(
    returns: np.ndarray,
    trades: list[dict] | None = None,
    current_drawdown: float = 0.0,
    positions: dict[str, float] | None = None,
    sector_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive portfolio risk report.

    Returns:
        Dict with VaR, CVaR, Kelly, drawdown_status, concentration, sharpe, sortino.
    """
    report: dict[str, Any] = {
        "var_95_historical": round(historical_var(returns, 0.95), 4),
        "var_99_historical": round(historical_var(returns, 0.99), 4),
        "cvar_95": round(cvar(returns, 0.95), 4),
    }

    if len(returns) > 2:
        try:
            report["var_95_parametric"] = round(parametric_var(returns, 0.95), 4)
        except Exception:
            pass

    report["volatility_annual"] = round(float(np.std(returns)) * np.sqrt(252), 4)
    report["sharpe_annual"] = round(float(np.mean(returns)) / max(float(np.std(returns)), 1e-10) * np.sqrt(252), 2)
    downside = returns[returns < 0]
    report["sortino_annual"] = round(
        float(np.mean(returns)) / max(float(np.std(downside)), 1e-10) * np.sqrt(252), 2
    ) if len(downside) > 1 else 0

    if trades:
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) <= 0]
        if wins and losses:
            avg_win = float(np.mean([t["pnl"] for t in wins]))
            avg_loss = float(abs(np.mean([t["pnl"] for t in losses])))
            wr = len(wins) / len(trades)
            report["kelly_full"] = round(kelly_fraction(wr, avg_win, avg_loss), 4)
            report["kelly_half"] = round(half_kelly(wr, avg_win, avg_loss), 4)

    report["drawdown_status"] = max_drawdown_circuit(current_drawdown)

    if positions and sector_map:
        report["concentration"] = sector_concentration(positions, sector_map)

    return report
