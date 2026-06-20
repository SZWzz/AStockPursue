"""Stock symbol search / autocomplete API avec minute-line data.

TODO(P5-task8): The data-fetching paths in this module (OHLCV via
backtest_bridge, minute-line/F10/finance via mootdx, Sina finance reports)
use direct loader imports rather than the shared gRPC DataService client.
- The OHLCV endpoint already uses ``src.lab.backtest_bridge.fetch_ohlcv``
  which is the preferred path for bar data.
- Minute-line, F10, and finance data are mootdx-specific features not yet
  exposed by the DataService gRPC — leave as-is until those features are
  added to the DataService proto.
- The tencent quote helpers (_is_cn, _is_hk, normalize_cn_code) are used
  for real-time quotes and code normalization; these are orthogonal to
  historical bar fetching.
"""

from __future__ import annotations

import json
import logging
from datetime import date as date_type
from pathlib import Path

import pandas as pd
import requests
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
                resp = requests.get(f"https://qt.gtimg.cn/q={tc}", timeout=5, headers={"Referer": "https://qt.gtimg.cn/"})
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
    refresh: bool = Query(False, description="Bypass cache and force re-fetch"),
    user: dict = Depends(require_auth),
):
    """Fetch OHLCV price bars for a symbol.  Uses PostgreSQL cache for 1D bars."""
    user_id = user["user_id"]
    try:
        from src.auth.user_config import load_user_config
        load_user_config(user_id)
    except Exception as _e:
        logger.debug("Failed to load user config for OHLCV: %s", _e)
        pass

    # ── Try cache first (1D only) ──────────────────────────────────────────
    cached_source = ""
    if not refresh and interval == "1D" and source in ("auto", "mootdx", "tushare", ""):
        try:
            from backtest.loaders.cache import query_cache, write_cache
            df = query_cache(symbol, interval, start_date, end_date)
            if df is not None and not df.empty:
                cached_source = "cache"
        except Exception:
            df = None
    else:
        df = None

    # ── Fetch from source (with cache backfill) ────────────────────────────
    if df is None or df.empty:
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
        df = data_map[symbol]

        # Write to cache for future requests
        if interval == "1D" and not refresh:
            try:
                write_cache(symbol, interval, df)
            except Exception as _e:
                logger.debug("Failed to write OHLCV cache for %s: %s", symbol, _e)
                pass

    if df.empty:
        return {"symbol": symbol, "bars": [], "source": cached_source or source}

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
    return {"symbol": symbol, "bars": bars, "source": cached_source or source}


