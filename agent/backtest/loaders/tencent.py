"""Tencent Finance data loader: free, no-auth real-time quotes and K-lines for CN/HK stocks.

Endpoints:
  - Real-time quote: https://qt.gtimg.cn/q=<code>
  - K-line (adjusted): https://web.ifzq.gtimg.cn/appstock/app/fqkline/get

Tencent provides millisecond-level real-time data and is a stable alternative
when yfinance/Tushare/AKShare are rate-limited or unreachable.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={code}"
_TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

_INTERVAL_MAP: dict[str, str] = {
    "1D": "day",
    "1W": "week",
    "1M": "month",
}


def normalize_cn_code(symbol: str) -> str:
    """Normalize A-share symbol to Tencent code: sh600519 / sz000001."""
    s = (symbol or "").strip().upper()
    if not s:
        return s
    if s.endswith(".SH") or s.endswith(".SS"):
        digits = s[:-3]
        return ("SH" if digits.startswith("6") else "SZ") + digits
    if s.endswith(".SZ"):
        return "SZ" + s[:-3]
    if s.endswith(".BJ"):
        return "BJ" + s[:-3]
    if s.isdigit() and len(s) == 6:
        return ("SH" + s) if s.startswith(("6", "5", "9")) else ("SZ" + s)
    return s.lower()


def normalize_hk_code(symbol: str) -> str:
    """Normalize HK stock symbol to Tencent code: hk00700."""
    s = (symbol or "").strip().upper()
    if not s:
        return s
    if s.endswith(".HK"):
        s = s[:-3]
    if s.isdigit():
        return "HK" + s.zfill(5)
    if s.startswith("HK") and s[2:].isdigit():
        return "HK" + s[2:].zfill(5)
    return s.lower()


def _is_cn(code: str) -> bool:
    return code.upper().endswith((".SZ", ".SH", ".BJ"))


def _is_hk(code: str) -> bool:
    return code.upper().endswith(".HK")


def _parse_tencent_kline_time(raw: str) -> Optional[pd.Timestamp]:
    """Parse Tencent fqkline time string to pandas Timestamp."""
    raw = str(raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return pd.Timestamp(datetime.strptime(raw, fmt))
        except ValueError:
            continue
    try:
        ts = float(raw)
        if ts > 10**12:
            ts /= 1000
        return pd.Timestamp(datetime.fromtimestamp(ts))
    except (ValueError, TypeError, OSError):
        return None


@register
class DataLoader:
    """Tencent Finance OHLCV loader (free, no auth)."""

    name = "tencent"
    markets = {"a_share", "hk_equity"}
    requires_auth = False

    def is_available(self) -> bool:
        try:
            import requests  # noqa: F401
            return True
        except ImportError:
            return False

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
        period = _INTERVAL_MAP.get(interval, "day")
        adj = "qfq"  # 前复权

        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                if _is_cn(code):
                    tc = normalize_cn_code(code)
                    df = self._fetch_kline(tc, period, adj, count=2000)
                elif _is_hk(code):
                    tc = normalize_hk_code(code)
                    df = self._fetch_kline(tc, period, adj, count=2000)
                else:
                    logger.warning("Tencent does not support %s", code)
                    continue
                if df is not None and not df.empty:
                    df = df.loc[start_date:end_date]
                    if not df.empty:
                        result[code] = df
            except Exception as exc:
                logger.warning("Tencent failed for %s: %s", code, exc)
        return result

    def _fetch_kline(self, code: str, period: str, adj: str, count: int = 2000) -> Optional[pd.DataFrame]:
        """Fetch K-line data from Tencent fqkline endpoint."""
        params = {"param": f"{code},{period},,,{count},{adj}"}
        try:
            resp = self._session.get(
                _TENCENT_KLINE_URL,
                params=params,
                headers={"Referer": "https://gu.qq.com/"},
                timeout=15,
            )
            data = resp.json()
        except Exception as exc:
            logger.warning("Tencent kline request failed for %s: %s", code, exc)
            return None

        if not isinstance(data, dict) or int(data.get("code", 0)) != 0:
            return None

        root = (data.get("data") or {}).get(code)
        if not isinstance(root, dict):
            return None

        # Search for the data array: try adj+period, then period, then suffix match
        candidates = [f"{adj}{period}", period]
        rows = None
        for key in candidates:
            arr = root.get(key)
            if isinstance(arr, list) and arr:
                rows = arr
                break
        if rows is None:
            for k, v in root.items():
                if isinstance(v, list) and v and str(k).lower().endswith(period):
                    rows = v
                    break

        if not rows:
            return None

        return _rows_to_dataframe(rows)

    def fetch_quote(self, code: str) -> Optional[Dict[str, Any]]:
        """Fetch real-time quote for a single symbol.

        Returns a dict with: symbol, name, last, change, change_percent, high, low,
        open, previous_close, volume, amount, turnover, pe, market_cap.
        """
        if _is_cn(code):
            tc = normalize_cn_code(code)
        elif _is_hk(code):
            tc = normalize_hk_code(code)
        else:
            return None

        try:
            resp = self._session.get(
                _TENCENT_QUOTE_URL.format(code=tc),
                headers={"Referer": "https://qt.gtimg.cn/"},
                timeout=8,
            )
            resp.encoding = "gbk"
        except Exception as exc:
            logger.warning("Tencent quote request failed for %s: %s", code, exc)
            return None

        text = (resp.text or "").strip()
        if not text or "~" not in text:
            return None

        try:
            start = text.index('="') + 2
            end = text.rindex('"')
            payload = text[start:end]
        except ValueError:
            return None

        parts = payload.split("~")
        if len(parts) < 30:
            return None

        def _f(i: int, default: float = 0.0) -> float:
            try:
                v = parts[i]
                if v is None or v == "":
                    return default
                return float(v)
            except (ValueError, TypeError):
                return default

        last = _f(3)
        prev_close = _f(4)
        open_ = _f(5)
        volume = _f(6, 0.0)  # 成交量（手）
        high = _f(33, last)
        low = _f(34, last)
        amount = _f(37, 0.0)  # 成交额（万）
        turnover = _f(38, 0.0)  # 换手率
        pe = _f(39, 0.0)  # 市盈率
        market_cap = _f(45, 0.0)  # 总市值（亿）

        change = round(last - prev_close, 4) if prev_close else 0.0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0

        return {
            "symbol": parts[2].strip() if len(parts) > 2 else code,
            "name": parts[1].strip() if len(parts) > 1 else "",
            "last": last,
            "change": change,
            "change_percent": change_pct,
            "open": open_,
            "high": high,
            "low": low,
            "previous_close": prev_close,
            "volume": volume,
            "amount": amount,
            "turnover": turnover,
            "pe": pe,
            "market_cap": market_cap,
        }

    def fetch_quotes(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch real-time quotes for multiple symbols."""
        result: Dict[str, Dict[str, Any]] = {}
        for code in codes:
            try:
                quote = self.fetch_quote(code)
                if quote:
                    result[code] = quote
            except Exception as exc:
                logger.warning("Tencent quote failed for %s: %s", code, exc)
        return result


def _rows_to_dataframe(rows: List[Any]) -> pd.DataFrame:
    """Convert Tencent fqkline raw rows to OHLCV DataFrame."""
    records: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, (list, tuple)) or len(r) < 6:
            continue
        ts = _parse_tencent_kline_time(r[0])
        if ts is None:
            continue
        try:
            o, c, h, lo, vol = float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])
        except (TypeError, ValueError):
            continue
        records.append({
            "trade_date": ts,
            "open": round(o, 4),
            "high": round(h, 4),
            "low": round(lo, 4),
            "close": round(c, 4),
            "volume": round(vol, 2),
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.set_index("trade_date").sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
