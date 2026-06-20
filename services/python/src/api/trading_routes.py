"""Trading Dashboard REST API — OMS, broker, notify, optimize, indices, news.

All multi-tenant endpoints isolate data per authenticated user_id.

TODO(P5-task8): The data-access paths in this module use direct loader
imports (FutuLoader for broker status, tencent helpers for index prices,
NewsFetcher for news).  None of these are simple OHLCV fetches suitable
for the DataService gRPC migration:
- ``broker_status`` uses FutuLoader for connectivity checks, not bar data.
- ``get_indices`` uses tencent real-time quote helpers, not historical bars.
- ``get_news`` uses NewsFetcher (web search / Finnhub), not bar data.
These should remain as-is until the DataService proto is extended with
broker-status, real-time-quote, and news-fetch RPCs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from src.api.common import safe_error
from src.auth.dependencies import require_auth
from src.services.sentiment_analyzer import SentimentAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trading", tags=["trading"])

# ---------------------------------------------------------------------------
# Config file helpers (per-user JSON in backend/.user_configs/)
# ---------------------------------------------------------------------------

_USER_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / ".user_configs"


def _notify_config_path(user_id: int) -> Path:
    """Return the filesystem path to a user's notification config JSON.

    Args:
        user_id: Authenticated user ID.

    Returns:
        ``Path`` to ``.user_configs/<user_id>/notify_config.json``.
    """
    return _USER_CONFIGS_DIR / str(user_id) / "notify_config.json"


def _indices_config_path(user_id: int) -> Path:
    """Return the filesystem path to a user's indices config JSON.

    Args:
        user_id: Authenticated user ID.

    Returns:
        ``Path`` to ``.user_configs/<user_id>/indices_config.json``.
    """
    return _USER_CONFIGS_DIR / str(user_id) / "indices_config.json"


def _load_json(path: Path) -> dict:
    """Load a JSON file, returning an empty dict on any error.

    Args:
        path: Filesystem path to the JSON file.

    Returns:
        Parsed dict, or ``{}`` if the file does not exist or is malformed.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    """Save a dict to a JSON file, creating parent directories as needed.

    Args:
        path: Filesystem path for the output file.
        data: Dict to serialize as JSON.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ===================================================================
# Orders / OMS — PostgreSQL-backed, multi-user isolated
# ===================================================================

_TABLE = "vt_trading_orders"
_COLS = "id, user_id, symbol, side, order_type, qty, price, status, filled_qty, avg_price, created_at, updated_at"


def _order_row_to_dict(row: tuple) -> dict:
    """Convert a DB row tuple to a JSON-safe dict matching the TradingOrder TypeScript interface.

    Args:
        row: Tuple from ``SELECT id, user_id, symbol, side, order_type,
            qty, price, status, filled_qty, avg_price, created_at, updated_at``.

    Returns:
        Dict with camelCase-friendly keys ready for JSON serialization.
    """
    return {
        "id": row[0],
        "user_id": row[1],
        "symbol": row[2],
        "side": row[3],
        "order_type": row[4],
        "qty": float(row[5]),
        "price": float(row[6]),
        "status": row[7],
        "filled_qty": float(row[8]),
        "avg_price": float(row[9]),
        "created_at": row[10].isoformat() if hasattr(row[10], "isoformat") else str(row[10]),
    }


def _get_user_id(auth: dict) -> int:
    """Extract the authenticated user ID from the auth dependency dict.

    Args:
        auth: Auth payload from ``require_auth`` dependency.

    Returns:
        Integer user ID for multi-tenant data isolation.
    """
    return int(auth["user_id"])


@router.get("/orders")
async def list_orders(
    user: dict = Depends(require_auth),
    status: str = Query("", description="Filter: active, filled, cancelled, all"),
):
    """List orders for the current user."""
    user_id = _get_user_id(user)
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                if status and status != "all":
                    cur.execute(
                        f"SELECT {_COLS} FROM {_TABLE} WHERE user_id=%s AND status=%s ORDER BY created_at DESC",
                        (user_id, status),
                    )
                else:
                    cur.execute(
                        f"SELECT {_COLS} FROM {_TABLE} WHERE user_id=%s ORDER BY created_at DESC",
                        (user_id,),
                    )
                orders = [_order_row_to_dict(r) for r in cur.fetchall()]
        return {"orders": orders}
    except Exception as e:
        logger.exception("list_orders failed for user %s", user_id)
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.post("/orders")
async def create_order(request: Request, user: dict = Depends(require_auth)):
    """Place a new order."""
    user_id = _get_user_id(user)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    symbol = str(body.get("symbol", "")).strip().upper()
    side = str(body.get("side", "buy")).lower()
    order_type = str(body.get("order_type", "market")).lower()
    qty = float(body.get("qty", 0))
    price = float(body.get("price", 0)) if order_type == "limit" else 0.0

    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    if side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be buy or sell")
    if qty <= 0:
        raise HTTPException(status_code=400, detail="qty must be positive")
    if order_type == "limit" and price <= 0:
        raise HTTPException(status_code=400, detail="price required for limit orders")

    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {_TABLE} (user_id, symbol, side, order_type, qty, price, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 'active') RETURNING {_COLS}",
                    (user_id, symbol, side, order_type, qty, price),
                )
                order = _order_row_to_dict(cur.fetchone())
        return {"ok": True, "order": order}
    except Exception as e:
        logger.exception("create_order failed for user %s", user_id)
        raise HTTPException(status_code=500, detail=safe_error(e))


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, user: dict = Depends(require_auth)):
    """Cancel an active order. Only the owner can cancel."""
    user_id = _get_user_id(user)
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Fetch + verify ownership in one query
                cur.execute(
                    f"SELECT {_COLS} FROM {_TABLE} WHERE id=%s AND user_id=%s",
                    (order_id, user_id),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Order not found")

                order = _order_row_to_dict(row)
                if order["status"] != "active":
                    raise HTTPException(status_code=400, detail="Order cannot be cancelled")

                cur.execute(
                    f"UPDATE {_TABLE} SET status='cancelled', updated_at=now() WHERE id=%s AND user_id=%s",
                    (order_id, user_id),
                )
                order["status"] = "cancelled"
        return {"ok": True, "order": order}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("cancel_order failed for user %s, order %s", user_id, order_id)
        raise HTTPException(status_code=500, detail=safe_error(e))


# ===================================================================
# Broker (Futu) — per-user context isolation
# ===================================================================

# Cache of (host, port, ctx) per user_id to avoid reconnecting on every request.
# Keys are removed when the connection fails so the next request retries.
_broker_contexts: dict[int, tuple[str, int, Any]] = {}


def _get_broker_ctx(user_id: int) -> Any:
    """Return a cached Futu OpenSecTradeContext for *user_id*, or create one.

    Each user may point to a different FutuOpenD instance by setting
    ``FUTU_HOST`` / ``FUTU_PORT`` in their per-user env config.  Falls
    back to the global env vars.  Reuses cached connections; if the
    host/port changes for a user the old context is closed and a new one
    is created.

    Args:
        user_id: Authenticated user ID used as the cache key.

    Returns:
        An ``OpenSecTradeContext`` instance, or ``None`` if the ``futu``
        package is not installed.
    """
    host = os.getenv("FUTU_HOST", "127.0.0.1")
    port = int(os.getenv("FUTU_PORT", "11111"))
    key = (user_id, host, port)

    cached = _broker_contexts.get(user_id)
    if cached is not None:
        cached_host, cached_port, ctx = cached
        if cached_host == host and cached_port == port:
            return ctx
        # Config changed — close old context
        try:
            ctx.close()
        except Exception as _e:
            logger.debug("Failed to close old broker context for user %s: %s", user_id, _e)
            pass
        _broker_contexts.pop(user_id, None)

    try:
        from futu import OpenSecTradeContext, TrdEnv
        ctx = OpenSecTradeContext(host=host, port=port)
        _broker_contexts[user_id] = (host, port, ctx)
        return ctx
    except ImportError:
        return None


@router.get("/broker/status")
async def broker_status(user: dict = Depends(require_auth)):
    """Check FutuOpenD connection status (per-user environment)."""
    user_id = _get_user_id(user)
    host = os.getenv("FUTU_HOST", "127.0.0.1")
    port = int(os.getenv("FUTU_PORT", "11111"))
    try:
        from backtest.loaders.futu import FutuLoader
        loader = FutuLoader()
        available = loader.is_available()
    except Exception as e:
        return {"connected": False, "error": str(e), "host": host, "port": port}

    return {"connected": available, "host": host, "port": port}


@router.get("/broker/account")
async def broker_account(user: dict = Depends(require_auth)):
    """Get Futu account info (per-user context)."""
    user_id = _get_user_id(user)
    try:
        ctx = _get_broker_ctx(user_id)
        if ctx is None:
            return {"available": False, "error": "futu package not installed"}
        ret, data = ctx.accinfo_query()
        if ret != 0:
            return {"available": False, "error": str(data)}
        row = data.iloc[0] if data is not None and len(data) > 0 else None
        return {"available": True, "account": _pandas_row_to_dict(row) if row is not None else {}}
    except Exception as e:
        # Connection lost — clear cache so next request retries
        _broker_contexts.pop(user_id, None)
        return {"available": False, "error": safe_error(e)}


@router.get("/broker/positions")
async def broker_positions(user: dict = Depends(require_auth)):
    """Get Futu positions (per-user context)."""
    user_id = _get_user_id(user)
    try:
        ctx = _get_broker_ctx(user_id)
        if ctx is None:
            return {"positions": [], "error": "futu package not installed"}
        ret, data = ctx.position_list_query()
        if ret != 0:
            return {"positions": [], "error": str(data)}
        if data is None or len(data) == 0:
            return {"positions": []}
        return {"positions": [_pandas_row_to_dict(row) for _, row in data.iterrows()]}
    except Exception as e:
        _broker_contexts.pop(user_id, None)
        return {"positions": [], "error": safe_error(e)}


def _pandas_row_to_dict(row) -> dict:
    """Convert a pandas Series/row to a plain dict with JSON-safe values.

    Handles ``pd.Timestamp`` (converted to ISO string), ``NaN`` floats
    (converted to ``None``), and other non-serialisable types.

    Args:
        row: A pandas Series, DataFrame row, or plain dict.

    Returns:
        A plain ``dict`` suitable for JSON serialization.  Returns an
        empty dict if *row* is ``None`` or cannot be converted.
    """
    import pandas as pd
    if row is None:
        return {}
    if hasattr(row, "to_dict"):
        d = row.to_dict()
    elif isinstance(row, dict):
        d = row
    else:
        return {}
    result: dict = {}
    for k, v in d.items():
        key = str(k)
        if isinstance(v, (pd.Timestamp,)):
            result[key] = str(v)
        elif isinstance(v, float) and (pd.isna(v) or v != v):
            result[key] = None
        else:
            result[key] = v
    return result


# ===================================================================
# Multi-Broker (Futu / Binance / OKX) — credential management + queries
# ===================================================================

_AVAILABLE_BROKERS = [
    {"id": "futu", "label": "Futu (富途)", "fields": ["host", "port"], "note": "Requires FutuOpenD running locally"},
    {"id": "binance", "label": "Binance", "fields": ["api_key", "secret_key"], "note": "USDT-M perpetual futures. Supports testnet."},
    {"id": "okx", "label": "OKX", "fields": ["api_key", "secret_key", "passphrase"], "note": "Perpetual swaps. Supports demo trading."},
]


@router.get("/broker/list")
async def broker_list(user: dict = Depends(require_auth)):
    """List available broker types with their required config fields."""
    return {"brokers": _AVAILABLE_BROKERS}


@router.get("/broker/credentials")
async def broker_credentials_get(user: dict = Depends(require_auth)):
    """Get saved broker credentials for the current user (keys masked)."""
    from src.db.async_pool import async_get_connection

    user_id = _get_user_id(user)
    try:
        async with async_get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, exchange_id, label, testnet, is_active, created_at, updated_at
                   FROM broker_credentials WHERE user_id = %s ORDER BY exchange_id, label""",
                (user_id,),
            )
            rows = cur.fetchall()
            cur.close()
            cols = ["id", "exchange_id", "label", "testnet", "is_active", "created_at", "updated_at"]
            return {"credentials": [dict(zip(cols, r)) for r in rows]}
    except Exception as e:
        return {"credentials": [], "error": safe_error(e)}


