"""Shared utilities for API route modules."""

from __future__ import annotations

import csv
import ipaddress
import json
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

AGENT_DIR = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = AGENT_DIR / "runs"
SESSIONS_DIR = AGENT_DIR / "sessions"
UPLOADS_DIR = AGENT_DIR / "uploads"
ENV_PATH = AGENT_DIR / ".env"
ENV_EXAMPLE_PATH = AGENT_DIR / ".env.example"

LLM_PROVIDER_CONFIG_PATH = AGENT_DIR / "src" / "providers" / "llm_providers.json"

# ---------------------------------------------------------------------------
# Error helper — prevents internal details leaking to API clients
# ---------------------------------------------------------------------------

def safe_error(e: Exception, prefix: str = "Internal error") -> str:
    """Return a safe error message for API responses.

    In production, returns a generic message to avoid leaking file paths,
    stack traces, or database details.  Set ``ASTOCKPURSUE_DEBUG_ERRORS=1``
    to see the full exception string during development.
    """
    if os.getenv("ASTOCKPURSUE_DEBUG_ERRORS", "").lower() in ("1", "true", "yes"):
        return f"{prefix}: {e}"
    return f"{prefix}. Set ASTOCKPURSUE_DEBUG_ERRORS=1 for details."


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024
_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB

_SHELL_TOOLS_ENV = "ASTOCKPURSUE_ENABLE_SHELL_TOOLS"
_DOCKER_LOOPBACK_ENV = "ASTOCKPURSUE_TRUST_DOCKER_LOOPBACK"

LLM_API_KEY_PLACEHOLDERS = {"", "sk-or-v1-your-key-here", "sk-xxx", "xxx", "gsk_xxx"}
TUSHARE_TOKEN_PLACEHOLDERS = {"", "your-tushare-token"}

_SAFE_PATH_PARAM_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SHADOW_ID_RE = re.compile(r"^shadow_[0-9a-f]{8}$")

_BLOCKED_UPLOAD_EXT = {
    ".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".app", ".dmg",
    ".so", ".dll", ".dylib",
    ".py", ".pyw", ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".yaml", ".yml", ".j2", ".jinja", ".jinja2", ".template",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz",
}

_BLOCKED_UPLOAD_NAMES = {"dockerfile", "containerfile"}

# ---------------------------------------------------------------------------
# Pydantic models shared across route modules
# ---------------------------------------------------------------------------


class Artifact(BaseModel):
    name: str = Field(..., description="File name")
    path: str = Field(..., description="File path")
    type: str = Field(..., description="File type: csv, json, txt, etc.")
    size: int = Field(..., description="Size in bytes")
    exists: bool = Field(..., description="Whether the file exists")


class BacktestMetrics(BaseModel):
    model_config = {"extra": "allow"}
    final_value: float = Field(..., description="Ending portfolio value")
    total_return: float = Field(..., description="Total return")
    annual_return: float = Field(..., description="Annualized return")
    max_drawdown: float = Field(..., description="Max drawdown")
    sharpe: float = Field(..., description="Sharpe ratio")
    win_rate: float = Field(..., description="Win rate")
    trade_count: int = Field(..., description="Number of trades")


class RAGSelection(BaseModel):
    selected_api: str = Field(..., description="Selected API code")
    selected_name: str = Field(..., description="Selected API name")
    selected_score: float = Field(..., description="Match score")


class RunInfo(BaseModel):
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
    quality_hints: Optional[List[Dict[str, Any]]] = Field(None, description="Data-quality / survivorship warnings")
    run_directory: str = Field(..., description="Run directory path")
    run_stage: Optional[str] = Field(None, description="UI-facing run stage")
    run_context: Optional[Dict[str, Any]] = Field(None, description="Normalized request context")
    price_series: Optional[Dict[str, List[Dict[str, Any]]]] = Field(None, description="Grouped OHLC series")
    indicator_series: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]] = Field(
        None, description="Grouped indicator overlays"
    )
    trade_markers: Optional[List[Dict[str, Any]]] = Field(None, description="Trade markers for charts")
    run_logs: Optional[List[Dict[str, Any]]] = Field(None, description="Structured stdout/stderr lines")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    timestamp: str = Field(..., description="Server timestamp")


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def validate_path_param(value: str, kind: str) -> None:
    """Reject path parameters that could escape the parent directory."""
    if not _SAFE_PATH_PARAM_RE.fullmatch(value or ""):
        raise HTTPException(status_code=400, detail=f"invalid {kind}")


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON from disk if present."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Failed to load JSON: %s", path, exc_info=True)
    return None


