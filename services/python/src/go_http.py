"""Lightweight HTTP client for calling Go REST API from Python workflow nodes.

Go auth middleware accepts X-API-Key header (set GO_API_KEY env var to match
Go's API_KEY).  When API_KEY is not set, Go allows all requests.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

GO_BASE = os.environ.get("GO_API_URL", "http://localhost:8899").rstrip("/")
GO_API_KEY = os.environ.get("GO_API_KEY", "")
_http_retries = int(os.environ.get("GO_HTTP_RETRIES", "2"))


def _request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Make an HTTP request to Go REST API.

    Returns decoded JSON dict.  On any failure returns ``{"error": "..."}``
    so callers can degrade gracefully.
    """
    url = f"{GO_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if GO_API_KEY:
        req.add_header("X-API-Key", GO_API_KEY)

    for attempt in range(_http_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            if 500 <= exc.code < 600 and attempt < _http_retries:
                time.sleep(0.1 * (attempt + 1))
                continue
            # 非 5xx 或已耗尽重试次数，走原有错误处理
            try:
                detail = json.loads(exc.read())
                msg = detail.get("error", exc.reason)
            except Exception:
                msg = exc.reason
            logger.warning("Go API HTTP %s %s: %s", exc.code, path, msg)
            return {"error": f"HTTP {exc.code}: {msg}"}
        except (urllib.error.URLError, OSError) as exc:
            if attempt < _http_retries:
                delay = 0.1 * (attempt + 1) + random.uniform(0, 0.05)
                time.sleep(delay)
                continue
            logger.warning("Go API error %s: %s", path, exc)
            return {"error": str(exc)}
        except Exception as exc:
            logger.warning("Go API error %s: %s", path, exc)
            return {"error": str(exc)}


def broker_list() -> dict[str, Any]:
    """GET /api/v1/broker/list — list registered brokers."""
    return _request("GET", "/api/v1/broker/list")


def broker_positions() -> dict[str, Any]:
    """GET /api/v1/broker/positions — get positions across brokers."""
    return _request("GET", "/api/v1/broker/positions")


def broker_account() -> dict[str, Any]:
    """GET /api/v1/broker/account — get account balances."""
    return _request("GET", "/api/v1/broker/account")


def run_backtest(config: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/backtest — run a backtest.

    Required config keys: ``symbols``, ``start_date``, ``end_date``,
    ``frequency``, ``initial_cash``.
    """
    return _request("POST", "/api/v1/backtest", config)


def get_market_bars(
    symbol: str,
    start: str,
    end: str,
    freq: str = "1d",
) -> dict[str, Any]:
    """GET /api/v1/market/bars — fetch OHLCV bars."""
    params = f"symbol={symbol}&start={start}&end={end}&frequency={freq}"
    return _request("GET", f"/api/v1/market/bars?{params}")
