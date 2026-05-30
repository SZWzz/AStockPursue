"""MooTDX data loader: free TCP K-line + 分时图 (minute line) + 5-level order book
+ tick trades.

Connects directly to TongDaXin (通达信) quote servers via TCP port 7709.
No registration, no API key, no IP-blocking risk — the most stable free
A-share data source available.

K-line intervals: 1D / 1W / 1M / 1m / 5m / 15m / 30m / 60m.
Minute line: tick-level price/volume/amount per minute for a single trading day.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

# mootdx frequency values for market='std' (v0.9.0+ accepts string names like "1m").
# WARNING: the numeric values are NOT sequential — 0=5m, 1=15m, 2=30m, 3=1H,
# 4=1D, 5=1W, 6=1M, 9=1m.  Using strings avoids this entirely.
_FREQ_MAP: dict[str, str] = {
    "1D": "day",
    "1W": "week",
    "1M": "mon",
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1H": "1h",
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

    # Max bars returned by the TDX server per single request.
    _CHUNK_SIZE = 800

    def _fetch_bars_paginated(
        self,
        symbol: str,
        frequency: str,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV bars with pagination to cover the full date range.

        The TDX server returns at most ``_CHUNK_SIZE`` bars per call
        (``start`` counts backwards from the latest bar).  We loop
        with increasing ``start`` until we have enough data to cover
        *start_date*, or until the server returns fewer than
        ``_CHUNK_SIZE`` bars (beginning of available history).

        Args:
            symbol: Plain 6-digit stock code (e.g. ``"600519"``).
            frequency: mootdx frequency string (e.g. ``"day"``, ``"1m"``).
            start_date: ISO date string, oldest bar to include.
            end_date: ISO date string, newest bar to include.

        Returns:
            DataFrame indexed by ``trade_date`` with OHLCV columns,
            filtered to [*start_date*, *end_date*]; or ``None``.
        """
        CHUNK = self._CHUNK_SIZE
        all_frames: list[pd.DataFrame] = []
        chunk_start = 0
        start_ts = pd.Timestamp(start_date)

        # Safety cap — 50 000 chunks × 800 bars = 40 million bars
        # (≈ 160 000 years of daily data).
        MAX_CHUNKS = 50_000

        for _ in range(MAX_CHUNKS):
            raw = self._client.bars(
                symbol=symbol,
                frequency=frequency,
                start=chunk_start,
                offset=CHUNK,
            )

            if raw is None or len(raw) == 0:
                break

            df = pd.DataFrame(raw)

            # Normalise columns: datetime → trade_date, vol → volume
            col_map: dict[str, str] = {}
            if "datetime" in df.columns:
                col_map["datetime"] = "trade_date"
            if "vol" in df.columns:
                col_map["vol"] = "volume"
            df = df.rename(columns=col_map)

            if "trade_date" not in df.columns:
                logger.warning(
                    "mootdx bars missing 'datetime' column for %s", symbol,
                )
                break

            df["trade_date"] = pd.to_datetime(df["trade_date"])
            all_frames.append(df)

            # Stop when we've gone past the requested start_date.
            if df["trade_date"].min() <= start_ts:
                break

            # Stop when the server has no more data.
            if len(raw) < CHUNK:
                break

            chunk_start += CHUNK

        if not all_frames:
            return None

        result = pd.concat(all_frames, ignore_index=True)
        result = result.drop_duplicates(subset=["trade_date"])
        result = result.set_index("trade_date")
        result = result.sort_index()

        # Filter to the requested window.
        result = result.loc[start_date:end_date]
        return result

    # ── 分时图 (minute line) — price/volume/amount per minute for one day ──

    def _fetch_single_minute_line(
        self,
        symbol: str,
        date: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch minute-line data for *symbol* on a single trading day.

        Calls ``client.minutes()`` (historical) when *date* is not today,
        ``client.minute()`` (live) otherwise.  Returns the raw DataFrame
        normalised to columns ``time, price, volume, amount`` indexed by
        ``time`` (datetime).
        """
        self._ensure_client()
        target_date = pd.Timestamp(date).date()
        today = pd.Timestamp.now().date()

        try:
            if target_date == today:
                raw = self._client.minute(symbol=symbol)
            else:
                raw = self._client.minutes(symbol=symbol, date=str(target_date))
        except Exception:
            logger.debug("mootdx minute(s) call failed for %s on %s", symbol, date)
            return None

        if raw is None or len(raw) == 0:
            return None

        df = pd.DataFrame(raw)

        # The raw DataFrame from mootdx may use Chinese or English column names.
        # Normalise to a stable schema: time, price, volume, amount.
        col_map: dict[str, str] = {}
        for c in df.columns:
            c_lower = str(c).strip().lower()
            if c_lower in ("time", "datetime", "date", "时间"):
                col_map[c] = "time"
            elif c_lower in ("price", "close", "价格"):
                col_map[c] = "price"
            elif c_lower in ("volume", "vol", "成交量"):
                col_map[c] = "volume"
            elif c_lower in ("amount", "amt", "成交额"):
                col_map[c] = "amount"
        df = df.rename(columns=col_map)

        # Ensure we have at least time + price.
        if "time" not in df.columns:
            logger.warning("mootdx minute data missing 'time' column for %s", symbol)
            return None
        if "price" not in df.columns:
            logger.warning("mootdx minute data missing 'price' column for %s", symbol)
            return None

        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time").sort_index()

        # Keep only standard columns that exist.
        keep = [c for c in ("price", "volume", "amount") if c in df.columns]
        return df[keep].astype("float64")

    def fetch_minute_line(
        self,
        code: str,
        date: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch 分时图 (minute-by-minute price trace) for a single stock on a
        single trading day.

        Args:
            code: Stock code (e.g. ``"600519.SH"`` or ``"600519"``).
            date: Date string ``"YYYY-MM-DD"``.

        Returns:
            DataFrame indexed by ``time`` with columns ``price, volume, amount``,
            or ``None`` if no data is available.
        """
        try:
            plain, _, _ = _normalize_code(code)
        except ValueError:
            logger.debug("mootdx minute line code not supported: %s", code)
            return None

        try:
            return self._fetch_single_minute_line(plain, date)
        except Exception as exc:
            logger.warning("mootdx minute line fetch failed for %s on %s: %s", code, date, exc)
            return None

    def fetch_minute_lines(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
    ) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
        """Fetch 分时图 data for multiple stocks over a date range.

        For each stock, returns one DataFrame per trading day in
        [*start_date*, *end_date*].  Days with no data (weekends, holidays,
        suspended) map to ``None``.

        Args:
            codes: List of stock codes.
            start_date: Oldest date (``"YYYY-MM-DD"``).
            end_date: Newest date (``"YYYY-MM-DD"``).

        Returns:
            ``{code: {date_str: DataFrame | None}}`` — nested dict keyed by
            code then date.  Each DataFrame is indexed by ``time`` with columns
            ``price, volume, amount``.
        """
        validate_date_range(start_date, end_date)

        # Build a list of trading days.  We use pd.bdate_range as a rough
        # approximation; the actual mootdx server simply returns empty for
        # non-trading days, so over-fetching is harmless.
        date_range = pd.bdate_range(start=start_date, end=end_date)
        date_strs = [d.strftime("%Y-%m-%d") for d in date_range]

        result: Dict[str, Dict[str, Optional[pd.DataFrame]]] = {}

        for code in codes:
            try:
                plain, _, _ = _normalize_code(code)
            except ValueError:
                logger.debug("mootdx minute line code not supported: %s", code)
                result[code] = {d: None for d in date_strs}
                continue

            code_result: Dict[str, Optional[pd.DataFrame]] = {}
            for d in date_strs:
                try:
                    df = self._fetch_single_minute_line(plain, d)
                    code_result[d] = df
                except Exception as exc:
                    logger.debug("mootdx minute line failed for %s on %s: %s", code, d, exc)
                    code_result[d] = None
            result[code] = code_result

        return result

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

        freq = _FREQ_MAP.get(interval)
        if freq is None:
            raise ValueError(
                f"mootdx does not support interval={interval!r}. "
                f"Supported: {list(_FREQ_MAP.keys())}"
            )

        self._ensure_client()
        result: Dict[str, pd.DataFrame] = {}

        for code in codes:
            try:
                plain, market, _ = _normalize_code(code)
                df = self._fetch_bars_paginated(
                    symbol=plain,
                    frequency=freq,
                    start_date=start_date,
                    end_date=end_date,
                )

                if df is None or df.empty:
                    logger.debug(
                        "mootdx returned empty for %s (freq=%s)", plain, freq,
                    )
                    continue

                # Warn about missing OHLCV columns (non-fatal — engine handles it).
                for col in ("open", "high", "low", "close"):
                    if col not in df.columns:
                        logger.warning(
                            "mootdx bars missing '%s' column for %s", col, code,
                        )

                # Keep only OHLCV columns
                keep_cols = [
                    c for c in ("open", "high", "low", "close", "volume")
                    if c in df.columns
                ]
                result[code] = df[keep_cols].astype("float64")

            except ValueError:
                logger.debug("mootdx code not supported: %s", code)
                continue
            except Exception as exc:
                logger.warning("mootdx fetch failed for %s: %s", code, exc)
                continue

        return result
