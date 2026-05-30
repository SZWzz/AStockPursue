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

from src.api.common import safe_error
from pydantic import BaseModel, Field

from src.auth.dependencies import require_auth

from src.lab.params import IndicatorParamsParser, StrategyConfigParser
from src.lab.quality import analyze_indicator_code_quality
from src.lab.storage.repository import IndicatorRepository
from src.security.sandbox import build_safe_builtins, safe_exec_with_validation, validate_code_safety

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/indicator-lab", tags=["indicator-lab"])

_repo: IndicatorRepository | None = None
_repo_lock = __import__("threading").Lock()


def _get_repo() -> IndicatorRepository:
    global _repo
    if _repo is None:
        with _repo_lock:
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
    interval: str = Field(default="1D", pattern=r"^(1m|5m|15m|30m|1H|4H|1D|1W|4W)$")
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
    """Generate mock K-line data for code verification using GBM.

    Uses Geometric Brownian Motion with stochastic volatility to produce
    more realistic price paths (volatility clustering, occasional gaps)
    compared to the old fixed-seed Gaussian random walk.
    """
    dates = [datetime.now() - timedelta(minutes=i) for i in range(length)]
    dates.reverse()

    mu = 0.0001       # drift
    sigma_base = 0.02 # base volatility
    close = 100.0
    data: dict[str, list[float]] = {
        "open": [], "high": [], "low": [], "close": [], "volume": []
    }
    # Random seed with entropy from system time — avoid fixed seed so
    # indicators are tested against varying data distributions.
    np.random.seed(None)

    # GBM with stochastic volatility (volatility clustering)
    vol = sigma_base
    for _ in range(length):
        # Random walk on volatility (clustering effect)
        vol += np.random.randn() * 0.002
        vol = max(vol, 0.005)  # floor volatility
        vol = min(vol, 0.06)   # ceiling volatility

        # GBM step
        epsilon = np.random.randn()
        ret = mu + vol * epsilon
        gap = np.random.randn() * vol * 0.3 if np.random.random() < 0.02 else 0.0  # occasional gap
        o = close + gap * close
        c = o * (1 + ret)
        h = max(o, c) * (1 + abs(np.random.randn()) * vol * 0.5)
        l = min(o, c) * (1 - abs(np.random.randn()) * vol * 0.5)
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

    import sys as _sys
    _safe_sys = type("_SafeSys", (), {
        "maxsize": _sys.maxsize, "float_info": _sys.float_info,
        "version_info": _sys.version_info, "version": _sys.version,
        "platform": _sys.platform, "byteorder": _sys.byteorder,
        "__repr__": lambda s: "<module 'sys' (sandboxed)>",
    })()

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
        "sys": _safe_sys,
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
    # Safety validation before saving
    is_safe, err = validate_code_safety(req.code)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Code safety check failed: {err}")

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
        raise HTTPException(status_code=500, detail=safe_error(e))


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
        raise HTTPException(status_code=400, detail=safe_error(e))


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


# ── Built-in indicators ────────────────────────────────────────────────────


@router.get("/builtins")
async def list_builtins():
    """List all built-in indicator templates."""
    return {
        "builtins": [
            {
                "key": "sma",
                "name": "Simple Moving Average",
                "description": "Classic SMA with configurable period. Use as trend filter or overlay.",
                "category": "trend",
            },
            {
                "key": "ema",
                "name": "Exponential Moving Average",
                "description": "EMA crossover — faster response than SMA for trend changes.",
                "category": "trend",
            },
            {
                "key": "rsi",
                "name": "Relative Strength Index",
                "description": "Momentum oscillator measuring speed and change of price movements.",
                "category": "momentum",
            },
            {
                "key": "macd",
                "name": "MACD",
                "description": "Moving Average Convergence Divergence — trend + momentum in one.",
                "category": "momentum",
            },
            {
                "key": "bollinger",
                "name": "Bollinger Bands",
                "description": "Volatility bands around a moving average — fade the extremes.",
                "category": "volatility",
            },
            {
                "key": "atr",
                "name": "Average True Range",
                "description": "Volatility measure — use for dynamic stop-loss and position sizing.",
                "category": "volatility",
            },
            {
                "key": "obv",
                "name": "On-Balance Volume",
                "description": "Cumulative volume indicator — confirm price trends with volume flow.",
                "category": "volume",
            },
            {
                "key": "kdj",
                "name": "KDJ Indicator",
                "description": "Stochastic oscillator variant popular in China A-share markets.",
                "category": "momentum",
            },
            {
                "key": "ichimoku",
                "name": "Ichimoku Cloud",
                "description": "All-in-one indicator: trend direction, support/resistance, momentum.",
                "category": "trend",
            },
        ]
    }


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
                from src.security.sandbox import build_safe_builtins, validate_code_safety

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
async def backtest_indicator(req: BacktestRequest, user: dict = Depends(require_auth)):
    """Run indicator code against real market data and return backtest results."""
    from src.lab.backtest_bridge import run_indicator_backtest

    user_id = user["user_id"]
    try:
        from src.auth.user_config import load_user_config
        load_user_config(user_id)
    except Exception:
        pass

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


