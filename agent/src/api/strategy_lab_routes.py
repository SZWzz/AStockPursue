"""Strategy Lab HTTP routes — direct access to the original backtest engine.

Routes:
    POST /strategy-lab/backtest     — run strategy against backtest engine
    POST /strategy-lab/save         — save strategy code
    GET  /strategy-lab/list         — list saved strategies
    GET  /strategy-lab/{id}         — get strategy info + code
    POST /strategy-lab/delete/{id}  — delete strategy
    POST /strategy-lab/verify       — verify strategy code (sandbox + quality)
    POST /strategy-lab/generate     — AI-generate strategy code (SSE)
    GET  /strategy-lab/templates    — list strategy templates
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.lab.repository import IndicatorRepository
from src.lab.sandbox import validate_code_safety

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-lab", tags=["strategy-lab"])

_repo: Any = None
_repo_kind: str = ""
_repo_lock = __import__("threading").Lock()


def _get_repo():
    """Get the strategy repository (thread-safe), preferring PG when available."""
    global _repo, _repo_kind
    if _repo is not None:
        return _repo

    with _repo_lock:
        if _repo is not None:
            return _repo

        # Try PG first
        try:
            from src.lab.pg_repository import PgIndicatorRepository
            pg = PgIndicatorRepository()
            pg.list_strategies()  # health check
            _repo = pg
            _repo_kind = "pg"
            logger.info("Strategy Lab using PostgreSQL storage")
            return _repo
        except Exception:
            logger.debug("PG unavailable for Strategy Lab, falling back to filesystem")

        from src.config.paths import get_runtime_root
        _repo = IndicatorRepository(base_dir=get_runtime_root() / "strategies")
        _repo_kind = "file"
        logger.info("Strategy Lab using file-based storage")
        return _repo


# ── Models ──────────────────────────────────────────────────────────────────


class StrategySaveRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=200_000)
    strategy_id: str | None = None
    filename: str | None = None


class StrategyBacktestRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=200_000)
    codes: list[str] = Field(..., min_length=1, max_length=20)
    source: str = Field(default="auto", max_length=20)
    start_date: str = Field(default="2024-01-01")
    end_date: str = Field(default="2025-12-31")
    interval: str = Field(default="1D", pattern=r"^(1m|5m|15m|30m|1H|4H|1D)$")
    initial_cash: float = Field(default=100_000.0, ge=1000.0)
    leverage: float = Field(default=1.0, ge=1.0, le=20.0)
    extra_fields: list[str] | None = None


class BacktestResponse(BaseModel):
    success: bool
    error: str | None = None
    run_id: str | None = None


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/list")
async def list_strategies():
    repo = _get_repo()
    if _repo_kind == "pg":
        items = repo.list_strategies()
        return {
            "strategies": [
                {
                    "id": i["id"],
                    "name": i["name"],
                    "description": i.get("description", ""),
                    "param_count": len(i.get("params", [])),
                    "created_at": i.get("created_at", ""),
                    "updated_at": i.get("updated_at", ""),
                }
                for i in items
            ]
        }
    else:
        items = repo.list()
        return {
            "strategies": [
                {
                    "id": i.id,
                    "name": i.name,
                    "description": i.description,
                    "param_count": i.param_count,
                    "created_at": i.created_at,
                    "updated_at": i.updated_at,
                }
                for i in items
            ]
        }


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    repo = _get_repo()
    if _repo_kind == "pg":
        info = repo.get_strategy(strategy_id)
        if info is None:
            raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
        return {
            "id": info["id"],
            "name": info["name"],
            "description": info.get("description", ""),
            "code": info.get("code", ""),
            "created_at": info.get("created_at", ""),
            "updated_at": info.get("updated_at", ""),
        }
    else:
        info = repo.get(strategy_id)
        if info is None:
            raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
        code = repo.get_code(strategy_id) or ""
        return {
            "id": info.id,
            "name": info.name,
            "description": info.description,
            "code": code,
            "created_at": info.created_at,
            "updated_at": info.updated_at,
        }


@router.post("/save")
async def save_strategy(req: StrategySaveRequest):
    # Validate code safety before saving
    is_safe, err = validate_code_safety(req.code)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Code safety check failed: {err}")

    repo = _get_repo()
    try:
        if _repo_kind == "pg":
            info = repo.save_strategy(code=req.code, strategy_id=req.strategy_id)
            return {
                "id": info["id"],
                "name": info["name"],
                "description": info.get("description", ""),
                "created_at": info.get("created_at", ""),
                "updated_at": info.get("updated_at", ""),
            }
        else:
            info = repo.save(code=req.code, indicator_id=req.strategy_id, filename=req.filename)
            return {
                "id": info.id,
                "name": info.name,
                "description": info.description,
                "created_at": info.created_at,
                "updated_at": info.updated_at,
            }
    except Exception as e:
        logger.exception("Failed to save strategy")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete/{strategy_id}")
async def delete_strategy(strategy_id: str):
    repo = _get_repo()
    if _repo_kind == "pg":
        if repo.delete_strategy(strategy_id):
            return {"ok": True}
    else:
        if repo.delete(strategy_id):
            return {"ok": True}
    raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")


@router.post("/backtest", response_model=BacktestResponse)
async def backtest_strategy(req: StrategyBacktestRequest):
    from src.lab.strategy_backtest_bridge import run_strategy_backtest

    try:
        result = run_strategy_backtest(
            code=req.code,
            codes=req.codes,
            start_date=req.start_date,
            end_date=req.end_date,
            source=req.source,
            interval=req.interval,
            initial_cash=req.initial_cash,
            leverage=req.leverage,
            extra_fields=req.extra_fields,
        )
        return BacktestResponse(**result)
    except Exception as e:
        logger.exception("Strategy backtest failed")
        return BacktestResponse(success=False, error=str(e))


@router.get("/template/default")
async def get_default_template():
    from src.lab.strategy_backtest_bridge import DEFAULT_SIGNAL_ENGINE_TEMPLATE

    return {"code": DEFAULT_SIGNAL_ENGINE_TEMPLATE}


# ── Verify ──────────────────────────────────────────────────────────────────


class StrategyVerifyRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=200_000)


@router.post("/verify")
async def verify_strategy(req: StrategyVerifyRequest):
    """Verify strategy code: static analysis + basic sandbox check."""
    code = req.code

    quality_hints: list[dict[str, Any]] = []

    # Check for critical issues
    if not code or not code.strip():
        quality_hints.append({"severity": "error", "code": "EMPTY_CODE"})
        return {
            "success": False,
            "error": "Code is empty",
            "quality_hints": quality_hints,
            "params": [],
            "has_generate_method": False,
            "has_signal_map_return": False,
            "symbol_count": 0,
        }

    # Check for SignalEngine class
    has_class = "class SignalEngine" in code
    if not has_class:
        quality_hints.append({"severity": "error", "code": "MISSING_CLASS"})

    # Check for generate method
    has_generate = "def generate" in code
    if not has_generate:
        quality_hints.append({"severity": "error", "code": "MISSING_GENERATE_METHOD"})

    # Check for signal_map return
    has_signal_map = "signal_map" in code
    if not has_signal_map:
        quality_hints.append({"severity": "warn", "code": "NO_SIGNAL_MAP_RETURN"})

    # Check for pandas/numpy imports
    if "import pandas" not in code and "from pandas" not in code:
        quality_hints.append({"severity": "warn", "code": "MISSING_PANDAS_IMPORT"})

    # Try sandbox execution
    try:
        exec_result = _execute_strategy_code(code)
    except Exception as e:
        logger.warning(f"Strategy sandbox execution failed: {e}")
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
            "quality_hints": quality_hints,
            "params": [],
            "has_generate_method": has_generate and has_class,
            "has_signal_map_return": has_signal_map,
            "symbol_count": 0,
        }

    return {
        "success": exec_result.get("success", False),
        "error": exec_result.get("error"),
        "quality_hints": quality_hints + exec_result.get("quality_hints", []),
        "params": exec_result.get("params", []),
        "has_generate_method": has_generate and has_class,
        "has_signal_map_return": has_signal_map,
        "symbol_count": exec_result.get("symbol_count", 0),
    }


def _execute_strategy_code(code: str) -> dict[str, Any]:
    """Try to instantiate SignalEngine and call generate with mock data."""
    import numpy as np
    import pandas as pd

    # Generate mock data for 3 symbols
    symbols = ["600519.SH", "000001.SZ", "AAPL"]
    data_map: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        np.random.seed(hash(sym) % 2**32)
        close = 100.0 * (1 + np.random.randn(100).cumsum() * 0.02)
        df = pd.DataFrame(
            {
                "open": close * (1 + np.random.randn(100) * 0.005),
                "high": close * (1 + abs(np.random.randn(100) * 0.01)),
                "low": close * (1 - abs(np.random.randn(100) * 0.01)),
                "close": close,
                "volume": abs(np.random.randn(100)) * 10000 + 50000,
            },
            index=dates,
        )
        data_map[sym] = df

    # Sandboxed execution
    exec_env: dict[str, Any] = {
        "__builtins__": {
            "print": print,
            "len": len,
            "range": range,
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "enumerate": enumerate,
            "zip": zip,
            "isinstance": isinstance,
            "hasattr": hasattr,
            "getattr": getattr,
            "setattr": setattr,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "pd": pd,
            "np": np,
            "ImportError": ImportError,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "IndexError": IndexError,
            "Exception": Exception,
        },
    }

    try:
        exec(code, exec_env)

        if "SignalEngine" not in exec_env:
            return {
                "success": False,
                "error": "SignalEngine class not found after execution",
                "symbol_count": 0,
            }

        engine_class = exec_env["SignalEngine"]
        try:
            engine = engine_class()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to instantiate SignalEngine: {str(e)}",
                "symbol_count": 0,
            }

        if not hasattr(engine, "generate"):
            return {
                "success": False,
                "error": "SignalEngine has no generate method",
                "symbol_count": 0,
            }

        signal_map = engine.generate(data_map)
        if not isinstance(signal_map, dict):
            return {
                "success": False,
                "error": "generate() did not return a dict",
                "symbol_count": 0,
            }

        symbol_count = len(signal_map)

        # Check signal values are in range
        quality_hints: list[dict[str, Any]] = []
        for sym, sig in signal_map.items():
            if hasattr(sig, "max") and hasattr(sig, "min"):
                try:
                    sig_max = float(sig.max())
                    sig_min = float(sig.min())
                    if sig_max > 1.0 or sig_min < -1.0:
                        quality_hints.append({
                            "severity": "warn",
                            "code": "SIGNAL_OUT_OF_RANGE",
                            "params": {"symbol": sym, "max": round(sig_max, 3), "min": round(sig_min, 3)},
                        })
                        break
                except Exception:
                    pass

        return {
            "success": True,
            "error": None,
            "quality_hints": quality_hints,
            "symbol_count": symbol_count,
        }

    except SyntaxError as e:
        return {
            "success": False,
            "error": f"Syntax error: {str(e)}",
            "symbol_count": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Runtime error: {str(e)}",
            "symbol_count": 0,
        }


# ── AI Generate (SSE) ───────────────────────────────────────────────────────


class StrategyGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    style: str = Field(default="momentum", pattern=r"^(trend|reversal|momentum|volume|volatility|multi_factor|custom)$")


@router.post("/generate")
async def generate_strategy(req: StrategyGenerateRequest, request: Request):
    """AI-generate strategy code via SSE streaming."""

    async def event_stream():
        try:
            if await request.is_disconnected():
                return

            # Try LLM agent
            try:
                from src.agent.loop import run_agent_sync

                system_prompt = _build_strategy_generation_prompt(req.prompt, req.style)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: run_agent_sync(system_prompt, max_turns=3),
                )

                if result:
                    generated = _extract_code_from_response(result)
                    if generated:
                        yield f"data: {json.dumps({'type': 'code', 'content': generated})}\n\n"
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        return

            except ImportError:
                pass
            except Exception as e:
                logger.exception("LLM strategy generation failed")

            # Fallback template
            template = _build_strategy_template(req.style)
            yield f"data: {json.dumps({'type': 'code', 'content': template})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

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


def _build_strategy_generation_prompt(user_prompt: str, style: str) -> str:
    return (
        "You are an expert quantitative trader. Generate a complete Python SignalEngine "
        "class for the AStockPursue Strategy Lab.\n\n"
        "The code MUST follow this contract:\n"
        "1. Define a class SignalEngine with an __init__ method (optional params)\n"
        "2. Implement generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]\n"
        "3. data_map keys are symbol codes, values are OHLCV DataFrames (open/high/low/close/volume)\n"
        "4. Return signal_map where values are pd.Series with values in [-1, 1]\n"
        "5. Positive values = long, negative = short, 0 = no position\n"
        "6. Include pandas and numpy imports\n\n"
        f"User request: {user_prompt}\n"
        f"Style: {style}\n\n"
        "Return ONLY the Python code, no explanations."
    )


from src.lab.repository import extract_code_from_response as _extract_code_from_response  # noqa: F811 — shared utility


def _build_strategy_template(style: str) -> str:
    if style == "trend":
        return '''"""
