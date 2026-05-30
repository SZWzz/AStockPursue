"""TongHuaShun (同花顺) hot stocks + theme attribution.

Unique capability: not just "which stocks are strong today", but WHY —
curated theme tags from THS editorial team (e.g. "算力租赁+Token工厂+AI政务").

Free, no auth, ~73ms response for ~125 stocks.

Usage::

    from backtest.loaders.ths_hot import ths_hot_reason, theme_trend

    df = ths_hot_reason("2026-05-30")
    trends = theme_trend(df)
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "Chrome/117.0.0.0 Safari/537.36"
)


def ths_hot_reason(trade_date: str | None = None) -> pd.DataFrame:
    """TongHuaShun daily hot stocks with theme attribution.

    Args:
        trade_date: ``"YYYY-MM-DD"``, defaults to today.

    Returns:
        DataFrame with columns: 代码, 名称, 涨幅%, 题材归因, 换手率%, 成交额, 大单净量.
        ``题材归因`` is the key field — human-curated theme tags.
    """
    if trade_date is None:
        trade_date = date.today().strftime("%Y-%m-%d")

    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{trade_date}/orderby/date/orderway/desc/charset/GBK/"
    )
    headers = {"User-Agent": UA}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if data.get("errocode", 0) != 0:
            raise RuntimeError(f"THS hot error: {data.get('errormsg', '')}")
    except Exception as exc:
        logger.warning("THS hot reason fetch failed: %s", exc)
        return pd.DataFrame()

    rows = data.get("data") or []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    rename_map = {
        "code": "代码",
        "name": "名称",
        "reason": "题材归因",
        "close": "收盘价",
        "zhangfu": "涨幅%",
        "huanshou": "换手率%",
        "chengjiaoe": "成交额",
        "ddejingliang": "大单净量",
        "market": "市场",
    }
    existing = {k: v for k, v in rename_map.items() if k in df.columns}
    return df.rename(columns=existing)


def theme_trend(df: pd.DataFrame | None = None, trade_date: str | None = None) -> list[dict[str, Any]]:
    """Extract theme keyword trends from hot stock data.

    Parses the ``题材归因`` column (e.g. "算力租赁+Token工厂+AI政务"),
    counts keyword frequency, and returns a ranked list.

    Args:
        df: DataFrame from ``ths_hot_reason()``. If None, fetches fresh data.
        trade_date: Date to fetch if df is None.

    Returns:
        List of {theme, count, stocks} sorted by count desc.
    """
    if df is None:
        df = ths_hot_reason(trade_date)

    reason_col = "题材归因" if "题材归因" in df.columns else "reason"
    name_col = "名称" if "名称" in df.columns else "name"
    code_col = "代码" if "代码" in df.columns else "code"

    if reason_col not in df.columns:
        return []

    # Collect theme → stock list
    theme_stocks: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        reason = str(row.get(reason_col, ""))
        if not reason:
            continue
        stock_label = f"{row.get(name_col, '')}({row.get(code_col, '')})"
        tags = [t.strip() for t in reason.replace("，", ",").replace("+", ",").split(",") if t.strip()]
        for tag in tags:
            theme_stocks.setdefault(tag, []).append(stock_label)

    # Sort by count
    sorted_themes = sorted(theme_stocks.items(), key=lambda x: len(x[1]), reverse=True)
    return [{"theme": theme, "count": len(stocks), "stocks": stocks[:5]} for theme, stocks in sorted_themes]


def hot_stocks_by_theme(df: pd.DataFrame, theme_keyword: str) -> pd.DataFrame:
    """Filter hot stocks by theme keyword.

    Args:
        df: From ``ths_hot_reason()``.
        theme_keyword: e.g. ``"算力"``, ``"AI"``, ``"机器人"``.

    Returns:
        Filtered DataFrame.
    """
    reason_col = "题材归因" if "题材归因" in df.columns else "reason"
    if reason_col not in df.columns:
        return pd.DataFrame()
    mask = df[reason_col].astype(str).str.contains(theme_keyword, na=False)
    return df[mask].reset_index(drop=True)
