"""Twelve Data loader: global market data (paid, 800 free credits/day).

Twelve Data (https://twelvedata.com) provides:
  - Global stock OHLCV (US, HK, CN, EU, JP, etc.)
  - Forex, commodities, indices, crypto
  - Fundamentals: statistics, financial statements, profile, earnings
  - Real-time and delayed quotes

API key required: set TWELVE_DATA_API_KEY environment variable.
Free tier: 800 credits/day (~80-100 requests).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_TD_BASE = "https://api.twelvedata.com"
_TD_TIMEOUT = 15
_TD_MAX_RETRIES = 2
_TD_BACKOFF = 2.0


def _get_api_key() -> Optional[str]:
    return os.getenv("TWELVE_DATA_API_KEY") or os.getenv("TWELVEDATA_API_KEY")


def _td_request(endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Generic Twelve Data GET with retry."""
    api_key = _get_api_key()
    if not api_key:
        return None
    params["apikey"] = api_key
    for attempt in range(_TD_MAX_RETRIES):
        try:
            resp = requests.get(f"{_TD_BASE}{endpoint}", params=params, timeout=_TD_TIMEOUT)
            data = resp.json()
            if data.get("status") == "error":
                code = data.get("code", "")
                msg = str(data.get("message", ""))[:120]
                if code == 429 or "API credits" in msg or "minute limit" in msg:
                    logger.warning("TwelveData rate limit on %s: %s", endpoint, msg)
                else:
                    logger.debug("TwelveData error on %s: %s", endpoint, msg)
                return None
            return data
        except Exception as e:
            if attempt + 1 < _TD_MAX_RETRIES:
                time.sleep(_TD_BACKOFF)
                continue
            logger.warning("TwelveData %s request failed: %s", endpoint, e)
    return None


# ---------------------------------------------------------------------------
# Exchange / symbol mapping
# ---------------------------------------------------------------------------

_TD_EXCHANGE_MAP: Dict[str, str] = {
    "SH": "SHH",   # Shanghai
    "SZ": "SHZ",   # Shenzhen
    "HK": "HKG",   # Hong Kong
    "US": "NYSE",  # Default US (may need NASDAQ for some)
}


def _td_symbol(code: str) -> tuple[str, str]:
    """Convert internal symbol to (symbol, exchange) for Twelve Data.

    Returns:
        (symbol, exchange) tuple.
    """
    upper = code.upper().strip()
    if upper.endswith(".SH") or upper.endswith(".SS"):
        return upper.split(".")[0], "SHH"
    if upper.endswith(".SZ"):
        return upper.split(".")[0], "SHZ"
    if upper.endswith(".HK"):
        return upper.split(".")[0].zfill(4), "HKG"
    if upper.endswith(".US"):
        return upper[:-3], "NYSE"
    return upper, ""