def load_csv_to_dict(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
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
        logger.debug("Failed to load CSV: %s", path, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Network / auth helpers
# ---------------------------------------------------------------------------


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _default_gateway_ips() -> set:
    """Return IPv4 default gateway addresses from Linux procfs."""
    gateways = set()
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


def _trusted_docker_loopback_ip(ip) -> bool:
    if not isinstance(ip, ipaddress.IPv4Address):
        return False
    if not _env_flag_enabled(_DOCKER_LOOPBACK_ENV):
        return False
    return ip in _default_gateway_ips()


def is_local_client(request: Request) -> bool:
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


def shell_tools_enabled_for_request(request: Request) -> bool:
    """Return whether this API request may expose shell tools to the agent."""
    return is_local_client(request) or _env_flag_enabled(_SHELL_TOOLS_ENV)


# ---------------------------------------------------------------------------
# Run response builder
# ---------------------------------------------------------------------------


def build_response_from_run_dir(run_dir: Path, elapsed: float, *, include_analysis: bool = False) -> RunResponse:
    """Build a run response from a persisted run directory."""
    run_id = run_dir.name

    response = RunResponse(
        status="unknown",
        run_id=run_id,
        elapsed_seconds=elapsed,
        run_directory=str(run_dir),
    )

    state_data = load_json_file(run_dir / "state.json")
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
    response.planner_output = load_json_file(planner_path)

    design_path = run_dir / "design_spec.json"
    response.strategy_spec = load_json_file(design_path)

    rag_path = run_dir / "rag_metadata.json"
    rag_data = load_json_file(rag_path)
    if rag_data:
        response.rag_selection = RAGSelection(
            selected_api=rag_data.get("selected_api") or rag_data.get("api_code", ""),
            selected_name=rag_data.get("selected_name") or rag_data.get("api_name", ""),
            selected_score=float(rag_data.get("selected_score") or rag_data.get("score", 0.0)),
        )

    metrics_path = run_dir / "artifacts" / "metrics.csv"
    if metrics_path.exists():
        metrics_dict_list = load_csv_to_dict(metrics_path, limit=1)
        if metrics_dict_list:
            row = metrics_dict_list[0]
            try:
                parsed: dict = {}
                for k, v in row.items():
                    if not k or not v:
                        continue
                    try:
                        parsed[k] = int(float(v)) if k in ("trade_count", "max_consecutive_loss") else float(v)
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

    # Survivorship / data-quality warnings from run_card
    run_card_path = run_dir / "run_card.json"
    if run_card_path.exists():
        run_card = load_json_file(run_card_path)
        if run_card and run_card.get("warnings"):
            response.quality_hints = [
                {"severity": "warn", "code": "BACKTEST_WARNING", "message": w}
                for w in run_card["warnings"]
            ]

    equity_path = run_dir / "artifacts" / "equity.csv"
    if equity_path.exists():
        response.artifacts_equity_csv = load_csv_to_dict(equity_path)

    metrics_csv_path = run_dir / "artifacts" / "metrics.csv"
    if metrics_csv_path.exists():
        response.artifacts_metrics_csv = load_csv_to_dict(metrics_csv_path)

    run_card_path = run_dir / "run_card.json"
    if run_card_path.exists():
        try:
            response.run_card = json.loads(run_card_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    trades_path = run_dir / "artifacts" / "trades.csv"
    if trades_path.exists():
        response.artifacts_trades_csv = load_csv_to_dict(trades_path)

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
        from src.ui_services import build_run_analysis
        analysis = build_run_analysis(run_dir)
        response.run_stage = analysis.get("run_stage")
        response.run_context = analysis.get("run_context")
        response.price_series = analysis.get("price_series")
        response.indicator_series = analysis.get("indicator_series")
        response.trade_markers = analysis.get("trade_markers")
        response.run_logs = analysis.get("run_logs")

    return response