@router.post("/broker/credentials")
async def broker_credentials_save(payload: dict, user: dict = Depends(require_auth)):
    """Save or update broker credentials for an exchange.

    Request body:
        exchange_id: str — futu | binance | okx
        label: str (optional) — user-defined label
        api_key: str — API key
        secret_key: str — secret key
        passphrase: str (optional) — OKX passphrase
        testnet: bool — use testnet/demo
    """
    from src.db.async_pool import async_get_connection
    from src.trading.credential_store import encrypt_credential

    user_id = _get_user_id(user)
    exchange_id = payload.get("exchange_id", "")
    if exchange_id not in [b["id"] for b in _AVAILABLE_BROKERS]:
        raise HTTPException(400, f"Unknown exchange: {exchange_id}")

    api_key = payload.get("api_key", "")
    secret_key = payload.get("secret_key", "")
    passphrase = payload.get("passphrase", "")
    label = payload.get("label", "")
    testnet = payload.get("testnet", True)

    enc_api = encrypt_credential(api_key) if api_key else ""
    enc_secret = encrypt_credential(secret_key) if secret_key else ""
    enc_pass = encrypt_credential(passphrase) if passphrase else None

    try:
        async with async_get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO broker_credentials (user_id, exchange_id, label, api_key_enc, secret_key_enc, passphrase_enc, testnet)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id, exchange_id, label)
                   DO UPDATE SET api_key_enc=EXCLUDED.api_key_enc, secret_key_enc=EXCLUDED.secret_key_enc,
                                 passphrase_enc=EXCLUDED.passphrase_enc, testnet=EXCLUDED.testnet, updated_at=NOW()""",
                (user_id, exchange_id, label, enc_api, enc_secret, enc_pass, testnet),
            )
            cur.close()
        return {"status": "ok", "exchange_id": exchange_id}
    except Exception as e:
        raise HTTPException(500, safe_error(e))


@router.delete("/broker/credentials/{credential_id}")
async def broker_credentials_delete(credential_id: int, user: dict = Depends(require_auth)):
    """Delete saved broker credentials."""
    from src.db.async_pool import async_get_connection

    user_id = _get_user_id(user)
    try:
        async with async_get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM broker_credentials WHERE id = %s AND user_id = %s",
                (credential_id, user_id),
            )
            cur.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, safe_error(e))


@router.post("/broker/test")
async def broker_test_connection(payload: dict, user: dict = Depends(require_auth)):
    """Test connection to a broker exchange.

    Request body:
        exchange_id: str — futu | binance | okx
        testnet: bool
    """
    from src.db.async_pool import async_get_connection
    from src.trading.credential_store import decrypt_credential

    exchange_id = payload.get("exchange_id", "")
    testnet = payload.get("testnet", True)
    user_id = _get_user_id(user)

    try:
        creds = {}
        if exchange_id != "futu":
            async with async_get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """SELECT api_key_enc, secret_key_enc, passphrase_enc
                       FROM broker_credentials
                       WHERE user_id = %s AND exchange_id = %s AND is_active = TRUE
                       LIMIT 1""",
                    (user_id, exchange_id),
                )
                rows = cur.fetchall()
                cur.close()
                if rows:
                    api_enc, secret_enc, pass_enc = rows[0]
                    creds["api_key"] = decrypt_credential(api_enc or "")
                    creds["secret_key"] = decrypt_credential(secret_enc or "")
                    if pass_enc:
                        creds["passphrase"] = decrypt_credential(pass_enc)

        if exchange_id == "futu":
            ctx = _get_broker_ctx(user_id)
            connected = ctx is not None
            return {"connected": connected, "exchange": "futu",
                    "error": None if connected else "futu package not installed or FutuOpenD not running"}

        from src.trading.brokers import create_broker
        broker = create_broker(exchange_id, {**creds, "testnet": testnet})
        connected = await broker.test_connection()
        if hasattr(broker, "close"):
            await broker.close()
        return {"connected": connected, "exchange": exchange_id, "testnet": testnet}

    except Exception as e:
        return {"connected": False, "exchange": exchange_id, "error": safe_error(e)}


@router.get("/broker/{exchange_id}/positions")
async def broker_positions_multi(exchange_id: str, user: dict = Depends(require_auth), testnet: bool = True):
    """Get positions from a specific exchange (Binance/OKX)."""
    from src.db.async_pool import async_get_connection
    from src.trading.credential_store import decrypt_credential

    if exchange_id == "futu":
        return await broker_positions(user)

    user_id = _get_user_id(user)
    try:
        async with async_get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT api_key_enc, secret_key_enc, passphrase_enc
                   FROM broker_credentials
                   WHERE user_id = %s AND exchange_id = %s AND is_active = TRUE
                   LIMIT 1""",
                (user_id, exchange_id),
            )
            rows = cur.fetchall()
            cur.close()

        if not rows:
            return {"positions": [], "error": f"No credentials saved for {exchange_id}"}

        api_enc, secret_enc, pass_enc = rows[0]
        creds = {
            "api_key": decrypt_credential(api_enc or ""),
            "secret_key": decrypt_credential(secret_enc or ""),
        }
        passphrase = decrypt_credential(pass_enc or "")
        if passphrase:
            creds["passphrase"] = passphrase

        from src.trading.brokers import create_broker
        broker = create_broker(exchange_id, {**creds, "testnet": testnet})
        positions = await broker.get_positions()
        if hasattr(broker, "close"):
            await broker.close()

        return {"positions": [p.__dict__ if hasattr(p, "__dict__") else p for p in positions]}
    except Exception as e:
        return {"positions": [], "error": safe_error(e)}


