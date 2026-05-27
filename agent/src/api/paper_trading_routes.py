"""Paper trading REST API + SSE streaming endpoints.

Every endpoint that reads or mutates a run validates ownership via the
authenticated user's id so that users cannot access each other's runs.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from papertrade.models import (
    CreateRunRequest,
    EquityPoint,
    PositionOut,
    RunDetail,
    RunStatus,
    RunSummary,
    StrategyState,
    TradeOut,
)
from papertrade.repository import OwnershipError, PaperTradeRepository
from src.auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])
_repo = PaperTradeRepository()


# ── Helpers ────────────────────────────────────────────────────────────


def _get_scheduler(request: Request):
    sched = getattr(request.app.state, "paper_trading_scheduler", None)
    if sched is None:
        raise HTTPException(status_code=503, detail="Paper trading scheduler not initialised")
    return sched


def _get_user_id(auth: dict) -> int:
    return int(auth["user_id"])


def _require_run_owner(run_id: str, user_id: int) -> dict:
    """Fetch run metadata, raising 404 if missing or belonging to another user."""
    try:
        meta = _repo.get_run(run_id, user_id=user_id)
    except OwnershipError:
        raise HTTPException(status_code=404, detail="Run not found")
    if meta is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return meta


# ── Run CRUD ───────────────────────────────────────────────────────────


@router.post("/runs")
async def create_run(
    req: CreateRunRequest,
    request: Request,
    auth: dict = Depends(require_auth),
) -> dict:
    user_id = _get_user_id(auth)

    from src.security.sandbox import validate_code_safety
    valid, msg = validate_code_safety(req.strategy_code)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Strategy code unsafe: {msg}")
    if "SignalEngine" not in req.strategy_code:
        raise HTTPException(status_code=400, detail="Strategy code must define a SignalEngine class")
    if "def generate" not in req.strategy_code:
        raise HTTPException(status_code=400, detail="SignalEngine must define a generate method")

    run_id = _repo.create_run(
        run_name=req.run_name,
        market=req.market,
        codes=req.codes,
        interval=req.interval,
        initial_capital=req.initial_capital,
        strategy_code=req.strategy_code,
        risk_config=req.risk_config.model_dump(),
        user_id=user_id,
    )
    return {"id": run_id, "message": "Run created"}


@router.get("/runs")
async def list_runs(
    request: Request,
    auth: dict = Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RunSummary]:
    user_id = _get_user_id(auth)
    rows = _repo.list_runs(user_id=user_id, limit=limit)

    summaries = []
    for r in rows:
        config = r.get("config", {})
        initial_cap = float(config.get("initial_capital", 100_000))
        current_cap = float(r.get("current_capital", initial_cap))
        equity = current_cap
        positions = _repo.get_positions(r["id"])
        total_return = ((equity - initial_cap) / initial_cap * 100) if initial_cap > 0 else 0.0

        summaries.append(RunSummary(
            id=r["id"],
            run_name=r.get("run_name", ""),
            market=r.get("market", "a_share"),
            status=RunStatus(r.get("status", "stopped")),
            tick_mode=bool(r.get("tick_mode", False)),
            state=StrategyState(r.get("state", "flat")),
            current_equity=round(equity, 2),
            total_return_pct=round(total_return, 2),
            trade_count=0,
            open_positions=len(positions),
            created_at=r.get("created_at"),
            started_at=r.get("start_time"),
            last_bar_time=r.get("last_bar_time"),
        ))

    return summaries


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
) -> RunDetail:
    user_id = _get_user_id(auth)
    meta = _require_run_owner(run_id, user_id)

    config = meta.get("config", {})
    initial_cap = float(config.get("initial_capital", 100_000))
    current_cap = float(meta.get("current_capital", initial_cap))
    total_return = ((current_cap - initial_cap) / initial_cap * 100) if initial_cap > 0 else 0.0

    positions_raw = _repo.get_positions(run_id)
    trades_raw = _repo.get_trades(run_id, limit=20)

    sched = _get_scheduler(request)
    engine = sched.get_engine(run_id) if sched is not None else None
    engine_summary = engine.get_summary() if engine else {}
    data_source = sched.get_loader_name(run_id) if sched else "unknown"

    positions = []
    for p in positions_raw:
        current_price = None
        unrealized_pnl = None
        pnl_pct = None
        if engine:
            price_map = getattr(engine, "_last_bar_prices", {})
            current_price = price_map.get(p["symbol"])
            if current_price and p["entry_price"] > 0:
                direction = p["direction"]
                unrealized_pnl = direction * p["size"] * (current_price - p["entry_price"])
                margin = p["size"] * p["entry_price"] / p.get("leverage", 1.0)
                pnl_pct = (unrealized_pnl / margin * 100) if margin > 0 else 0.0

        positions.append(PositionOut(
            symbol=p["symbol"],
            direction=p["direction"],
            entry_price=p["entry_price"],
            entry_time=p["entry_time"],
            size=p["size"],
            leverage=p.get("leverage", 1.0),
            current_price=round(current_price, 4) if current_price else None,
            unrealized_pnl=round(unrealized_pnl, 2) if unrealized_pnl else None,
            pnl_pct=round(pnl_pct, 2) if pnl_pct else None,
        ))

    trades = [
        TradeOut(
            id=t["id"],
            symbol=t["symbol"],
            direction=t["direction"],
            entry_price=t["entry_price"],
            exit_price=t["exit_price"],
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            size=t["size"],
            leverage=t.get("leverage", 1.0),
            pnl=t["pnl"],
            pnl_pct=t["pnl_pct"],
            exit_reason=t["exit_reason"],
            holding_bars=t.get("holding_bars", 0),
            commission=t.get("commission", 0.0),
        )
        for t in trades_raw
    ]

    summary = RunSummary(
        id=meta["id"],
        run_name=meta.get("run_name", ""),
        market=meta.get("market", "a_share"),
        status=RunStatus(meta.get("status", "stopped")),
        tick_mode=bool(meta.get("tick_mode", False)),
        state=StrategyState(engine_summary.get("state", meta.get("state", "flat")) if engine else meta.get("state", "flat")),
        current_equity=round(engine_summary.get("equity", current_cap), 2),
        total_return_pct=round(total_return, 2),
        trade_count=engine_summary.get("trade_count", len(trades_raw)) if engine else len(trades_raw),
        open_positions=len(positions),
        created_at=meta.get("created_at"),
        started_at=meta.get("start_time"),
        last_bar_time=engine_summary.get("last_bar_time") or meta.get("last_bar_time"),
    )

    return RunDetail(run=summary, positions=positions, recent_trades=trades, data_source=data_source)


# ── Run lifecycle ──────────────────────────────────────────────────────


@router.post("/runs/{run_id}/start")
async def start_run(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
) -> dict:
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    sched = _get_scheduler(request)
    try:
        await sched.start(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception("Failed to start run %s", run_id)
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Run started", "run_id": run_id}


@router.post("/runs/{run_id}/stop")
async def stop_run(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
    close_positions: bool = Query(default=True),
) -> dict:
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    sched = _get_scheduler(request)
    try:
        await sched.stop(run_id, close_positions=close_positions)
    except Exception as e:
        logger.exception("Failed to stop run %s", run_id)
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Run stopped", "run_id": run_id}


@router.post("/runs/{run_id}/pause")
async def pause_run(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
) -> dict:
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    sched = _get_scheduler(request)
    try:
        await sched.pause(run_id)
    except Exception as e:
        logger.exception("Failed to pause run %s", run_id)
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Run paused", "run_id": run_id}


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
) -> dict:
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    sched = _get_scheduler(request)
    try:
        await sched.resume(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception("Failed to resume run %s", run_id)
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Run resumed", "run_id": run_id}


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
) -> dict:
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    sched = _get_scheduler(request)
    if sched.is_active(run_id):
        await sched.stop(run_id, close_positions=True)

    deleted = _repo.delete_run(run_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"message": "Run deleted", "run_id": run_id}


# ── Data endpoints ─────────────────────────────────────────────────────


@router.get("/runs/{run_id}/equity")
async def get_equity(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
    since: str | None = Query(default=None),
) -> list[EquityPoint]:
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    raw = _repo.get_equity(run_id, since=since)
    return [
        EquityPoint(
            point_time=r["point_time"],
            equity=r["equity"],
            capital=r["capital"],
            unrealized=r["unrealized"],
            drawdown=r["drawdown"],
        )
        for r in raw
    ]


@router.get("/runs/{run_id}/bars")
async def get_bars(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
    codes: str | None = Query(default=None, description="Comma-separated symbols. All if empty."),
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, list[dict]]:
    """Return OHLCV bar history from the running engine's ``_data_map``.

    Each bar: ``{time, open, high, low, close, volume}``.
    """
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    sched = _get_scheduler(request)
    engine = sched.get_engine(run_id)
    if engine is None:
        return {}

    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    return engine.get_bars(codes=code_list, limit=limit)


@router.get("/runs/{run_id}/trades")
async def get_trades(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[TradeOut]:
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    raw = _repo.get_trades(run_id, limit=limit, offset=offset)
    return [
        TradeOut(
            id=t["id"],
            symbol=t["symbol"],
            direction=t["direction"],
            entry_price=t["entry_price"],
            exit_price=t["exit_price"],
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            size=t["size"],
            leverage=t.get("leverage", 1.0),
            pnl=t["pnl"],
            pnl_pct=t["pnl_pct"],
            exit_reason=t["exit_reason"],
            holding_bars=t.get("holding_bars", 0),
            commission=t.get("commission", 0.0),
        )
        for t in raw
    ]


# ── SSE streaming ──────────────────────────────────────────────────────


@router.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: str,
    request: Request,
    auth: dict = Depends(require_auth),
) -> StreamingResponse:
    """SSE endpoint for real-time paper trading events.

    Validates run ownership before opening the stream.
    """
    user_id = _get_user_id(auth)
    _require_run_owner(run_id, user_id)

    sched = _get_scheduler(request)
    queue = sched.get_queue(run_id) if sched is not None else None
    if queue is None:
        raise HTTPException(status_code=404, detail="Run not active — start it first")

    async def event_generator():
        yield f"event: connected\ndata: {json.dumps({'run_id': run_id})}\n\n"

        while True:
            disconnected = await request.is_disconnected()
            if disconnected:
                break

            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                event_data = json.loads(payload) if isinstance(payload, str) else payload
                event_type = event_data.get("event", "message")
                data = event_data.get("data", event_data)
                yield f"event: {event_type}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
