"""Finnhub data loader: US stock real-time quotes and fundamentals.

Finnhub (https://finnhub.io) provides:
  - Real-time US stock quotes
  - Company fundamentals (PE, PB, market cap, etc.)
  - News and SEC filings
  - Earnings calendar

Free tier: 60 API calls/minute. API key required — set FINNHUB_API_KEY env var.
Register at https://finnhub.io/register
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_FINNHUB_BASE = "https://finnhub.io/api/v1"


def _get_api_key() -> Optional[str]:
    return os.getenv("FINNHUB_API_KEY") or os.getenv("FINNHUB_KEY")


def _finnhub_request(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Generic Finnhub API request."""
    api_key = _get_api_key()
    if not api_key:
        return None
    url = f"{_FINNHUB_BASE}{endpoint}"
    p = dict(params or {})
    p["token"] = api_key
    try:
        resp = requests.get(url, params=p, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            logger.warning("Finnhub API error on %s: %s", endpoint, data.get("error"))
            return None
        return data
    except Exception as e:
        logger.warning("Finnhub request failed for %s: %s", endpoint, e)
        return None


@register
class DataLoader:
    """Finnhub US stock data loader (requires API key)."""

    name = "finnhub"
    markets = {"us_equity"}
    requires_auth = True

    def is_available(self) -> bool:
        return bool(_get_api_key())

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
        """Finnhub OHLCV via /stock/candle endpoint.

        Note: Finnhub candle only returns up to 1 year of daily data on free tier.
        For longer history, use yfinance or twelvedata.
        """
        validate_date_range(start_date, end_date)

        start_ts = int(pd.Timestamp(start_date).timestamp())
        end_ts = int(pd.Timestamp(end_date).timestamp())

        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            symbol = code.replace(".US", "").upper()
            try:
                data = _finnhub_request("/stock/candle", {
                    "symbol": symbol,
                    "resolution": interval.upper().replace("1D", "D").replace("1W", "W").replace("1M", "M"),
                    "from": start_ts,
                    "to": end_ts,
                })
                if data and data.get("s") == "ok":
                    t = data.get("t", [])
                    if not t:
                        continue
                    df = pd.DataFrame({
                        "trade_date": pd.to_datetime(t, unit="s"),
                        "open": data.get("o", []),
                        "high": data.get("h", []),
                        "low": data.get("l", []),
                        "close": data.get("c", []),
                        "volume": data.get("v", []),
                    })
                    df = df.set_index("trade_date").sort_index()
                    result[code] = df
            except Exception as exc:
                logger.warning("Finnhub failed for %s: %s", code, exc)
        return result

    # ------------------------------------------------------------------
    # Real-time quote
    # ------------------------------------------------------------------

    def fetch_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch real-time US stock quote."""
        sym = symbol.replace(".US", "").upper()
        data = _finnhub_request("/quote", {"symbol": sym})
        if not data:
            return None
        return {
            "symbol": sym,
            "current": data.get("c"),
            "change": data.get("d"),
            "change_percent": data.get("dp"),
            "high": data.get("h"),
            "low": data.get("l"),
            "open": data.get("o"),
            "previous_close": data.get("pc"),
        }

    # ------------------------------------------------------------------
    # Company profile & fundamentals
    # ------------------------------------------------------------------

    def fetch_profile(self, symbol: str) -> Dict[str, Any]:
        """Fetch company profile."""
        sym = symbol.replace(".US", "").upper()
        data = _finnhub_request("/stock/profile2", {"symbol": sym})
        if not data:
            return {}
        return {
            "name": data.get("name"),
            "country": data.get("country"),
            "currency": data.get("currency"),
            "exchange": data.get("exchange"),
            "industry": data.get("finnhubIndustry"),
            "market_cap": data.get("marketCapitalization"),
            "ipo": data.get("ipo"),
            "logo": data.get("logo"),
            "weburl": data.get("weburl"),
        }

    def fetch_basic_financials(self, symbol: str) -> Dict[str, Any]:
        """Fetch key financial metrics."""
        sym = symbol.replace(".US", "").upper()
        data = _finnhub_request("/stock/metric", {"symbol": sym, "metric": "all"})
        if not data or "metric" not in data:
            return {}
        m = data["metric"]
        return {
            "pe_ratio": m.get("peBasicExclExtraTTM") or m.get("peTTM"),
            "pb_ratio": m.get("pbAnnual") or m.get("pbQuarterly"),
            "ps_ratio": m.get("psTTM"),
            "eps": m.get("epsBasicExclExtraItemsTTM"),
            "roe": m.get("roeTTM"),
            "roa": m.get("roaTTM"),
            "profit_margin": m.get("netProfitMarginTTM"),
            "debt_to_equity": m.get("totalDebt/totalEquityAnnual"),
            "current_ratio": m.get("currentRatioAnnual"),
            "dividend_yield": m.get("dividendYieldIndicatedAnnual"),
            "beta": m.get("beta"),
            "52_week_high": m.get("52WeekHigh"),
            "52_week_low": m.get("52WeekLow"),
            "revenue_growth": m.get("revenueGrowthTTMYoy"),
            "earnings_growth": m.get("epsGrowthTTMYoy"),
        }