@register
class DataLoader:
    """Twelve Data global OHLCV loader (requires API key)."""

    name = "twelvedata"
    markets = {"a_share", "us_equity", "hk_equity", "forex", "futures", "index", "commodity"}
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
        validate_date_range(start_date, end_date)

        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                symbol, exchange = _td_symbol(code)
                if not symbol:
                    logger.warning("Cannot map %s to Twelve Data symbol", code)
                    continue
                df = self._fetch_one(symbol, exchange, start_date, end_date, interval)
                if df is not None and not df.empty:
                    result[code] = df
            except Exception as exc:
                logger.warning("TwelveData failed for %s: %s", code, exc)
        return result

    def _fetch_one(
        self, symbol: str, exchange: str, start_date: str, end_date: str, interval: str,
    ) -> Optional[pd.DataFrame]:
        params = {
            "symbol": symbol,
            "exchange": exchange,
            "interval": interval.lower(),
            "start_date": start_date,
            "end_date": end_date,
            "outputsize": 5000,
        }
        data = _td_request("/time_series", params)
        if not data or "values" not in data:
            return None

        records = []
        for item in data["values"]:
            try:
                records.append({
                    "trade_date": pd.Timestamp(item["datetime"]),
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": float(item.get("volume", 0) or 0),
                })
            except (ValueError, KeyError, TypeError):
                continue

        if not records:
            return None

        df = pd.DataFrame(records)
        df = df.set_index("trade_date").sort_index()
        return df

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def fetch_statistics(self, code: str) -> Dict[str, Any]:
        """Fetch valuation statistics (PE, PB, PS, market cap, ROE, etc.)."""
        symbol, exchange = _td_symbol(code)
        if not symbol:
            return {}
        data = _td_request("/statistics", {"symbol": symbol, "exchange": exchange})
        if not data or "statistics" not in data:
            return {}

        stats = data["statistics"]
        result: Dict[str, Any] = {"source": "twelvedata"}

        vm = stats.get("valuations_metrics") or {}
        result["market_cap"] = _safe_float(vm.get("market_capitalization"))
        result["pe_ratio"] = _safe_float(vm.get("trailing_pe"))
        result["forward_pe"] = _safe_float(vm.get("forward_pe"))
        result["pb_ratio"] = _safe_float(vm.get("price_to_book_mrq"))
        result["ps_ratio"] = _safe_float(vm.get("price_to_sales_ttm"))
        result["peg"] = _safe_float(vm.get("peg_ratio"))

        fin = stats.get("financials") or {}
        result["roe"] = _safe_float(fin.get("return_on_equity_ttm"))
        result["roa"] = _safe_float(fin.get("return_on_assets_ttm"))
        result["profit_margin"] = _safe_float(fin.get("profit_margin"))
        result["eps"] = _safe_float(fin.get("diluted_eps_ttm"))
        result["revenue_ttm"] = _safe_float(fin.get("revenue_ttm"))

        fin_is = fin.get("income_statement") or {}
        result["revenue_growth"] = _safe_float(fin_is.get("quarterly_revenue_growth"))
        result["earnings_growth"] = _safe_float(fin_is.get("quarterly_earnings_growth_yoy"))

        fin_bs = fin.get("balance_sheet") or {}
        result["debt_to_equity"] = _safe_float(fin_bs.get("total_debt_to_equity_mrq"))
        result["current_ratio"] = _safe_float(fin_bs.get("current_ratio_mrq"))

        ss = stats.get("stock_statistics") or {}
        result["beta"] = _safe_float(ss.get("beta"))

        div = stats.get("dividends_and_splits") or {}
        result["dividend_yield"] = _safe_float(div.get("trailing_annual_dividend_yield"))

        return result

    def fetch_profile(self, code: str) -> Dict[str, Any]:
        """Fetch company profile."""
        symbol, exchange = _td_symbol(code)
        if not symbol:
            return {}
        data = _td_request("/profile", {"symbol": symbol, "exchange": exchange})
        if not data or not data.get("name"):
            return {}

        result: Dict[str, Any] = {"source": "twelvedata"}
        for field in ("name", "industry", "sector", "website", "description", "employees", "country"):
            v = data.get(field)
            if v is not None and str(v).strip():
                result[field] = str(v).strip() if isinstance(v, str) else v
        return result

    def fetch_financial_statements(self, code: str) -> Dict[str, Any]:
        """Fetch income statement, balance sheet, and cash flow."""
        symbol, exchange = _td_symbol(code)
        if not symbol:
            return {}
        result: Dict[str, Any] = {}

        for endpoint, key in [
            ("/income_statement", "income_statement"),
            ("/balance_sheet", "balance_sheet"),
            ("/cash_flow", "cash_flow"),
        ]:
            try:
                data = _td_request(endpoint, {"symbol": symbol, "exchange": exchange})
                items = (data or {}).get(key) or []
                if items:
                    result[key] = items[0]
            except Exception as e:
                logger.debug("TwelveData %s failed for %s: %s", endpoint, code, e)

        return result


def _safe_float(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        v = float(x)
        return None if (v != v or v == float("inf") or v == float("-inf")) else v
    except (TypeError, ValueError):
        return None
