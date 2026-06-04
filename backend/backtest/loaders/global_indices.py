"""Global indices data loader via yfinance.

Covers 15+ major global stock indices. Free, no API key required.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

# Major global indices with yfinance tickers
GLOBAL_INDICES: Dict[str, Dict[str, str]] = {
    # US
    "SPX":   {"ticker": "^GSPC",   "name": "S&P 500",            "region": "US",     "currency": "USD"},
    "DJI":   {"ticker": "^DJI",    "name": "Dow Jones Industrial","region": "US",     "currency": "USD"},
    "IXIC":  {"ticker": "^IXIC",   "name": "NASDAQ Composite",    "region": "US",     "currency": "USD"},
    "NDX":   {"ticker": "^NDX",    "name": "NASDAQ 100",          "region": "US",     "currency": "USD"},
    "RUT":   {"ticker": "^RUT",    "name": "Russell 2000",        "region": "US",     "currency": "USD"},
    # Europe
    "DAX":   {"ticker": "^GDAXI",  "name": "DAX 40",              "region": "EU",     "currency": "EUR"},
    "FTSE":  {"ticker": "^FTSE",   "name": "FTSE 100",            "region": "EU",     "currency": "GBP"},
    "CAC":   {"ticker": "^FCHI",   "name": "CAC 40",              "region": "EU",     "currency": "EUR"},
    "STOXX": {"ticker": "^STOXX50E","name": "Euro STOXX 50",      "region": "EU",     "currency": "EUR"},
    # Asia
    "N225":  {"ticker": "^N225",   "name": "Nikkei 225",          "region": "Asia",   "currency": "JPY"},
    "HSI":   {"ticker": "^HSI",    "name": "Hang Seng Index",     "region": "Asia",   "currency": "HKD"},
    "KOSPI": {"ticker": "^KS11",   "name": "KOSPI",              "region": "Asia",   "currency": "KRW"},
    "ASX":   {"ticker": "^AXJO",   "name": "ASX 200",            "region": "Asia",   "currency": "AUD"},
    "SENSEX":{"ticker": "^BSESN",  "name": "BSE SENSEX",         "region": "Asia",   "currency": "INR"},
    # China (offshore-accessible)
    "CSI300":{"ticker": "510300.SS","name": "CSI 300 ETF",       "region": "China",  "currency": "CNY"},
    "SZ50":  {"ticker": "510050.SS","name": "SSE 50 ETF",        "region": "China",  "currency": "CNY"},
}


def get_index_info(code: str) -> Optional[Dict[str, str]]:
    return GLOBAL_INDICES.get(code.upper())


def list_indices(region: Optional[str] = None) -> List[Dict[str, str]]:
    """List available global indices, optionally filtered by region."""
    result = []
    for code, info in GLOBAL_INDICES.items():
        if region and info["region"] != region:
            continue
        result.append({"code": code, **info})
    return result


@register
class DataLoader:
    """Global indices OHLCV loader via yfinance (free, no auth)."""

    name = "global_indices"
    markets = {"index"}
    requires_auth = False

    def is_available(self) -> bool:
        try:
            import yfinance  # noqa: F401
            return True
        except ImportError:
            return False

    def __init__(self) -> None:
        pass

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

        import yfinance as yf

        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            info = get_index_info(code)
            if not info:
                logger.warning("Unknown index code: %s", code)
                continue
            try:
                ticker = yf.Ticker(info["ticker"])
                df = ticker.history(start=start_date, end=end_date, interval=interval)
                if df is not None and not df.empty:
                    df.index = pd.to_datetime(df.index).tz_localize(None)
                    df.index.name = "trade_date"
                    cols = ["Open", "High", "Low", "Close", "Volume"]
                    df = df[[c for c in cols if c in df.columns]]
                    df.columns = [c.lower() for c in df.columns]
                    result[code] = df
            except Exception as exc:
                logger.warning("Global index %s (%s) failed: %s", code, info["ticker"], exc)
        return result

    def fetch_latest(self, codes: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Fetch latest snapshot for specified indices (or all if None)."""
        import yfinance as yf

        if codes is None:
            codes = list(GLOBAL_INDICES.keys())

        result: Dict[str, Dict[str, Any]] = {}
        for code in codes:
            info = get_index_info(code)
            if not info:
                continue
            try:
                ticker = yf.Ticker(info["ticker"])
                hist = ticker.history(period="5d")
                if hist is not None and not hist.empty and len(hist) >= 2:
                    current = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2])
                    change_pct = round((current - prev) / prev * 100, 2) if prev else 0.0
                    result[code] = {
                        "code": code,
                        "name": info["name"],
                        "region": info["region"],
                        "currency": info["currency"],
                        "last": round(current, 2),
                        "change_percent": change_pct,
                    }
            except Exception as exc:
                logger.warning("Index snapshot %s failed: %s", code, exc)
        return result