# ── Alpha Zoo → Indicator conversion ────────────────────────────────────────


@router.get("/alpha/list")
async def list_alpha_zoo_factors(
    zoo: str | None = None,
    limit: int = 50,
):
    """List available Alpha Zoo factors for conversion to indicators."""
    from src.factors.registry import Registry, get_default_registry

    alphas: list[dict] = []
    seen: set[str] = set()

    registries = [get_default_registry()]
    try:
        from src.config.paths import get_runtime_root
        runtime_zoo = get_runtime_root() / "zoo"
        if runtime_zoo.is_dir():
            registries.append(Registry(zoo_root=runtime_zoo))
    except Exception:
        pass

    for registry in registries:
        try:
            ids = registry.list(zoo=zoo)
        except Exception:
            continue
        for aid in ids:
            if aid in seen:
                continue
            if len(alphas) >= limit:
                break
            try:
                a = registry.get(aid)
            except KeyError:
                continue
            seen.add(aid)
            meta = a.meta or {}
            alphas.append({
                "id": a.id,
                "zoo": a.zoo,
                "nickname": meta.get("nickname", a.id),
                "theme": meta.get("theme", []),
                "universe": meta.get("universe", []),
                "formula_latex": meta.get("formula_latex", ""),
            })
        if len(alphas) >= limit:
            break

    return {"alphas": alphas}


@router.get("/alpha/{alpha_id}/convert")
async def convert_alpha_to_indicator(alpha_id: str):
    """Convert an Alpha Zoo factor to Indicator Lab format code."""
    from src.factors.registry import Registry, RegistryError, get_default_registry

    # Find alpha in bundled or runtime zoo
    alpha = None
    source_code = None
    registries = [get_default_registry()]
    try:
        from src.config.paths import get_runtime_root
        runtime_zoo = get_runtime_root() / "zoo"
        if runtime_zoo.is_dir():
            registries.append(Registry(zoo_root=runtime_zoo))
    except Exception:
        pass

    for registry in registries:
        try:
            alpha = registry.get(alpha_id)
            source_code = registry.get_source(alpha_id)
            break
        except (KeyError, RegistryError):
            continue

    if alpha is None:
        raise HTTPException(status_code=404, detail=f"Alpha not found: {alpha_id}")

    meta = alpha.meta or {}
    nickname = meta.get("nickname", alpha_id)
    formula = meta.get("formula_latex", "")
    description = f"Converted from Alpha Zoo factor: {nickname}"
    if formula:
        description += f" | Formula: {formula}"

    indicator_code = _build_indicator_from_alpha(
        alpha_id=alpha_id,
        nickname=nickname,
        description=description,
        source_code=source_code,
        theme=meta.get("theme", []),
    )

    return {
        "alpha_id": alpha_id,
        "nickname": nickname,
        "code": indicator_code,
    }


