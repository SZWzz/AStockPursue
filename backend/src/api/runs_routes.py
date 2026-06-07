"""Run history and artifact retrieval API."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.common import (
    RUNS_DIR,
    RunInfo,
    RunResponse,
    build_response_from_run_dir,
    load_json_file,
    validate_path_param,
)
from src.ui_services import load_run_context


router = APIRouter(tags=["runs"])

@router.get("/runs/{run_id}/code")
async def get_run_code(run_id: str):
    """Return strategy source files for a run."""
    validate_path_param(run_id, "run_id")
    run_dir = RUNS_DIR / run_id / "code"
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Code directory for run {run_id} not found")
    result = {}
    for f in ["signal_engine.py"]:
        p = run_dir / f
        if p.exists():
            result[f] = p.read_text(encoding="utf-8")
    return result

@router.get("/runs/{run_id}/pine")
async def get_run_pine(run_id: str):
    """Return Pine Script file for a run."""
    validate_path_param(run_id, "run_id")
    pine_path = RUNS_DIR / run_id / "artifacts" / "strategy.pine"
    if not pine_path.exists():
        return {"exists": False, "content": None}
    return {
        "exists": True,
        "content": pine_path.read_text(encoding="utf-8"),
    }

@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run_result(run_id: str):
    """Fetch full details for a historical run by run_id.

    Tries PG-backed backtest store first, then falls back to filesystem.
    """
    validate_path_param(run_id, "run_id")

    # ── Try PG backtest store ──────────────────────────────────────────
    try:
        from src.db.backtest_store import get_backtest_run
        pg_run = get_backtest_run(run_id)
        if pg_run:
            metrics = pg_run.get("metrics", {})
            equity = pg_run.get("equity_curve", [])
            trades_data = pg_run.get("trades", [])

            equity_points = [
                {"time": e.get("time", str(i)), "equity": e.get("equity", 0)}
                for i, e in enumerate(equity)
            ] if equity else []

            trade_log = []
            if trades_data:
                for t in trades_data:
                    is_long = t.get("side") == "long"
                    entry_time = str(t.get("entry_time", ""))
                    exit_time = str(t.get("exit_time", ""))
                    code = str(t.get("symbol", ""))
                    entry_px = t.get("entry_price") or 0
                    exit_px = t.get("exit_price") or 0
                    size = t.get("size") or 0
                    exit_reason = str(t.get("exit_reason", ""))
                    # Entry row
                    trade_log.append({
                        "time": entry_time, "code": code,
                        "side": "BUY" if is_long else "SELL",
                        "price": entry_px, "qty": size,
                        "reason": "signal",
                        "pnl": t.get("pnl", 0), "return_pct": t.get("return_pct", 0),
                    })
                    # Exit row
                    trade_log.append({
                        "time": exit_time, "code": code,
                        "side": "SELL" if is_long else "BUY",
                        "price": exit_px, "qty": size,
                        "reason": exit_reason or "signal",
                        "pnl": t.get("pnl", 0), "return_pct": t.get("return_pct", 0),
                    })

            # Build price_series from OHLCV bars for K-line chart
            ohlcv_bars = pg_run.get("ohlcv_bars", [])
            price_series: dict[str, list[dict]] = {}
            if ohlcv_bars:
                for b in ohlcv_bars:
                    code = b.get("code", "")
                    price_series.setdefault(code, []).append({
                        "time": b.get("time", ""),
                        "open": b.get("open", 0),
                        "high": b.get("high", 0),
                        "low": b.get("low", 0),
                        "close": b.get("close", 0),
                        "volume": b.get("volume", 0),
                    })

            # Ensure BacktestMetrics required fields
            if isinstance(metrics, dict):
                metrics.setdefault("final_value", metrics.get("total_return", 0))
                metrics.setdefault("total_return", 0.0)
                metrics.setdefault("annual_return", 0.0)
                metrics.setdefault("max_drawdown", 0.0)
                metrics.setdefault("sharpe", 0.0)
                metrics.setdefault("win_rate", 0.0)
                metrics.setdefault("trade_count", 0)

            return RunResponse(
                status="success",
                run_id=run_id,
                elapsed_seconds=0.0,
                metrics=metrics,
                equity_curve=equity_points,
                trade_log=trade_log,
                price_series=price_series if price_series else None,
                run_directory="pg://" + run_id,
            )
    except Exception:
        pass

    # ── Fallback to filesystem ─────────────────────────────────────────
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found in database or filesystem",
        )
    response = build_response_from_run_dir(run_dir, elapsed=0.0, include_analysis=True)
    return response

@router.get("/runs", response_model=List[RunInfo])
async def list_runs(limit: int = 20):
    """List recent runs with summary fields.

    Merges PG-backed backtest store runs with filesystem runs.
    """
    limit = min(max(1, limit), 100)
    results: list[RunInfo] = []

    # ── PG backtest store runs ──────────────────────────────────────────
    try:
        from src.db.backtest_store import list_backtest_runs
        pg_runs = list_backtest_runs(limit=limit, offset=0)
        for r in pg_runs:
            metrics = r.get("metrics", {}) or {}
            results.append(RunInfo(
                run_id=r.get("id", ""),
                status=r.get("status", "success"),
                created_at=str(r.get("created_at", "")),
                prompt=r.get("run_name", "Backtest"),
                total_return=metrics.get("total_return"),
                sharpe=metrics.get("sharpe_ratio", metrics.get("sharpe")),
                codes=list((r.get("config", {}) or {}).get("codes", [])),
                start_date=str((r.get("config", {}) or {}).get("start_date", "")),
                end_date=str((r.get("config", {}) or {}).get("end_date", "")),
            ))
    except Exception:
        pass

    # ── Filesystem runs (merge with PG results) ──────────────────────────
    runs_dir = RUNS_DIR
    if not runs_dir.exists():
        return sorted(results, key=lambda r: r.created_at, reverse=True)[:limit]
    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda x: x.name,
        reverse=True,
    )
    # Track PG run_ids to avoid duplicates
    pg_ids = {r.run_id for r in results}
    for d in run_dirs:
        run_id = d.name
        status_val = "unknown"
        state_file = load_json_file(d / "state.json")
        if state_file:
            status_val = str(state_file.get("status") or "unknown").lower()
        elif (d / "artifacts" / "equity.csv").exists():
            status_val = "success"
        elif (d / "review_report.json").exists():
            status_val = "success"
        created_at = "Unknown"
        if run_id.startswith("run_"):
            parts = run_id.split('_')
            if len(parts) >= 3:
                d_str, t_str = parts[1], parts[2]
                if len(d_str) == 8 and len(t_str) == 6:
                    created_at = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]} {t_str[:2]}:{t_str[2:4]}:{t_str[4:6]}"
        elif "_" in run_id:
            parts = run_id.split('_')
            if len(parts) >= 2:
                d_str, t_str = parts[0], parts[1]
                if len(d_str) == 8 and len(t_str) == 6:
                    created_at = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]} {t_str[:2]}:{t_str[2:4]}:{t_str[4:6]}"
        if created_at == "Unknown":
            mtime = datetime.fromtimestamp(d.stat().st_mtime)
            created_at = mtime.strftime("%Y-%m-%d %H:%M:%S")
        prompt = None
        req_file = d / "req.json"
        planner_file = d / "planner_output.json"
        if req_file.exists():
            try:
                req_data = json.loads(req_file.read_text(encoding="utf-8"))
                prompt = req_data.get("prompt")
            except (json.JSONDecodeError, OSError):
                pass
        if not prompt and planner_file.exists():
            try:
                planner_data = json.loads(planner_file.read_text(encoding="utf-8"))
                prompt = planner_data.get("user_goal") or planner_data.get("goal")
            except (json.JSONDecodeError, OSError):
                pass
        if not prompt:
            prompt_file = d / "user_prompt.txt"
            if prompt_file.exists():
                prompt = prompt_file.read_text(encoding="utf-8").strip()
        total_return = None
        sharpe = None
        metrics_file = d / "artifacts" / "metrics.csv"
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        total_return = float(row.get('total_return', 0) or 0)
                        sharpe = float(row.get('sharpe', 0) or 0)
                        break
            except (OSError, ValueError):
                pass
        if run_id in pg_ids:
            continue  # already from PG
        run_context = load_run_context(d)
        results.append(RunInfo(
            run_id=run_id,
            status=status_val,
            created_at=created_at,
            prompt=prompt or "Manual Analysis",
            total_return=total_return,
            sharpe=sharpe,
            codes=run_context.get("codes") or [],
            start_date=run_context.get("start_date"),
            end_date=run_context.get("end_date"),
        ))
    return sorted(results, key=lambda r: r.created_at, reverse=True)[:limit]