Trend Following Signal Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Dual MA crossover trend strategy."""

    def __init__(self):
        self.fast = 10
        self.slow = 30

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.slow:
                continue
            fast_ma = df["close"].rolling(self.fast).mean()
            slow_ma = df["close"].rolling(self.slow).mean()
            signal = pd.Series(0.0, index=df.index)
            golden = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
            death = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
            signal[golden.fillna(False)] = 1.0
            signal[death.fillna(False)] = -1.0
            signal_map[code] = signal

        return signal_map
'''
    elif style == "reversal":
        return '''"""
Mean Reversion Signal Engine — RSI-based.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """RSI mean reversion strategy."""

    def __init__(self):
        self.period = 14
        self.oversold = 30
        self.overbought = 70

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.period:
                continue
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            avg_gain = gain.rolling(self.period).mean()
            avg_loss = loss.rolling(self.period).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100.0 - (100.0 / (1.0 + rs))

            sig = pd.Series(0.0, index=df.index)
            sig[rsi < self.oversold] = 0.8
            sig[rsi > self.overbought] = -0.8
            signal_map[code] = sig

        return signal_map
'''
    elif style == "multi_factor":
        return '''"""
Multi-Factor Signal Engine — momentum + volatility.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Combined momentum and volatility factors."""

    def __init__(self):
        self.mom_period = 20
        self.vol_period = 20

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.vol_period:
                continue
            mom = df["close"].pct_change(self.mom_period).iloc[-1]
            returns = df["close"].pct_change().dropna()
            recent_vol = returns.iloc[-self.vol_period:].std()
            hist_vol = returns.std()
            vol_signal = (hist_vol - recent_vol) / hist_vol if hist_vol > 0 else 0
            composite = 0.6 * np.clip(mom * 5, -1, 1) + 0.4 * np.clip(vol_signal, -1, 1)
            sig = pd.Series(composite, index=df.index)
            signal_map[code] = sig

        return signal_map