def _inline_factor_base() -> str:
    """Return the source of src/factors/base.py utility functions, stripped of
    imports / docstring / classes, suitable for inlining into Indicator Lab code."""
    from pathlib import Path

    base_path = Path(__file__).resolve().parent.parent / "factors" / "base.py"
    base_source = base_path.read_text(encoding="utf-8")

    lines = base_source.split("\n")
    out: list[str] = []
    in_docstring = False
    in_class = False
    class_indent: int | None = None
    skip_decorator = False
    for line in lines:
        s = line.strip()
        if not s:
            if in_class:
                continue
            if not out:
                continue
            out.append(line)
            continue

        if s in ("from __future__ import annotations",):
            continue
        if s.startswith("from ") or s.startswith("import "):
            continue

        # Skip decorators (they precede class/function defs we may skip)
        if s.startswith("@"):
            skip_decorator = True
            continue

        # Track and skip class definitions
        if s.startswith("class "):
            in_class = True
            class_indent = len(line) - len(line.lstrip())
            skip_decorator = False
            continue
        if in_class:
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= (class_indent or 0) and s:
                in_class = False
                class_indent = None
                # This line is outside the class, process it normally
            else:
                continue

        # Track docstrings
        if in_docstring:
            if '"""' in s or "'''" in s:
                in_docstring = False
            continue
        if s.startswith('"""') or s.startswith("'''"):
            triple = '"""' if s.startswith('"""') else "'''"
            is_single_line = len(s) > len(triple) * 2 and s.endswith(triple)
            if not is_single_line:
                in_docstring = True
            continue

        if skip_decorator and s.startswith("def "):
            skip_decorator = False

        out.append(line)
    return "\n".join(out)


