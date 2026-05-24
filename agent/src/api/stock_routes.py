"""Stock symbol search / autocomplete API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Query

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
