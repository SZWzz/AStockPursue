"""A-share (China mainland) backtest engine.

Market rules:
  - T+1: cannot sell shares bought today
  - No short selling for retail investors
  - Price limits: ±10% main board, ±20% ChiNext/STAR, ±5% ST
  - Minimum lot: 100 shares (odd lots can only be sold, not bought)
  - Commission: ¥5 minimum, 0.03% (万3) bilateral
  - Stamp tax: 0.05% (万5) sell-side only
  - Transfer fee: 0.001% (万0.1) bilateral
"""

from __future__ import annotations

import pandas as pd

from backtest.engines.base import BaseEngine


class ChinaAEngine(BaseEngine):
    """A-share market engine.

    Config keys:
      - commission_rate: default 0.0003 (万3, 3 bps per side)
      - commission_min: default 5.0 (RMB)
      - stamp_tax: default 0.0005 (万5, sell-only)
      - transfer_fee: default 0.00001 (万0.1)
      - slippage: default 0.001
    """

    def __init__(self, config: dict):
        config = {**config, "leverage": 1.0}  # A-shares: no leverage
        super().__init__(config)
        self.commission_rate: float = config.get("commission_rate", 0.0003)
        self.commission_min: float = config.get("commission_min", 5.0)
        self.stamp_tax: float = config.get("stamp_tax", 0.0005)
        self.transfer_fee: float = config.get("transfer_fee", 0.00001)
        self.slippage_rate: float = config.get("slippage", 0.001)
        self.slippage_mode: str = config.get("slippage_mode", "fixed")  # "fixed" | "volume"

    def can_execute(self, symbol: str, direction: int, bar: pd.Series) -> bool:
        """A-share execution rules.

        Args:
            symbol: Stock code (e.g. 000001.SZ).
            direction: 1 (buy), -1 (short — always blocked), 0 (sell/close).
            bar: Current bar (needs 'close', 'pre_close' or 'pct_chg').

        Returns:
            True if the trade is allowed.
        """
        # 1. No short selling
        if direction == -1:
            return False

        # 2. T+1: can't sell shares bought today
        if direction == 0:
            pos = self.positions.get(symbol)
            if pos is not None:
                bar_date = _bar_date(bar)
                entry_date = pos.entry_time.date() if hasattr(pos.entry_time, "date") else None
                if bar_date is not None and entry_date is not None and bar_date == entry_date:
                    return False

        # 3. Open-based price limits (execution-time check).
        #    _process_signals() executes at bar open, so we must verify
        #    the stock is tradable at that price — not just at the close.
        open_price = float(bar.get("open", 0))
        pre_close = float(bar.get("pre_close", 0))
        if open_price > 0 and pre_close > 0:
            open_pct = (open_price - pre_close) / pre_close
            limit = _price_limit(symbol)
            if direction == 1 and open_pct >= limit - 0.001:
                return False  # opened at limit-up, cannot buy
            if direction == 0 and open_pct <= -limit + 0.001:
                return False  # opened at limit-down, cannot sell

        # 4. Close-based price limits (supplementary — catches stocks that
        #    hit the limit during the session)
        pct_chg = _calc_pct_change(bar)
        if pct_chg is not None:
            limit = _price_limit(symbol)
            if direction == 1 and pct_chg >= limit - 0.001:
                return False  # limit-up: can't buy
            if direction == 0 and pct_chg <= -limit + 0.001:
                return False  # limit-down: can't sell

        return True

    def round_size(self, raw_size: float, price: float) -> float:
        """Round down to 100-share lots."""
        return max(int(raw_size / 100) * 100, 0)

    def calc_commission(self, size: float, price: float, _direction: int, is_open: bool) -> float:
        """A-share fee structure: commission + stamp tax (sell) + transfer fee.

        ``_direction`` is unused today — reserved for future asymmetric
        long/short fee schedules (margin trading, securities lending).
        """
        notional = size * price
        # Commission: 万3 (3 bps per side), min ¥5
        comm = max(notional * self.commission_rate, self.commission_min)
        # Transfer fee: 万0.1 bilateral
        comm += notional * self.transfer_fee
        # Stamp tax: 万5 sell-only
        if not is_open:
            comm += notional * self.stamp_tax
        return comm

    def apply_slippage(self, price: float, direction: int, volume: float = 0.0) -> float:
        """A-share slippage.

        In ``fixed`` mode (default): constant percentage of price.
        In ``volume`` mode: tiered by notional turnover.
        """
        if self.slippage_mode == "volume" and volume > 0:
            notional = price * volume
            if notional < 500_000:        # < ¥50万 → 0.3%
                rate = 0.003
            elif notional < 5_000_000:    # ¥50万 ~ ¥500万 → 0.15%
                rate = 0.0015
            else:                          # > ¥500万 → 0.05%
                rate = 0.0005
            return price * (1 + direction * rate)
        return price * (1 + direction * self.slippage_rate)


# ── Helpers ──


def _bar_date(bar: pd.Series):
    """Extract the trade date from a bar Series, handling various column names.

    Tries ``trade_date`` and ``date`` columns first (common in tushare
    and EastMoney data).  Falls back to the Series name (index timestamp).

    Args:
        bar: A pandas Series representing one OHLCV bar.

    Returns:
        A ``datetime.date`` object, or ``None`` if no date can be
        extracted.
    """
    for col in ("trade_date", "date"):
        if col in bar.index:
            val = bar[col]
            if hasattr(val, "date"):
                return val.date()
            try:
                return pd.Timestamp(val).date()
            except Exception:
                pass
    # Fall back to bar name (index timestamp)
    if hasattr(bar, "name") and hasattr(bar.name, "date"):
        return bar.name.date()
    return None


# Note: china_futures and global_futures have variants that prioritise
# settle/pre_settle (futures-native); see those modules for the
# futures-specific logic.
def _calc_pct_change(bar: pd.Series):
    """Calculate price change percentage from a bar Series.

    Prefers the ``pct_chg`` column (returned by tushare as percentage
    points, e.g. 5.0 = +5%).  Falls back to computing ``(close - pre_close)
    / pre_close`` if ``pct_chg`` is missing.

    Args:
        bar: A pandas Series representing one OHLCV bar.

    Returns:
        Price change as a decimal fraction (e.g. 0.05 = +5%), or
        ``None`` if neither column is available.
    """
    if "pct_chg" in bar.index:
        val = bar["pct_chg"]
        if pd.notna(val):
            return float(val) / 100.0  # tushare pct_chg is in percentage points

    close = bar.get("close")
    pre_close = bar.get("pre_close")
    if close is not None and pre_close is not None and pre_close > 0:
        return (float(close) - float(pre_close)) / float(pre_close)
    return None


def _price_limit(symbol: str) -> float:
    """Determine the daily price limit based on board membership.

    Args:
        symbol: Stock code (e.g. ``300001.SZ``, ``688001.SH``,
            ``000001.SZ``).

    Returns:
        Limit as a decimal fraction:
            - 0.20 for ChiNext (300xxx) and STAR (688xxx)
            - 0.30 for Beijing Exchange (8xxxxx)
            - 0.10 for main board and everything else
    """
    code = symbol.split(".")[0] if "." in symbol else symbol
    # ChiNext (300xxx) / STAR (688xxx): ±20%
    if code.startswith("300") or code.startswith("688"):
        return 0.20
    # ST stocks: ±5% (heuristic: can't fully detect from code alone)
    # Beijing exchange (8xxxxx): ±30% — simplified to 0.30
    if code.startswith("8") and len(code) == 6:
        return 0.30
    # Main board: ±10%
    return 0.10
