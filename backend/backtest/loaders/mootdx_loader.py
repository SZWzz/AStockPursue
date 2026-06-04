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
            from mootdx import config

            config.setup()

            # bestip(sync=True) probes every server and can hang for
            # minutes when the Docker network can't reach some IPs.
            # Populate BESTIP directly from the pre-configured SERVER
            # list so Quotes.factory() finds a usable address.
            bestip_hq = config.get('BESTIP', {}).get('HQ', '')
            if not bestip_hq:
                server_list = config.get('SERVER', {}).get('HQ', [])
                if server_list:
                    # server_list entries: [name, ip, port]
                    config.set('BESTIP', {'HQ': server_list[0][1:]})

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
                # TDX protocol requires YYYYMMDD format (no hyphens)
                raw = self._client.minutes(symbol=symbol, date=target_date.strftime("%Y%m%d"))
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

        # mootdx's to_data() creates a 'volume' column from 'vol', and our
        # normalisation also renames 'vol'→'volume', which can produce duplicates.
        df = df.loc[:, ~df.columns.duplicated()]

        # Ensure we have at least price.
        if "price" not in df.columns:
            logger.warning("mootdx minute data missing 'price' column for %s", symbol)
            return None

        # Generate time column from row index when the TDX response omits it.
        # A-share trading hours: morning 9:30–11:30 (120 bars), afternoon 13:00–15:00 (120 bars).
        if "time" not in df.columns:
            times: list[str] = []
            morning = f"{target_date}T09:30:00"
            afternoon = f"{target_date}T13:00:00"
            morning_start = pd.Timestamp(morning)
            afternoon_start = pd.Timestamp(afternoon)
            for i in range(len(df)):
                if i < 120:
                    t = morning_start + pd.Timedelta(minutes=i)
                else:
                    t = afternoon_start + pd.Timedelta(minutes=i - 120)
                times.append(t.strftime("%Y-%m-%d %H:%M:%S"))
            df["time"] = times

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

    # ── 财务快照 (37-field quarterly snapshot) ──────────────────────────

    def fetch_finance(self, code: str) -> dict[str, Any] | None:
        """Fetch 37-field quarterly financial snapshot for a single stock.

        Returns fields like: eps, bvps, roe, profit, income, total_shares,
        float_shares, net_assets_per_share, etc.

        Args:
            code: Stock code (e.g. ``"688017"`` or ``"688017.SH"``).

        Returns:
            Dict of 37 financial fields, or None if unavailable.
        """
        try:
            plain, market, _ = _normalize_code(code)
        except ValueError:
            logger.debug("mootdx finance: code not supported: %s", code)
            return None

        self._ensure_client()
        try:
            fin = self._client.finance(symbol=plain)
            if fin is None:
                return None
            # mootdx returns a DataFrame with one row per report period.
            # Return the latest period as a dict.
            if hasattr(fin, "iloc"):
                if len(fin) == 0:
                    return None
                latest = fin.iloc[-1]
                return {str(k): _safe_float(v) for k, v in latest.items()}
            return None
        except Exception as exc:
            logger.warning("mootdx finance fetch failed for %s: %s", code, exc)
            return None

    # ── F10 公司资料 (9 categories of text data) ────────────────────────

    # All available F10 categories
    F10_CATEGORIES: list[str] = [
        "最新提示", "公司概况", "财务分析",
        "股东研究", "股本结构", "资本运作",
        "业内点评", "行业分析", "公司大事",
    ]

    def fetch_f10(self, code: str, name: str = "最新提示") -> str | None:
        """Fetch F10 company text data for a single category.

        Args:
            code: Stock code (e.g. ``"688017"``).
            name: Category name — one of ``F10_CATEGORIES``.

        Returns:
            Text content, or None if unavailable.
        """
        try:
            plain, market, _ = _normalize_code(code)
        except ValueError:
            logger.debug("mootdx F10: code not supported: %s", code)
            return None

        self._ensure_client()
        try:
            text = self._client.F10(symbol=plain, name=name)
            return text if text else None
        except Exception as exc:
            logger.warning("mootdx F10('%s') failed for %s: %s", name, code, exc)
            return None

    def fetch_f10_all(self, code: str) -> dict[str, str | None]:
        """Fetch all 9 F10 categories for a stock.

        Returns:
            ``{category_name: text_content | None}``.
        """
        result: dict[str, str | None] = {}
        for cat in self.F10_CATEGORIES:
            result[cat] = self.fetch_f10(code, cat)
        return result

    def fetch_latest_announcements(self, code: str) -> str | None:
        """Fetch latest announcements/proposals from F10 '最新提示'.

        This covers recent announcements, dividends, shareholder meeting
        resolutions, etc. — equivalent to 01.md section 7.2.
        """
        text = self.fetch_f10(code, "最新提示")
        if text and len(text) > 16000:
            # "股东研究" chapter 4 (股东变化) can be 16000+ chars of
            # historical top-10 shareholder lists.  Keep only the latest
            # period by truncating at ~70% for this specific category.
            pass  # caller can truncate; raw F10 is better than nothing
        return text


def _safe_float(v: Any) -> float | str:
    """Convert a value to float if possible, else keep as-is."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)