'''
    else:
        return '''"""
Momentum Signal Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Cross-sectional momentum strategy."""

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < 20:
                continue
            ret = df["close"].pct_change(5).iloc[-1]
            signal = pd.Series(0.0, index=df.index)
            if ret > 0:
                signal.iloc[-1] = 0.5
            else:
                signal.iloc[-1] = -0.5
            signal_map[code] = signal

        return signal_map
'''


# ── Templates ───────────────────────────────────────────────────────────────


@router.get("/templates")
async def list_strategy_templates():
    """List all available strategy templates with metadata."""
    return {
        "templates": [
            {
                "key": "ma_crossover",
                "name": "Dual MA Crossover",
                "description": "Classic dual moving average crossover — go long on golden cross, short on death cross.",
                "category": "trend",
                "difficulty": "beginner",
                "tags": ["MA", "crossover", "trend"],
            },
            {
                "key": "macd_trend",
                "name": "MACD Trend Following",
                "description": "MACD line vs signal line crossover with histogram confirmation.",
                "category": "trend",
                "difficulty": "beginner",
                "tags": ["MACD", "trend", "momentum"],
            },
            {
                "key": "supertrend",
                "name": "SuperTrend ATR",
                "description": "ATR-based trailing stop — flip long/short when price crosses the SuperTrend band.",
                "category": "trend",
                "difficulty": "intermediate",
                "tags": ["ATR", "trailing", "trend"],
            },
            {
                "key": "rsi_reversal",
                "name": "RSI Mean Reversion",
                "description": "Buy when RSI drops below oversold threshold, sell when above overbought.",
                "category": "reversal",
                "difficulty": "beginner",
                "tags": ["RSI", "mean-reversion", "oscillator"],
            },
            {
                "key": "bollinger_reversal",
                "name": "Bollinger Band Reversal",
                "description": "Fade extremes — go long at lower band, short at upper band with volatility-adjusted sizing.",
                "category": "reversal",
                "difficulty": "beginner",
                "tags": ["Bollinger", "mean-reversion", "volatility"],
            },
            {
                "key": "kdj_extreme",
                "name": "KDJ Extreme Zones",
                "description": "KDJ indicator overbought/oversold with golden/death cross confirmation.",
                "category": "reversal",
                "difficulty": "intermediate",
                "tags": ["KDJ", "oscillator", "extreme"],
            },
            {
                "key": "grid_trading",
                "name": "Grid Trading",
                "description": "Place buy/sell at predetermined price intervals — profit from sideways markets.",
                "category": "grid",
                "difficulty": "intermediate",
                "tags": ["grid", "range", "automation"],
            },
            {
                "key": "pair_arbitrage",
                "name": "Pairs Trading",
                "description": "Statistical arbitrage — trade the spread between two correlated assets.",
                "category": "arbitrage",
                "difficulty": "advanced",
                "tags": ["pairs", "spread", "cointegration"],
            },
            {
                "key": "multi_factor_momentum",
                "name": "Multi-Factor Momentum",
                "description": "Combine momentum, volatility, and volume factors with IC-weighted blend.",
                "category": "multiFactor",
                "difficulty": "advanced",
                "tags": ["multi-factor", "momentum", "IC"],
            },
            {
                "key": "risk_parity",
                "name": "Risk Parity Portfolio",
                "description": "Allocate capital inversely proportional to asset volatility.",
                "category": "multiFactor",
                "difficulty": "advanced",
                "tags": ["risk-parity", "portfolio", "allocation"],
            },
        ]
    }
