"""TongHuaShun (同花顺) consensus EPS loader.

Direct HTTP connection to basic.10jqka.com.cn — no API key required.
Parses HTML table containing institutional consensus EPS forecasts.

Used for: forward PE calculation, PEG analysis, PE digestion estimates.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


def _normalize_code(symbol: str) -> str:
    """Return 6-digit plain code."""
    s = (symbol or "").strip().upper()
    for suffix in (".SH", ".SZ", ".BJ", ".SS"):
        if s.endswith(suffix):
            s = s[:-3]
            break
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix) and len(s) > 2:
            s = s[2:]
            break
    return s.strip()


def fetch_eps_forecast(symbol: str) -> pd.DataFrame:
    """Fetch institutional consensus EPS forecast from THS.

    Connects to ``https://basic.10jqka.com.cn/new/{code}/worth.html``
    and parses the HTML table containing EPS forecast data.

    Args:
        symbol: A-share symbol, e.g. ``"688017"``, ``"600519.SH"``.

    Returns:
        DataFrame with columns like: 年度, 预测机构数, 最小值, 均值, 最大值.
        The "均值" column = consensus EPS.

        Returns empty DataFrame if no institutional coverage exists.
    """
    code = _normalize_code(symbol)
    url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/117.0.0.0 Safari/537.36"
        ),
        "Referer": "https://basic.10jqka.com.cn/",
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.encoding = "gbk"
        dfs = pd.read_html(r.text)

        # Search for the table containing "每股收益" or "均值"
        for df in dfs:
            cols = [str(c) for c in df.columns]
            if any("每股收益" in c or "均值" in c for c in cols):
                return df

        # Fallback: return the first table (may be empty/unrelated)
        return dfs[0] if dfs else pd.DataFrame()

    except Exception as exc:
        logger.warning("THS EPS forecast failed for %s: %s", symbol, exc)
        return pd.DataFrame()


def parse_consensus_eps(df: pd.DataFrame) -> dict:
    """Parse the THS EPS forecast table into structured data.

    Args:
        df: DataFrame from ``fetch_eps_forecast()``.

    Returns:
        dict with keys: ``current_year_eps``, ``next_year_eps``,
        ``analyst_count``, ``eps_cagr``.
        Values are ``None`` when not available.
    """
    result: dict = {
        "current_year_eps": None,
        "next_year_eps": None,
        "analyst_count": 0,
        "eps_cagr": None,
    }

    if df.empty:
        return result

    try:
        # THS table structure: rows are years, columns include 预测机构数/最小值/均值/最大值
        rows = df.values
        if len(rows) >= 1:
            # Try to extract: first numeric row = current year, second = next year
            for i, row in enumerate(rows[:2]):
                eps_val = None
                analyst_val = 0
                for j, val in enumerate(row):
                    if val is None:
                        continue
                    try:
                        v = float(val)
                        # EPS values are typically small (0.01 ~ 50)
                        # analyst counts are integers (1 ~ 50)
                        if 0 < v < 100:
                            if v < 50 and abs(v - round(v)) < 0.001 and v > 1:
                                analyst_val = int(v)
                            elif v < 50:
                                eps_val = v
                    except (ValueError, TypeError):
                        continue

                if i == 0:
                    result["current_year_eps"] = eps_val
                    result["analyst_count"] = analyst_val
                elif i == 1:
                    result["next_year_eps"] = eps_val

        if result["current_year_eps"] and result["next_year_eps"]:
            result["eps_cagr"] = (result["next_year_eps"] / result["current_year_eps"]) - 1

    except Exception as exc:
        logger.debug("Failed to parse THS EPS table: %s", exc)

    return result
