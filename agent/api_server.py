#!/usr/bin/env python3
"""AStockPursue API Server - RESTful API for finance research and backtesting.

V5: ReAct Agent + async /run + CORS env + SSE tool events.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import signal
import time
import csv
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Security, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console

from src.ui_services import build_run_analysis, load_run_context

# UTF-8 on Windows
import sys as _sys
for _s in ("stdout", "stderr"):
    _r = getattr(getattr(_sys, _s, None), "reconfigure", None)
    if callable(_r):
        _r(encoding="utf-8", errors="replace")

RUNS_DIR = Path(__file__).resolve().parent / "runs"
SESSIONS_DIR = Path(__file__).resolve().parent / "sessions"
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
AGENT_DIR = Path(__file__).resolve().parent
ENV_PATH = AGENT_DIR / ".env"
ENV_EXAMPLE_PATH = AGENT_DIR / ".env.example"

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB

# Rich console for colored logs
console = Console()


# ============================================================================
# Pydantic Models
# ============================================================================

class Artifact(BaseModel):
    """Artifact file metadata."""
    name: str = Field(..., description="File name")
    path: str = Field(..., description="File path")
    type: str = Field(..., description="File type: csv, json, txt, etc.")
    size: int = Field(..., description="Size in bytes")
    exists: bool = Field(..., description="Whether the file exists")


class BacktestMetrics(BaseModel):
    """Backtest summary metrics."""
    model_config = {"extra": "allow"}

    final_value: float = Field(..., description="Ending portfolio value")
    total_return: float = Field(..., description="Total return")
    annual_return: float = Field(..., description="Annualized return")
    max_drawdown: float = Field(..., description="Max drawdown")
    sharpe: float = Field(..., description="Sharpe ratio")
    win_rate: float = Field(..., description="Win rate")
    trade_count: int = Field(..., description="Number of trades")



class RAGSelection(BaseModel):
    """RAG routing result."""
    selected_api: str = Field(..., description="Selected API code")
    selected_name: str = Field(..., description="Selected API name")
    selected_score: float = Field(..., description="Match score")


class RunInfo(BaseModel):
    """Compact run row for list views."""
    run_id: str
    status: str
    created_at: str
    prompt: Optional[str] = None
    total_return: Optional[float] = None
    sharpe: Optional[float] = None
    codes: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class RunResponse(BaseModel):
    """API response payload for a single run."""

    status: str = Field(..., description="Run status: success, failed, aborted")
    run_id: str = Field(..., description="Run identifier")
    elapsed_seconds: float = Field(..., description="Execution time in seconds")
    reason: Optional[str] = Field(None, description="Failure reason when available")

    planner_output: Optional[Dict[str, Any]] = Field(None, description="Planner output")
    strategy_spec: Optional[Dict[str, Any]] = Field(None, description="Strategy specification")
    rag_selection: Optional[RAGSelection] = Field(None, description="Selected RAG metadata")

    metrics: Optional[BacktestMetrics] = Field(None, description="Backtest metrics")
    artifacts: List[Artifact] = Field(default_factory=list, description="Run artifacts")
    run_card: Optional[Dict[str, Any]] = Field(None, description="Trust Layer run card payload")

    equity_curve: Optional[List[Dict[str, Any]]] = Field(None, description="Equity preview")
    trade_log: Optional[List[Dict[str, Any]]] = Field(None, description="Trade preview")

    artifacts_equity_csv: Optional[List[Dict[str, Any]]] = Field(None, description="Full equity rows")
    artifacts_metrics_csv: Optional[List[Dict[str, Any]]] = Field(None, description="Full metrics rows")
    artifacts_trades_csv: Optional[List[Dict[str, Any]]] = Field(None, description="Full trade rows")
    validation: Optional[Dict[str, Any]] = Field(None, description="Statistical validation results")

    run_directory: str = Field(..., description="Run directory path")
    run_stage: Optional[str] = Field(None, description="UI-facing run stage")
    run_context: Optional[Dict[str, Any]] = Field(None, description="Normalized request context")
    price_series: Optional[Dict[str, List[Dict[str, Any]]]] = Field(None, description="Grouped OHLC series")
    indicator_series: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]] = Field(
        None,
        description="Grouped indicator overlays",
    )
    trade_markers: Optional[List[Dict[str, Any]]] = Field(None, description="Trade markers for charts")
    run_logs: Optional[List[Dict[str, Any]]] = Field(None, description="Structured stdout/stderr lines")


class HealthResponse(BaseModel):
    """Health check payload."""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    timestamp: str = Field(..., description="Server timestamp")


class LLMProviderOption(BaseModel):
    """Supported LLM provider metadata for the settings UI."""

    name: str
    label: str
    api_key_env: Optional[str] = None
    base_url_env: str
    default_model: str
    default_base_url: str
    api_key_required: bool = True
    auth_type: str = "api_key"
    login_command: Optional[str] = None


class LLMSettingsResponse(BaseModel):
    """Current LLM runtime settings."""

    provider: str
    model_name: str
    base_url: str
    api_key_env: Optional[str] = None
    api_key_configured: bool
    api_key_hint: Optional[str] = None
    api_key_required: bool
    temperature: float
    timeout_seconds: int
    max_retries: int
    reasoning_effort: str
    env_path: str
    providers: List[LLMProviderOption]


class UpdateLLMSettingsRequest(BaseModel):
    """Update LLM settings persisted to agent/.env."""

    provider: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1)
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    clear_api_key: bool = False
    temperature: float = 0.0
    timeout_seconds: int = Field(120, ge=1, le=3600)
    max_retries: int = Field(2, ge=0, le=20)
    reasoning_effort: Optional[str] = None


class DataSourceSettingsResponse(BaseModel):
    """Current data source credential settings."""

    tushare_token_configured: bool
    tushare_token_hint: Optional[str] = None
    okx_api_key_configured: bool = False
    okx_secret_key_configured: bool = False
    okx_passphrase_configured: bool = False
    twelvedata_api_key_configured: bool = False
    finnhub_api_key_configured: bool = False
    tiingo_api_key_configured: bool = False
    akshare_available: bool = False
    akshare_version: str = ""
    yfinance_available: bool = False
    tencent_available: bool = False
    ccxt_available: bool = False
    coingecko_available: bool = False
    futu_available: bool = False
    global_indices_available: bool = False
    commodities_available: bool = False
    env_path: str


class UpdateDataSourceSettingsRequest(BaseModel):
    """Update data source credentials (stored encrypted in DB)."""

    tushare_token: Optional[str] = None
    clear_tushare_token: bool = False
    okx_api_key: Optional[str] = None
    okx_secret_key: Optional[str] = None
    okx_passphrase: Optional[str] = None
    clear_okx: bool = False
    twelvedata_api_key: Optional[str] = None
    clear_twelvedata: bool = False
    finnhub_api_key: Optional[str] = None
    clear_finnhub: bool = False
    tiingo_api_key: Optional[str] = None
    clear_tiingo: bool = False


# ---- V4 Session Models ----

class CreateSessionRequest(BaseModel):
    """Create session request body."""
    title: str = Field("", description="Session title")
    config: Optional[Dict[str, Any]] = Field(None, description="Session config")


class SessionResponse(BaseModel):
    """Session record."""
    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    last_attempt_id: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Send chat message: natural-language strategy description."""
    content: str = Field(..., description="Natural language strategy description", min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    """Stored chat message."""
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str
    linked_attempt_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None



# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="AStockPursue API",
    description="AStockPursue API: natural-language finance research, backtesting, and swarm workflows",
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]


def _parse_cors_origins(raw: Optional[str]) -> List[str]:
    """Parse CORS origins and reject credentialed wildcard configuration.

    Args:
        raw: Comma-separated CORS origins from ``CORS_ORIGINS``. ``None`` or a
            blank value uses the loopback development defaults.

    Returns:
        Explicit CORS origins accepted by the API server.

    Raises:
        RuntimeError: If a wildcard origin is configured while credentials are
            enabled.
    """
    if raw is None or not raw.strip():
        return list(_DEFAULT_CORS_ORIGINS)
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS='*' is not allowed while credentials are enabled; "
            "configure explicit Web UI origins instead."
        )
    return origins


