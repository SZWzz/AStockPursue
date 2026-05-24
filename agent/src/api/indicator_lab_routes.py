"""Indicator Lab HTTP routes for the Web UI.

Provides endpoints for the indicator IDE: save, verify, list, generate, and
promote to Alpha Zoo.

Routes:
    GET  /indicator-lab/list          — list all saved indicators
    GET  /indicator-lab/{id}          — get indicator info + source
    POST /indicator-lab/save          — save or update an indicator
    POST /indicator-lab/delete/{id}   — delete an indicator
    POST /indicator-lab/verify        — verify code (sandbox exec + quality)
    POST /indicator-lab/generate      — AI-generate indicator code (SSE)
    POST /indicator-lab/promote/{id}  — promote to Alpha Zoo factor
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.lab.params import IndicatorParamsParser, StrategyConfigParser
from src.lab.quality import analyze_indicator_code_quality
from src.lab.repository import IndicatorRepository
from src.lab.sandbox import build_safe_builtins, safe_exec_with_validation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/indicator-lab", tags=["indicator-lab"])

_repo: IndicatorRepository | None = None


def _get_repo() -> IndicatorRepository:
    global _repo
    if _repo is None:
        _repo = IndicatorRepository()
    return _repo


# ── Pydantic models ─────────────────────────────────────────────────────────


class SaveRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=200_000)
    indicator_id: str | None = None
    filename: str | None = None


class VerifyResponse(BaseModel):
    success: bool
    error: str | None = None
    quality_hints: list[dict[str, Any]] = Field(default_factory=list)
    params: list[dict[str, Any]] = Field(default_factory=list)
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    plots_count: int = 0
    signals_count: int = 0
    has_buy_sell: bool = False


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    style: str = Field(default="trend", pattern=r"^(trend|reversal|momentum|volume|volatility|custom)$")


class BacktestRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=200_000)
    symbol: str = Field(..., min_length=1, max_length=50)
    source: str = Field(default="auto", max_length=20)
    start_date: str = Field(default="2024-01-01")
    end_date: str = Field(default="2025-12-31")
    interval: str = Field(default="1D", pattern=r"^(1m|5m|15m|30m|1H|4H|1D)$")
    initial_cash: float = Field(default=100_000.0, ge=1000.0)
    leverage: float = Field(default=1.0, ge=1.0, le=20.0)


class CompileRequest(BaseModel):
    name: str = Field(default="Compiled Strategy", max_length=100)
    entry_rules: list[dict] = Field(..., min_length=1)
    position_config: dict | None = None
    pyramiding_rules: dict | None = None
    risk_management: dict | None = None


class BacktestResponse(BaseModel):
    success: bool
    error: str | None = None
    run_id: str | None = None


# ── Helpers ─────────────────────────────────────────────────────────────────


def _generate_mock_df(length: int = 200) -> pd.DataFrame:
    """Generate mock K-line data for code verification."""
    dates = [datetime.now() - timedelta(minutes=i) for i in range(length)]
    dates.reverse()

    np.random.seed(42)
    close = 100.0
    data: dict[str, list[float]] = {
        "open": [], "high": [], "low": [], "close": [], "volume": []
    }
    for _ in range(length):
        change = np.random.randn() * 2
        o = close
        c = close + change
        h = max(o, c) + abs(np.random.randn()) * 1.5
        l = min(o, c) - abs(np.random.randn()) * 1.5
        v = abs(np.random.randn()) * 1000 + 5000
        data["open"].append(round(o, 2))
        data["high"].append(round(h, 2))
        data["low"].append(round(l, 2))
        data["close"].append(round(c, 2))
        data["volume"].append(round(v, 2))
        close = c

    return pd.DataFrame(data, index=pd.DatetimeIndex(dates))


def _execute_indicator_code(code: str) -> dict[str, Any]:
    """Run indicator code in sandbox against mock data, return output dict."""
    df = _generate_mock_df()

    exec_env: dict[str, Any] = {
        "__builtins__": build_safe_builtins(),
        "df": df.copy(),
        "open": df["open"].astype("float64"),
        "high": df["high"].astype("float64"),
        "low": df["low"].astype("float64"),
        "close": df["close"].astype("float64"),
        "volume": df["volume"].astype("float64"),
        "np": np,
        "pd": pd,
        "params": {},
        "my_indicator_name": "",
        "my_indicator_description": "",
    }

    result = safe_exec_with_validation(code=code, exec_globals=exec_env, timeout=30)
    if not result["success"]:
        return result

    # Extract output
    output = exec_env.get("output", {})
    plots = output.get("plots", []) if isinstance(output, dict) else []
    signals = output.get("signals", []) if isinstance(output, dict) else []

    # Validate plots and signals
    n_rows = len(df)
    for i, plot in enumerate(plots):
        if not isinstance(plot, dict):
            continue
        data = plot.get("data", [])
        if not isinstance(data, (list, np.ndarray)) or len(data) != n_rows:
            return {
                "success": False,
                "error": f"plot[{i}] '{plot.get('name', '?')}': data length {len(data) if isinstance(data, (list, np.ndarray)) else '?'} != df length {n_rows}",
                "result": None,
            }

    for i, signal in enumerate(signals):
        if not isinstance(signal, dict):
            continue
        data = signal.get("data", [])
        if not isinstance(data, (list, np.ndarray)) or len(data) != n_rows:
            return {
                "success": False,
                "error": f"signal[{i}] '{signal.get('text', '?')}': data length {len(data) if isinstance(data, (list, np.ndarray)) else '?'} != df length {n_rows}",
                "result": None,
            }

    has_buy = "buy" in exec_env.get("df", pd.DataFrame()).columns
    has_sell = "sell" in exec_env.get("df", pd.DataFrame()).columns

    return {
        "success": True,
        "error": None,
        "result": {
            "plots_count": len(plots),
            "signals_count": len(signals),
            "has_buy": has_buy,
            "has_sell": has_sell,
            "output": {
                "name": output.get("name", "") if isinstance(output, dict) else "",
                "plots": [
                    {"name": p.get("name", ""), "color": p.get("color", "#000000"), "overlay": p.get("overlay", False)}
                    for p in (plots if isinstance(plots, list) else [])
                    if isinstance(p, dict)
                ],
                "signals": [
                    {"type": s.get("type", ""), "text": s.get("text", ""), "color": s.get("color", "#000000")}
                    for s in (signals if isinstance(signals, list) else [])
                    if isinstance(s, dict)
                ],
            },
        },
    }


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/list")
async def list_indicators():
    """List all saved indicators."""
    repo = _get_repo()
    items = repo.list()
    return {
        "indicators": [
            {
                "id": i.id,
                "name": i.name,
                "description": i.description,
                "param_count": i.param_count,
                "strategy_config": i.strategy_config,
                "created_at": i.created_at,
                "updated_at": i.updated_at,
            }
            for i in items
        ]
    }


@router.post("/save")
async def save_indicator(req: SaveRequest):
    """Save or update an indicator."""
    repo = _get_repo()
    try:
        info = repo.save(code=req.code, indicator_id=req.indicator_id, filename=req.filename)
        params = IndicatorParamsParser.parse_params(req.code)
        strategy = StrategyConfigParser.parse(req.code)
        return {
            "id": info.id,
            "name": info.name,
            "description": info.description,
            "param_count": len(params),
            "strategy_config": strategy,
            "created_at": info.created_at,
            "updated_at": info.updated_at,
        }
    except Exception as e:
        logger.exception("Failed to save indicator")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete/{indicator_id}")
async def delete_indicator(indicator_id: str):
    """Delete an indicator."""
    repo = _get_repo()
    if repo.delete(indicator_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail=f"Indicator not found: {indicator_id}")


@router.post("/verify", response_model=VerifyResponse)
async def verify_indicator(req: SaveRequest):
    """Verify indicator code: safety check, sandbox execution, quality analysis."""
    code = req.code

    # 1. Quality analysis (static)
    quality_hints = analyze_indicator_code_quality(code)

    # 2. Parameter parsing
    params = IndicatorParamsParser.parse_params(code)
    strategy = StrategyConfigParser.parse(code)

    # Check for fatal quality errors
    fatal_codes = {"EMPTY_CODE", "MISSING_OUTPUT", "NDARRAY_PANDAS_METHOD_MISUSE", "FUTURE_DATA_LEAK"}
    has_fatal = any(h["code"] in fatal_codes and h["severity"] == "error" for h in quality_hints)
    if has_fatal:
        fatal_errors = [h for h in quality_hints if h["code"] in fatal_codes and h["severity"] == "error"]
        return VerifyResponse(
            success=False,
            error=f"Code quality check failed: {', '.join(h['code'] for h in fatal_errors)}",
            quality_hints=quality_hints,
            params=params,
            strategy_config=strategy,
        )

    # 3. Sandbox execution
    exec_result = _execute_indicator_code(code)

    if not exec_result.get("success"):
        return VerifyResponse(
            success=False,
            error=exec_result.get("error", "Unknown execution error"),
            quality_hints=quality_hints,
            params=params,
            strategy_config=strategy,
        )

    inner = exec_result.get("result", {})
    return VerifyResponse(
        success=True,
        error=None,
        quality_hints=quality_hints,
        params=params,
        strategy_config=strategy,
        plots_count=inner.get("plots_count", 0),
        signals_count=inner.get("signals_count", 0),
        has_buy_sell=inner.get("has_buy", False) or inner.get("has_sell", False),
    )


@router.post("/compile")
async def compile_strategy(req: CompileRequest):
    """Compile a visual strategy config into indicator code."""
    from src.lab.compiler import compile_strategy

    try:
        code = compile_strategy(req.model_dump())
        return {"code": code}
    except Exception as e:
        logger.exception("Strategy compilation failed")
        raise HTTPException(status_code=400, detail=str(e))


# ── Template routes ────────────────────────────────────────────────────────


@router.get("/templates")
async def list_templates():
    """List all available strategy templates."""
    from src.lab.template_generator import load_templates

    templates = load_templates()
    return {"templates": templates}


@router.post("/templates/{template_key}/generate")
async def generate_from_template(template_key: str):
    """Generate indicator code from a template."""
    from src.lab.template_generator import generate_from_template

    code = generate_from_template(template_key)
    if code is None:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_key}")
    return {"code": code}


@router.get("/{indicator_id}")
async def get_indicator(indicator_id: str):
    """Get a single indicator's metadata and source code."""
    repo = _get_repo()
    info = repo.get(indicator_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Indicator not found: {indicator_id}")
    code = repo.get_code(indicator_id) or ""
    return {
        "id": info.id,
        "name": info.name,
        "description": info.description,
        "code": code,
        "param_count": info.param_count,
        "strategy_config": info.strategy_config,
        "created_at": info.created_at,
        "updated_at": info.updated_at,
    }


@router.post("/generate")
async def generate_indicator(req: GenerateRequest, request: Request):
    """AI-generate indicator code via SSE streaming.

    Delegates to the LLM agent if available; falls back to a template.
    """

    async def event_stream():
        try:
            # Check if the request was disconnected
            if await request.is_disconnected():
                return

            # Try to use the agent loop for generation
            try:
                from src.agent.loop import run_agent_sync
                from src.lab.sandbox import build_safe_builtins, validate_code_safety

                system_prompt = _build_generation_prompt(req.prompt, req.style)
                generated_code = ""

                # Run agent in a thread to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: run_agent_sync(
                        system_prompt,
                        max_turns=3,
                    ),
                )

                if result:
                    # Extract code from agent response
                    generated_code = _extract_code_from_response(result)

                if generated_code:
                    # Validate the generated code
                    is_safe, err = validate_code_safety(generated_code)
                    if not is_safe:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Safety check failed: {err}'})}\n\n"
                        return

                    # Stream the code back
                    yield f"data: {json.dumps({'type': 'code', 'content': generated_code})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to generate code'})}\n\n"

            except ImportError:
                # Agent loop not available, use template fallback
                template = _build_template_code(req.prompt, req.style)
                yield f"data: {json.dumps({'type': 'code', 'content': template})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                logger.exception("AI generation failed")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        except Exception as e:
            logger.exception("SSE stream error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/backtest", response_model=BacktestResponse)
