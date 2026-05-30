"""Stock symbol search / autocomplete API avec minute-line data."""

from __future__ import annotations

import json
import logging
from datetime import date as date_type
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from src.auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stock", tags=["stock"])

_SYMBOLS_CACHE: list[dict] | None = None


def _load_symbols() -> list[dict]:
    global _SYMBOLS_CACHE
    if _SYMBOLS_CACHE is not None:
        return _SYMBOLS_CACHE
    data_path = Path(__file__).parent.parent / "data" / "stock_symbols.json"
    try:
        _SYMBOLS_CACHE = json.loads(data_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load stock symbols")
        _SYMBOLS_CACHE = []
    return _SYMBOLS_CACHE


# A-share code prefix → exchange suffix
#  https://www.sse.com.cn/ (Shanghai) / https://www.szse.cn/ (Shenzhen)
_CN_PREFIX_EXCHANGE: dict[tuple[str, ...], str] = {
    ("000", "001", "002", "003", "300", "301"): ".SZ",
    ("600", "601", "603", "605", "688"): ".SH",
    ("430", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839",
     "870", "871", "872", "873", "920"): ".BJ",
}


def _cn_exchange_candidates(code: str) -> list[str]:
    """Return the most likely exchange-qualified code(s) for a numeric A-share code."""
    if len(code) != 6:
        # Unrecognised length — try both major exchanges
        return [f"{code}.SZ", f"{code}.SH"]
    prefix = code[:3]
    for prefixes, suffix in _CN_PREFIX_EXCHANGE.items():
        if prefix in prefixes:
            return [f"{code}{suffix}"]
    # Prefix not in known map — try both
    return [f"{code}.SZ", f"{code}.SH"]


@router.get("/search")
async def search_stocks(q: str = Query("", max_length=64)):
    """Search stock symbols by code, name, or pinyin. Returns up to 20 matches.
    Static JSON covers CN indices + major A-shares. Falls back to yfinance
    for US/HK stocks not in the static list."""
    symbols = _load_symbols()
    query = q.strip().lower()
    if not query:
        return {"results": symbols[:20]}

    results: list[dict] = []
    seen = set()
    for s in symbols:
        code_lower = s["code"].lower()
        if code_lower in seen:
            continue
        if (
            query in code_lower
            or query in s["name"].lower()
            or query in s.get("pinyin", "")
        ):
            results.append(s)
            seen.add(code_lower)
            if len(results) >= 20:
                break

    # For queries not found in static JSON, try Tencent quote API (CN/HK stocks)
    if len(results) < 10 and len(query) >= 1:
        q = query.strip().upper()
        candidates = []
        if "." in q or "-" in q:
            candidates = [q]
        elif q.isalpha() and len(q) <= 5:
            candidates = [q, f"{q}.HK"]
        elif q.isdigit():
            # Determine exchange by A-share code prefix to avoid duplicate results
            candidates = _cn_exchange_candidates(q) + [f"{q}.HK"]
        for code in candidates[:5]:
            try:
                from backtest.loaders.tencent import normalize_cn_code, normalize_hk_code, _is_cn, _is_hk
                tc = ""
                if _is_cn(code):
                    tc = normalize_cn_code(code)
                elif _is_hk(code):
                    tc = normalize_hk_code(code)
                else:
                    continue
                resp = __import__("requests").get(f"https://qt.gtimg.cn/q={tc}", timeout=5, headers={"Referer": "https://qt.gtimg.cn/"})
                resp.encoding = "gbk"
                text = (resp.text or "").strip()
                if "~" in text and "v_" in text:
                    try:
                        s = text.index('="') + 2
                        e = text.rindex('"')
                        parts = text[s:e].split("~")
                        name = parts[1].strip() if len(parts) > 1 else code
                        if name and code.lower() not in seen:
                            market = "HK" if _is_hk(code) else "CN"
                            results.append({"code": code, "name": name, "market": market, "type": "", "pinyin": query.lower()})
                            seen.add(code.lower())
                    except (ValueError, IndexError):
                        pass
            except Exception:
                continue

    # Final fallback: anything not yet matched
    if len(results) == 0 and len(query) >= 1:
        q = query.strip().upper()
        clean = q.replace(".US", "").replace(".HK", "").replace(".SZ", "").replace(".SH", "")
        if "-" in q:
            results.append({"code": q, "name": q, "market": "CRYPTO", "type": "", "pinyin": query.lower()})
        elif q.endswith(".US") or (clean.isascii() and clean.isalpha() and len(clean) <= 5):
            results.append({"code": q if q.endswith(".US") else q, "name": q, "market": "US", "type": "", "pinyin": query.lower()})
        elif q.endswith(".HK") or (clean.isdigit() and len(clean) <= 5):
            results.append({"code": q, "name": q, "market": "HK", "type": "", "pinyin": query.lower()})

    return {"results": results[:20]}


@router.get("/ohlcv")
async def get_ohlcv(
    symbol: str = Query(..., description="Symbol e.g. 600519.SH, AAPL.US, BTC-USDT"),
    start_date: str = Query("2024-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query("2025-12-31", description="End date YYYY-MM-DD"),
    source: str = Query("auto", description="Data source: auto, tushare, yfinance, okx, akshare, etc."),
    interval: str = Query("1D", description="Bar interval: 1D, 1H, 4H, etc."),
    user: dict = Depends(require_auth),
):
    """Fetch OHLCV price bars for a symbol."""
    user_id = user["user_id"]
    try:
        from src.auth.user_config import load_user_config
        load_user_config(user_id)
    except Exception:
        pass

    try:
        from src.lab.backtest_bridge import fetch_ohlcv

        data_map = fetch_ohlcv(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            source=source,
            interval=interval,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data fetch failed: {e}")

    if not data_map or symbol not in data_map or data_map[symbol].empty:
        return {"symbol": symbol, "bars": [], "source": source}

    import pandas as pd
    df: pd.DataFrame = data_map[symbol]
    bars = [
        {
            "time": str(idx),
            "open": round(float(row["open"]), 4),
            "high": round(float(row["high"]), 4),
            "low": round(float(row["low"]), 4),
            "close": round(float(row["close"]), 4),
            "volume": int(row["volume"]),
        }
        for idx, row in df.iterrows()
    ]
    return {"symbol": symbol, "bars": bars, "source": source}


@router.get("/minute-line")
async def get_minute_line(
    symbol: str = Query(..., description="A-share symbol e.g. 600519.SH"),
    date: str = Query("", description="Trading date YYYY-MM-DD, defaults to today"),
    user: dict = Depends(require_auth),
):
    """Fetch 分时图 minute-line data for an A-share stock on a single trading day.

    Returns per-minute price, volume, and amount. Non-trading days return
    ``available: false``.
    """
    user_id = user["user_id"]
    try:
        from src.auth.user_config import load_user_config
        load_user_config(user_id)
    except Exception:
        pass

    # Resolve date
    if not date:
        date = pd.Timestamp.now().strftime("%Y-%m-%d")

    # Validate symbol is A-share
    upper = symbol.strip().upper()
    if not (upper.endswith(".SH") or upper.endswith(".SZ") or upper.endswith(".BJ")):
        return {
            "symbol": upper,
            "date": date,
            "available": False,
            "reason": "分时图目前仅支持 A 股（.SH / .SZ / .BJ）",
            "minutes": [],
        }

    # Check if date is a weekend
    ts = pd.Timestamp(date)
    if ts.dayofweek >= 5:
        return {
            "symbol": upper,
            "date": date,
            "available": False,
            "reason": "周末休市",
            "minutes": [],
        }

    try:
        from backtest.loaders.mootdx_loader import DataLoader

        loader = DataLoader()
        if not loader.is_available():
            return {
                "symbol": upper,
                "date": date,
                "available": False,
                "reason": "MooTDX 数据源不可用（请安装 mootdx 包）",
                "minutes": [],
            }

        df = loader.fetch_minute_line(upper, date)
    except Exception as e:
        logger.warning("minute-line fetch failed for %s on %s: %s", upper, date, e)
        raise HTTPException(status_code=500, detail=f"分时数据获取失败: {e}")

    if df is None or df.empty:
        return {
            "symbol": upper,
            "date": date,
            "available": False,
            "reason": "非交易日或无分时数据（TDX 仅保留最近 5-10 个交易日）",
            "minutes": [],
        }

    # Compute pre-close from first price (or try to get from OHLCV)
    pre_close = None
    try:
        pre_close = round(float(df["price"].iloc[0]), 2)
    except Exception:
        pass

    minutes = []
    for idx, row in df.iterrows():
        minutes.append({
            "time": str(idx).split(" ")[-1][:5] if " " in str(idx) else str(idx)[:5],
            "price": round(float(row["price"]), 2),
            "volume": int(row.get("volume", 0)),
            "amount": round(float(row.get("amount", 0)), 2),
        })

    return {
        "symbol": upper,
        "date": date,
        "available": True,
        "preClose": pre_close,
        "minutes": minutes,
    }
