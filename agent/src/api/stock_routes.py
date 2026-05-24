"""Stock symbol search / autocomplete API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

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


@router.get("/search")
async def search_stocks(q: str = Query("", max_length=64)):
    """Search stock symbols by code, name, or pinyin. Returns up to 20 matches."""
    symbols = _load_symbols()
    query = q.strip().lower()
    if not query:
        return {"results": symbols[:20]}

    results: list[dict] = []
    for s in symbols:
        if (
            query in s["code"].lower()
            or query in s["name"].lower()
            or query in s.get("pinyin", "")
        ):
            results.append(s)
            if len(results) >= 20:
                break

    return {"results": results}


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
    user_id = user.get("user_id", 1)
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