def _build_indicator_from_alpha(
    alpha_id: str,
    nickname: str,
    description: str,
    source_code: str,
    theme: list[str],
) -> str:
    """Convert alpha source code into Indicator Lab format."""
    import re

    # Determine strategy config based on theme
    stop_loss = "0.05" if "trend" in theme else "0.03"
    take_profit = "0.10" if "trend" in theme else "0.06"

    lines = []
    lines.append(f'my_indicator_name = "{nickname}"')
    lines.append(f'my_indicator_description = "{description}"')
    lines.append("")
    lines.append("# @param lookback int 20 Lookback period range=5:60:5")
    lines.append(f"# @strategy stopLossPct {stop_loss}")
    lines.append(f"# @strategy takeProfitPct {take_profit}")
    lines.append("# @strategy entryPct 0.5")
    lines.append("")
    lines.append("df = df.copy()")
    lines.append("")
    lines.append("# Import alpha helpers")
    lines.append("import numpy as np")
    lines.append("import pandas as pd")
    lines.append("")

    # Detect whether the alpha uses factor base imports
    needs_factor_base = "from src.factors.base import" in source_code or "from src.factors.base import (" in source_code

    # Strip the alpha source of its own imports, __alpha_meta__, ALPHA_ID
    stripped_lines: list[str] = []
    in_meta = False
    in_docstring = False
    in_import_cont = False
    for line in source_code.split("\n"):
        s = line.strip()

        # Track __alpha_meta__ dict block
        if s.startswith("__alpha_meta__"):
            in_meta = True
            continue
        if in_meta:
            if s == "}" or s.startswith("}"):
                in_meta = False
            continue

        # Track multi-line import continuations:  from X import (\n  ...\n)
        if in_import_cont:
            if ")" in s:
                in_import_cont = False
            continue

        # Track multi-line docstrings ("""...""" or '''...''')
        if in_docstring:
            if '"""' in s or "'''" in s:
                in_docstring = False
            continue

        if s.startswith('"""') or s.startswith("'''"):
            # Single-line docstring: starts and ends with same triple-quote
            triple = '"""' if s.startswith('"""') else "'''"
            is_single_line = len(s) > len(triple) * 2 and s.endswith(triple)
            if not is_single_line:
                in_docstring = True
            continue

        if s.startswith("from __future__"):
            continue
        if s.startswith("import ") or s.startswith("from "):
            if "(" in s and ")" not in s:
                in_import_cont = True
            continue
        if s.startswith("ALPHA_ID"):
            continue
        if s.startswith("#"):
            continue
        stripped_lines.append(line)

    # Extract compute function body
    func_source = "\n".join(stripped_lines)

    # Inline factor base utility functions if the alpha uses them
    if needs_factor_base:
        lines.append("# ── Inlined from src/factors/base.py ──")
        lines.append(_inline_factor_base())
        lines.append("# ── End inlined factor base ──")
        lines.append("")

    # The compute function takes panel (dict of DataFrames for multi-asset) and
    # returns a wide alpha DataFrame. For single-asset Indicator Lab,
    # we adapt it: panel is a single DataFrame (OHLCV), and we build
    # a single-key dict for the compute function.
    lines.append("# Adapted from Alpha Zoo factor (single-asset mode)")
    lines.append("# The original compute() works on multi-asset panels;")
    lines.append("# here we wrap it with a single-asset dict and extract the result.")
    lines.append("")
    lines.append(f"# {func_source.split(chr(10))[0] if func_source else ''}")
    lines.append("")

    # Build the adapted code
    lines.append("# Build single-asset panel dict for the alpha compute function")
    lines.append('panel = {"close": df["close"], "open": df["open"],')
    lines.append('         "high": df["high"], "low": df["low"],')
    lines.append('         "volume": df["volume"]}')
    lines.append("")
    lines.append("lookback = params.get(\"lookback\", 20)")
    lines.append("")

    # Include the alpha's own helper functions and compute logic
    # We strip the compute function's `def compute` line and re-add it with local adaptation
    # Find compute function and inline its body
    compute_match = re.search(r'def compute\(.*?\n(.*?)(?=\n\S|\Z)', func_source, re.DOTALL)
    if compute_match:
        compute_body = compute_match.group(1)
        # Add helper functions (everything before compute).
        # Imports are already stripped from the source, so pre_compute only
        # contains helper function definitions and blank lines.
        pre_compute = func_source[:compute_match.start()].strip()
        if pre_compute:
            for line in pre_compute.split("\n"):
                lines.append(line)
            if lines and lines[-1] != "":
                lines.append("")
        # Add the adapted compute logic
        lines.append("# Call the alpha's compute logic (adapted for single asset)")
        lines.append("def _compute_local(panel):")

        # Strip the compute function's own docstring from the body
        body_lines = compute_body.split("\n")
        in_body_docstring = False
        for bl in body_lines:
            bs = bl.strip()
            if in_body_docstring:
                if '"""' in bs or "'''" in bs:
                    in_body_docstring = False
                continue
            if bs.startswith('"""') or bs.startswith("'''"):
                triple = '"""' if bs.startswith('"""') else "'''"
                is_single_line = len(bs) > len(triple) * 2 and bs.endswith(triple)
                if is_single_line:
                    continue
                in_body_docstring = True
                continue
            # The body lines already have their original indentation;
            # we only add the standard 4-space indent for the new wrapper function.
            if bs:
                lines.append(f"    {bl}")
            else:
                lines.append("")

        lines.append("")
        lines.append("alpha_values = _compute_local(panel)")
    else:
        # Fallback: inline the entire source
        lines.append("# Inlined alpha source (could not extract compute function)")
        lines.append("_exec_env = {}")
        lines.append('exec("""' + func_source + '""", _exec_env)')
        lines.append('alpha_values = _exec_env["compute"](panel)')

    lines.append("")
    lines.append("# Alpha values are typically a Series or DataFrame — extract the first column if needed")
    lines.append("if isinstance(alpha_values, pd.DataFrame):")
    lines.append("    alpha_values = alpha_values.iloc[:, 0]")
    lines.append("")
    lines.append("# Generate buy/sell signals from alpha")
    lines.append("# Positive alpha → buy, negative alpha → sell")
    lines.append("df[\"buy\"] = alpha_values > 0")
    lines.append("df[\"sell\"] = alpha_values < 0")
    lines.append("")
    lines.append("output = {")
    lines.append('    "name": my_indicator_name,')
    lines.append('    "plots": [')
    lines.append('        {"name": "Alpha Value", "data": alpha_values.tolist(),')
    lines.append('         "color": "#2196F3", "overlay": False},')
    lines.append("    ],")
    lines.append('    "signals": [')
    lines.append('        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(),')
    lines.append('         "color": "#4CAF50"},')
    lines.append('        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(),')
    lines.append('         "color": "#F44336"},')
    lines.append("    ],")
    lines.append("}")

    return "\n".join(lines)


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


from src.lab.storage.repository import extract_code_from_response as _extract_code_from_response  # noqa: F811 — shared utility


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
        {{"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#F44336"}},
        {{"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#4CAF50"}},
    ],
}}
'''
