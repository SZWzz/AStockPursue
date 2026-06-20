"""Stress testing — scenario-based portfolio shock simulation.

Preset scenarios for extreme market events plus custom scenario support.

Usage::

    from backtest.stress_test import run_stress_test, PRESET_SCENARIOS

    results = run_stress_test(daily_returns, scenarios=["2008_gfc", "2015_a_share"])
    for r in results:
        print(f"{r['name']}: max_dd={r['max_drawdown']:.1%}, recovery={r['recovery_days']}d")
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# ── Preset scenarios ─────────────────────────────────────────────────────────

PRESET_SCENARIOS: dict[str, dict[str, float]] = {
    "2008_gfc": {
        "shock": -0.50,         # 50% crash over period
        "vol_mult": 3.0,        # 3x normal volatility
        "correlation": 0.90,    # correlations spike to 0.9
        "shock_days": 60,       # crash unfolds over 60 trading days
        "recovery_mult": 0.5,   # half-strength bounce after crash
        "description": "2008 Global Financial Crisis",
    },
    "2015_a_share": {
        "shock": -0.40,
        "vol_mult": 2.5,
        "correlation": 0.95,
        "shock_days": 30,
        "recovery_mult": 0.3,
        "description": "2015 A-Share Market Crash",
    },
    "2020_covid": {
        "shock": -0.35,
        "vol_mult": 4.0,
        "correlation": 0.80,
        "shock_days": 22,
        "recovery_mult": 0.8,
        "description": "2020 COVID-19 Crash + Rapid Recovery",
    },
    "2024_cny_crash": {
        "shock": -0.15,
        "vol_mult": 2.0,
        "correlation": 0.85,
        "shock_days": 10,
        "recovery_mult": 0.4,
        "description": "2024 Pre-CNY Liquidity Crunch",
    },
    "flash_crash": {
        "shock": -0.20,
        "vol_mult": 6.0,
        "correlation": 0.95,
        "shock_days": 1,
        "recovery_mult": 0.9,
        "description": "Flash Crash (single-day extreme volatility)",
    },
    "stagflation": {
        "shock": -0.25,
        "vol_mult": 1.5,
        "correlation": 0.60,
        "shock_days": 120,
        "recovery_mult": 0.1,
        "description": "Prolonged Stagflation (slow grind down)",
    },
}


# ── Core engine ──────────────────────────────────────────────────────────────

def run_stress_test(
    daily_returns: pd.Series | np.ndarray,
    scenarios: list[str] | None = None,
    custom_scenarios: list[dict[str, Any]] | None = None,
    initial_equity: float = 1.0,
) -> list[dict[str, Any]]:
    """Apply stress scenarios to a daily return series.

    Args:
        daily_returns: Historical daily return series (fractional, e.g. 0.01 = 1%).
        scenarios: List of preset scenario names from ``PRESET_SCENARIOS``.
        custom_scenarios: List of custom scenario dicts with same keys as presets.
        initial_equity: Starting equity (default 1.0 for percentage returns).

    Returns:
        List of dicts with keys:
        {name, description, max_drawdown, total_return, recovery_days,
         final_equity, worst_day, volatility, sharpe_annualized}.
    """
    if scenarios is None:
        scenarios = list(PRESET_SCENARIOS.keys())

    if isinstance(daily_returns, pd.Series):
        rets = daily_returns.values
    else:
        rets = np.asarray(daily_returns)

    base_vol = float(np.std(rets)) if len(rets) > 1 else 0.01
    base_sharpe = float(np.mean(rets) / base_vol * np.sqrt(252)) if base_vol > 0 else 0

    all_scenarios = []
    for name in scenarios:
        cfg = PRESET_SCENARIOS.get(name)
        if cfg:
            all_scenarios.append({"name": name, **cfg})
    for cs in (custom_scenarios or []):
        all_scenarios.append(cs)

    results = []
    for sc in all_scenarios:
        name = sc.get("name", "custom")
        desc = sc.get("description", "")
        shock = float(sc.get("shock", -0.2))
        vol_mult = float(sc.get("vol_mult", 2.0))
        shock_days = int(sc.get("shock_days", 20))
        recovery_mult = float(sc.get("recovery_mult", 0.5))

        # Build stressed return series
        n = len(rets) + shock_days + 30  # add recovery period
        stressed = np.zeros(n)
        rng = np.random.RandomState(42)  # deterministic for reproducibility

        # Pre-shock: copy original returns (or sample from them)
        pre_len = min(len(rets), shock_days)
        stressed[:pre_len] = rets[-pre_len:] if len(rets) >= pre_len else rng.choice(rets, pre_len)

        # Shock period: daily shock distributed over shock_days
        daily_shock = shock / shock_days
        shock_vol = base_vol * vol_mult
        for i in range(shock_days):
            stressed[pre_len + i] = daily_shock + rng.normal(0, shock_vol)

        # Recovery period
        recovery_start = pre_len + shock_days
        recovery_len = n - recovery_start
        for i in range(recovery_len):
            # Partial mean reversion
            recovery_return = abs(shock * recovery_mult) / max(recovery_len, 1)
            stressed[recovery_start + i] = recovery_return + rng.normal(0, base_vol)

        # Calculate equity curve
        equity = np.cumprod(1 + stressed) * initial_equity
        peak = np.maximum.accumulate(equity)
        drawdown = equity / peak - 1

        max_dd = float(np.min(drawdown))
        total_ret = float(equity[-1] / initial_equity - 1)
        final_eq = float(equity[-1])
        worst_day = float(np.min(stressed))

        # Recovery days: days from max_dd until equity returns to previous peak
        dd_end_idx = int(np.argmin(drawdown))
        recovered = False
        recovery_days = -1
        for j in range(dd_end_idx + 1, len(equity)):
            if equity[j] >= peak[dd_end_idx]:
                recovery_days = j - dd_end_idx
                recovered = True
                break
        if not recovered:
            recovery_days = -1  # never recovered

        stressed_vol = float(np.std(stressed))
        stressed_sharpe = float(np.mean(stressed) / stressed_vol * np.sqrt(252)) if stressed_vol > 0 else 0

        results.append({
            "name": name,
            "description": desc,
            "shock": shock,
            "vol_multiplier": vol_mult,
            "max_drawdown": max_dd,
            "total_return": total_ret,
            "final_equity": final_eq,
            "recovery_days": recovery_days,
            "recovered": recovered,
            "worst_day": worst_day,
            "stressed_volatility": stressed_vol,
            "stressed_sharpe": stressed_sharpe,
            "base_volatility": base_vol,
            "base_sharpe": base_sharpe,
        })

    return results


def stress_test_summary(results: list[dict]) -> pd.DataFrame:
    """Convert stress test results to a readable DataFrame."""
    rows = []
    for r in results:
        rows.append({
            "Scenario": r["name"],
            "Description": r["description"],
            "Max DD": f"{r['max_drawdown']:.1%}",
            "Total Return": f"{r['total_return']:.1%}",
            "Recovery": f"{r['recovery_days']}d" if r["recovered"] else "Never",
            "Worst Day": f"{r['worst_day']:.1%}",
            "Stressed Vol": f"{r['stressed_volatility']:.1%}",
            "Stressed Sharpe": f"{r['stressed_sharpe']:.2f}",
        })
    return pd.DataFrame(rows)
