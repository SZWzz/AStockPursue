"""Commodities data loader via yfinance.

Covers major commodities: precious metals, energy, industrial metals, agriculture.
Free, no API key required.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

# Major commodities with yfinance tickers
COMMODITIES: Dict[str, Dict[str, str]] = {
    # Precious metals
    "XAUUSD": {"ticker": "GC=F",   "name": "Gold Futures",          "category": "precious_metal", "unit": "USD/oz"},
    "XAGUSD": {"ticker": "SI=F",   "name": "Silver Futures",        "category": "precious_metal", "unit": "USD/oz"},
    "XPTUSD": {"ticker": "PL=F",   "name": "Platinum Futures",      "category": "precious_metal", "unit": "USD/oz"},
    "XPDUSD": {"ticker": "PA=F",   "name": "Palladium Futures",     "category": "precious_metal", "unit": "USD/oz"},
    # Energy
    "CL":     {"ticker": "CL=F",   "name": "WTI Crude Oil",         "category": "energy",         "unit": "USD/bbl"},
    "BZ":     {"ticker": "BZ=F",   "name": "Brent Crude Oil",       "category": "energy",         "unit": "USD/bbl"},
    "NG":     {"ticker": "NG=F",   "name": "Natural Gas",           "category": "energy",         "unit": "USD/MMBtu"},
    "HO":     {"ticker": "HO=F",   "name": "Heating Oil",           "category": "energy",         "unit": "USD/gal"},
    "RB":     {"ticker": "RB=F",   "name": "RBOB Gasoline",         "category": "energy",         "unit": "USD/gal"},
    # Industrial metals
    "HG":     {"ticker": "HG=F",   "name": "Copper Futures",        "category": "industrial",     "unit": "USD/lb"},
    "ALI":    {"ticker": "ALI=F",  "name": "Aluminum Futures",      "category": "industrial",     "unit": "USD/MT"},
    "ZNC":    {"ticker": "ZNC=F",  "name": "Zinc Futures",          "category": "industrial",     "unit": "USD/MT"},
    "NI":     {"ticker": "NI=F",   "name": "Nickel Futures",        "category": "industrial",     "unit": "USD/MT"},
    # Agriculture
    "ZC":     {"ticker": "ZC=F",   "name": "Corn Futures",          "category": "agriculture",    "unit": "USC/bu"},
    "ZW":     {"ticker": "ZW=F",   "name": "Wheat Futures",         "category": "agriculture",    "unit": "USC/bu"},
    "ZS":     {"ticker": "ZS=F",   "name": "Soybean Futures",       "category": "agriculture",    "unit": "USC/bu"},
    "KC":     {"ticker": "KC=F",   "name": "Coffee Futures",        "category": "agriculture",    "unit": "USC/lb"},
    "CT":     {"ticker": "CT=F",   "name": "Cotton Futures",        "category": "agriculture",    "unit": "USC/lb"},
    "SB":     {"ticker": "SB=F",   "name": "Sugar Futures",         "category": "agriculture",    "unit": "USC/lb"},
}


def get_commodity_info(code: str) -> Optional[Dict[str, str]]:
    return COMMODITIES.get(code.upper())


def list_commodities(category: Optional[str] = None) -> List[Dict[str, str]]:
    """List available commodities, optionally filtered by category."""
    result = []
    for code, info in COMMODITIES.items():
        if category and info["category"] != category:
            continue
        result.append({"code": code, **info})
    return result


@register
class DataLoader:
    """Commodities OHLCV loader via yfinance (free, no auth)."""

    name = "commodities"
    markets = {"commodity"}
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
            info = get_commodity_info(code)
            if not info:
                logger.warning("Unknown commodity code: %s", code)
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
                logger.warning("Commodity %s (%s) failed: %s", code, info["ticker"], exc)
        return result

    def fetch_latest(self, codes: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Fetch latest snapshot for specified commodities (or all if None)."""
        import yfinance as yf

        if codes is None:
            codes = list(COMMODITIES.keys())

        result: Dict[str, Dict[str, Any]] = {}
        for code in codes:
            info = get_commodity_info(code)
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
                        "category": info["category"],
                        "unit": info["unit"],
                        "last": round(current, 4),
                        "change_percent": change_pct,
                    }
            except Exception as exc:
                logger.warning("Commodity snapshot %s failed: %s", code, exc)
        return result
