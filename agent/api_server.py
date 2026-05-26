#!/usr/bin/env python3
"""AStockPursue API Server - RESTful API for finance research and backtesting.

V5: ReAct Agent + async /run + CORS env + SSE tool events.
"""

from __future__ import annotations

import ipaddress
import os
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from rich.console import Console

from src.api.common import (
    AGENT_DIR,
    ENV_PATH,
    ENV_EXAMPLE_PATH,
    RUNS_DIR,
    SESSIONS_DIR,
    UPLOADS_DIR,
    MAX_UPLOAD_SIZE,
    _UPLOAD_CHUNK_SIZE,
    HealthResponse,
    is_local_client,
    shell_tools_enabled_for_request,
    validate_path_param,
)

# UTF-8 on Windows
import sys as _sys
for _s in ("stdout", "stderr"):
    _r = getattr(getattr(_sys, _s, None), "reconfigure", None)
    if callable(_r):
        _r(encoding="utf-8", errors="replace")

# Rich console for colored logs
console = Console()

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AStockPursue API",
    description="AStockPursue API: natural-language finance research, backtesting, and swarm workflows",
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
    if raw is None or not raw.strip():
        return list(_DEFAULT_CORS_ORIGINS)
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS='*' is not allowed while credentials are enabled; "
            "configure explicit Web UI origins instead."
        )
    return origins


_CORS_ORIGINS = _parse_cors_origins(os.getenv("CORS_ORIGINS"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup event
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def _run_startup_preflight() -> None:
    """Run preflight checks on server startup."""
    from src.preflight import run_preflight

    run_preflight(console)

    # Initialize PostgreSQL connection pool and auto-migrate
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

    # Load default user's data-source tokens into os.environ
    # Single-user design: user_id=1 is the default admin user.
    try:
        from src.auth.user_config import load_user_config
        load_user_config(1)
        console.print("[green]Default user data-source tokens loaded[/green]")
    except Exception as e:
        console.print(f"[yellow]Default user tokens not loaded:[/yellow] {e}")

    # Initialize paper trading scheduler
    try:
        from papertrade.scheduler import PaperTradingScheduler
        app.state.paper_trading_scheduler = PaperTradingScheduler()
        console.print("[green]Paper trading scheduler initialized[/green]")
    except Exception as e:
        console.print(f"[yellow]Paper trading scheduler init skipped:[/yellow] {e}")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

_security = HTTPBearer(auto_error=False)
_SHELL_TOOLS_ENV = "ASTOCKPURSUE_ENABLE_SHELL_TOOLS"
_DOCKER_LOOPBACK_ENV = "ASTOCKPURSUE_TRUST_DOCKER_LOOPBACK"


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _default_gateway_ips() -> set:
    """Return IPv4 default gateway addresses from Linux procfs."""
    gateways: set = set()
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


def _load_ds_tokens(user_id: int) -> None:
    """Load per-user data-source tokens into os.environ.
    Single-user design: most users only have user_id=1.
    """
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

    Also loads per-user data-source tokens into os.environ.
    """
    api_key = os.getenv("API_AUTH_KEY", "")
    if not api_key and is_local_client(request):
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


# ---------------------------------------------------------------------------
# API versioning
# ---------------------------------------------------------------------------

API_PREFIX = "/v1"
v1 = APIRouter(prefix=API_PREFIX)

# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

# --- Already-extracted route modules (use APIRouter directly) ---
from src.api.alpha_routes import register_alpha_routes  # noqa: E402
register_alpha_routes(v1)

from src.api.indicator_lab_routes import router as indicator_lab_router  # noqa: E402
v1.include_router(indicator_lab_router, dependencies=[Depends(require_auth)])

from src.api.strategy_lab_routes import router as strategy_lab_router  # noqa: E402
v1.include_router(strategy_lab_router, dependencies=[Depends(require_auth)])

from src.api.stock_routes import router as stock_router  # noqa: E402
v1.include_router(stock_router, dependencies=[Depends(require_auth)])

from src.api.paper_trading_routes import router as paper_trading_router  # noqa: E402
v1.include_router(paper_trading_router, dependencies=[Depends(require_auth)])

# --- New route modules (use create_router factory) ---
from src.api.runs_routes import create_router as create_runs_router  # noqa: E402
v1.include_router(create_runs_router(require_auth), dependencies=[Depends(require_auth)])

from src.api.sessions_routes import create_router as create_sessions_router  # noqa: E402
v1.include_router(create_sessions_router(require_auth), dependencies=[Depends(require_auth)])

from src.api.settings_routes import create_router as create_settings_router  # noqa: E402
v1.include_router(create_settings_router(require_auth), dependencies=[Depends(require_auth)])

from src.api.auth_routes import create_router as create_auth_router  # noqa: E402
v1.include_router(create_auth_router(require_auth))

from src.api.system_routes import create_router as create_system_router  # noqa: E402
v1.include_router(create_system_router(require_auth))

# Version endpoint — reads from project root VERSION
_VERSION_PATH = Path(__file__).resolve().parent.parent / "VERSION"


@v1.get("/version")
def get_version():
    try:
        ver = _VERSION_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        ver = "0.0.0"
    return {"version": ver}


app.include_router(v1)


# ---------------------------------------------------------------------------
# Backward-compatible re-exports for tests (moved to common.py / settings_routes.py)
# ---------------------------------------------------------------------------

from src.api.common import build_response_from_run_dir  # noqa: E402
_build_response_from_run_dir = build_response_from_run_dir
_is_local_client = is_local_client
_shell_tools_enabled_for_request = shell_tools_enabled_for_request
_validate_path_param = validate_path_param

from src.api.settings_routes import (  # noqa: E402
    _read_user_llm_config,
    _read_user_ds_config,
    _write_user_llm_config,
    _write_user_ds_config,
)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def serve_main(argv: list[str] | None = None) -> int:
    """Start the API server from CLI-style arguments."""
    import argparse
    import subprocess
    import uvicorn
    from fastapi.staticfiles import StaticFiles
    from starlette.exceptions import HTTPException as StarletteHTTPException

    class SPAStaticFiles(StaticFiles):
        """Serve index.html for browser refreshes on client-side routes."""

        async def get_response(self, path: str, scope: dict):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as exc:
                if exc.status_code != 404:
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
