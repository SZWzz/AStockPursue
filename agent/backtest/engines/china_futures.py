"""China futures backtest engine.

Market rules (exchange-level, CFFEX / SHFE / DCE / ZCE / INE / GFEX):
  - T+0: can open and close same day (intraday trading allowed)
  - Margin trading: 5%~15% by product (exchange-set minimum)
  - Price limits: stock-index +-10%, bonds +-2%, commodities +-3%~8%
  - Commission: per-lot fixed or per-notional rate (varies by product)
  - Contract multiplier: product-specific (IF=300, rb=10, au=1000, ...)
  - Minimum trading unit: 1 contract
  - Night session: 21:00-02:30 (varies by product, not enforced in bar-level sim)
"""

from __future__ import annotations

import re
from datetime import time

import pandas as pd

from backtest.engines.futures_base import FuturesBaseEngine


# ── Trading session definitions (for minute-level backtests) ──

# Each entry: [(start_h, start_m, end_h, end_m), ...]
# Times are in Asia/Shanghai (no DST).  Products not listed default to
# day-only: 9:00-11:30, 13:30-15:00 (no night session filter applied).
_TRADING_SESSIONS: dict[str, list[tuple[int, int, int, int]]] = {
    # CFFEX — stock index futures have no night session
    "IC": [(9, 30, 11, 30), (13, 0, 15, 0)],   # CSI 500
    "IF": [(9, 30, 11, 30), (13, 0, 15, 0)],   # CSI 300
    "IH": [(9, 30, 11, 30), (13, 0, 15, 0)],   # SSE 50
    "IM": [(9, 30, 11, 30), (13, 0, 15, 0)],   # CSI 1000
    "T":  [(9, 30, 11, 30), (13, 0, 15, 15)],  # 10Y Treasury
    "TF": [(9, 30, 11, 30), (13, 0, 15, 15)],  # 5Y Treasury
    "TS": [(9, 30, 11, 30), (13, 0, 15, 15)],  # 2Y Treasury
    # SHFE — night session to 23:00 or 01:00 or 02:30 by product
    "AU": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 2, 30)],   # Gold
    "AG": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 2, 30)],   # Silver
    "CU": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 1, 0)],    # Copper
    "AL": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 1, 0)],    # Aluminium
    "ZN": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 1, 0)],    # Zinc
    "PB": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 1, 0)],    # Lead
    "NI": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 1, 0)],    # Nickel
    "SN": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 1, 0)],    # Tin
    "RB": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Rebar
    "HC": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Hot-rolled coil
    "SS": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Stainless steel
    "BU": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Asphalt
    "FU": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Fuel oil
    "RU": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Rubber
    "SP": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Pulp
    "AO": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Alumina
    "BR": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Butadiene rubber
    # DCE
    "I":  [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Iron ore
    "J":  [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Coke
    "JM": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Coking coal
    "P":  [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Palm oil
    "Y":  [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Soybean oil
    "A":  [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # No.1 Soybean
    "M":  [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Soybean meal
    "EG": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Ethylene glycol
    "L":  [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # LLDPE
    "PP": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # PP
    "V":  [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # PVC
    # ZCE
    "SR": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Sugar
    "CF": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Cotton
    "TA": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # PTA
    "MA": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Methanol
    "FG": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Glass
    "SA": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Soda ash
    "RM": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Rapeseed meal
    "OI": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Rapeseed oil
    "UR": [(9, 0, 11, 30), (13, 30, 15, 0)],                    # Urea (no night)
    "SH": [(9, 0, 11, 30), (13, 30, 15, 0)],                    # Soda ash lite
    # INE
    "SC": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 2, 30)],   # Crude oil
    "LU": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # Low-sulfur fuel oil
    "BC": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 1, 0)],    # Bonded copper
    "NR": [(9, 0, 11, 30), (13, 30, 15, 0), (21, 0, 23, 0)],   # TSR 20 rubber
    # GFEX
    "SI": [(9, 0, 11, 30), (13, 30, 15, 0)],                    # Silicon (no night)
    "LC": [(9, 0, 11, 30), (13, 30, 15, 0)],                    # Lithium carbonate
}


def bar_in_trading_session(code: str, ts: pd.Timestamp) -> bool:
    """Check whether a timestamp falls within the code's trading sessions.

    Only enforced for minute-level bars (intraday).  Daily bars always pass.
    """
    product = _extract_product(code).upper()  # session keys are uppercase
    sessions = _TRADING_SESSIONS.get(product)
    if sessions is None:
        # Unknown product → assume day-only
        sessions = [(9, 0, 11, 30), (13, 30, 15, 0)]

    t = ts.time()
    for sh, sm, eh, em in sessions:
        start = time(sh, sm)
        end = time(eh, em)
        if start <= end:
            # Normal session (e.g. 9:00-11:30)
            if start <= t <= end:
                return True
        else:
            # Overnight session (e.g. 21:00-02:30)
            if t >= start or t <= end:
                return True

    return False


# ── Contract multiplier lookup ──

_MULTIPLIER: dict[str, int] = {
    # Stock index futures (CFFEX)
    "IF": 300, "IC": 200, "IH": 300, "IM": 200,
    # Treasury bond futures (CFFEX)
    "T": 10000, "TF": 10000, "TS": 20000, "TL": 10000,
    # Metals (SHFE)
    "au": 1000, "ag": 15, "cu": 5, "al": 5, "zn": 5,
    "pb": 5, "ni": 1, "sn": 1, "ss": 5,
    # Ferrous (SHFE / DCE)
    "rb": 10, "hc": 10, "i": 100, "j": 100, "jm": 60,
    # Energy (SHFE / INE)
    "sc": 1000, "fu": 10, "lu": 10, "bu": 10, "nr": 10,
    # Agriculture (DCE)
    "c": 10, "cs": 10, "m": 10, "y": 10, "a": 10,
    "p": 10, "jd": 10, "lh": 16, "rr": 10, "pg": 20,
    # Agriculture (ZCE)
    "CF": 5, "SR": 10, "TA": 5, "MA": 10, "AP": 10,
    "RM": 10, "OI": 10, "CJ": 5, "PK": 5, "CY": 5,
    # Chemical (DCE / ZCE)
    "pp": 5, "l": 5, "v": 5, "eg": 10, "eb": 5,
    "PF": 5, "SA": 20, "FG": 20, "UR": 20,
    # GFEX
    "si": 5, "lc": 1,
}

# ── Margin rate (exchange minimum) ──

_MARGIN_RATE: dict[str, float] = {
    # CFFEX stock index
    "IF": 0.12, "IC": 0.12, "IH": 0.12, "IM": 0.12,
    # CFFEX bonds
    "T": 0.03, "TF": 0.02, "TS": 0.015, "TL": 0.035,
    # SHFE metals
    "au": 0.08, "ag": 0.09, "cu": 0.08, "al": 0.07,
    "zn": 0.08, "pb": 0.08, "ni": 0.12, "sn": 0.10, "ss": 0.08,
    # Ferrous
    "rb": 0.10, "hc": 0.10, "i": 0.12, "j": 0.12, "jm": 0.12,
    # Energy
    "sc": 0.10, "fu": 0.10, "lu": 0.10, "bu": 0.10,
    # Agriculture
    "c": 0.07, "cs": 0.07, "m": 0.08, "y": 0.08, "a": 0.08,
    "p": 0.08, "jd": 0.08, "lh": 0.12,
    # Textiles / chemical
    "CF": 0.07, "SR": 0.07, "TA": 0.07, "MA": 0.07,
    "pp": 0.07, "l": 0.07, "v": 0.07, "eg": 0.08,
    "SA": 0.08, "FG": 0.08, "UR": 0.08,
}

# ── Price limit (fraction, ± from settlement) ──

_PRICE_LIMIT: dict[str, float] = {
    # CFFEX stock index ±10%
    "IF": 0.10, "IC": 0.10, "IH": 0.10, "IM": 0.10,
    # CFFEX bonds ±2% (simplified)
    "T": 0.02, "TF": 0.012, "TS": 0.005, "TL": 0.035,
}
_DEFAULT_PRICE_LIMIT = 0.05  # most commodities ±4%~7%, use 5% as default

# ── Commission structure ──
# ("rate", pct) = per-notional  |  ("fixed", amount_per_lot) = per-contract

_COMMISSION: dict[str, tuple[str, float]] = {
    # CFFEX stock index: ~0.0023% of notional
    "IF": ("rate", 0.000023), "IC": ("rate", 0.000023),
    "IH": ("rate", 0.000023), "IM": ("rate", 0.000023),
    # CFFEX bonds
    "T": ("fixed", 3.0), "TF": ("fixed", 3.0), "TS": ("fixed", 3.0),
    # Metals
    "au": ("fixed", 10.0), "ag": ("fixed", 3.0), "cu": ("fixed", 5.0),
    "al": ("fixed", 3.0), "zn": ("fixed", 3.0), "ni": ("fixed", 3.0),
    # Ferrous
    "rb": ("rate", 0.0001), "hc": ("rate", 0.0001), "i": ("rate", 0.0001),
    "j": ("rate", 0.0001), "jm": ("rate", 0.0001),
    # Energy
    "sc": ("fixed", 20.0), "fu": ("rate", 0.00005),
    # Agriculture
    "c": ("fixed", 1.2), "cs": ("fixed", 1.5), "m": ("fixed", 1.5),
    "y": ("fixed", 2.5), "a": ("fixed", 2.0), "p": ("fixed", 2.5),
    "jd": ("rate", 0.00015), "lh": ("rate", 0.0002),
    # Textiles / chemical
    "CF": ("fixed", 4.3), "SR": ("fixed", 3.0), "TA": ("fixed", 3.0),
    "MA": ("fixed", 2.0), "pp": ("fixed", 1.0), "l": ("fixed", 1.0),
    "v": ("fixed", 1.0), "SA": ("fixed", 3.5), "FG": ("fixed", 3.0),
}
_DEFAULT_COMMISSION: tuple[str, float] = ("fixed", 5.0)


def _extract_product(symbol: str) -> str:
    """Extract product code from futures symbol.

    Examples:
        'IF2406.CFFEX' -> 'IF'
        'rb2410.SHFE'  -> 'rb'

    Args:
        symbol: Futures symbol string.

    Returns:
        Product code (e.g. 'IF', 'rb', 'au').
    """
    code = symbol.split(".")[0]
    m = re.match(r"([A-Za-z]+)", code)
    return m.group(1) if m else code


class ChinaFuturesEngine(FuturesBaseEngine):
    """China futures engine covering CFFEX / SHFE / DCE / ZCE / INE / GFEX.

    Config keys:
      - slippage: default 0.0005
      - margin_rate_override: override margin rate for all products
      - commission_override: override commission for all products
    """

    def __init__(self, config: dict):
        # Derive leverage from margin rate of first code, or use config override
        margin_override = config.get("margin_rate_override")
        if margin_override:
            leverage = 1.0 / margin_override
        else:
            codes = config.get("codes", [])
            if codes:
                product = _extract_product(codes[0])
                mr = _MARGIN_RATE.get(product, 0.10)
                leverage = 1.0 / mr
            else:
                leverage = 10.0  # ~10% margin default
        config = {**config, "leverage": leverage}
        super().__init__(config)
        self.slippage_rate: float = config.get("slippage", 0.0005)
        self._commission_override = config.get("commission_override")

    def can_execute(self, symbol: str, direction: int, bar: pd.Series) -> bool:
        """China futures: T+0, both directions, price-limit enforced.

        Args:
            symbol: Futures code.
            direction: 1 (long), -1 (short), 0 (close).
            bar: Current bar data.

        Returns:
            True if allowed.
        """
        # T+0: no same-day sell restriction
        # Both long and short allowed

        # Price limit check
        pct_chg = _calc_pct_change(bar)
        if pct_chg is not None:
            product = _extract_product(symbol)
            limit = _PRICE_LIMIT.get(product, _DEFAULT_PRICE_LIMIT)
            if direction == 1 and pct_chg >= limit - 0.001:
                return False  # limit-up: can't open long / can't buy
            if direction == -1 and pct_chg <= -limit + 0.001:
                return False  # limit-down: can't open short
            if direction == 0:
                pos = self.positions.get(symbol)
                if pos is not None:
                    # Can't close long at limit-down, can't close short at limit-up
                    if pos.direction == 1 and pct_chg <= -limit + 0.001:
                        return False
                    if pos.direction == -1 and pct_chg >= limit - 0.001:
                        return False
        return True

    def round_size(self, raw_size: float, price: float) -> float:
        """Minimum 1 contract, integer lots only."""
        return max(int(raw_size), 0)

    def calc_commission(self, size: float, price: float, _direction: int, is_open: bool) -> float:
        """Commission varies by product: fixed per-lot or percentage of notional.

        For close orders, the engine passes ``entry_time`` via the market engine's
        ``_active_entry_time`` attribute (set before close).  If the entry date
        matches the current bar date, the 平今仓 (close-today) multiplier applies.
        """
        if self._commission_override is not None:
            return size * price * self._commission_override
        entry_time = getattr(self, "_active_entry_time", None)
        return self.calc_commission_for_symbol(self._active_symbol, size, price, is_open, entry_time)

    # ── 平今仓 (close-today) multipliers ──────────────────────────────
    # Products not listed here use 1.0 (no day-trade surcharge).
    # Values sourced from exchange fee schedules (2024).
    _CLOSE_TODAY_MULT: dict[str, float] = {
        # CFFEX — stock index futures: 15× normal for close-today
        "IF": 15.0, "IC": 15.0, "IH": 15.0, "IM": 15.0,
        # SHFE — metals: close-today is free for some, normal for others
        "CU": 1.0, "AL": 1.0, "ZN": 1.0, "PB": 1.0,  # close-today = normal
        "AU": 0.0, "AG": 0.0,                          # close-today free
        # SHFE — steel: close-today = 1.5× (rebars, HR coil)
        "RB": 1.5, "HC": 1.5, "SS": 1.5,
        # DCE — most: close-today free
        "I": 0.0, "J": 0.0, "JM": 0.0, "P": 0.0, "Y": 0.0,
        "A": 0.0, "M": 0.0, "EG": 0.0, "L": 0.0, "PP": 0.0, "V": 0.0,
        # ZCE — most: close-today free
        "SR": 0.0, "CF": 0.0, "TA": 0.0, "MA": 0.0,
        "FG": 0.0, "SA": 0.0, "RM": 0.0, "OI": 0.0,
        # INE — close-today = normal
        "SC": 1.0, "LU": 1.0, "BC": 1.0, "NR": 1.0,
    }

    def calc_commission_for_symbol(
        self, symbol: str, size: float, price: float, is_open: bool,
        entry_time: Any = None,
    ) -> float:
        """Symbol-aware commission calculation.

        Args:
            symbol: Futures code.
            size: Number of contracts.
            price: Execution price.
            is_open: True for opening trade.
            entry_time: Position entry timestamp (for 平今仓 detection).

        Returns:
            Commission in RMB.
        """
        product = _extract_product(symbol)
        mode, value = _COMMISSION.get(product, _DEFAULT_COMMISSION)
        cm = _MULTIPLIER.get(product, 10)

        base = size * price * cm * value if mode == "rate" else size * value

        # 平今仓 (close-today) surcharge / discount
        if not is_open and entry_time is not None:
            mult = self._CLOSE_TODAY_MULT.get(product, 1.0)
            if mult != 1.0 and hasattr(entry_time, "date"):
                try:
                    import datetime as _dt
                    today = _dt.date.today()  # approximate — engine sets this
                    # The engine sets _active_bar_date before calling close
                    bar_date = getattr(self, "_active_bar_date", today)
                    entry_date = entry_time.date() if hasattr(entry_time, "date") else entry_time
                    if hasattr(entry_date, "__call__"):
                        entry_date = entry_date()
                    # Compare dates
                    if str(bar_date) == str(entry_date):
                        if mult == 0.0:
                            return 0.0  # close-today free
                        return base * mult
                except Exception:
                    pass

        return base

    def apply_slippage(self, price: float, direction: int) -> float:
        """Futures slippage."""
        return price * (1 + direction * self.slippage_rate)

    def get_contract_multiplier(self, symbol: str) -> float:
        """Look up contract multiplier from product code."""
        product = _extract_product(symbol)
        return float(_MULTIPLIER.get(product, 10))

    # ── Delivery fee (charged when holding into delivery month) ─────
    # Approximate per-contract delivery fees in RMB.  Only charged on the
    # last trading day if the strategy still holds a position.
    # Products not listed have no delivery fee (cash-settled or unknown).
    _DELIVERY_FEE: dict[str, float] = {
        "I": 2.0, "J": 2.0, "JM": 2.0,   # iron ore / coke — ¥2/ton
        "RB": 1.0, "HC": 1.0,             # rebar / HRC — ¥1/ton
        "CU": 2.0, "AL": 2.0, "ZN": 2.0, # metals — ¥2/ton
        "AU": 2.0, "AG": 2.0,             # precious metals
        "SC": 2.0,                         # crude oil
        "P": 1.0, "Y": 1.0, "M": 1.0,    # agri — ¥1/ton
        "SR": 1.0, "CF": 1.0, "TA": 1.0, # ZCE agri
    }

    def get_delivery_fee(self, symbol: str, size: float) -> float:
        """Return delivery fee for a symbol at end of backtest.

        Only charged on physical-delivery products.
        """
        product = _extract_product(symbol)
        rate = self._DELIVERY_FEE.get(product, 0.0)
        cm = _MULTIPLIER.get(product, 10)
        return size * rate * cm

    def get_margin_rate(self, symbol: str) -> float:
        """Look up exchange margin rate for a product.

        Args:
            symbol: Futures symbol.

        Returns:
            Margin rate (e.g. 0.10 for 10%).
        """
        product = _extract_product(symbol)
        return _MARGIN_RATE.get(product, 0.10)


# ── Helpers ──


# Note: china_a uses close/pre_close-only; global_futures prioritises
# close/pre_close before settle. This China-futures variant prefers
# settle/pre_settle because tushare reports settlement as the canonical
# daily price for domestic contracts. See those modules for the equity /
# global-futures equivalents.
def _calc_pct_change(bar: pd.Series):
    """Calculate bar price change percentage.

    Priority: settle/pre_settle (futures native) > close/pre_close > pct_chg.
    pct_chg from tushare is always in percentage points (0.5 = 0.5%).
    """
    # Prefer settlement prices (unambiguous for futures)
    settle = bar.get("settle")
    pre_settle = bar.get("pre_settle")
    if settle is not None and pre_settle is not None and pre_settle > 0:
        return (float(settle) - float(pre_settle)) / float(pre_settle)

    close = bar.get("close")
    pre_close = bar.get("pre_close")
    if close is not None and pre_close is not None and pre_close > 0:
        return (float(close) - float(pre_close)) / float(pre_close)

    # tushare pct_chg is in percentage points (e.g. 0.5 = 0.5%)
    if "pct_chg" in bar.index:
        val = bar["pct_chg"]
        if pd.notna(val):
            return float(val) / 100.0

    return None