async def backtest_indicator(req: BacktestRequest):
    """Run indicator code against real market data and return backtest results."""
    from src.lab.backtest_bridge import run_indicator_backtest

    try:
        result = run_indicator_backtest(
            code=req.code,
            symbol=req.symbol,
            start_date=req.start_date,
            end_date=req.end_date,
            source=req.source,
            interval=req.interval,
            initial_cash=req.initial_cash,
            leverage=req.leverage,
        )
        return BacktestResponse(**result)
    except Exception as e:
        logger.exception("Backtest failed")
        return BacktestResponse(success=False, error=str(e))


@router.get("/{indicator_id}/history")
async def get_indicator_history(indicator_id: str):
    """Get git commit history for an indicator."""
    repo = _get_repo()
    history = repo.history(indicator_id)
    return {"history": history}


@router.post("/{indicator_id}/rollback")
async def rollback_indicator(
    indicator_id: str,
    commit_hash: str = Query(..., min_length=8, max_length=40),
):
    """Rollback an indicator to a previous version."""
    repo = _get_repo()
    info = repo.rollback(indicator_id, commit_hash)
    if info is None:
        raise HTTPException(status_code=404, detail="Rollback failed")
    return {"ok": True, "id": info.id, "name": info.name}


@router.post("/promote/{indicator_id}")
async def promote_to_alpha(
    indicator_id: str,
    zoo_id: str = Query("user", max_length=32),
    theme: str = Query("momentum", max_length=256),
    universe: str = Query("equity_us", max_length=256),
):
    """Promote an indicator to an Alpha Zoo factor."""
    repo = _get_repo()
    theme_list = [t.strip() for t in theme.split(",") if t.strip()]
    universe_list = [u.strip() for u in universe.split(",") if u.strip()]

    result_path = repo.promote_to_alpha(
        indicator_id=indicator_id,
        zoo_id=zoo_id,
        theme=theme_list or ["momentum"],
        universe=universe_list or ["equity_us"],
    )
    if result_path is None:
        raise HTTPException(status_code=404, detail=f"Indicator not found: {indicator_id}")

    return {"ok": True, "path": str(result_path), "zoo_id": zoo_id}


