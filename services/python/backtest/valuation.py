"""Valuation formulas for A-share growth stocks.

Reference: 01.md Layer "估值计算公式"

Usage:
    from backtest.valuation import forward_pe, pe_digestion, peg, ValuationResult
    v = ValuationResult.from_data(price=50.0, eps_current=2.0, eps_forecast=2.8)
    print(v)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class ValuationResult:
    """Structured valuation output for a single stock."""

    symbol: str = ""
    price: float = 0.0
    eps_current: float = 0.0       # 当期 EPS（TTM 或最近年报）
    eps_forecast: float = 0.0       # 下一年度一致预期 EPS

    # Computed
    pe_current: float = 0.0         # 当前 PE = price / eps_current
    forward_pe: float = 0.0         # 前向 PE = price / eps_forecast
    cagr: float = 0.0               # EPS 增速 = eps_forecast / eps_current - 1
    peg: float = 0.0                # PEG = forward_pe / (cagr * 100)
    pe_digestion_years: float = 0.0  # PE 消化到 30x 需要的年数

    # Signals
    peg_signal: str = ""            # cheap / fair / expensive
    digestion_signal: str = ""      # fast / normal / slow

    @classmethod
    def from_data(
        cls,
        price: float,
        eps_current: float,
        eps_forecast: float,
        symbol: str = "",
        target_pe: float = 30.0,
    ) -> ValuationResult:
        """Compute all valuation metrics from raw inputs.

        Args:
            price: Current stock price.
            eps_current: Current EPS (TTM or latest annual).
            eps_forecast: Forward EPS estimate (next fiscal year).
            symbol: Optional stock code for display.
            target_pe: Target PE for digestion calculation (default 30x).
        """
        pe_current = price / eps_current if eps_current > 0 else float("inf")
        fwd_pe = forward_pe(price, eps_forecast)
        cagr = _calc_cagr(eps_current, eps_forecast)
        peg_val = calc_peg(fwd_pe, cagr)
        digestion = pe_digestion(fwd_pe, cagr, target_pe)

        return cls(
            symbol=symbol,
            price=price,
            eps_current=eps_current,
            eps_forecast=eps_forecast,
            pe_current=round(pe_current, 2),
            forward_pe=round(fwd_pe, 2),
            cagr=round(cagr, 4),
            peg=round(peg_val, 2),
            pe_digestion_years=round(digestion, 1),
            peg_signal=_classify_peg(peg_val),
            digestion_signal=_classify_digestion(digestion),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "eps_current": self.eps_current,
            "eps_forecast": self.eps_forecast,
            "pe_current": self.pe_current,
            "forward_pe": self.forward_pe,
            "cagr": self.cagr,
            "peg": self.peg,
            "pe_digestion_years": self.pe_digestion_years,
            "peg_signal": self.peg_signal,
            "digestion_signal": self.digestion_signal,
        }


# ── Core formulas ──────────────────────────────────────────────────────────


def forward_pe(price: float, eps_forecast: float) -> float:
    """前向PE = 当前股价 / 未来年度一致预期EPS.

    Args:
        price: Current stock price.
        eps_forecast: Forward EPS estimate.

    Returns:
        Forward PE ratio, or infinity if EPS <= 0.
    """
    if eps_forecast <= 0:
        return float("inf")
    return price / eps_forecast


def pe_digestion(
    current_pe: float,
    cagr: float,
    target_pe: float = 30.0,
) -> float:
    """当前PE消化到目标PE需要多少年.

    target_pe 固定 30x（A 股成长股合理估值锚点）。

    Uses the formula:  years = ln(current_pe / target_pe) / ln(1 + cagr)

    Args:
        current_pe: Current PE ratio.
        cagr: EPS compound annual growth rate (decimal, e.g. 0.20 = 20%).
        target_pe: Target PE for digestion (default 30).

    Returns:
        Years to digest, or infinity if CAGR <= 0.
    """
    if current_pe <= target_pe:
        return 0.0
    if cagr <= 0:
        return float("inf")
    return math.log(current_pe / target_pe) / math.log(1 + cagr)


def calc_peg(pe: float, cagr: float) -> float:
    """PEG = 前向PE / (CAGR * 100).

    PEG < 1    → 便宜
    PEG 1-1.5  → 合理
    PEG > 1.5  → 贵

    Args:
        pe: Forward PE ratio.
        cagr: EPS growth rate (decimal).

    Returns:
        PEG ratio, or infinity if CAGR <= 0.
    """
    if cagr <= 0:
        return float("inf")
    return pe / (cagr * 100)


# ── Helpers ────────────────────────────────────────────────────────────────


def _calc_cagr(eps_current: float, eps_forecast: float) -> float:
    """1-year forward EPS growth rate."""
    if eps_current <= 0:
        return 0.0
    return (eps_forecast / eps_current) - 1.0


def _classify_peg(peg_val: float) -> str:
    if peg_val == float("inf") or peg_val < 0:
        return "unknown"
    if peg_val < 1.0:
        return "cheap"
    if peg_val <= 1.5:
        return "fair"
    return "expensive"


def _classify_digestion(years: float) -> str:
    if years == float("inf"):
        return "never"
    if years == 0.0:
        return "already"
    if years <= 3.0:
        return "fast"
    if years <= 7.0:
        return "normal"
    return "slow"