# CORS: override with CORS_ORIGINS (comma-separated explicit origins)
_CORS_ORIGINS = _parse_cors_origins(os.getenv("CORS_ORIGINS"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _run_startup_preflight() -> None:
    """Run preflight checks on server startup."""
    from src.preflight import run_preflight

    run_preflight(console)

    # Initialise PostgreSQL connection pool and auto-migrate
    try:
        from src.db import init_pool, init_database
        init_pool()
        init_database()
        from src.db.pool import run_paper_trading_migration
        run_paper_trading_migration()
        from papertrade.repository import PaperTradeRepository
        PaperTradeRepository().mark_stopped_on_startup()
    except Exception as e:
        console.print(f"[yellow]PG init skipped:[/yellow] {e}")

    # Load default user's data-source tokens into os.environ so all
    # endpoints (including those that don't call load_user_config) can
    # find tokens like TUSHARE_TOKEN.
    try:
        from src.auth.user_config import load_user_config
        load_user_config(1)
        console.print("[green]Default user data-source tokens loaded[/green]")
    except Exception as e:
        console.print(f"[yellow]Default user tokens not loaded:[/yellow] {e}")

    # Initialise paper trading scheduler
    try:
        from papertrade.scheduler import PaperTradingScheduler
        app.state.paper_trading_scheduler = PaperTradingScheduler()
        console.print("[green]Paper trading scheduler initialised[/green]")
    except Exception as e:
        console.print(f"[yellow]Paper trading scheduler init skipped:[/yellow] {e}")


# ============================================================================
# Authentication
# ============================================================================

_security = HTTPBearer(auto_error=False)
_SHELL_TOOLS_ENV = "ASTOCKPURSUE_ENABLE_SHELL_TOOLS"
_DOCKER_LOOPBACK_ENV = "ASTOCKPURSUE_TRUST_DOCKER_LOOPBACK"


def _load_ds_tokens(user_id: int) -> None:
    try:
        from src.auth.user_config import load_user_config
        load_user_config(user_id)
    except Exception:
        pass


async def require_auth(
    request: Request,
    cred: Optional[HTTPAuthorizationCredentials] = Security(_security),
    jwt: Optional[str] = Query(None),
) -> dict:
    """JWT login. Token from Authorization header or ?jwt= query param.
    Returns the decoded JWT payload dict: {user_id, username, role, token_version}.
    Local loopback clients are exempt when no API_AUTH_KEY is configured (dev mode).

    Also loads per-user data-source tokens (TUSHARE_TOKEN, etc.) into os.environ.
    """
    # Dev mode: allow local loopback / test clients without auth
    api_key = os.getenv("API_AUTH_KEY", "")
    if not api_key and _is_local_client(request):
        _load_ds_tokens(1)
        return {"user_id": 1, "username": "dev", "role": "admin", "token_version": 0}

    token = (cred.credentials if cred and cred.credentials else "") or (jwt or "")
    if token:
        try:
            from src.auth.jwt import verify_token
            payload = verify_token(token)
            if payload:
                _load_ds_tokens(payload.get("user_id", 1))
                return payload
        except ImportError:
            pass

    raise HTTPException(status_code=401, detail="Login required")


def _is_local_client(request: Request) -> bool:
    """Return whether the request originates from a loopback client."""
    host = request.client.host if request.client else ""
    if host in {"localhost", "testclient"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.is_loopback:
        return True
    return _trusted_docker_loopback_ip(ip)


def _env_flag_enabled(name: str) -> bool:
    """Return whether a boolean environment flag is enabled."""
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _default_gateway_ips() -> set[ipaddress.IPv4Address]:
    """Return IPv4 default gateway addresses from Linux procfs."""
    gateways: set[ipaddress.IPv4Address] = set()
    try:
        lines = Path("/proc/net/route").read_text(encoding="utf-8").splitlines()
    except OSError:
        return gateways

    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 3 or fields[1] != "00000000":
            continue
        try:
            raw = int(fields[2], 16).to_bytes(4, byteorder="little")
            gateways.add(ipaddress.IPv4Address(raw))
        except ValueError:
            continue
    return gateways


def _trusted_docker_loopback_ip(ip: ipaddress._BaseAddress) -> bool:
    """Return whether an IP is the trusted Docker host gateway.

    Docker Desktop presents host requests to a container as the bridge gateway
    instead of 127.0.0.1. This escape hatch is safe only when the published
    port is bound to host loopback, so the official compose file enables it
    together with a 127.0.0.1 port binding.
    """
    if not isinstance(ip, ipaddress.IPv4Address):
        return False
    if not _env_flag_enabled(_DOCKER_LOOPBACK_ENV):
        return False
    return ip in _default_gateway_ips()


def _env_shell_tools_enabled() -> bool:
    """Return whether server-side shell tools are explicitly enabled."""
    return _env_flag_enabled(_SHELL_TOOLS_ENV)


def _shell_tools_enabled_for_request(request: Request) -> bool:
    """Return whether this API request may expose shell tools to the agent."""
    return _is_local_client(request) or _env_shell_tools_enabled()


    raise HTTPException(status_code=401, detail="Login required")


# ============================================================================
# Workflow Factory
# ============================================================================

# ============================================================================
# Helper Functions
# ============================================================================

LLM_PROVIDER_CONFIG_PATH = AGENT_DIR / "src" / "providers" / "llm_providers.json"


def _load_llm_providers() -> List[LLMProviderOption]:
    """Load provider metadata from JSON so additions stay data-driven."""
    try:
        raw = json.loads(LLM_PROVIDER_CONFIG_PATH.read_text(encoding="utf-8"))
        providers = [LLMProviderOption(**item) for item in raw]
    except Exception as exc:
        raise RuntimeError(f"Failed to load LLM provider config: {LLM_PROVIDER_CONFIG_PATH}") from exc

    seen: set[str] = set()
    for provider in providers:
        if provider.name in seen:
            raise RuntimeError(f"Duplicate LLM provider name: {provider.name}")
        seen.add(provider.name)
    if not providers:
        raise RuntimeError("LLM provider config must not be empty")
    return providers


LLM_PROVIDERS = _load_llm_providers()
LLM_PROVIDER_BY_NAME = {provider.name: provider for provider in LLM_PROVIDERS}
LLM_REASONING_EFFORTS = {"", "low", "medium", "high", "max"}
LLM_API_KEY_PLACEHOLDERS = {"", "sk-or-v1-your-key-here", "sk-xxx", "xxx", "gsk_xxx"}
TUSHARE_TOKEN_PLACEHOLDERS = {"", "your-tushare-token"}


def _ensure_agent_env_file() -> Path:
    """Ensure the project-local agent/.env exists."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text("# Created by AStockPursue Web UI settings.\n", encoding="utf-8")
    return ENV_PATH


def _strip_env_value(value: str) -> str:
    """Remove basic dotenv quotes and inline comments."""
    value = value.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def _read_env_values(path: Path) -> Dict[str, str]:
    """Read active KEY=value entries from a dotenv file."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = _strip_env_value(value)
    return values


def _read_settings_env_values() -> Dict[str, str]:
    """Read settings without creating agent/.env.

    Prefer the user's active agent/.env. If it does not exist yet, fall back to
    agent/.env.example for display defaults only.
    """
    if ENV_PATH.exists():
        return _read_env_values(ENV_PATH)
    if ENV_EXAMPLE_PATH.exists():
        return _read_env_values(ENV_EXAMPLE_PATH)
    return {}


def _project_relative_path(path: Path) -> str:
    """Return a project-relative display path without leaking an absolute path."""
    try:
        return path.resolve().relative_to(AGENT_DIR.parent.resolve()).as_posix()
    except ValueError:
        return path.name


def _format_env_value(value: str) -> str:
    """Format a dotenv value without allowing multiline injection."""
    if "\n" in value or "\r" in value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Environment values cannot contain newlines")
    value = value.strip()
    if not value:
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _write_env_values(path: Path, updates: Dict[str, str]) -> None:
    """Upsert active dotenv values while preserving comments and ordering."""
    _ensure_agent_env_file()
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    for index, raw in enumerate(lines):
        stripped = raw.lstrip()
        is_comment = stripped.startswith("#")
        candidate = stripped[1:].lstrip() if is_comment else stripped
        if "=" not in candidate:
            continue
        key = candidate.split("=", 1)[0].strip()
        if key in updates and key not in seen:
            lines[index] = f"{key}={_format_env_value(updates[key])}"
            seen.add(key)
    missing = [key for key in updates if key not in seen]
    if missing:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Updated from Web UI")
        for key in missing:
            lines.append(f"{key}={_format_env_value(updates[key])}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _is_configured_secret(value: str, placeholders: set[str]) -> bool:
    """Return True when a secret is set and not a documented placeholder."""
    normalized = value.strip().strip('"').strip("'")
    if not normalized:
        return False
    return normalized.lower() not in {placeholder.lower() for placeholder in placeholders}


def _coerce_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_llm_settings_response(values: Optional[Dict[str, str]] = None, *, db_config: Optional[dict] = None) -> LLMSettingsResponse:
    """Build the public settings payload, preferring DB config over dotenv."""
    env_values = values if values is not None else _read_settings_env_values()
    db = db_config or {}

    provider_name = db.get("provider") or env_values.get("LANGCHAIN_PROVIDER", "openai").strip().lower()
    provider = LLM_PROVIDER_BY_NAME.get(provider_name, LLM_PROVIDER_BY_NAME["openai"])

    api_key = db.get("api_key", "") if db else env_values.get(provider.api_key_env or "", "")
    api_key_configured = bool(api_key) and _is_configured_secret(api_key, LLM_API_KEY_PLACEHOLDERS)
    api_key_hint = None
    if provider.auth_type == "oauth":
        try:
            from src.providers.openai_codex import get_openai_codex_login_status
            token = get_openai_codex_login_status()
        except Exception:
            token = None
        api_key_configured = bool(token)
        api_key_hint = None

    model_name = db.get("model") or env_values.get("LANGCHAIN_MODEL_NAME", provider.default_model)
    base_url = db.get("base_url") or env_values.get(provider.base_url_env, provider.default_base_url)
    temperature = db.get("temperature") if db.get("temperature") is not None else _coerce_float(env_values.get("LANGCHAIN_TEMPERATURE", "0.0"), 0.0)
    timeout_seconds = db.get("timeout_seconds") if db.get("timeout_seconds") is not None else _coerce_int(env_values.get("TIMEOUT_SECONDS", "120"), 120)
    max_retries = db.get("max_retries") if db.get("max_retries") is not None else _coerce_int(env_values.get("MAX_RETRIES", "2"), 2)
    reasoning_effort = db.get("reasoning_effort") if "reasoning_effort" in db else env_values.get("LANGCHAIN_REASONING_EFFORT", "").strip().lower()

    return LLMSettingsResponse(
        provider=provider.name,
        model_name=model_name,
        base_url=base_url,
        api_key_env=provider.api_key_env,
        api_key_configured=api_key_configured,
        api_key_hint=api_key_hint,
        api_key_required=provider.api_key_required,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        reasoning_effort=reasoning_effort,
        env_path=_project_relative_path(ENV_PATH),
        providers=LLM_PROVIDERS,
    )


def _build_data_source_settings_response(values: Optional[Dict[str, str]] = None, *, token: Optional[str] = None,
                                          okx_api_key: Optional[str] = None, okx_secret_key: Optional[str] = None,
                                          okx_passphrase: Optional[str] = None,
                                          twelvedata_api_key: Optional[str] = None,
                                          finnhub_api_key: Optional[str] = None,
                                          tiingo_api_key: Optional[str] = None) -> DataSourceSettingsResponse:
    """Build the public data source settings payload."""
    env_values = values if values is not None else _read_settings_env_values()
    if token is None:
        token = env_values.get("TUSHARE_TOKEN", "")
    token_configured = _is_configured_secret(token, TUSHARE_TOKEN_PLACEHOLDERS)
    okx_key_configured = bool(okx_api_key) if okx_api_key is not None else False
    okx_secret_configured = bool(okx_secret_key) if okx_secret_key is not None else False
    okx_pass_configured = bool(okx_passphrase) if okx_passphrase is not None else False
    td_configured = bool(twelvedata_api_key) if twelvedata_api_key is not None else False
    fh_configured = bool(finnhub_api_key) if finnhub_api_key is not None else False
    ti_configured = bool(tiingo_api_key) if tiingo_api_key is not None else False
    akshare_available = False
    akshare_version = ""
    try:
        import akshare
        akshare_available = True
        akshare_version = getattr(akshare, "__version__", "")
    except ImportError:
        pass

    # Free / no-auth loader availability
    yf_ok = tencent_ok = ccxt_ok = cg_ok = futu_ok = gi_ok = comm_ok = False
    try:
        from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
        _ensure_registered()
        for name, cls in LOADER_REGISTRY.items():
            try:
                inst = cls()
                avail = inst.is_available() if hasattr(inst, "is_available") else True
            except Exception:
                avail = False
            if name == "yfinance": yf_ok = avail
            elif name == "tencent": tencent_ok = avail
            elif name == "ccxt": ccxt_ok = avail
            elif name == "coingecko": cg_ok = avail
            elif name == "futu": futu_ok = avail
            elif name == "global_indices": gi_ok = avail
            elif name == "commodities": comm_ok = avail
    except Exception:
        pass

    return DataSourceSettingsResponse(
        tushare_token_configured=token_configured,
        tushare_token_hint=None,
        okx_api_key_configured=okx_key_configured,
        okx_secret_key_configured=okx_secret_configured,
        okx_passphrase_configured=okx_pass_configured,
        twelvedata_api_key_configured=td_configured,
        finnhub_api_key_configured=fh_configured,
        tiingo_api_key_configured=ti_configured,
        akshare_available=akshare_available,
        akshare_version=akshare_version,
        yfinance_available=yf_ok,
        tencent_available=tencent_ok,
        ccxt_available=ccxt_ok,
        coingecko_available=cg_ok,
        futu_available=futu_ok,
        global_indices_available=gi_ok,
        commodities_available=comm_ok,
        env_path=_project_relative_path(ENV_PATH),
    )


def _read_user_ds_config(user_id: int) -> dict:
    """Read and decrypt a user's data_source_config from the database."""
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import decrypt_config, _SENSITIVE_DS_FIELDS
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data_source_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    return decrypt_config(dict(row[0]), _SENSITIVE_DS_FIELDS)
    except Exception:
        pass
    return {}


def _write_user_ds_config(user_id: int, updates: dict) -> bool:
    """Merge updates into a user's data_source_config, encrypt, and save to DB."""
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import encrypt_config, _SENSITIVE_DS_FIELDS
        import json

        # Read existing config, merge updates
        current = {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data_source_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    current = dict(row[0])

        merged = {**current, **updates}
        encrypted = encrypt_config(merged, _SENSITIVE_DS_FIELDS)
        payload = json.dumps(encrypted)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_users SET data_source_config = %s WHERE id = %s",
                    (payload, user_id),
                )
            conn.commit()
        return True
    except Exception:
        return False


def _read_user_llm_config(user_id: int) -> dict:
    """Read and decrypt a user's llm_config from the database."""
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import decrypt_config, _SENSITIVE_LLM_FIELDS
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT llm_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    return decrypt_config(dict(row[0]), _SENSITIVE_LLM_FIELDS)
    except Exception:
        pass
    return {}


def _write_user_llm_config(user_id: int, updates: dict) -> bool:
    """Merge updates into a user's llm_config, encrypt, and save to DB."""
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import encrypt_config, _SENSITIVE_LLM_FIELDS
        import json

        current = {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT llm_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    current = dict(row[0])

        merged = {**current, **updates}
        encrypted = encrypt_config(merged, _SENSITIVE_LLM_FIELDS)
        payload = json.dumps(encrypted)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_users SET llm_config = %s WHERE id = %s",
                    (payload, user_id),
                )
            conn.commit()
        return True
    except Exception:
        return False


def _apply_llm_config_to_env(llm_config: dict) -> None:
    """Apply a decrypted LLM config dict to os.environ."""
    if llm_config.get("provider"):
        os.environ["LANGCHAIN_PROVIDER"] = llm_config["provider"]
    if llm_config.get("model"):
        os.environ["LANGCHAIN_MODEL_NAME"] = llm_config["model"]
    if llm_config.get("base_url"):
        os.environ["OPENAI_BASE_URL"] = llm_config["base_url"]
    if llm_config.get("api_key"):
        os.environ["OPENAI_API_KEY"] = llm_config["api_key"]
    if llm_config.get("temperature") is not None:
        os.environ["LANGCHAIN_TEMPERATURE"] = str(llm_config["temperature"])
    if llm_config.get("timeout_seconds") is not None:
        os.environ["TIMEOUT_SECONDS"] = str(llm_config["timeout_seconds"])
    if llm_config.get("max_retries") is not None:
        os.environ["MAX_RETRIES"] = str(llm_config["max_retries"])
    if "reasoning_effort" in llm_config:
        os.environ["LANGCHAIN_REASONING_EFFORT"] = llm_config["reasoning_effort"]


def _sync_runtime_env(provider: LLMProviderOption, updates: Dict[str, str]) -> None:
    """Apply saved LLM settings to the running API process."""
    for key, value in updates.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    if provider.api_key_env:
        key_value = os.environ.get(provider.api_key_env, "")
        if _is_configured_secret(key_value, LLM_API_KEY_PLACEHOLDERS):
            os.environ["OPENAI_API_KEY"] = key_value
        else:
            os.environ.pop("OPENAI_API_KEY", None)
    elif provider.auth_type == "oauth":
        os.environ.pop("OPENAI_API_KEY", None)
    else:
        os.environ["OPENAI_API_KEY"] = "ollama"

    base_url = os.environ.get(provider.base_url_env, "")
    if base_url:
        os.environ["OPENAI_API_BASE"] = base_url
        os.environ["OPENAI_BASE_URL"] = base_url
    else:
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_BASE_URL", None)


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON from disk if present."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _load_csv_to_dict(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load CSV rows into a list of dictionaries."""
    try:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [dict(row) for row in csv.DictReader(handle)]
        if limit is not None:
            rows = rows[:limit]
        return rows
    except Exception:
        return []



def _build_response_from_run_dir(run_dir: Path, elapsed: float, *, include_analysis: bool = False) -> RunResponse:
    """Build a run response from a persisted run directory."""
    run_id = run_dir.name

    response = RunResponse(
        status="unknown",
        run_id=run_id,
        elapsed_seconds=elapsed,
        run_directory=str(run_dir),
    )

    state_data = _load_json_file(run_dir / "state.json")
    if state_data:
        state_status = str(state_data.get("status") or "").lower()
        if state_status == "success":
            response.status = "success"
        elif state_status == "failed":
            response.status = "failed"
            response.reason = state_data.get("reason", "")
        else:
            response.status = state_status or "unknown"
    else:
        response.status = "unknown"

    planner_path = run_dir / "planner_output.json"
    response.planner_output = _load_json_file(planner_path)

    design_path = run_dir / "design_spec.json"
    response.strategy_spec = _load_json_file(design_path)

    rag_path = run_dir / "rag_metadata.json"
    rag_data = _load_json_file(rag_path)
    if rag_data:
        response.rag_selection = RAGSelection(
            selected_api=rag_data.get("selected_api") or rag_data.get("api_code", ""),
            selected_name=rag_data.get("selected_name") or rag_data.get("api_name", ""),
            selected_score=float(rag_data.get("selected_score") or rag_data.get("score", 0.0)),
        )

    metrics_path = run_dir / "artifacts" / "metrics.csv"
    if metrics_path.exists():
        metrics_dict_list = _load_csv_to_dict(metrics_path, limit=1)
        if metrics_dict_list:
            row = metrics_dict_list[0]
            try:
                # Pass ALL CSV columns to BacktestMetrics (extra="allow")
                parsed: dict = {}
                for k, v in row.items():
                    if not k or not v:
                        continue
                    try:
                        parsed[k] = int(float(v)) if k == "trade_count" or k == "max_consecutive_loss" else float(v)
                    except (ValueError, TypeError):
                        continue
                if "final_value" in parsed:
                    response.metrics = BacktestMetrics(**parsed)
            except (ValueError, TypeError):
                pass


    artifacts_dir = run_dir / "artifacts"
    if artifacts_dir.exists():
        for file_path in artifacts_dir.iterdir():
            if file_path.is_file():
                file_type = file_path.suffix.lstrip(".")
                response.artifacts.append(
                    Artifact(
                        name=file_path.name,
                        path=str(file_path),
                        type=file_type if file_type else "unknown",
                        size=file_path.stat().st_size,
                        exists=True,
                    )
                )

    equity_path = run_dir / "artifacts" / "equity.csv"
    if equity_path.exists():
        response.artifacts_equity_csv = _load_csv_to_dict(equity_path)

    metrics_csv_path = run_dir / "artifacts" / "metrics.csv"
    if metrics_csv_path.exists():
        response.artifacts_metrics_csv = _load_csv_to_dict(metrics_csv_path)

    run_card_path = run_dir / "run_card.json"
    if run_card_path.exists():
        try:
            response.run_card = json.loads(run_card_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    trades_path = run_dir / "artifacts" / "trades.csv"
    if trades_path.exists():
        response.artifacts_trades_csv = _load_csv_to_dict(trades_path)

    validation_path = run_dir / "artifacts" / "validation.json"
    if validation_path.exists():
        try:
            response.validation = json.loads(validation_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if response.artifacts_equity_csv:
        filtered_equity = []
        for row in response.artifacts_equity_csv[:1000]:
            filtered_row: Dict[str, Any] = {}
            if "timestamp" in row:
                filtered_row["time"] = row["timestamp"]
            if "equity" in row:
                filtered_row["equity"] = row["equity"]
            if "drawdown" in row:
                filtered_row["drawdown"] = row["drawdown"]
            filtered_equity.append(filtered_row)
        response.equity_curve = filtered_equity

    if response.artifacts_trades_csv:
        response.trade_log = response.artifacts_trades_csv[:500]

    if include_analysis:
        analysis = build_run_analysis(run_dir)
        response.run_stage = analysis.get("run_stage")
        response.run_context = analysis.get("run_context")
        response.price_series = analysis.get("price_series")
        response.indicator_series = analysis.get("indicator_series")
        response.trade_markers = analysis.get("trade_markers")
        response.run_logs = analysis.get("run_logs")

    return response


# ============================================================================
# Path-parameter validation
# ============================================================================

# ``run_id`` and ``session_id`` flow directly into filesystem paths
# (``RUNS_DIR / run_id`` etc.). Restrict to a safe character class so that
# values like ``..`` or ``foo/../bar`` cannot escape the parent directory.
_SAFE_PATH_PARAM_RE = __import__("re").compile(r"^[A-Za-z0-9_-]{1,128}$")


def _validate_path_param(value: str, kind: str) -> None:
    """Reject path parameters that could escape the parent directory.

    Args:
        value: User-supplied path-parameter value.
        kind: Parameter name, used in the error detail.

    Raises:
        HTTPException: 400 when ``value`` does not match the safe character
            class, mirroring the existing ``_SHADOW_ID_RE`` check.
    """
    if not _SAFE_PATH_PARAM_RE.fullmatch(value or ""):
        raise HTTPException(status_code=400, detail=f"invalid {kind}")


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/runs/{run_id}/code", dependencies=[Depends(require_auth)])
async def get_run_code(run_id: str):
    """Return strategy source files for a run.

    Args:
        run_id: Run identifier.

    Returns:
        Map filename -> source text.
    """
    _validate_path_param(run_id, "run_id")
    run_dir = RUNS_DIR / run_id / "code"
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Code directory for run {run_id} not found")
    result = {}
    for f in ["signal_engine.py"]:
        p = run_dir / f
        if p.exists():
            result[f] = p.read_text(encoding="utf-8")
    return result


@app.get("/runs/{run_id}/pine", dependencies=[Depends(require_auth)])
async def get_run_pine(run_id: str):
    """Return Pine Script file for a run.

    Args:
        run_id: Run identifier.

    Returns:
        Object with pine script content and exists flag.
    """
    _validate_path_param(run_id, "run_id")
    pine_path = RUNS_DIR / run_id / "artifacts" / "strategy.pine"
    if not pine_path.exists():
        return {"exists": False, "content": None}
    return {
        "exists": True,
        "content": pine_path.read_text(encoding="utf-8"),
    }


@app.get("/runs/{run_id}", response_model=RunResponse, dependencies=[Depends(require_auth)])
async def get_run_result(run_id: str):
    """Fetch full details for a historical run by ``run_id``."""
    _validate_path_param(run_id, "run_id")
    run_dir = RUNS_DIR / run_id

    if not run_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )

    response = _build_response_from_run_dir(run_dir, elapsed=0.0, include_analysis=True)

    return response


@app.get("/runs", response_model=List[RunInfo], dependencies=[Depends(require_auth)])
async def list_runs(limit: int = 20):
    """List recent runs with summary fields."""
    limit = min(max(1, limit), 100)
    runs_dir = RUNS_DIR
    
    if not runs_dir.exists():
        return []
    
    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda x: x.name,
        reverse=True
    )
    
    results = []
    for d in run_dirs[:limit]:
        run_id = d.name
        
        # Status from state.json or artifacts
        status_val = "unknown"
        state_file = _load_json_file(d / "state.json")
        if state_file:
            status_val = str(state_file.get("status") or "unknown").lower()
        elif (d / "artifacts" / "equity.csv").exists():
            status_val = "success"
        elif (d / "review_report.json").exists():
            status_val = "success"
        
        # Parse created_at from run_id (YYYYMMDD_HHMMSS or run_YYYYMMDD_HHMMSS)
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
                import csv
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        total_return = float(row.get('total_return', 0) or 0)
                        sharpe = float(row.get('sharpe', 0) or 0)
                        break
            except (OSError, ValueError):
                pass
        
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
        
    return results


@app.get(
    "/settings/llm",
    response_model=LLMSettingsResponse,
)
async def get_llm_settings(auth: dict = Depends(require_auth)):
    """Return per-user LLM settings from the database (with .env fallback)."""
    user_id = auth.get("user_id", 1)
    db_config = _read_user_llm_config(user_id) if user_id > 0 else {}
    return _build_llm_settings_response(db_config=db_config)


@app.put("/settings/llm", response_model=LLMSettingsResponse)
async def update_llm_settings(payload: UpdateLLMSettingsRequest, auth: dict = Depends(require_auth)):
    """Persist per-user LLM settings to the database (API key encrypted)."""
    user_id = auth.get("user_id", 1)
    provider_name = payload.provider.strip().lower()
    provider = LLM_PROVIDER_BY_NAME.get(provider_name)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported LLM provider")

    model_name = payload.model_name.strip()
    if not model_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name is required")

    if payload.temperature < 0 or payload.temperature > 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Temperature must be between 0 and 2")

    reasoning_effort = (payload.reasoning_effort or "").strip().lower()
    if reasoning_effort not in LLM_REASONING_EFFORTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reasoning effort must be low, medium, high, or max")

    base_url = (payload.base_url if payload.base_url is not None else provider.default_base_url).strip()
    if provider.auth_type == "oauth":
        try:
            from src.providers.openai_codex import validate_codex_base_url
            base_url = validate_codex_base_url(base_url)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Build DB config dict
    db_updates: dict = {
        "provider": provider.name,
        "model": model_name,
        "base_url": base_url,
        "temperature": payload.temperature,
        "timeout_seconds": payload.timeout_seconds,
        "max_retries": payload.max_retries,
        "reasoning_effort": reasoning_effort,
    }

    if provider.api_key_env:
        if payload.clear_api_key:
            db_updates["api_key"] = ""
        elif payload.api_key is not None and payload.api_key.strip():
            db_updates["api_key"] = payload.api_key.strip()
    elif payload.clear_api_key:
        db_updates["api_key"] = ""

    if user_id > 0:
        _write_user_llm_config(user_id, db_updates)

    # Apply to runtime env
    _apply_llm_config_to_env(db_updates)

    return _build_llm_settings_response(db_config=db_updates)


@app.get(
    "/settings/data-sources",
    response_model=DataSourceSettingsResponse,
)
async def get_data_source_settings(auth: dict = Depends(require_auth)):
    """Return per-user data source credentials from the database."""
    user_id = auth.get("user_id", 1)
    ds_config = _read_user_ds_config(user_id) if user_id > 0 else {}
    return _build_data_source_settings_response(
        token=ds_config.get("tushare_token", ""),
        okx_api_key=ds_config.get("okx_api_key", ""),
        okx_secret_key=ds_config.get("okx_secret_key", ""),
        okx_passphrase=ds_config.get("okx_passphrase", ""),
        twelvedata_api_key=ds_config.get("twelvedata_api_key", ""),
        finnhub_api_key=ds_config.get("finnhub_api_key", ""),
        tiingo_api_key=ds_config.get("tiingo_api_key", ""),
    )


@app.put(
    "/settings/data-sources",
    response_model=DataSourceSettingsResponse,
)
async def update_data_source_settings(payload: UpdateDataSourceSettingsRequest, auth: dict = Depends(require_auth)):
    """Persist per-user data source credentials to the database (encrypted)."""
    user_id = auth.get("user_id", 1)

    # Read existing DB config
    ds_config = _read_user_ds_config(user_id) if user_id > 0 else {}
    db_updates: dict = {}

    # --- Tushare ---
    if payload.clear_tushare_token:
        db_updates["tushare_token"] = ""
    elif payload.tushare_token is not None and payload.tushare_token.strip():
        db_updates["tushare_token"] = payload.tushare_token.strip()

    # --- OKX ---
    if payload.clear_okx:
        db_updates["okx_api_key"] = ""
        db_updates["okx_secret_key"] = ""
        db_updates["okx_passphrase"] = ""
    else:
        if payload.okx_api_key is not None:
            db_updates["okx_api_key"] = payload.okx_api_key.strip()
        if payload.okx_secret_key is not None:
            db_updates["okx_secret_key"] = payload.okx_secret_key.strip()
        if payload.okx_passphrase is not None:
            db_updates["okx_passphrase"] = payload.okx_passphrase.strip()

    # --- Twelve Data ---
    if payload.clear_twelvedata:
        db_updates["twelvedata_api_key"] = ""
    elif payload.twelvedata_api_key is not None and payload.twelvedata_api_key.strip():
        db_updates["twelvedata_api_key"] = payload.twelvedata_api_key.strip()

    # --- Finnhub ---
    if payload.clear_finnhub:
        db_updates["finnhub_api_key"] = ""
    elif payload.finnhub_api_key is not None and payload.finnhub_api_key.strip():
        db_updates["finnhub_api_key"] = payload.finnhub_api_key.strip()

    # --- Tiingo ---
    if payload.clear_tiingo:
        db_updates["tiingo_api_key"] = ""
    elif payload.tiingo_api_key is not None and payload.tiingo_api_key.strip():
        db_updates["tiingo_api_key"] = payload.tiingo_api_key.strip()

    if db_updates and user_id > 0:
        _write_user_ds_config(user_id, db_updates)

    # Apply to runtime env
    ds_config = _read_user_ds_config(user_id) if user_id > 0 else {}
    token = ds_config.get("tushare_token", "")
    okx_key = ds_config.get("okx_api_key", "")
    okx_secret = ds_config.get("okx_secret_key", "")
    okx_pass = ds_config.get("okx_passphrase", "")
    td_key = ds_config.get("twelvedata_api_key", "")
    fh_key = ds_config.get("finnhub_api_key", "")
    ti_key = ds_config.get("tiingo_api_key", "")

    if token and _is_configured_secret(token, TUSHARE_TOKEN_PLACEHOLDERS):
        os.environ["TUSHARE_TOKEN"] = token
    else:
        os.environ.pop("TUSHARE_TOKEN", None)

    if okx_key:
        os.environ["OKX_API_KEY"] = okx_key
        os.environ["OKX_SECRET_KEY"] = okx_secret
        os.environ["OKX_PASSPHRASE"] = okx_pass
    else:
        os.environ.pop("OKX_API_KEY", None)
        os.environ.pop("OKX_SECRET_KEY", None)
        os.environ.pop("OKX_PASSPHRASE", None)

    if td_key:
        os.environ["TWELVE_DATA_API_KEY"] = td_key
    else:
        os.environ.pop("TWELVE_DATA_API_KEY", None)

    if fh_key:
        os.environ["FINNHUB_API_KEY"] = fh_key
    else:
        os.environ.pop("FINNHUB_API_KEY", None)

    if ti_key:
        os.environ["TIINGO_API_KEY"] = ti_key
    else:
        os.environ.pop("TIINGO_API_KEY", None)

    return _build_data_source_settings_response(
        token=token,
        okx_api_key=okx_key,
        okx_secret_key=okx_secret,
        okx_passphrase=okx_pass,
        twelvedata_api_key=td_key,
        finnhub_api_key=fh_key,
        tiingo_api_key=ti_key,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness probe."""
    return HealthResponse(
        status="healthy",
        service="AStockPursue API",
        timestamp=datetime.now().isoformat()
    )


@app.get("/correlation")
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


def _terminate_current_process() -> None:
    """Stop the current API process after the response has been sent."""
    time.sleep(0.25)
    os.kill(os.getpid(), signal.SIGTERM)


@app.post("/system/shutdown", dependencies=[Depends(require_auth)])
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


@app.get("/skills")
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


@app.get("/api")
async def api_info():
    """Service metadata."""
    return {
        "service": "AStockPursue API",
        "version": "5.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ============================================================================
# Session API
# ============================================================================

_session_service = None


def _get_session_service():
    """Lazy-init session service when ENABLE_SESSION_RUNTIME=true."""
    global _session_service
    if _session_service is not None:
        return _session_service

    if os.getenv("ENABLE_SESSION_RUNTIME", "true").lower() != "true":
        return None

    import asyncio
    from src.session.events import EventBus
    from src.session.service import SessionService, _create_store

    store = _create_store(base_dir=SESSIONS_DIR)
    event_bus = EventBus()

    try:
        loop = asyncio.get_event_loop()
        event_bus.set_loop(loop)
    except RuntimeError:
        pass

    _session_service = SessionService(
        store=store,
        event_bus=event_bus,
        runs_dir=RUNS_DIR,
    )
    return _session_service


@app.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
async def create_session(request: CreateSessionRequest, auth: dict = Security(require_auth)):
    """Create a chat session."""
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    config = request.config or {}
    config["_user_id"] = auth.get("user_id", 1)
    session = svc.create_session(title=request.title, config=config)
    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        status=session.status.value,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_attempt_id=session.last_attempt_id,
    )


@app.get("/sessions", response_model=List[SessionResponse], dependencies=[Depends(require_auth)])
async def list_sessions(limit: int = Query(50, ge=1, le=200)):
    """List sessions."""
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    sessions = svc.list_sessions(limit=limit)
    return [
        SessionResponse(
            session_id=s.session_id,
            title=s.title,
            status=s.status.value,
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_attempt_id=s.last_attempt_id,
        )
        for s in sessions
    ]


@app.get("/sessions/{session_id}", response_model=SessionResponse, dependencies=[Depends(require_auth)])
async def get_session(session_id: str):
    """Get one session by id."""
    _validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        status=session.status.value,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_attempt_id=session.last_attempt_id,
    )


@app.delete("/sessions/{session_id}", dependencies=[Depends(require_auth)])
async def delete_session(session_id: str):
    """Delete a session."""
    _validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    deleted = svc.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"status": "deleted", "session_id": session_id}


class UpdateSessionRequest(BaseModel):
    """Session update fields."""
    title: Optional[str] = None


@app.patch("/sessions/{session_id}", dependencies=[Depends(require_auth)])
async def update_session(session_id: str, req: UpdateSessionRequest):
    """Update session fields (e.g. title)."""
    _validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    session = svc.store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if req.title is not None:
        session.title = req.title
    from datetime import datetime
    session.updated_at = datetime.now().isoformat()
    svc.store.update_session(session)
    return {"status": "updated", "session_id": session_id}


@app.post("/sessions/{session_id}/messages", dependencies=[Depends(require_auth)])
async def send_message(session_id: str, payload: SendMessageRequest, http_request: Request):
    """Send a user message and start the agent loop (natural language strategy)."""
    _validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    try:
        result = await svc.send_message(
            session_id=session_id,
            content=payload.content,
            include_shell_tools=_shell_tools_enabled_for_request(http_request),
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/sessions/{session_id}/cancel", dependencies=[Depends(require_auth)])
async def cancel_session(session_id: str):
    """Cancel the in-flight agent loop for this session."""
    _validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    cancelled = svc.cancel_current(session_id)
    if not cancelled:
        return {"status": "no_active_loop"}
    return {"status": "cancelled"}


@app.get("/sessions/{session_id}/messages", response_model=List[MessageResponse], dependencies=[Depends(require_auth)])
async def get_messages(session_id: str, limit: int = Query(100, ge=1, le=1000)):
    """List messages for a session."""
    _validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    messages = svc.get_messages(session_id, limit=limit)
    return [
        MessageResponse(
            message_id=m.message_id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            linked_attempt_id=m.linked_attempt_id,
            metadata=m.metadata if m.metadata else None,
        )
        for m in messages
    ]


@app.get("/sessions/{session_id}/events", dependencies=[Depends(require_auth)])
async def session_events(
    session_id: str,
    request: Request,
    last_event_id: Optional[str] = Query(None, alias="Last-Event-ID"),
):
    """SSE stream for agent events."""
    _validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    header_id = request.headers.get("Last-Event-ID")
    event_id = header_id or last_event_id

    async def event_generator():
        async for event in svc.event_bus.subscribe(session_id, last_event_id=event_id):
            if await request.is_disconnected():
                break
            yield event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# File Upload
# ============================================================================

_BLOCKED_UPLOAD_EXT = {
    # binaries / executables we should never accept
    ".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".app", ".dmg",
    ".so", ".dll", ".dylib",
    # executable-adjacent source, shell, config, and template files
    ".py", ".pyw", ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".yaml", ".yml", ".j2", ".jinja", ".jinja2", ".template",
    # archives — don't auto-extract; user can unpack locally
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz",
}

_BLOCKED_UPLOAD_NAMES = {
    "dockerfile",
    "containerfile",
}


_SHADOW_ID_RE = __import__("re").compile(r"^shadow_[0-9a-f]{8}$")


@app.get("/shadow-reports/{shadow_id}", dependencies=[Depends(require_auth)])
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


@app.post("/upload", dependencies=[Depends(require_auth)])
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


# ============================================================================
# Swarm API
# ============================================================================

_swarm_runtime = None


def _get_swarm_runtime():
    """Lazy-init SwarmRuntime singleton."""
    global _swarm_runtime
    if _swarm_runtime is not None:
        return _swarm_runtime
    from src.swarm.store import SwarmStore
    from src.swarm.runtime import SwarmRuntime
    swarm_dir = Path(__file__).resolve().parent / ".swarm" / "runs"
    store = SwarmStore(base_dir=swarm_dir)
    _swarm_runtime = SwarmRuntime(store=store)
    return _swarm_runtime


@app.get("/swarm/presets")
async def list_swarm_presets():
    """List Swarm YAML presets."""
    from src.swarm.presets import list_presets
    return list_presets()


@app.post("/swarm/runs", dependencies=[Depends(require_auth)])
async def create_swarm_run(payload: dict, http_request: Request):
    """Start a swarm run: body must include preset_name and user_vars."""
    runtime = _get_swarm_runtime()
    preset_name = payload.get("preset_name", "")
    user_vars = payload.get("user_vars", {})
    try:
        run = runtime.start_run(
            preset_name,
            user_vars,
            include_shell_tools=_shell_tools_enabled_for_request(http_request),
        )
        return {"id": run.id, "status": run.status.value, "preset_name": run.preset_name}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/swarm/runs", dependencies=[Depends(require_auth)])
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


@app.get("/swarm/runs/{run_id}", dependencies=[Depends(require_auth)])
async def get_swarm_run(run_id: str):
    """Swarm run detail including task statuses."""
    from src.swarm.task_store import TaskStore

    _validate_path_param(run_id, "run_id")
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


@app.get("/swarm/runs/{run_id}/events", dependencies=[Depends(require_auth)])
async def swarm_run_events(run_id: str, request: Request, last_index: int = Query(0, ge=0)):
    """SSE stream for a swarm run."""
    import asyncio

    _validate_path_param(run_id, "run_id")
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


@app.post("/swarm/runs/{run_id}/cancel", dependencies=[Depends(require_auth)])
async def cancel_swarm_run(run_id: str):
    """Cancel an active swarm run."""
    _validate_path_param(run_id, "run_id")
    runtime = _get_swarm_runtime()
    ok = runtime.cancel_run(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"No active run {run_id}")
    return {"status": "cancelled"}


# ============================================================================
# Alpha Zoo routes (Web UI) — defined in src/api/alpha_routes.py
# ============================================================================

from src.api.alpha_routes import register_alpha_routes  # noqa: E402
register_alpha_routes(app)

# ============================================================================
# Indicator Lab routes (Web UI) — defined in src/api/indicator_lab_routes.py
# ============================================================================

from src.api.indicator_lab_routes import router as indicator_lab_router  # noqa: E402
app.include_router(indicator_lab_router, dependencies=[Depends(require_auth)])

from src.api.strategy_lab_routes import router as strategy_lab_router  # noqa: E402
app.include_router(strategy_lab_router, dependencies=[Depends(require_auth)])

from src.api.stock_routes import router as stock_router  # noqa: E402
app.include_router(stock_router, dependencies=[Depends(require_auth)])

from src.api.paper_trading_routes import router as paper_trading_router  # noqa: E402
app.include_router(paper_trading_router, dependencies=[Depends(require_auth)])


# ============================================================================
# Auth API (user login / register)
# ============================================================================

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=4, max_length=128)
    email: str | None = None


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Login and get a JWT token."""
    from src.auth.jwt import create_token, verify_password
    from src.db.pool import get_connection

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, username, password_hash, role, token_version FROM vt_users WHERE username = %s",
                    (request.username,),
                )
                row = cur.fetchone()
                if not row or not verify_password(request.password, row[2]):
                    raise HTTPException(status_code=401, detail="Invalid username or password")

                user_id, username, _, role, token_version = row
                token = create_token(user_id, username, role, token_version)
                return {"token": token, "user_id": user_id, "username": username, "role": role}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """Register a new user."""
    from src.auth.jwt import hash_password
    from src.db.pool import get_connection

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM vt_users WHERE username = %s", (request.username,))
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Username already exists")
                cur.execute(
                    "INSERT INTO vt_users (username, password_hash, email) VALUES (%s, %s, %s) RETURNING id",
                    (request.username, hash_password(request.password), request.email or ""),
                )
                user_id = cur.fetchone()[0]
        return {"user_id": user_id, "username": request.username}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Watchlist API
# ============================================================================

# ============================================================================
# Admin API
# ============================================================================

@app.get("/admin/users")
async def list_users(auth: dict = Security(require_auth)):
    """List all users (admin only)."""
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, username, email, role, created_at, "
                    "llm_config->>'provider' as llm_provider, llm_config->>'model' as llm_model, "
                    "CASE WHEN data_source_config->>'tushare_token' IS NOT NULL AND data_source_config->>'tushare_token' != '' THEN true ELSE false END as tushare_configured "
                    "FROM vt_users ORDER BY id"
                )
                return {"users": [
                    {"id": r[0], "username": r[1], "email": r[2] or "", "role": r[3],
                     "created_at": str(r[4]), "llm_provider": r[5] or "", "llm_model": r[6] or "",
                     "tushare_configured": bool(r[7]) if len(r) > 7 else False}
                    for r in cur.fetchall()
                ]}
    except Exception as e:
        return {"users": [], "error": str(e)}


@app.delete("/admin/users/{user_id}")
async def delete_user(user_id: int, auth: dict = Security(require_auth)):
    """Delete a user (admin only)."""
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM vt_users WHERE id=%s", (user_id,))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Watchlist API
# ============================================================================

@app.get("/api/watchlist")
async def get_watchlist(auth: dict = Security(require_auth)):
    """Get the current user's watchlist."""
    user_id = auth.get("user_id", 1)
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


@app.post("/api/watchlist")
async def add_watchlist(request: Request, auth: dict = Security(require_auth)):
    """Add a symbol to the watchlist."""
    user_id = auth.get("user_id", 1)
    try:
        body = await request.json()
        symbol = body.get("symbol", "").strip().upper()
        name = body.get("name", "").strip()
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol required")
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO vt_watchlist (user_id, symbol, name) VALUES (%s, %s, %s) ON CONFLICT (user_id, symbol) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                    (user_id, symbol, name or symbol),
                )
                row = cur.fetchone()
        return {"ok": True, "id": row[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/watchlist/{symbol}")
async def remove_watchlist(symbol: str, auth: dict = Security(require_auth)):
    """Remove a symbol from the watchlist."""
    user_id = auth.get("user_id", 1)
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/watchlist/prices")
async def get_watchlist_prices(auth: dict = Security(require_auth)):
    """Get latest prices for watchlist symbols. Tushare for A-shares, yfinance fallback."""
    user_id = auth.get("user_id", 1)
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

        for sym in symbols:
            upper = sym.upper()
            # A-share: try tushare first
            if upper.endswith((".SH", ".SZ", ".BJ")):
                try:
                    from backtest.loaders.tushare import DataLoader as TushareLoader
                    import pandas as pd
                    loader = TushareLoader()
                    if hasattr(loader, "is_available") and loader.is_available():
                        today = pd.Timestamp.now().strftime("%Y-%m-%d")
                        start = (pd.Timestamp.now() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
                        data = loader.fetch([sym], start, today, interval="1D")
                        if sym in data and not data[sym].empty:
                            df = data[sym]
                            current = float(df["close"].iloc[-1])
                            prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else current
                            change_pct = (current - prev_close) / prev_close * 100 if prev_close else 0
                            prices[sym] = {"price": round(current, 2), "change_pct": round(change_pct, 2), "name": names.get(sym, sym)}
                            continue
                except Exception:
                    pass
                # Fallback: try akshare
                try:
                    from backtest.loaders.akshare_loader import DataLoader as AKLoader
                    import pandas as pd
                    loader = AKLoader()
                    today = pd.Timestamp.now().strftime("%Y-%m-%d")
                    start = (pd.Timestamp.now() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
                    data = loader.fetch([sym], start, today, interval="1D")
                    if sym in data and not data[sym].empty:
                        df = data[sym]
                        current = float(df["close"].iloc[-1])
                        prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else current
                        change_pct = (current - prev_close) / prev_close * 100 if prev_close else 0
                        prices[sym] = {"price": round(current, 2), "change_pct": round(change_pct, 2), "name": names.get(sym, sym)}
                        continue
                except Exception:
                    pass

            # Fallback: yfinance (for US/HK/crypto)
            try:
                import yfinance as yf
                ticker = yf.Ticker(sym)
                info = ticker.fast_info if hasattr(ticker, 'fast_info') else ticker.info
                prev_close = getattr(info, 'previous_close', None) or getattr(info, 'regularMarketPreviousClose', None) or 0
                current = getattr(info, 'last_price', None) or getattr(info, 'currentPrice', None) or 0
                change_pct = (current - prev_close) / prev_close * 100 if current and prev_close else 0
                prices[sym] = {"price": current or 0, "change_pct": round(change_pct, 2), "name": names.get(sym, sym)}
            except Exception:
                prices[sym] = {"price": 0, "change_pct": 0, "name": names.get(sym, sym), "error": "fetch failed"}

        return {"prices": prices}
    except Exception as e:
        return {"prices": {}, "error": str(e)}


@app.post("/api/auth/change-password")
async def change_password(request: Request, auth: dict = Security(require_auth)):
    """Change current user's password."""
    user_id = auth.get("user_id", 1)
    try:
        body = await request.json()
        old_pw = body.get("old_password", "")
        new_pw = body.get("new_password", "")
        if len(new_pw) < 4:
            raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
        from src.db.pool import get_connection
        from src.auth.jwt import verify_password, hash_password
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password_hash FROM vt_users WHERE id=%s", (user_id,))
                row = cur.fetchone()
                if not row or not verify_password(old_pw, row[0]):
                    raise HTTPException(status_code=401, detail="Current password is incorrect")
                cur.execute("UPDATE vt_users SET password_hash=%s, token_version=token_version+1, updated_at=now() WHERE id=%s",
                           (hash_password(new_pw), user_id))
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/change-username")
async def change_username(request: Request, auth: dict = Security(require_auth)):
    """Change current user's username."""
    user_id = auth.get("user_id", 1)
    try:
        body = await request.json()
        new_username = body.get("username", "").strip()
        if len(new_username) < 2:
            raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM vt_users WHERE username=%s AND id!=%s", (new_username, user_id))
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Username already taken")
                cur.execute("UPDATE vt_users SET username=%s, updated_at=now() WHERE id=%s", (new_username, user_id))
        return {"ok": True, "username": new_username}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/me")
async def get_current_user(auth: dict = Security(require_auth)):
    """Get current user info from JWT, including llm_config."""
    user_id = auth.get("user_id", 1)
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, role, email, llm_config FROM vt_users WHERE id=%s", (user_id,))
                row = cur.fetchone()
                if row:
                    return {
                        "user_id": row[0], "username": row[1], "role": row[2],
                        "email": row[3] or "",
                        "llm_config": row[4] if isinstance(row[4], dict) else {},
                    }
    except Exception:
        pass
    return auth


@app.post("/api/auth/llm-config")
async def save_user_llm_config(
    request: Request,
    auth: dict = Security(require_auth),
):
    """Save per-user LLM configuration (encrypted API key)."""
    user_id = auth.get("user_id", 1)
    try:
        body = await request.json()
        from src.db.pool import get_connection
        from src.auth.user_config import encrypt_config, _SENSITIVE_LLM_FIELDS
        import json as _json
        body = encrypt_config(body, _SENSITIVE_LLM_FIELDS)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_users SET llm_config=%s, updated_at=now() WHERE id=%s",
                    (_json.dumps(body, ensure_ascii=False), user_id),
                )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/llm-config")
async def get_user_llm_config(auth: dict = Security(require_auth)):
    """Get current user's LLM configuration (decrypted fields)."""
    user_id = auth.get("user_id", 1)
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import decrypt_config, _SENSITIVE_LLM_FIELDS
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT llm_config FROM vt_users WHERE id=%s", (user_id,))
                row = cur.fetchone()
                if row:
                    cfg = row[0] if isinstance(row[0], dict) else {}
                    cfg = decrypt_config(cfg, _SENSITIVE_LLM_FIELDS)
                    return {"llm_config": cfg}
    except Exception:
        pass
    return {"llm_config": {}}


@app.get("/api/auth/data-source-config")
async def get_user_data_source_config(auth: dict = Security(require_auth)):
    """Get current user's data source configuration (decrypted fields)."""
    user_id = auth.get("user_id", 1)
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import decrypt_config, _SENSITIVE_DS_FIELDS
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data_source_config FROM vt_users WHERE id=%s", (user_id,))
                row = cur.fetchone()
                if row:
                    cfg = row[0] if isinstance(row[0], dict) else {}
                    cfg = decrypt_config(cfg, _SENSITIVE_DS_FIELDS)
                    return {"data_source_config": cfg}
    except Exception:
        pass
    return {"data_source_config": {}}


@app.post("/api/auth/data-source-config")
async def save_user_data_source_config(
    request: Request,
    auth: dict = Security(require_auth),
):
    """Save per-user data source configuration (encrypted tokens)."""
    user_id = auth.get("user_id", 1)
    try:
        body = await request.json()
        from src.db.pool import get_connection
        from src.auth.user_config import encrypt_config, _SENSITIVE_DS_FIELDS
        import json as _json
        body = encrypt_config(body, _SENSITIVE_DS_FIELDS)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_users SET data_source_config=%s, updated_at=now() WHERE id=%s",
                    (_json.dumps(body, ensure_ascii=False), user_id),
                )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Backtest History API (PG-backed)
# ============================================================================

@app.get("/api/backtest-history")
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


@app.get("/api/backtest-history/{run_id}")
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
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/backtest-history/{run_id}")
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
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main Entry Point
# ============================================================================

def serve_main(argv: list[str] | None = None) -> int:
    """Start the API server from CLI-style arguments."""
    import argparse
    import subprocess
    import uvicorn
    from fastapi.staticfiles import StaticFiles
    from starlette.exceptions import HTTPException as StarletteHTTPException

    class SPAStaticFiles(StaticFiles):
        """Serve index.html for browser refreshes on client-side routes."""

        async def get_response(self, path: str, scope: Dict[str, Any]):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as exc:
                if exc.status_code != status.HTTP_404_NOT_FOUND:
                    raise
                return await super().get_response("index.html", scope)

    parser = argparse.ArgumentParser(description="AStockPursue Server")
    parser.add_argument("--port", type=int, default=8000, help="Listen port (default 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--dev", action="store_true", help="Dev mode: spawn Vite on :5173")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    frontend_root = Path(__file__).resolve().parent.parent / "frontend"

    vite_proc = None
    if args.dev and frontend_root.exists():
        print("[dev] Starting Vite dev server on :5173 ...")
        vite_proc = subprocess.Popen(
            ["npx", "vite", "--host", "0.0.0.0"],
            cwd=str(frontend_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"[dev] Vite PID={vite_proc.pid}")
        print("[dev] Frontend: http://localhost:5173")
        print(f"[dev] API: http://localhost:{args.port}")
    elif frontend_dist.exists():
        if not any(route.path == "/" for route in app.routes):
            app.mount("/", SPAStaticFiles(directory=str(frontend_dist), html=True), name="frontend")
        print(f"[prod] Frontend served from {frontend_dist}")
    else:
        print(f"[warn] No frontend build found at {frontend_dist}")
        print("[warn] Run: cd frontend && npm run build")

    print("=" * 50)
    print("  AStockPursue Server")
    print(f"  http://127.0.0.1:{args.port}")
    print("=" * 50)

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        if vite_proc:
            vite_proc.terminate()
            print("[dev] Vite stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(serve_main())
