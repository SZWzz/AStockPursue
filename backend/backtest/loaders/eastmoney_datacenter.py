"""EastMoney datacenter unified API — 6 data types via one helper.

Covers: Dragon Tiger Board, Lockup Expiry, Margin Trading, Block Trades,
Holder Numbers, Dividend History — all free, no auth.

Usage::

    from backtest.loaders.eastmoney_datacenter import (
        eastmoney_datacenter, dragon_tiger_board, daily_dragon_tiger,
        lockup_expiry, margin_trading, block_trade, holder_num_change,
        dividend_history, industry_comparison,
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/117.0.0.0 Safari/537.36"
)


# ── Unified helper ────────────────────────────────────────────────────────────

def eastmoney_datacenter(
    report_name: str,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 50,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list[dict[str, Any]]:
    """EastMoney datacenter unified query.

    Args:
        report_name: RPT_* report identifier.
        columns: Comma-separated field names or "ALL".
        filter_str: Filter expression, e.g. ``'(SECURITY_CODE="600519")'``.
        page_size: Rows per page.
        sort_columns: Column name for sorting.
        sort_types: ``-1`` desc, ``1`` asc.

    Returns:
        List of row dicts.
    """
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    try:
        r = requests.get(DATACENTER_URL, params=params, headers={"User-Agent": UA}, timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
        return []
    except Exception as exc:
        logger.warning("EastMoney datacenter query failed: %s", exc)
        return []


# ── Dragon Tiger Board ────────────────────────────────────────────────────────

def dragon_tiger_board(code: str, trade_date: str, look_back: int = 30) -> dict:
    """Dragon Tiger Board (龙虎榜) for a single stock.

    Returns: {records, seats: {buy, sell}, institution: {buy_amt, sell_amt, net_amt}}.
    """
    start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back)
    start_str = start.strftime("%Y-%m-%d")

    # 1. Board records
    records = []
    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{code}\")",
        page_size=50,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    for row in data:
        records.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "reason": row.get("EXPLANATION", ""),
            "net_buy_wan": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
            "turnover": round(float(row.get("TURNOVERRATE") or 0), 2),
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
        })

    seats = {"buy": [], "sell": []}
    if records:
        latest_date = records[0]["date"]
        for side_key, report, sort_col in [
            ("buy", "RPT_BILLBOARD_DAILYDETAILSBUY", "BUY"),
            ("sell", "RPT_BILLBOARD_DAILYDETAILSSELL", "SELL"),
        ]:
            detail = eastmoney_datacenter(
                report,
                filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
                page_size=10,
                sort_columns=sort_col, sort_types="-1",
            )
            for row in detail[:5]:
                seats[side_key].append({
                    "name": row.get("OPERATEDEPT_NAME", ""),
                    "buy_amt": round((row.get("BUY") or 0) / 10000, 1),
                    "sell_amt": round((row.get("SELL") or 0) / 10000, 1),
                    "net": round((row.get("NET") or 0) / 10000, 1),
                })

    return {"records": records, "seats": seats}


def daily_dragon_tiger(trade_date: str = "", min_net_buy: float | None = None) -> dict:
    """All-market Dragon Tiger Board for *trade_date*."""
    if not trade_date:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT", sort_types="-1",
    )
    if not data:
        return {"date": trade_date, "total_records": 0, "stocks": []}

    stocks = []
    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if min_net_buy is not None and net_buy < min_net_buy:
            continue
        stocks.append({
            "code": row.get("SECURITY_CODE", ""),
            "name": row.get("SECURITY_NAME_ABBR", ""),
            "reason": row.get("EXPLANATION", ""),
            "net_buy_wan": round(net_buy, 1),
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    return {"date": trade_date, "total_records": len(stocks), "stocks": stocks}


# ── Lockup Expiry ─────────────────────────────────────────────────────────────

def lockup_expiry(code: str, trade_date: str, forward_days: int = 90) -> dict:
    """Lockup expiry (限售解禁) — historical + upcoming."""
    history = []
    h_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=15,
        sort_columns="FREE_DATE", sort_types="-1",
    )
    for row in h_data:
        history.append({
            "date": str(row.get("FREE_DATE", ""))[:10],
            "type": row.get("LIMITED_STOCK_TYPE", ""),
            "shares": row.get("FREE_SHARES_NUM", 0),
            "ratio": row.get("FREE_RATIO", 0),
        })

    end_date = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
    end_str = end_date.strftime("%Y-%m-%d")
    upcoming = []
    u_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f'(SECURITY_CODE="{code}")(FREE_DATE>=\"{trade_date}\")(FREE_DATE<=\"{end_str}\")',
        page_size=20,
        sort_columns="FREE_DATE", sort_types="1",
    )
    for row in u_data:
        upcoming.append({
            "date": str(row.get("FREE_DATE", ""))[:10],
            "type": row.get("LIMITED_STOCK_TYPE", ""),
            "shares": row.get("FREE_SHARES_NUM", 0),
            "ratio": row.get("FREE_RATIO", 0),
        })

    return {"history": history, "upcoming": upcoming}


# ── Margin Trading ────────────────────────────────────────────────────────────

def margin_trading(code: str, page_size: int = 30) -> list[dict]:
    """Margin trading details (融资融券), daily."""
    data = eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        filter_str=f'(SCODE="{code}")',
        page_size=page_size,
        sort_columns="DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("DATE", ""))[:10],
            "rzye": row.get("RZYE", 0),        # 融资余额(元)
            "rzmre": row.get("RZMRE", 0),       # 融资买入额
            "rzche": row.get("RZCHE", 0),       # 融资偿还额
            "rqye": row.get("RQYE", 0),         # 融券余额
            "rqmcl": row.get("RQMCL", 0),       # 融券卖出量
            "rzrqye": row.get("RZRQYE", 0),     # 融资融券余额合计
        })
    return rows


# ── Block Trade ───────────────────────────────────────────────────────────────

def block_trade(code: str, page_size: int = 20) -> list[dict]:
    """Block trade records (大宗交易)."""
    data = eastmoney_datacenter(
        "RPT_DATA_BLOCKTRADE",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        close = row.get("CLOSE_PRICE") or 0
        deal = row.get("DEAL_PRICE") or 0
        premium = ((deal / close - 1) * 100) if close else 0
        rows.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "price": deal,
            "close": close,
            "premium_pct": round(premium, 2),
            "vol": row.get("DEAL_VOLUME", 0),
            "amount": row.get("DEAL_AMT", 0),
            "buyer": row.get("BUYER_NAME", ""),
            "seller": row.get("SELLER_NAME", ""),
        })
    return rows


# ── Holder Numbers ────────────────────────────────────────────────────────────

def holder_num_change(code: str, page_size: int = 10) -> list[dict]:
    """Shareholder count change (股东户数变化, quarterly)."""
    data = eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="END_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("END_DATE", ""))[:10],
            "holder_num": row.get("HOLDER_NUM", 0),
            "change_ratio": row.get("HOLDER_NUM_RATIO", 0),   # 环比%
            "avg_shares": row.get("AVG_FREE_SHARES", 0),      # 户均持股
        })
    return rows


# ── Dividend History ──────────────────────────────────────────────────────────

def dividend_history(code: str, page_size: int = 20) -> list[dict]:
    """Dividend & bonus history (分红送转)."""
    data = eastmoney_datacenter(
        "RPT_SHAREBONUS_DET",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="EX_DIVIDEND_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
            "bonus_rmb": row.get("PRETAX_BONUS_RMB", 0),   # 每股派息(税前)
            "transfer_ratio": row.get("TRANSFER_RATIO", 0), # 每10股转增
            "bonus_ratio": row.get("BONUS_RATIO", 0),       # 每10股送股
            "plan": row.get("ASSIGN_PROGRESS", ""),          # 进度
        })
    return rows


# ── Industry Comparison ───────────────────────────────────────────────────────

def industry_comparison(top_n: int = 20) -> dict:
    """Industry ranking by daily change (行业板块排名)."""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141",
    }
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
        d = r.json()
        items = d.get("data", {}).get("diff", []) or []
        rows = []
        for i, item in enumerate(items):
            rows.append({
                "rank": i + 1,
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "code": item.get("f12", ""),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
            })
        return {"top": rows[:top_n], "bottom": rows[-top_n:], "total": len(rows)}
    except Exception as exc:
        logger.warning("Industry comparison failed: %s", exc)
        return {"top": [], "bottom": [], "total": 0}
