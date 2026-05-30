"""System routes: health, correlation, upload, watchlist, backtest-history, swarm, etc."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Security, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from src.api.common import (
    safe_error,
    validate_path_param,
    UPLOADS_DIR,
    RUNS_DIR,
    HealthResponse,
    shell_tools_enabled_for_request,
    MAX_UPLOAD_SIZE,
    _UPLOAD_CHUNK_SIZE,
    _BLOCKED_UPLOAD_EXT,
    _BLOCKED_UPLOAD_NAMES,
)

_SHADOW_ID_RE = __import__("re").compile(r"^shadow_[0-9a-f]{8}$")

# ---------------------------------------------------------------------------
# Swarm lazy-init singleton
# ---------------------------------------------------------------------------

_swarm_runtime = None


def _get_swarm_runtime():
    """Lazy-init SwarmRuntime singleton."""
    global _swarm_runtime
    if _swarm_runtime is not None:
        return _swarm_runtime
    from src.swarm.store import SwarmStore
    from src.swarm.runtime import SwarmRuntime

    swarm_dir = Path(__file__).resolve().parent.parent.parent / ".swarm" / "runs"
    store = SwarmStore(base_dir=swarm_dir)
    _swarm_runtime = SwarmRuntime(store=store)
    return _swarm_runtime


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _terminate_current_process() -> None:
    """Stop the current API process after the response has been sent."""
    time.sleep(0.25)
    os.kill(os.getpid(), signal.SIGTERM)


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def create_router(require_auth) -> APIRouter:
    router = APIRouter()

    # ========================================================================
    # Health check
    # ========================================================================

    @router.get("/health", response_model=HealthResponse)
    async def health_check():
        """Liveness probe."""
        return HealthResponse(
            status="healthy",
            service="AStockPursue API",
            timestamp=datetime.now().isoformat(),
        )

    # ========================================================================
    # Cross-asset correlation matrix
    # ========================================================================

    @router.get("/correlation")
    async def get_correlation_matrix(
        codes: str = Query(..., description="Comma-separated asset codes, e.g. BTC-USDT,ETH-USDT,SPY"),
        days: int = Query(90, description="Lookback window in days", ge=7, le=365),
        method: str = Query("pearson", description="Correlation method: pearson or spearman"),
    ):
        """Compute cross-asset correlation matrix from daily returns.

        Fetches price data for each code via available data loaders,
        computes pairwise correlation of daily returns over the lookback window.
        """
        from backtest.correlation import compute_correlation_matrix

        code_list = [c.strip() for c in codes.split(",") if c.strip()]
        if len(code_list) < 2:
            raise HTTPException(status_code=400, detail="At least 2 asset codes required")
        if len(code_list) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 assets per request")
        if method not in ("pearson", "spearman"):
            raise HTTPException(status_code=400, detail="method must be 'pearson' or 'spearman'")

        try:
            result = compute_correlation_matrix(codes=code_list, days=days, method=method)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Correlation computation failed: {exc}")

    # ========================================================================
    # System shutdown (loopback only)
    # ========================================================================

    @router.post("/system/shutdown", dependencies=[Depends(require_auth)])
    async def shutdown_local_api(background_tasks: BackgroundTasks, request: Request):
        """Shut down the local API server when requested from loopback clients."""
        client_host = request.client.host if request.client else ""
        if client_host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local access only")

        background_tasks.add_task(_terminate_current_process)
        return {
            "status": "shutting-down",
            "service": "AStockPursue API",
            "timestamp": datetime.now().isoformat(),
        }

    # ========================================================================
    # Skills listing
    # ========================================================================

    @router.get("/skills")
    async def list_skills():
        """List registered skills (name and description)."""
        from src.agent.skills import SkillsLoader

        loader = SkillsLoader()
        return [
            {
                "name": s.name,
                "description": s.description,
            }
            for s in loader.skills
        ]

    # ========================================================================
    # Service metadata
    # ========================================================================

    @router.get("/api")
    async def api_info():
        """Service metadata."""
        return {
            "service": "AStockPursue API",
            "version": "5.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    # ========================================================================
    # Shadow Account reports
    # ========================================================================

    @router.get("/shadow-reports/{shadow_id}", dependencies=[Depends(require_auth)])
    async def get_shadow_report(shadow_id: str, format: str = "html"):
        """Serve a rendered Shadow Account report (HTML by default, PDF if available).

        Reports live under ``~/.AStockPursue/shadow_reports/<shadow_id>.{html,pdf}``.
        """
        if not _SHADOW_ID_RE.match(shadow_id):
            raise HTTPException(status_code=400, detail="invalid shadow_id")
        if format not in ("html", "pdf"):
            raise HTTPException(status_code=400, detail="format must be html or pdf")

        reports_dir = Path.home() / ".AStockPursue" / "shadow_reports"
        path = reports_dir / f"{shadow_id}.{format}"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Shadow report not found: {shadow_id}.{format}")

        media_type = "text/html; charset=utf-8" if format == "html" else "application/pdf"
        # Inline so browsers render HTML/PDF directly instead of forcing download.
        return FileResponse(
            path,
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{shadow_id}.{format}"'},
        )

    # ========================================================================
    # File upload
    # ========================================================================

    @router.post("/upload", dependencies=[Depends(require_auth)])
    async def upload_file(file: UploadFile):
        """Upload any document or data file (max 50MB).

        Accepts most common formats: PDF, Word, Excel, PowerPoint, images,
        CSV/TSV, plain text, JSON, and TOML. Executables, executable-adjacent
        source/config/template files, and archives are rejected.
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")
        filename = Path(file.filename).name
        ext = Path(file.filename).suffix.lower()
        if ext in _BLOCKED_UPLOAD_EXT or filename.lower() in _BLOCKED_UPLOAD_NAMES:
            raise HTTPException(
                status_code=400,
                detail="This file type is not allowed for upload.",
            )

        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOADS_DIR / safe_name
        total_size = 0

        try:
            with dest.open("wb") as handle:
                while True:
                    chunk = await file.read(_UPLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_UPLOAD_SIZE:
                        handle.close()
                        if dest.exists():
                            dest.unlink()
                        raise HTTPException(
                            status_code=413,
                            detail=f"File too large (limit {MAX_UPLOAD_SIZE // (1024 * 1024)} MB)",
                        )
                    handle.write(chunk)
        except HTTPException:
            raise
        except OSError as exc:
            if dest.exists():
                dest.unlink()
            raise HTTPException(status_code=500, detail=f"Failed to store upload: {exc}") from exc
        finally:
            await file.close()

        return {
            "status": "ok",
            "file_path": str(dest.resolve()),
            "filename": file.filename,
        }

    # ========================================================================
    # Watchlist API
    # ========================================================================

    def _resolve_stock_name(code: str) -> str:
        """Try to resolve a stock's display name via Tencent quote API.

        Returns the resolved name on success, or *code* on failure.
        """
        try:
            from backtest.loaders.tencent import _is_cn, _is_hk, normalize_cn_code, normalize_hk_code

            tc = ""
            if _is_cn(code):
                tc = normalize_cn_code(code)
            elif _is_hk(code):
                tc = normalize_hk_code(code)
            else:
                return code

            import requests
            resp = requests.get(
                f"https://qt.gtimg.cn/q={tc}",
                timeout=5,
                headers={"Referer": "https://qt.gtimg.cn/"},
            )
            resp.encoding = "gbk"
            text = (resp.text or "").strip()
            if "~" in text and "v_" in text:
                s = text.index('="') + 2
                e = text.rindex('"')
                parts = text[s:e].split("~")
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        except Exception:
            pass
        return code

    @router.get("/api/watchlist")
    async def get_watchlist(auth: dict = Security(require_auth)):
        """Get the current user's watchlist."""
        user_id = auth["user_id"]
        try:
            from src.db.pool import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, symbol, name, market, sort_order FROM vt_watchlist WHERE user_id=%s ORDER BY sort_order, created_at",
                        (user_id,),
                    )
                    return {"symbols": [{"id": r[0], "symbol": r[1], "name": r[2], "market": r[3]} for r in cur.fetchall()]}
        except Exception as e:
            return {"symbols": [], "error": str(e)}

    @router.post("/api/watchlist")
    async def add_watchlist(request: Request, auth: dict = Security(require_auth)):
        """Add a symbol to the watchlist."""
        user_id = auth["user_id"]
        try:
            body = await request.json()
            symbol = body.get("symbol", "").strip().upper()
            name = body.get("name", "").strip()
            if not symbol:
                raise HTTPException(status_code=400, detail="symbol required")

            # Auto-resolve stock name via Tencent quote API if not provided
            if not name:
                name = _resolve_stock_name(symbol)

            from src.db.pool import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO vt_watchlist (user_id, symbol, name) VALUES (%s, %s, %s) ON CONFLICT (user_id, symbol) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                        (user_id, symbol, name or symbol),
                    )
                    row = cur.fetchone()
            return {"ok": True, "id": row[0], "name": name}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    @router.delete("/api/watchlist/{symbol}")
    async def remove_watchlist(symbol: str, auth: dict = Security(require_auth)):
        """Remove a symbol from the watchlist."""
        user_id = auth["user_id"]
        try:
            from src.db.pool import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM vt_watchlist WHERE user_id=%s AND symbol=%s",
                        (user_id, symbol.upper()),
                    )
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    @router.get("/api/watchlist/prices")
    async def get_watchlist_prices(auth: dict = Security(require_auth)):
        """Get latest prices for watchlist symbols. Tushare for A-shares, yfinance fallback."""
        user_id = auth["user_id"]
        try:
            from src.auth.user_config import load_user_config

            load_user_config(user_id)
        except Exception:
            pass
        try:
            from src.db.pool import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT symbol, name FROM vt_watchlist WHERE user_id=%s ORDER BY sort_order, created_at", (user_id,))
                    rows = cur.fetchall()

            if not rows:
                return {"prices": {}}

            symbols = [r[0] for r in rows]
            names = {r[0]: r[1] for r in rows}
            prices = {}

            # Batch-fetch through DataStore instead of N+1 per-symbol calls
            import pandas as pd
            today = pd.Timestamp.now().strftime("%Y-%m-%d")
            start = (pd.Timestamp.now() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")

            # Separate A-share symbols for batch fetching
            cn_symbols = [s for s in symbols if s.upper().endswith((".SH", ".SZ", ".BJ"))]
            other_symbols = [s for s in symbols if s not in cn_symbols]

            # Batch-fetch A-shares via DataStore (single call per loader)
            if cn_symbols:
                try:
                    from backtest.data_store import get_data_store
                    store = get_data_store()
                    data_map = store.get_multi_ohlcv(cn_symbols, start, today, interval="1D")
                    for sym in cn_symbols:
                        df = data_map.get(sym)
                        if df is not None and len(df) >= 2:
                            current = float(df["close"].iloc[-1])
                            prev_close = float(df["close"].iloc[-2])
                            change_pct = (current - prev_close) / prev_close * 100 if prev_close else 0
                            prices[sym] = {"price": round(current, 2), "change_pct": round(change_pct, 2), "name": names.get(sym, sym)}
                        else:
                            prices[sym] = {"price": 0, "change_pct": 0, "name": names.get(sym, sym), "error": "no data"}
                except Exception:
                    for sym in cn_symbols:
                        prices.setdefault(sym, {"price": 0, "change_pct": 0, "name": names.get(sym, sym), "error": "batch fetch failed"})

            # Other markets: try yfinance (for US/HK/crypto)
            for sym in other_symbols:
                try:
                    import yfinance as yf
                    ticker = yf.Ticker(sym)
                    info = ticker.fast_info if hasattr(ticker, "fast_info") else ticker.info
                    prev_close = getattr(info, "previous_close", None) or getattr(info, "regularMarketPreviousClose", None) or 0
                    current = getattr(info, "last_price", None) or getattr(info, "currentPrice", None) or 0
                    change_pct = (current - prev_close) / prev_close * 100 if current and prev_close else 0
                    prices[sym] = {"price": current or 0, "change_pct": round(change_pct, 2), "name": names.get(sym, sym)}
                except Exception:
                    prices[sym] = {"price": 0, "change_pct": 0, "name": names.get(sym, sym), "error": "fetch failed"}

            return {"prices": prices}
        except Exception as e:
            return {"prices": {}, "error": str(e)}

    # ========================================================================
    # Backtest History API (PG-backed)
    # ========================================================================

    @router.get("/api/backtest-history", dependencies=[Depends(require_auth)])
    async def list_backtest_history(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """List recent backtest runs from PostgreSQL."""
        try:
            from src.db.backtest_store import list_backtest_runs

            runs = list_backtest_runs(limit=limit, offset=offset)
            return {"runs": runs, "total": len(runs)}
        except Exception as e:
            return {"runs": [], "total": 0, "error": str(e)}

    @router.get("/api/backtest-history/{run_id}", dependencies=[Depends(require_auth)])
    async def get_backtest_history(run_id: str):
        """Get a single backtest run with equity and trades."""
        try:
            from src.db.backtest_store import get_backtest_run

            run = get_backtest_run(run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="Backtest run not found")
            return run
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    @router.delete("/api/backtest-history/{run_id}", dependencies=[Depends(require_auth)])
    async def delete_backtest_history(run_id: str):
        """Delete a backtest run."""
        try:
            from src.db.backtest_store import delete_backtest_run

            if delete_backtest_run(run_id):
                return {"ok": True}
            raise HTTPException(status_code=404, detail="Backtest run not found")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    # ========================================================================
    # Swarm API
    # ========================================================================

    @router.get("/swarm/presets", dependencies=[Depends(require_auth)])
    async def list_swarm_presets():
        """List Swarm YAML presets."""
        from src.swarm.presets import list_presets

        return list_presets()

    @router.post("/swarm/runs", dependencies=[Depends(require_auth)])
    async def create_swarm_run(payload: dict, http_request: Request):
        """Start a swarm run: body must include preset_name and user_vars."""
        runtime = _get_swarm_runtime()
        preset_name = payload.get("preset_name", "")
        user_vars = payload.get("user_vars", {})
        try:
            run = runtime.start_run(
                preset_name,
                user_vars,
                include_shell_tools=shell_tools_enabled_for_request(http_request),
            )
            return {"id": run.id, "status": run.status.value, "preset_name": run.preset_name}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=safe_error(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=safe_error(e))

    @router.get("/swarm/runs", dependencies=[Depends(require_auth)])
    async def list_swarm_runs(limit: int = Query(20, ge=1, le=100)):
        """List swarm runs (newest first)."""
        runtime = _get_swarm_runtime()
        runs = runtime._store.list_runs(limit=limit)
        return [
            {
                "id": r.id,
                "preset_name": r.preset_name,
                "status": r.status.value,
                "created_at": r.created_at,
                "task_count": len(r.tasks),
                "completed_count": sum(1 for t in r.tasks if t.status.value == "completed"),
            }
            for r in runs
        ]

    @router.get("/swarm/runs/{run_id}", dependencies=[Depends(require_auth)])
    async def get_swarm_run(run_id: str):
        """Swarm run detail including task statuses."""
        from src.swarm.task_store import TaskStore

        validate_path_param(run_id, "run_id")
        runtime = _get_swarm_runtime()
        run = runtime._store.load_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Merge real-time task statuses from task_store (updated during execution)
        run_dir = runtime._store.run_dir(run_id)
        tasks_dir = run_dir / "tasks"
        if tasks_dir.exists():
            task_store = TaskStore(run_dir)
            live_tasks = task_store.load_all()
            if live_tasks:
                run.tasks = live_tasks

        return {
            "id": run.id,
            "preset_name": run.preset_name,
            "status": run.status.value,
            "user_vars": run.user_vars,
            "agents": [a.model_dump() for a in run.agents],
            "tasks": [t.model_dump() for t in run.tasks],
            "created_at": run.created_at,
            "completed_at": run.completed_at,
            "final_report": run.final_report,
        }

    @router.get("/swarm/runs/{run_id}/events", dependencies=[Depends(require_auth)])
    async def swarm_run_events(run_id: str, request: Request, last_index: int = Query(0, ge=0)):
        """SSE stream for a swarm run."""
        validate_path_param(run_id, "run_id")
        runtime = _get_swarm_runtime()

        async def event_stream():
            idx = last_index
            while True:
                if await request.is_disconnected():
                    break
                events = runtime._store.read_events(run_id, after_index=idx)
                for evt in events:
                    idx += 1
                    yield f"id: {idx}\nevent: {evt.type}\ndata: {json.dumps(evt.model_dump(), ensure_ascii=False)}\n\n"
                run = runtime._store.load_run(run_id)
                if run and run.status.value in ("completed", "failed", "cancelled"):
                    yield f"event: done\ndata: {{\"status\": \"{run.status.value}\"}}\n\n"
                    break
                await asyncio.sleep(2)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @router.post("/swarm/runs/{run_id}/cancel", dependencies=[Depends(require_auth)])
    async def cancel_swarm_run(run_id: str):
        """Cancel an active swarm run."""
        validate_path_param(run_id, "run_id")
        runtime = _get_swarm_runtime()
        ok = runtime.cancel_run(run_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"No active run {run_id}")
        return {"status": "cancelled"}

    return router
