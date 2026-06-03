"""EastMoney push2 K-line data loader.

Free HTTP API, no auth required.  Supports daily + minute-level K-lines
for A-shares via the same push2/push2his endpoints used by the EastMoney
web and mobile clients — the most stable free HTTP K-line source for CN.

Intervals: 1D / 1W / 1M / 1m / 5m / 15m / 30m / 60m
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import requests

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_BASE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

# EastMoney klt parameter mapping
_KLT_MAP: dict[str, int] = {
    "1D": 101,
    "1W": 102,
    "1M": 103,
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1H": 60,
}

# Max bars per request (EastMoney push2 limits vary by interval)
_MAX_COUNT = 300


def _build_secid(code: str) -> str:
    """Build EastMoney secid from a 6-digit code."""
    s = (code or "").strip().upper()
    for suffix in (".SH", ".SZ", ".BJ", ".SS"):
        if s.endswith(suffix):
            s = s[:-3]
            break
    s = s.strip()
    if s.startswith(("6", "9")):
        return f"1.{s}"
    return f"0.{s}"


def _parse_push2_response(data: dict) -> pd.DataFrame | None:
    """Parse EastMoney push2 kline JSON into OHLCV DataFrame."""
    klines = (data.get("data") or {}).get("klines") or []
    if not klines:
        return None

    rows = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 6:
            continue
        try:
            ts = datetime.strptime(parts[0], "%Y-%m-%d") if "-" in str(parts[0]) else datetime.fromtimestamp(int(parts[0]) / 1000)
        except (ValueError, TypeError, OSError):
            continue
        rows.append({
            "trade_date": ts,
            "open":     float(parts[1]),
            "close":    float(parts[2]),
            "high":     float(parts[3]),
            "low":      float(parts[4]),
            "volume":   float(parts[5]),
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.set_index("trade_date").sort_index()
    return df[["open", "high", "low", "close", "volume"]]


@register
class DataLoader:
    """EastMoney OHLCV loader (free HTTP, no auth)."""

    name = "eastmoney"
    markets = {"a_share"}
    requires_auth = False

    def is_available(self) -> bool:
        # [P2-06 fix] Check actual API reachability instead of just import.
        # Previously always returned True, breaking the fallback chain.
        try:
            import requests
            resp = requests.head(
                "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                timeout=2.0,
            )
            return True
        except Exception:
            return False

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/117.0.0.0 Safari/537.36"
            ),
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "*/*",
        })

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

        klt = _KLT_MAP.get(interval)
        if klt is None:
            raise ValueError(
                f"EastMoney does not support interval={interval!r}. "
                f"Supported: {list(_KLT_MAP.keys())}"
            )

        result: Dict[str, pd.DataFrame] = {}

        for code in codes:
            try:
                df = self._fetch_one_paginated(code, klt, start_date, end_date)
                if df is not None and not df.empty:
                    result[code] = df
            except Exception as exc:
                logger.warning("EastMoney fetch failed for %s: %s", code, exc)
                continue

        return result

    def _fetch_one_paginated(
        self,
        code: str,
        klt: int,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV bars for a single code with pagination.

        EastMoney's push2 API returns at most ``_MAX_COUNT`` bars per call.
        We paginate backwards by setting ``end`` to just before the earliest
        bar received in the previous chunk, repeating until we have enough
        data or the API returns fewer than ``_MAX_COUNT`` bars (end of history).

        Args:
            code: Stock code string (e.g. ``"000001.SZ"``).
            klt: EastMoney K-line type code (e.g. 101 for daily).
            start_date: ISO date string, oldest bar to include.
            end_date: ISO date string, newest bar to include.

        Returns:
            DataFrame indexed by ``trade_date`` with OHLCV columns,
            filtered to [*start_date*, *end_date*]; or ``None``.
        """
        secid = _build_secid(code)
        start_ts = pd.Timestamp(start_date)
        all_frames: list[pd.DataFrame] = []
        chunk_end = "20500101"  # far future = latest available
        max_chunks = 500  # safety cap: 500 × 300 = 150 000 bars (~600 years daily)

        for _ in range(max_chunks):
            params = {
                "secid": secid,
                "klt": str(klt),
                "fqt": "1",           # 前复权
                "lmt": str(_MAX_COUNT),
                "end": chunk_end,
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            }
            resp = self._session.get(_BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            df = _parse_push2_response(data)
            if df is None or df.empty:
                break

            all_frames.append(df)

            earliest = df.index.min()
            # Stop when we've gone past the requested start_date.
            if earliest <= start_ts:
                break

            # Stop when the server has no more data (returned fewer than limit).
            if len(df) < _MAX_COUNT:
                break

            # Next chunk: set end to one day before the earliest bar we just got.
            chunk_end = (earliest - pd.Timedelta(days=1)).strftime("%Y%m%d")

        if not all_frames:
            return None

        result = pd.concat(all_frames)
        result = result[~result.index.duplicated()]
        result = result.sort_index()

        # Filter to the requested window.
        result = result.loc[start_date:end_date]
        return result
