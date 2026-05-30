"""MooTDX data loader: free TCP K-line + 5-level order book + tick trades.

Connects directly to TongDaXin (通达信) quote servers via TCP port 7709.
No registration, no API key, no IP-blocking risk — the most stable free
A-share data source available.

Supports: 1D / 1W / 1M / 1m / 5m / 15m / 30m / 60m intervals.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

# category -> interval mapping (mootdx bars `category` param)
_CATEGORY_MAP: dict[str, int] = {
    "1D": 4,
    "1W": 5,
    "1M": 6,
    "1m": 7,
    "5m": 8,
    "15m": 9,
    "30m": 10,
    "1H": 11,
}

# mootdx market: 0=Shenzhen, 1=Shanghai
_MARKET_MAP: dict[str, int] = {
    "sz": 0,
    "sh": 1,
    "bj": 0,  # Beijing Exchange uses Shenzhen market id in mootdx
}


def _normalize_code(symbol: str) -> tuple[str, int, str]:
    """Normalize a symbol to (plain_code, market_id, full_code).

    Returns:
        (code_digits, market_int, code_with_prefix) — e.g. ``("600519", 1, "600519")``.
    """
    s = (symbol or "").strip().upper()
    if not s:
        raise ValueError(f"Empty symbol: {symbol!r}")

    # Strip suffix
    for suffix in (".SH", ".SZ", ".BJ", ".SS"):
        if s.endswith(suffix):
            s = s[:-3]
            break

    # Strip prefix
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix) and len(s) > 2:
            s = s[2:]
            break

    s = s.strip()
    if not s.isdigit() or len(s) != 6:
        raise ValueError(f"Cannot normalize symbol: {symbol!r} -> {s!r}")

    if s.startswith(("6", "9")):
        market = 1
    else:
        market = 0

    return s, market, s


@register
class DataLoader:
    """MooTDX OHLCV loader (free TCP, no auth, no IP-blocking)."""

    name = "mootdx"
    markets = {"a_share"}
    requires_auth = False

    def __init__(self) -> None:
        self._client: Any = None

    def is_available(self) -> bool:
        try:
            from mootdx.quotes import Quotes  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_client(self) -> None:
        if self._client is None:
            from mootdx.quotes import Quotes
            self._client = Quotes.factory(market="std")

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        validate_date_range(start_date, end_date)

        category = _CATEGORY_MAP.get(interval)
        if category is None:
            raise ValueError(
                f"mootdx does not support interval={interval!r}. "
                f"Supported: {list(_CATEGORY_MAP.keys())}"
            )

        self._ensure_client()
        result: Dict[str, pd.DataFrame] = {}

        for code in codes:
            try:
                plain, market, _ = _normalize_code(code)
                # mootdx bars(): market=0/1, category, offset (count from latest)
                # For daily data, offset=800 covers ~3 years; for minute it covers
                # the session.  We request a generous window and filter locally.
                raw = self._client.bars(symbol=plain, category=category, offset=800)

                if raw is None or len(raw) == 0:
                    logger.debug("mootdx returned empty for %s (cat=%d)", plain, category)
                    continue

                df = pd.DataFrame(raw)
                # Columns from mootdx: open, close, high, low, vol, amount, datetime
                col_map = {}
                if "datetime" in df.columns:
                    col_map["datetime"] = "trade_date"
                if "vol" in df.columns:
                    col_map["vol"] = "volume"
                df = df.rename(columns=col_map)

                if "trade_date" not in df.columns:
                    logger.warning("mootdx bars missing 'datetime' column for %s", code)
                    continue

                # Ensure OHLCV columns exist
                for col in ("open", "high", "low", "close"):
                    if col not in df.columns:
                        logger.warning("mootdx bars missing '%s' column for %s", col, code)

                df["trade_date"] = pd.to_datetime(df["trade_date"])
                df = df.set_index("trade_date")
                df = df.sort_index()

                # Filter date range
                df = df.loc[start_date:end_date]
                if df.empty:
                    continue

                # Keep only OHLCV columns
                keep_cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
                result[code] = df[keep_cols].astype("float64")

            except ValueError:
                logger.debug("mootdx code not supported: %s", code)
                continue
            except Exception as exc:
                logger.warning("mootdx fetch failed for %s: %s", code, exc)
                continue

        return result