# ── Generation helpers ──────────────────────────────────────────────────────


def _build_generation_prompt(user_prompt: str, style: str) -> str:
    return (
        "You are an expert quantitative trader. Generate a complete Python indicator "
        "script for the AStockPursue Indicator Lab.\n\n"
        "The script MUST follow this contract:\n"
        "1. Define my_indicator_name = '...' and my_indicator_description = '...'\n"
        "2. Start with df = df.copy()\n"
        "3. Use # @param name type default description for tunable parameters\n"
        "4. Use # @strategy key value for risk config (stopLossPct, takeProfitPct, entryPct)\n"
        "5. Set df['buy'] and df['sell'] as boolean Series for entry/exit signals\n"
        "6. Build an output dict with 'name', 'plots' (list of {name, data, color, overlay}), "
        "and 'signals' (list of {type, text, data, color})\n\n"
        "Available variables: df (DataFrame with open/high/low/close/volume), params (dict), "
        "np, pd, open, high, low, close, volume (as float64 Series).\n\n"
        f"User request: {user_prompt}\n"
        f"Style preference: {style}\n\n"
        "Return ONLY the Python code, no explanations."
    )


def _extract_code_from_response(response: str) -> str:
    """Extract Python code from an agent response (may contain markdown fences)."""
    import re as _re

    pattern = _re.compile(r"```(?:python)?\s*\n(.*?)```", _re.DOTALL)
    m = pattern.search(response)
    if m:
        return m.group(1).strip()

    # No fence found — assume the whole response is code
    return response.strip()


def _build_template_code(prompt: str, style: str) -> str:
    """Build a template indicator as fallback when LLM is unavailable."""
    return f'''my_indicator_name = "Custom {style.title()} Strategy"
my_indicator_description = "Auto-generated {style} indicator based on: {prompt[:100]}"

# @param period int 14 Lookback period
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05
# @strategy entryPct 0.5

df = df.copy()

period = params.get("period", 14)

# RSI calculation
delta = df["close"].diff()
gain = delta.where(delta > 0, 0.0)
loss = (-delta).where(delta < 0, 0.0)
avg_gain = gain.rolling(window=period, min_periods=period).mean()
avg_loss = loss.rolling(window=period, min_periods=period).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100.0 - (100.0 / (1.0 + rs))

# Entry/exit signals
df["buy"] = rsi < 30
df["sell"] = rsi > 70

output = {{
    "name": my_indicator_name,
    "plots": [
        {{"name": "RSI", "data": rsi.tolist(), "color": "#9C27B0", "overlay": False}},
    ],
    "signals": [
        {{"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"}},
        {{"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"}},
    ],
}}
'''
