"""Strategy Marketplace REST API — publish, browse, rate, install."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.common import safe_error
from src.auth.dependencies import require_auth

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


def _get_user_id(auth: dict) -> int:
    return int(auth["user_id"])


class PublishRequest(BaseModel):
    title: str
    description: str = ""
    code: str
    market: str = "equity_cn"
    asset_class: str = "stock"
    category: str = "trend"
    tags: list[str] = Field(default_factory=list)
    backtest_sharpe: float | None = None
    backtest_return: float | None = None
    backtest_drawdown: float | None = None


class RateRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)


@router.get("/strategies")
async def browse_strategies(
    market: str = "",
    category: str = "",
    sort: str = Query("rating", pattern="^(rating|installs|newest)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Browse published strategies with sort/filter."""
    try:
        from src.db.pool import init_pool, get_connection
        init_pool()
        with get_connection() as conn:
            with conn.cursor() as cur:
                where = "WHERE is_public = true"
                params: list[Any] = []
                if market:
                    where += " AND market = %s"
                    params.append(market)
                if category:
                    where += " AND category = %s"
                    params.append(category)
                order = {"rating": "rating_count DESC, rating_sum DESC", "installs": "installs_count DESC", "newest": "created_at DESC"}.get(sort, "rating_count DESC")
                cur.execute(f"SELECT id, user_id, title, description, market, category, tags, backtest_sharpe, backtest_return, backtest_drawdown, installs_count, rating_sum, rating_count, created_at FROM vt_strategy_marketplace {where} ORDER BY {order} LIMIT %s OFFSET %s", params + [limit, offset])
                rows = cur.fetchall()
                return {"strategies": [{"id": str(r[0]), "user_id": r[1], "title": r[2], "description": r[3], "market": r[4], "category": r[5], "tags": r[6], "backtest_sharpe": r[7], "backtest_return": r[8], "backtest_drawdown": r[9], "installs_count": r[10], "rating_sum": r[11], "rating_count": r[12], "created_at": r[13].isoformat() if hasattr(r[13], "isoformat") else str(r[13]), "rating_avg": round(r[11] / max(r[12], 1), 1)} for r in rows], "total": len(rows)}
    except Exception as e:
        return {"strategies": [], "total": 0, "error": safe_error(e)}


@router.post("/publish")
async def publish_strategy(req: PublishRequest, auth: dict = Depends(require_auth)):
    user_id = _get_user_id(auth)
    import uuid, json
    sid = uuid.uuid4().hex[:12]
    try:
        from src.db.pool import init_pool, get_connection
        init_pool()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO vt_strategy_marketplace
                       (id, user_id, title, description, code, market, asset_class, category, tags, backtest_sharpe, backtest_return, backtest_drawdown)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (sid, user_id, req.title, req.description, req.code, req.market, req.asset_class, req.category, req.tags, req.backtest_sharpe, req.backtest_return, req.backtest_drawdown),
                )
        return {"ok": True, "strategy_id": sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.get("/strategy/{strategy_id}")
async def get_strategy(strategy_id: str):
    try:
        from src.db.pool import init_pool, get_connection
        init_pool()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, user_id, title, description, code, market, category, tags, backtest_sharpe, installs_count, rating_sum, rating_count, created_at FROM vt_strategy_marketplace WHERE id = %s", (strategy_id,))
                r = cur.fetchone()
                if not r:
                    raise HTTPException(status_code=404, detail="Strategy not found")
        return {"id": str(r[0]), "user_id": r[1], "title": r[2], "description": r[3], "code": r[4], "market": r[5], "category": r[6], "tags": r[7], "backtest_sharpe": r[8], "installs_count": r[9], "rating_sum": r[10], "rating_count": r[11], "created_at": r[12].isoformat() if hasattr(r[12], "isoformat") else str(r[12]), "rating_avg": round(r[10] / max(r[11], 1), 1)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.post("/strategy/{strategy_id}/rate")
async def rate_strategy(strategy_id: str, req: RateRequest, auth: dict = Depends(require_auth)):
    user_id = _get_user_id(auth)
    try:
        from src.db.pool import init_pool, get_connection
        init_pool()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO vt_strategy_ratings (strategy_id, user_id, rating) VALUES (%s, %s, %s) ON CONFLICT (strategy_id, user_id) DO UPDATE SET rating = EXCLUDED.rating",
                    (strategy_id, user_id, req.rating),
                )
                cur.execute(
                    "UPDATE vt_strategy_marketplace SET rating_sum = (SELECT COALESCE(SUM(rating),0) FROM vt_strategy_ratings WHERE strategy_id=%s), rating_count = (SELECT COUNT(*) FROM vt_strategy_ratings WHERE strategy_id=%s) WHERE id=%s",
                    (strategy_id, strategy_id, strategy_id),
                )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.post("/strategy/{strategy_id}/install")
async def install_strategy(strategy_id: str, auth: dict = Depends(require_auth)):
    user_id = _get_user_id(auth)
    try:
        from src.db.pool import init_pool, get_connection
        init_pool()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT title, code FROM vt_strategy_marketplace WHERE id = %s", (strategy_id,))
                s = cur.fetchone()
                if not s:
                    raise HTTPException(status_code=404, detail="Strategy not found")
                cur.execute(
                    "INSERT INTO vt_strategies (user_id, name, description, code) VALUES (%s, %s, %s, %s)",
                    (user_id, s[0] + " (from marketplace)", "Installed from marketplace", s[1]),
                )
                cur.execute("UPDATE vt_strategy_marketplace SET installs_count = installs_count + 1 WHERE id = %s", (strategy_id,))
        return {"ok": True, "message": f"Strategy '{s[0]}' installed to your Strategy Lab"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.delete("/strategy/{strategy_id}")
async def unpublish_strategy(strategy_id: str, auth: dict = Depends(require_auth)):
    user_id = _get_user_id(auth)
    try:
        from src.db.pool import init_pool, get_connection
        init_pool()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM vt_strategy_marketplace WHERE id = %s AND user_id = %s", (strategy_id, user_id))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Strategy not found or not owned by you")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))
