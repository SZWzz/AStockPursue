"""EastMoney push2 fund flow — minute-level + 120-day daily fund flows.

Free HTTP API, no auth.  Provides categorized net flows:
  main_net (主力净流入), super_net (超大单), large_net (大单),
  mid_net (中单), small_net (小单).

Usage::

    from backtest.loaders.fund_flow import fund_flow_minute, fund_flow_daily

    minute_data = fund_flow_minute("600519")
    daily_data = fund_flow_daily("600519")
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/117.0.0.0 Safari/537.36"
)


def _build_secid(code: str) -> str:
    """Build EastMoney secid from a 6-digit code."""
    s = (code or "").strip()
    for suffix in (".SH", ".SZ", ".BJ"):
        if s.upper().endswith(suffix):
            s = s[:-3]
            break
    s = s.strip()
    market = "1" if s.startswith(("6", "9")) else "0"
    return f"{market}.{s}"


def fund_flow_minute(code: str) -> list[dict[str, Any]]:
    """Intraday minute-level fund flow (当日分钟级资金流).

    Returns:
        List of {time, main_net, small_net, mid_net, large_net, super_net}.
        Amounts in RMB yuan.
    """
    secid = _build_secid(code)
    url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {
        "secid": secid, "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=10)
        d = r.json()
    except Exception as exc:
        logger.warning("Fund flow minute fetch failed for %s: %s", code, exc)
        return []

    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({
                "time": parts[0],
                "main_net": float(parts[1]),    # 主力净流入
                "small_net": float(parts[2]),   # 小单净流入
                "mid_net": float(parts[3]),     # 中单净流入
                "large_net": float(parts[4]),   # 大单净流入
                "super_net": float(parts[5]),   # 超大单净流入
            })
    return rows


def fund_flow_daily(code: str, days: int = 120) -> list[dict[str, Any]]:
    """Daily fund flow for the last *days* trading days (日级资金流).

    Returns:
        List of {date, main_net, small_net, mid_net, large_net, super_net}.
        Amounts in RMB yuan.
    """
    secid = _build_secid(code)
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": str(min(days, 120)),
    }
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
        d = r.json()
    except Exception as exc:
        logger.warning("Fund flow daily fetch failed for %s: %s", code, exc)
        return []

    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 7:
            rows.append({
                "date": parts[0],
                "main_net": float(parts[1]) if parts[1] != "-" else 0,
                "small_net": float(parts[2]) if parts[2] != "-" else 0,
                "mid_net": float(parts[3]) if parts[3] != "-" else 0,
                "large_net": float(parts[4]) if parts[4] != "-" else 0,
                "super_net": float(parts[5]) if parts[5] != "-" else 0,
            })
    return rows


def fund_flow_summary(code: str, recent_days: int = 20) -> dict[str, Any]:
    """Summary of recent fund flow for *code*.

    Returns:
        {total_main_net, total_super_net, avg_main_net, bullish_days, bearish_days, signal}.
    """
    daily = fund_flow_daily(code, days=max(recent_days, 20))
    if not daily:
        return {"signal": "no_data"}

    recent = daily[-recent_days:]
    total_main = sum(d["main_net"] for d in recent)
    total_super = sum(d["super_net"] for d in recent)
    bullish = sum(1 for d in recent if d["main_net"] > 0)
    bearish = sum(1 for d in recent if d["main_net"] < 0)

    signal = "neutral"
    if bullish > bearish * 1.5 and total_main > 0:
        signal = "bullish"
    elif bearish > bullish * 1.5 and total_main < 0:
        signal = "bearish"

    return {
        "total_main_net": total_main,
        "total_super_net": total_super,
        "avg_main_net": total_main / recent_days,
        "bullish_days": bullish,
        "bearish_days": bearish,
        "signal": signal,
    }