@router.get("/broker/{exchange_id}/balance")
async def broker_balance_multi(exchange_id: str, user: dict = Depends(require_auth), testnet: bool = True):
    """Get balance from a specific exchange (Binance/OKX)."""
    from src.db.async_pool import async_get_connection
    from src.trading.credential_store import decrypt_credential

    if exchange_id == "futu":
        return await broker_account(user)

    user_id = _get_user_id(user)
    try:
        async with async_get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT api_key_enc, secret_key_enc, passphrase_enc
                   FROM broker_credentials
                   WHERE user_id = %s AND exchange_id = %s AND is_active = TRUE
                   LIMIT 1""",
                (user_id, exchange_id),
            )
            rows = cur.fetchall()
            cur.close()

        if not rows:
            return {"balance": {}, "error": f"No credentials saved for {exchange_id}"}

        api_enc, secret_enc, pass_enc = rows[0]
        creds = {
            "api_key": decrypt_credential(api_enc or ""),
            "secret_key": decrypt_credential(secret_enc or ""),
        }
        passphrase = decrypt_credential(pass_enc or "")
        if passphrase:
            creds["passphrase"] = passphrase

        from src.trading.brokers import create_broker
        broker = create_broker(exchange_id, {**creds, "testnet": testnet})
        bal = await broker.get_balance()
        if hasattr(broker, "close"):
            await broker.close()

        return {"balance": bal.__dict__ if hasattr(bal, "__dict__") else bal}
    except Exception as e:
        return {"balance": {}, "error": safe_error(e)}


# ===================================================================
# Notify (per-user JSON config files)
# ===================================================================


@router.get("/notify/config")
async def get_notify_config(user: dict = Depends(require_auth)):
    """Get notification configuration for the current user."""
    user_id = _get_user_id(user)
    return _load_json(_notify_config_path(user_id))


@router.put("/notify/config")
async def update_notify_config(request: Request, user: dict = Depends(require_auth)):
    """Update notification configuration."""
    user_id = _get_user_id(user)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    _save_json(_notify_config_path(user_id), body)
    return {"ok": True, "config": body}


@router.post("/notify/test")
async def test_notify(request: Request, user: dict = Depends(require_auth)):
    """Send a test notification."""
    user_id = _get_user_id(user)
    try:
        body = await request.json()
        channel = body.get("channel", "email")
        target = body.get("target", "")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        from src.notify import send_alert
        send_alert(f"[AStockPursue] Test — user {user_id}", f"Channel: {channel}", channel=channel)
        return {"ok": True, "message": f"Test notification sent via {channel}"}
    except Exception as e:
        return {"ok": False, "error": safe_error(e)}


# ===================================================================
# Optimize (per-user jobs — isolated by user_id in the jobs dict)
# ===================================================================

_OPTIMIZE_JOBS: dict[str, dict] = {}


@router.post("/optimize/run")
async def start_optimize(request: Request, user: dict = Depends(require_auth)):
    """Start a parameter optimisation job.

    Body:
        method: "grid" | "random" | "bayesian"
        params: {param_name: [value1, value2, ...]}  — search space
        codes: [symbol, ...]
        strategy_code: optional — strategy to inject params into
    """
    user_id = _get_user_id(user)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    job_id = uuid.uuid4().hex[:12]
    method = body.get("method", "grid")
    params = body.get("params", {})
    codes = body.get("codes", [])
    strategy_code = body.get("strategy_code", "")

    _OPTIMIZE_JOBS[job_id] = {
        "job_id": job_id,
        "user_id": user_id,
        "method": method,
        "params": params,
        "codes": codes,
        "strategy_code": strategy_code,
        "status": "queued",
        "progress": 0,
        "result": None,
        "queue": asyncio.Queue(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    asyncio.create_task(_run_optimize(job_id))
    return {"ok": True, "job_id": job_id}


def _build_param_combinations(params: dict) -> list[dict]:
    """Build all Cartesian-product combinations for grid-search optimization.

    Args:
        params: Dict mapping parameter names to lists of candidate values,
            e.g. ``{"lookback": [10, 20], "threshold": [0.5, 0.8]}``.

    Returns:
        List of param dicts, each representing one grid point, e.g.
        ``[{"lookback": 10, "threshold": 0.5}, {"lookback": 10,
        "threshold": 0.8}, ...]``.  Returns ``[{}]`` if *params* is empty.
    """
    if not params:
        return [{}]
    import itertools
    keys = list(params.keys())
    values = [params[k] for k in keys]
    combinations = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))
    return combinations


def _inject_params(strategy_code: str, params: dict) -> str:
    """Inject parameter values into strategy code by replacing top-level assignments.

    Uses regex to find module-level assignments like ``LOOKBACK = 20``
    and replace the value with the optimised parameter.

    Args:
        strategy_code: Python source code of the strategy.
        params: Dict mapping parameter names to values, e.g.
            ``{"LOOKBACK": 15, "THRESHOLD": 0.75}``.

    Returns:
        Modified strategy code with injected parameter values.  Float
        values are formatted to 4 decimal places.
    """
    import re
    code = strategy_code
    for name, value in params.items():
        val_str = str(value) if not isinstance(value, float) else f"{value:.4f}"
        # Replace module-level assignments like `NAME = old_value`
        code = re.sub(
            rf"^({name}\s*=\s*)(.+)$",
            rf"\g<1>{val_str}",
            code,
            flags=re.MULTILINE,
        )
    return code


async def _run_optimize(job_id: str) -> None:
    """Background optimisation worker — grid search over parameter space.

    Iterates over all parameter combinations, runs a backtest for each,
    and tracks the best-scoring combination.  Progress updates are pushed
    to the job's ``asyncio.Queue`` for SSE streaming.

    Args:
        job_id: UUID identifying the optimisation job in ``_OPTIMIZE_JOBS``.
    """
    job = _OPTIMIZE_JOBS.get(job_id)
    if not job:
        return
    job["status"] = "running"

    try:
        param_space = job.get("params", {})
        codes = job.get("codes", [])
        strategy_code = job.get("strategy_code", "")

        combinations = _build_param_combinations(param_space)
        total = len(combinations)

        if total == 0:
            job["status"] = "failed"
            job["error"] = "No parameter combinations to test"
            return

        best_score = float("-inf")
        best_params: dict = {}
        best_metrics: dict = {}

        for idx, combo in enumerate(combinations):
            # Inject params into strategy code
            test_code = _inject_params(strategy_code, combo) if strategy_code else ""

            # Run backtest
            score = 0.0
            metrics: dict = {}
            try:
                from src.lab.strategy_backtest_bridge import run_strategy_backtest

                result = run_strategy_backtest(
                    code=test_code or strategy_code,
                    codes=codes,
                    start_date="2023-01-01",
                    end_date="2025-12-31",
                    initial_cash=100_000,
                )
                if result.get("success"):
                    m = result.get("metrics", {})
                    score = float(m.get("sharpe", 0)) or float(m.get("total_return", 0))
                    metrics = {k: v for k, v in m.items() if isinstance(v, (int, float))}
            except Exception as e:
                logger.debug("Optimize iteration %d/%d failed: %s", idx + 1, total, e)

            if score > best_score:
                best_score = score
                best_params = combo
                best_metrics = metrics

            # Progress update every combination
            progress = int((idx + 1) / total * 100)
            job["progress"] = progress
            await job["queue"].put({
                "job_id": job_id, "progress": progress, "status": "running",
                "iter": idx + 1, "total": total,
            })
            # Yield to event loop
            await asyncio.sleep(0)

        job["result"] = {
            "best_params": best_params,
            "best_score": round(best_score, 4),
            "iterations": total,
            **best_metrics,
        }
        job["status"] = "completed"
        await job["queue"].put({
            "job_id": job_id, "progress": 100, "status": "completed", "result": job["result"],
        })
    except Exception as e:
        job["status"] = "failed"
        job["error"] = safe_error(e)
        await job["queue"].put({
            "job_id": job_id, "progress": job["progress"], "status": "failed", "error": job["error"],
        })


def _check_optimize_job_owner(job_id: str, user_id: int) -> dict:
    """Verify job ownership for multi-tenant isolation.

    Args:
        job_id: UUID of the optimisation job.
        user_id: Authenticated user ID to check against.

    Returns:
        The job dict if the user owns it.

    Raises:
        HTTPException 404: If the job does not exist or belongs to
            another user.
    """
    job = _OPTIMIZE_JOBS.get(job_id)
    if not job or job["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/optimize/{job_id}/stream")
async def stream_optimize(job_id: str, user: dict = Depends(require_auth)):
    """SSE stream for optimisation progress (ownership verified)."""
    user_id = _get_user_id(user)
    job = _check_optimize_job_owner(job_id, user_id)

    async def _stream():
        yield f"data: {json.dumps({'job_id': job_id, 'progress': job['progress'], 'status': job['status']})}\n\n"
        while job["status"] in ("queued", "running"):
            try:
                msg = await asyncio.wait_for(job["queue"].get(), timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("status") in ("completed", "failed"):
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'job_id': job_id, 'status': 'running', 'progress': job['progress']})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/optimize/{job_id}/result")
async def get_optimize_result(job_id: str, user: dict = Depends(require_auth)):
    """Get the result of a completed optimisation job."""
    user_id = _get_user_id(user)
    job = _check_optimize_job_owner(job_id, user_id)
    return {"job_id": job_id, "status": job["status"], "result": job.get("result")}


# ===================================================================
# WebSocket Feed — per-user subscription isolation
# ===================================================================

# Per-user set of subscribed symbols
_subscriptions: dict[int, set[str]] = {}


@router.get("/ws-feed/status")
async def ws_feed_status(user: dict = Depends(require_auth)):
    """Get market feed status for the current user's subscriptions."""
    user_id = _get_user_id(user)
    subs = _subscriptions.get(user_id, set())
    try:
        from src.trading.ws_feed import MarketFeed
        feed = MarketFeed()
        running = feed.is_running() if hasattr(feed, "is_running") else False
        return {"available": running, "subscriptions": sorted(subs)}
    except Exception:
        return {"available": False, "subscriptions": sorted(subs), "error": "MarketFeed not available"}


