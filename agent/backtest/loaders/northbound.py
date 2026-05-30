"""North-bound capital flow (北向资金) — HSGT minute-level net flow.

Tracks Shanghai-HK Stock Connect + Shenzhen-HK Stock Connect real-time
cumulative net buy amounts.  Includes local CSV self-caching for history.

Free, no auth.  Data from data.hexin.cn.

Usage::

    from backtest.loaders.northbound import hsgt_realtime, northbound_history

    df_minute = hsgt_realtime()          # today's intraday minute flow
    df_hist = northbound_history(20)     # last 20 days cached history
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

HSGT_URL = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"

HSGT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Host": "data.hexin.cn",
    "Referer": "https://data.hexin.cn/",
}


def _cache_path() -> Path:
    """Local CSV cache path."""
    p = Path.home() / ".AStockPursue" / "cache" / "northbound_daily.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def hsgt_realtime() -> pd.DataFrame:
    """Fetch real-time HSGT minute-level flow for today.

    Returns:
        DataFrame with columns: time, hgt_yi (沪股通累计净买入), sgt_yi (深股通累计净买入).
        Values in RMB yi (亿元人民币).
    """
    try:
        r = requests.get(HSGT_URL, headers=HSGT_HEADERS, timeout=10)
        d = r.json()
    except Exception as exc:
        logger.warning("HSGT realtime fetch failed: %s", exc)
        return pd.DataFrame()

    times = d.get("time", [])
    hgt = d.get("hgt", [])
    sgt = d.get("sgt", [])

    n = len(times)
    df = pd.DataFrame({
        "time": times,
        "hgt_yi": hgt[:n] + [None] * (n - len(hgt)),
        "sgt_yi": sgt[:n] + [None] * (n - len(sgt)),
    })
    return df


def save_northbound_snapshot(date_str: str, hgt_val: float, sgt_val: float) -> None:
    """Save today's closing northbound data to local CSV cache.

    Call this after market close with the last valid values from ``hsgt_realtime()``.
    """
    path = _cache_path()
    rows: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().strip().split("\n")[1:]:
            parts = line.split(",")
            if len(parts) == 3:
                rows[parts[0]] = line
    rows[date_str] = f"{date_str},{hgt_val},{sgt_val}"

    with open(path, "w") as f:
        f.write("date,hgt,sgt\n")
        for d in sorted(rows.keys()):
            f.write(rows[d] + "\n")
    logger.debug("Northbound snapshot saved: %s HGT=%.1f SGT=%.1f", date_str, hgt_val, sgt_val)


def northbound_history(n_days: int = 20) -> pd.DataFrame:
    """Read the last *n_days* of cached northbound daily data."""
    path = _cache_path()
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        return df.tail(n_days)
    except Exception as exc:
        logger.warning("Northbound history read failed: %s", exc)
        return pd.DataFrame()


def northbound_summary() -> dict:
    """One-shot northbound summary: today's realtime + recent history trend.

    Returns:
        {today_hgt_cumulative, today_sgt_cumulative, recent_5d_hgt_sum, recent_5d_sgt_sum,
         trend: "inflow" | "outflow" | "neutral"}.
    """
    realtime = hsgt_realtime()
    today_hgt = today_sgt = 0.0
    if not realtime.empty:
        last = realtime.dropna()
        if not last.empty:
            today_hgt = last["hgt_yi"].iloc[-1]
            today_sgt = last["sgt_yi"].iloc[-1]
        # Auto-save
        from datetime import date
        try:
            save_northbound_snapshot(
                date.today().strftime("%Y-%m-%d"),
                float(today_hgt) if today_hgt else 0,
                float(today_sgt) if today_sgt else 0,
            )
        except Exception:
            pass

    history = northbound_history(5)
    recent_hgt = float(history["hgt"].sum()) if not history.empty else 0
    recent_sgt = float(history["sgt"].sum()) if not history.empty else 0

    total = (today_hgt or 0) + (today_sgt or 0) + recent_hgt + recent_sgt
    if total > 10:
        trend = "inflow"
    elif total < -10:
        trend = "outflow"
    else:
        trend = "neutral"

    return {
        "today_hgt_cumulative": today_hgt,
        "today_sgt_cumulative": today_sgt,
        "recent_5d_hgt_sum": recent_hgt,
        "recent_5d_sgt_sum": recent_sgt,
        "trend": trend,
    }
