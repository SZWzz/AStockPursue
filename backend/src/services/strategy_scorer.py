"""Multi-factor strategy scoring service.

Input: backtest result dict (BACKTEST_RESULT format)
Output: 0-100 composite score + per-dimension breakdown + grade (A/B/C/D/E)

Weights can be customised or adapt to market regime.
Penalties apply for insufficient sample size (<5 trades: -12, <12: -5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_WEIGHTS = {
    "total_return":     0.22,   # Total return
    "annual_return":    0.12,   # Annualised return
    "sharpe_ratio":     0.18,   # Sharpe ratio
    "profit_factor":    0.14,   # Gross profit / gross loss
    "win_rate":         0.09,   # Win rate
    "max_drawdown":     0.15,   # Maximum drawdown (negative: smaller is better)
    "equity_stability": 0.10,   # Equity curve stability (R² of linear fit)
}


@dataclass
class ScoreResult:
    """Composite score with per-dimension breakdown."""
    overall: float = 0.0        # 0-100
    grade: str = "E"            # A / B / C / D / E
    components: dict[str, float] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)


class StrategyScorer:
    """Compute a composite score from a backtest result."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or dict(DEFAULT_WEIGHTS)

    def score(self, backtest_result: dict) -> ScoreResult:
        """Score a single backtest result.

        Args:
            backtest_result: Dict with at least ``metrics`` and ``summary`` keys.

        Returns:
            ScoreResult with overall 0-100 score, grade, and per-component breakdown.
        """
        metrics = backtest_result.get("metrics", {})
        summary = backtest_result.get("summary", {})

        # Extract raw values
        total_return = float(metrics.get("total_return", 0) or 0)
        annual_return = float(metrics.get("annual_return", 0)
                              or summary.get("annual_return", 0) or 0)
        sharpe = float(metrics.get("sharpe", 0) or 0)
        max_dd = float(metrics.get("max_drawdown", 0) or 0)
        win_rate = float(metrics.get("win_rate", 0) or 0)
        trade_count = int(metrics.get("trade_count", 0) or 0)

        # Profit factor
        profit_factor = float(metrics.get("profit_factor", 0) or 0)
        if profit_factor <= 0 and trade_count > 0:
            gross_profit = float(metrics.get("gross_profit", 0) or 0)
            gross_loss = float(metrics.get("gross_loss", 0) or 0)
            if gross_loss > 0:
                profit_factor = gross_profit / abs(gross_loss)

        # ── Per-dimension scoring (0-100) ──────────────────────────────────

        # Total return: score as percentile-like sigmoid
        cmp_total = _sigmoid_score(total_return, center=0.10, scale=5.0)

        # Annual return
        cmp_annual = _sigmoid_score(annual_return, center=0.08, scale=6.0)

        # Sharpe: 0→30, 1→60, 2→85, 3+→95
        cmp_sharpe = _sigmoid_score(sharpe, center=1.0, scale=1.5)

        # Max drawdown (negative): -5%→90, -10%→75, -20%→50, -30%→25
        cmp_drawdown = _sigmoid_score(-max_dd * 100, center=10.0, scale=8.0)

        # Win rate: 40%→50, 50%→70, 60%→85
        cmp_winrate = _sigmoid_score(win_rate * 100, center=50.0, scale=15.0)

        # Profit factor: 1→50, 1.5→75, 2→90
        cmp_profit = _sigmoid_score(profit_factor, center=1.2, scale=0.6)

        # Equity stability: R² of linear fit to equity curve
        equity_curve = backtest_result.get("equity_curve", [])
        r2 = _equity_r2(equity_curve)
        cmp_stability = _sigmoid_score(r2, center=0.85, scale=0.1)

        components = {
            "total_return":     min(100, max(0, cmp_total)),
            "annual_return":    min(100, max(0, cmp_annual)),
            "sharpe_ratio":     min(100, max(0, cmp_sharpe)),
            "max_drawdown":     min(100, max(0, cmp_drawdown)),
            "win_rate":         min(100, max(0, cmp_winrate)),
            "profit_factor":    min(100, max(0, cmp_profit)),
            "equity_stability": min(100, max(0, cmp_stability)),
        }

        # Weighted composite
        overall = sum(
            components[k] * self.weights.get(k, 0)
            for k in components
        )

        # Sample size penalty
        if trade_count < 5:
            overall -= 12
        elif trade_count < 12:
            overall -= 5

        overall = max(0.0, min(100.0, overall))

        # Grade
        if overall >= 75:
            grade = "A"
        elif overall >= 60:
            grade = "B"
        elif overall >= 45:
            grade = "C"
        elif overall >= 30:
            grade = "D"
        else:
            grade = "E"

        return ScoreResult(
            overall=round(overall, 1),
            grade=grade,
            components={k: round(v, 1) for k, v in components.items()},
            summary={
                "total_return": total_return,
                "annual_return": annual_return,
                "sharpe": sharpe,
                "max_drawdown": max_dd,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "trade_count": trade_count,
                "equity_r2": round(r2, 4),
            },
        )

    def rank(self, scored_candidates: list[dict]) -> list[dict]:
        """Sort candidates by overall score descending, add rank field.

        Each candidate dict should have a ``score`` key with a ScoreResult
        or a dict containing at least ``overall``.
        """
        def _overall(c: dict) -> float:
            s = c.get("score", {})
            if isinstance(s, ScoreResult):
                return s.overall
            if isinstance(s, dict):
                return float(s.get("overall", 0) or 0)
            return 0.0

        ranked = sorted(scored_candidates, key=_overall, reverse=True)
        for i, c in enumerate(ranked):
            c["rank"] = i + 1
        return ranked


# ── Helpers ─────────────────────────────────────────────────────────────────

def _sigmoid_score(x: float, center: float, scale: float) -> float:
    """Map a raw value to 0-100 via a sigmoid centred at *center* with *scale*."""
    import math
    try:
        z = (x - center) / max(scale, 1e-9)
        return 100.0 / (1.0 + math.exp(-z))
    except (OverflowError, ValueError):
        return 100.0 if z > 0 else 0.0


def _equity_r2(equity_curve: list[dict]) -> float:
    """Compute R² of a linear fit to equity curve timesteps."""
    if len(equity_curve) < 5:
        return 0.0
    try:
        import numpy as np  # noqa: F811
        y = np.array([p.get("equity", 0) for p in equity_curve], dtype=float)
        x = np.arange(len(y), dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        if ss_tot < 1e-9:
            return 1.0
        return float(1 - ss_res / ss_tot)
    except Exception:
        return 0.0