@router.post("/ws-feed/subscribe")
async def ws_feed_subscribe(request: Request, user: dict = Depends(require_auth)):
    """Subscribe to symbols via the WebSocket feed (per-user)."""
    user_id = _get_user_id(user)
    try:
        body = await request.json()
        symbols = body.get("symbols", [])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _subscriptions[user_id] = _subscriptions.get(user_id, set()) | set(symbols)

    try:
        from src.trading.ws_feed import MarketFeed
        feed = MarketFeed()
        if hasattr(feed, "subscribe"):
            feed.subscribe(list(_subscriptions[user_id]))
        return {"ok": True, "symbols": sorted(_subscriptions[user_id])}
    except Exception as e:
        return {"ok": False, "error": safe_error(e)}


# ===================================================================
# Indices (per-user JSON config)
# ===================================================================

_DEFAULT_INDICES = [
    {"code": "000001.SH", "name": "上证指数"},
    {"code": "399001.SZ", "name": "深证成指"},
    {"code": "399006.SZ", "name": "创业板指"},
    {"code": "000688.SH", "name": "科创50"},
    {"code": "000300.SH", "name": "沪深300"},
]


@router.get("/indices")
async def get_indices(user: dict = Depends(require_auth)):
    """Get configured indices with latest prices."""
    user_id = _get_user_id(user)
    config = _load_json(_indices_config_path(user_id))
    items = config.get("indices", _DEFAULT_INDICES)

    try:
        from backtest.loaders.tencent import normalize_cn_code, _is_cn, normalize_hk_code, _is_hk
    except ImportError:
        return {"indices": [{"code": it["code"], "name": it["name"], "price": 0, "change_pct": 0} for it in items]}

    result = []
    for it in items:
        code = it["code"]
        price, change = 0.0, 0.0
        try:
            import requests
            if _is_cn(code):
                tc = normalize_cn_code(code)
            elif _is_hk(code):
                tc = normalize_hk_code(code)
            else:
                tc = code
            resp = requests.get(f"https://qt.gtimg.cn/q={tc}", timeout=5,
                              headers={"Referer": "https://qt.gtimg.cn/"})
            resp.encoding = "gbk"
            text = (resp.text or "").strip()
            if "~" in text:
                parts = text.split("~")
                if len(parts) > 4:
                    price = float(parts[3]) if parts[3] else 0
                if len(parts) > 32:
                    change = float(parts[32]) if parts[32] else 0
        except Exception as _e:
            logger.debug("Failed to fetch price for %s: %s", code, _e)
            pass
        result.append({
            "code": code, "name": it["name"],
            "price": round(price, 2), "change_pct": round(change, 2),
        })

    return {"indices": result}