@router.get("/minute-line")
async def get_minute_line(
    symbol: str = Query(..., description="A-share symbol e.g. 600519.SH"),
    date: str = Query("", description="Trading date YYYY-MM-DD, defaults to today"),
    refresh: bool = Query(False, description="Bypass cache and force re-fetch from TDX"),
    user: dict = Depends(require_auth),
):
    """Fetch 分时图 minute-line data for an A-share stock on a single trading day.

    Returns per-minute price, volume, and amount.  When *date* falls on a
    weekend or holiday the endpoint automatically walks backwards to find the
    most recent trading day and returns ``adjustedDate`` in the response so the
    frontend can update its picker.

    Uses PostgreSQL cache (minute_line_cache) to avoid repeated TDX fetches.
    """
    user_id = user["user_id"]
    try:
        from src.auth.user_config import load_user_config
        load_user_config(user_id)
    except Exception as _e:
        logger.debug("Failed to load user config for minute-line: %s", _e)
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

    # ── Try cache first ────────────────────────────────────────────────────
    from backtest.loaders.cache import query_minute_cache, write_minute_cache, query_preclose_cache
    from backtest.loaders.mootdx_loader import DataLoader

    original_date = date
    df = None
    pre_close = None

    if not refresh:
        # Check cache for each candidate date (walking back over weekends)
        for _ in range(14):
            ts = pd.Timestamp(date)
            if ts.dayofweek >= 5:
                date = (ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                continue
            df = query_minute_cache(upper, date)
            if df is not None and not df.empty:
                break
            date = (ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        if df is not None:
            pre_close = query_preclose_cache(upper, date)

    # ── Cache miss — fetch from TDX ────────────────────────────────────────
    if df is None or df.empty:
        loader = DataLoader()
        if not loader.is_available():
            return {
                "symbol": upper,
                "date": original_date,
                "available": False,
                "reason": "MooTDX 数据源不可用（请安装 mootdx 包）",
                "minutes": [],
            }

        # Reset date walk
        date = original_date
        df = None
        for _ in range(14):
            ts = pd.Timestamp(date)
            if ts.dayofweek >= 5:
                date = (ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                continue
            try:
                df = loader.fetch_minute_line(upper, date)
            except Exception as e:
                logger.warning("minute-line fetch failed for %s on %s: %s", upper, date, e)
                raise HTTPException(status_code=500, detail=f"分时数据获取失败: {e}")
            if df is not None and not df.empty:
                break
            date = (ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        if df is None or df.empty:
            return {
                "symbol": upper,
                "date": original_date,
                "available": False,
                "reason": "非交易日或无分时数据（TDX 仅保留最近 5-10 个交易日）",
                "minutes": [],
            }

        # Write to cache
        try:
            write_minute_cache(upper, date, df)
        except Exception as _e:
            logger.debug("Failed to write minute-line cache for %s: %s", upper, _e)
            pass

        # Compute preClose (ohlcv_cache first, then TDX, then fallback)
        if pre_close is None:
            pre_close = query_preclose_cache(upper, date)
        if pre_close is None:
            try:
                prev = pd.Timestamp(date) - pd.Timedelta(days=1)
                for _ in range(10):
                    if prev.dayofweek < 5:
                        ohlcv = loader.fetch([upper], prev.strftime("%Y-%m-%d"), prev.strftime("%Y-%m-%d"), interval="1D")
                        if upper in ohlcv and ohlcv[upper] is not None and not ohlcv[upper].empty:
                            pre_close = round(float(ohlcv[upper]["close"].iloc[-1]), 2)
                            break
                    prev = prev - pd.Timedelta(days=1)
            except Exception as _e:
                logger.debug("Failed to fetch preClose from TDX for %s: %s", upper, _e)
                pass

    # Fallback preClose
    if pre_close is None:
        try:
            pre_close = round(float(df["price"].iloc[0]), 2)
        except Exception as _e:
            logger.debug("Failed to derive preClose from first bar for %s: %s", upper, _e)
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
        "date": original_date,
        "adjustedDate": date if date != original_date else None,
        "available": True,
        "preClose": pre_close,
        "minutes": minutes,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Fundamental Data Endpoints (mootdx finance, F10, Sina reports, valuation)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/finance/{code}")
async def get_stock_finance(code: str):
    """37-field quarterly financial snapshot via mootdx.

    Returns: eps, bvps, roe, profit, income, total_shares, float_shares, etc.
    """
    from backtest.loaders.mootdx_loader import DataLoader

    loader = DataLoader()
    if not loader.is_available():
        raise HTTPException(status_code=503, detail="mootdx 数据源不可用")

    result = loader.fetch_finance(code)
    if result is None:
        return {"symbol": code.upper(), "available": False, "fields": {}}

    return {"symbol": code.upper(), "available": True, "fields": result, "field_count": len(result)}


@router.get("/f10/{code}")
async def get_stock_f10(code: str, name: str = Query("最新提示", description="F10 category name")):
    """Single F10 company text category.

    Categories: 最新提示, 公司概况, 财务分析, 股东研究, 股本结构, 资本运作, 业内点评, 行业分析, 公司大事
    """
    from backtest.loaders.mootdx_loader import DataLoader

    loader = DataLoader()
    if not loader.is_available():
        raise HTTPException(status_code=503, detail="mootdx 数据源不可用")

    valid = loader.F10_CATEGORIES
    if name not in valid:
        raise HTTPException(status_code=400, detail=f"无效的 F10 类别: {name}. 有效值: {valid}")

    text = loader.fetch_f10(code, name)
    if text is None:
        return {"symbol": code.upper(), "name": name, "available": False, "text": None}

    return {"symbol": code.upper(), "name": name, "available": True, "text": text}


@router.get("/f10/{code}/all")
async def get_stock_f10_all(code: str):
    """All 9 F10 categories for a stock."""
    from backtest.loaders.mootdx_loader import DataLoader

    loader = DataLoader()
    if not loader.is_available():
        raise HTTPException(status_code=503, detail="mootdx 数据源不可用")

    result = loader.fetch_f10_all(code)
    return {
        "symbol": code.upper(),
        "categories": {k: v for k, v in result.items()},
        "available_count": sum(1 for v in result.values() if v),
    }


@router.get("/financials/{code}")
async def get_stock_financials(code: str):
    """Sina finance 3-statement reports (利润表, 资产负债表, 现金流量表).

    Returns up to 20 periods of each statement.
    """
    from backtest.loaders.sina_finance import SinaFinanceLoader

    loader = SinaFinanceLoader()
    try:
        result = loader.fetch_all(code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新浪财报获取失败: {e}")

    return {
        "symbol": code.upper(),
        "income_statement": result["income_statement"],
        "balance_sheet": result["balance_sheet"],
        "cash_flow": result["cash_flow"],
        "income_count": len(result["income_statement"]),
        "balance_count": len(result["balance_sheet"]),
        "cashflow_count": len(result["cash_flow"]),
    }


@router.get("/valuation/{code}")
async def get_stock_valuation(
    code: str,
    price: float = Query(..., description="当前股价"),
    eps_current: float = Query(..., description="当期 EPS（TTM 或最近年报）"),
    eps_forecast: float = Query(..., description="下一年度一致预期 EPS"),
    target_pe: float = Query(30.0, description="目标 PE（默认 30x）"),
):
    """Valuation metrics: forward PE, PEG, PE digestion years.

    Query params: price, eps_current, eps_forecast
    """
    from backtest.valuation import ValuationResult

    if price <= 0:
        raise HTTPException(status_code=400, detail="price 必须 > 0")
    if eps_current <= 0:
        raise HTTPException(status_code=400, detail="eps_current 必须 > 0")

    result = ValuationResult.from_data(
        price=price,
        eps_current=eps_current,
        eps_forecast=eps_forecast,
        symbol=code.upper(),
        target_pe=target_pe,
    )
    return result.to_dict()