@router.post("/indices/config")
async def save_indices_config(request: Request, user: dict = Depends(require_auth)):
    """Save the user's indices configuration."""
    user_id = _get_user_id(user)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    _save_json(_indices_config_path(user_id), {"indices": body.get("indices", [])})
    return {"ok": True}


# ===================================================================
# News
# ===================================================================


@router.get("/news/{symbol}")
async def get_news(
    symbol: str,
    user: dict = Depends(require_auth),
    limit: int = Query(20, ge=1, le=50),
):
    """Fetch news/articles for a symbol."""
    upper = symbol.strip().upper()
    articles: list[dict] = []
    source = ""

    # 1) Try DuckDuckGo search via NewsFetcher (free, no API key)
    try:
        from backtest.loaders.news import NewsFetcher
        fetcher = NewsFetcher()
        raw = fetcher.fetch_stock_news(upper, max_results=limit)
        for r in raw:
            articles.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "source": r.get("source", "web_search"),
                "summary": r.get("snippet", "")[:200],
                "published_at": "",
            })
        if articles:
            source = "web_search"
    except ImportError:
        pass
    except Exception as e:
        logger.debug("NewsFetcher failed for %s: %s", upper, e)

    # 2) Fallback: Finnhub API (requires FINNHUB_API_KEY)
    if not articles:
        try:
            key = os.getenv("FINNHUB_API_KEY") or os.getenv("FINNHUB_KEY")
            if key:
                import requests
                sym = upper.replace(".US", "").replace(".SH", "").replace(".SZ", "").replace(".HK", "")
                url = f"https://finnhub.io/api/v1/company-news?symbol={sym}&from=2024-01-01&to=2030-01-01&token={key}"
                resp = requests.get(url, timeout=10)
                data = resp.json()
                if isinstance(data, list):
                    for item in data[:limit]:
                        articles.append({
                            "title": item.get("headline", ""),
                            "url": item.get("url", ""),
                            "source": item.get("source", ""),
                            "summary": item.get("summary", "")[:200],
                            "published_at": str(item.get("datetime", "")),
                        })
                    source = "finnhub"
        except Exception as _e:
            logger.debug("Finnhub news fetch failed for %s: %s", upper, _e)
            pass

    # Apply sentiment analysis to all articles
    analyzer = SentimentAnalyzer()
    for a in articles:
        text = f"{a.get('title', '')} {a.get('summary', '')}"
        score = analyzer.analyze_text(text)
        a["sentiment_score"] = score
        a["sentiment_label"] = "positive" if score > 0.6 else ("negative" if score < 0.4 else "neutral")

    # Per-stock sentiment aggregation
    import numpy as np
    scores = [a.get("sentiment_score", 0.5) for a in articles]
    stock_sentiment = {
        "symbol": upper,
        "sentiment_mean": round(float(np.mean(scores)), 4) if scores else 0.5,
        "sentiment_std": round(float(np.std(scores, ddof=1)), 4) if len(scores) > 1 else 0.0,
        "news_count": len(scores),
        "trending_score": round(float(np.mean(scores)) * min(1.0, len(scores) / 10), 4) if scores else 0.0,
    }

    return {"symbol": upper, "articles": articles, "source": source, "stock_sentiment": stock_sentiment}
