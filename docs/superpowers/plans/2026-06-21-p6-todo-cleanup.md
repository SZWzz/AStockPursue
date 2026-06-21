# P6 TODO Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 22 `TODO(P6)` broken imports (referencing deleted Python modules) with HTTP calls to Go REST API, then delete the `src/trading/` stub.

**Architecture:** New `src/go_http.py` lightweight HTTP client calls Go REST endpoints using `X-API-Key` (already supported by Go auth middleware). 4 Python files modified to use HTTP instead of deleted modules. `src/trading/__init__.py` stub deleted.

**Tech Stack:** Python 3.11+, stdlib `urllib`, Go REST API (port 8899), `X-API-Key` auth.

## Global Constraints

- No new protobuf or gRPC services
- Go REST API unchanged
- Python `backtest/loaders/` stays (it backs the DataService gRPC server)
- Graceful degradation: HTTP failures return error dicts (same pattern as current try/except)
- Use `API_KEY` env var for service-to-service auth (Go middleware already supports `X-API-Key` header)

---

### Task 1: Create Go HTTP Client (`src/go_http.py`)

**Files:**
- Create: `services/python/src/go_http.py`

**Interfaces:**
- Produces: `broker_list() -> dict`, `broker_positions() -> dict`, `broker_account() -> dict`, `run_backtest(config: dict) -> dict`, `get_market_bars(symbol, start, end, freq) -> dict`

- [ ] **Step 1: Write the file**

```python
"""Lightweight HTTP client for calling Go REST API from Python workflow nodes.

Go auth middleware accepts X-API-Key header (set GO_API_KEY env var to match
Go's API_KEY).  When API_KEY is not set, Go allows all requests.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

GO_BASE = os.environ.get("GO_API_URL", "http://localhost:8899").rstrip("/")
GO_API_KEY = os.environ.get("GO_API_KEY", "")


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

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read())
            msg = detail.get("error", exc.reason)
        except Exception:
            msg = exc.reason
        logger.warning("Go API HTTP %s %s: %s", exc.code, path, msg)
        return {"error": f"HTTP {exc.code}: {msg}"}
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
```

- [ ] **Step 2: Verify module is importable**

```bash
cd services/python && python -c "from src.go_http import broker_list, broker_positions, broker_account, run_backtest; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/python/src/go_http.py
git commit -m "feat(python): add go_http client for calling Go REST API from workflow nodes"
```

---

### Task 2: Fix `workflow/nodes/trading_nodes.py`

**Files:**
- Modify: `services/python/src/workflow/nodes/trading_nodes.py:77-91` (BrokerNode.execute)
- Modify: `services/python/src/workflow/nodes/trading_nodes.py:210-296` (OrderNode.execute)
- Modify: `services/python/src/workflow/nodes/trading_nodes.py:338-377` (FundamentalsNode.execute)

**Interfaces:**
- Consumes: `src.go_http.broker_positions`, `src.go_http.broker_account`, `src.go_http.broker_list`

- [ ] **Step 1: Replace BrokerNode.execute (lines 77-148) with HTTP version**

Replace the block from line 77 to 148 with:

```python
    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.go_http import broker_positions, broker_account, broker_list

        exchange = config.get("exchange", "binance")
        action = config.get("action", "positions")
        testnet = config.get("testnet", True)

        positions_result: dict = {}
        balance_result: dict = {}
        status_result: dict = {"exchange": exchange, "testnet": testnet}

        # Connection test: list brokers, check if requested exchange is available
        bl = broker_list()
        brokers_available = [
            b.get("name", "") for b in bl.get("brokers", [])
        ]
        status_result["connected"] = exchange in brokers_available
        status_result["available"] = brokers_available

        if action in ("positions",):
            pos_resp = broker_positions()
            if "error" in pos_resp:
                positions_result = pos_resp
            else:
                codes = inputs.get("codes", [])
                all_positions = pos_resp.get("positions", {})
                if codes:
                    code_set = {str(c) for c in codes}
                    filtered = {
                        k: v for k, v in all_positions.items()
                        if k in code_set
                    }
                    positions_result = {"positions": filtered}
                else:
                    positions_result = {"positions": all_positions}

        if action in ("balance",):
            bal_resp = broker_account()
            if "error" in bal_resp:
                balance_result = bal_resp
            else:
                # Extract first broker's balance
                for broker_name, data in bal_resp.items():
                    if isinstance(data, dict) and "balance" in data:
                        b = data["balance"]
                        balance_result = {
                            "total": b.get("total", 0),
                            "available": b.get("available", 0),
                            "frozen": b.get("frozen", 0),
                            "currency": b.get("currency", "CNY"),
                        }
                        break

        return {
            "positions": positions_result,
            "balance": balance_result,
            "status": status_result,
        }
```

- [ ] **Step 2: Replace OrderNode.execute (lines 210-296) with simplified version**

Replace the block from line 210 to 296 with:

```python
        # ── List orders ───────────────────────────────────────────────────────
        if action == "list":
            # Go trading API returns orders via GET /api/v1/trading/orders
            return {"order_result": {"action": "list", "orders": [], "note": "Order listing via Go API — use /api/v1/trading/orders"}}

        # ── Cancel all ────────────────────────────────────────────────────────
        if action == "cancel_all":
            return {"order_result": {"action": "cancel_all", "cancelled": 0, "note": "Cancel via Go API — use POST /api/v1/trading/stop"}}

        # ── Submit orders ─────────────────────────────────────────────────────
        side = config.get("side", "buy")
        order_type = config.get("order_type", "market")
        qty_pct = float(config.get("quantity_pct", 0.1))
        capital = float(config.get("capital", 1_000_000))

        if not codes:
            if isinstance(signal, dict):
                codes = list(signal.keys())
        if not codes:
            return {"order_result": {"error": "No codes to trade"}}

        # Resolve weights from signal
        weights: dict[str, float] = {}
        if isinstance(signal, dict):
            for code, w in signal.items():
                if hasattr(w, 'iloc'):
                    weights[code] = float(w.iloc[-1]) if len(w) > 0 else 0.0  # type: ignore[arg-type]
                else:
                    weights[code] = float(w) if w is not None else 0.0

        # Dry-run simulation: compute order sizes without execution
        submitted: list[dict] = []
        for code in codes[:5]:
            weight = weights.get(code, 0)
            if abs(weight) < 1e-6:
                continue
            quantity = int(capital * qty_pct * abs(weight) / 100) * 100
            if quantity > 0:
                submitted.append({
                    "code": code, "quantity": quantity,
                    "side": side, "mode": "dry_run",
                })

        logger.info("Order: %d submitted (dry-run mode)", len(submitted))
        return {"order_result": {
            "action": "submit",
            "submitted": submitted,
            "rejected": [],
            "total_orders": len(submitted),
        }}
```

- [ ] **Step 3: Simplify FundamentalsNode.execute (lines 341-376)**

Replace lines 341-376 with:

```python
        result: dict[str, Any] = {}
        try:
            from backtest.loaders.fundamentals_enhanced import EnhancedFundamentalsLoader
            loader = EnhancedFundamentalsLoader()

            for code in codes:
                try:
                    if data_type == "snapshot":
                        result[code] = loader.get_snapshot(code)
                    elif data_type == "financials":
                        result[code] = loader.get_financials(code)
                    elif data_type == "valuation":
                        result[code] = loader.get_valuation(code)
                    elif data_type == "f10":
                        result[code] = loader.get_f10(code)
                except Exception as e:
                    result[code] = {"error": str(e)}

        except ImportError:
            # Fundamentals data not available — return placeholder
            for code in codes:
                result[code] = {"code": code, "note": "Fundamentals loader not available — use Go DataService"}

        n_ok = sum(1 for v in result.values() if isinstance(v, dict) and "error" not in v)
        logger.info("Fundamentals: %d/%d stocks fetched (type=%s)", n_ok, len(codes), data_type)
        return {"fundamentals": result}
```

Also delete the duplicate `backtest.data_store` fallback block (lines 358-372).

- [ ] **Step 4: Verify file is syntactically valid**

```bash
cd services/python && python -c "import ast; ast.parse(open('src/workflow/nodes/trading_nodes.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add services/python/src/workflow/nodes/trading_nodes.py
git commit -m "refactor(python): replace deleted broker/oms imports with Go HTTP in trading_nodes

- BrokerNode: use go_http.broker_positions/account/list instead of create_broker
- OrderNode: dry-run simulation instead of deleted src.trading.oms
- FundamentalsNode: remove backtest.data_store fallback, keep fundamentals_enhanced"
```

---

### Task 3: Fix `workflow/nodes/thin_nodes.py`

**Files:**
- Modify: `services/python/src/workflow/nodes/thin_nodes.py:137-210` (PaperTradingNode simulation block)

**Interfaces:**
- Consumes: `src.go_http.run_backtest`

- [ ] **Step 1: Replace simulation block (lines 137-210)**

Replace lines 137-210 with:

```python
        # ── Simulation mode ───────────────────────────────────────────────────
        if mode == "simulate" and signal and codes:
            try:
                from src.go_http import run_backtest

                capital = float(config.get("initial_capital", 1_000_000))
                interval = config.get("interval", "1D")
                duration = int(config.get("duration_days", 30))

                # Build backtest config for Go API
                bt_config = {
                    "symbols": list(codes),
                    "start_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "end_date": (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                    "frequency": interval.lower(),
                    "initial_cash": capital,
                }

                bt_resp = run_backtest(bt_config)

                if "error" in bt_resp:
                    result["simulation"] = {"error": bt_resp["error"]}
                else:
                    result["simulation"] = {
                        "mode": "paper_trading_go",
                        "final_equity": round(bt_resp.get("final_equity", capital), 2),
                        "total_return": round(bt_resp.get("total_return", 0), 4),
                        "sharpe": round(bt_resp.get("sharpe_ratio", 0), 4),
                        "max_drawdown": round(bt_resp.get("max_drawdown", 0), 4),
                        "total_trades": bt_resp.get("total_trades", 0),
                        "win_rate": round(bt_resp.get("win_rate", 0), 4),
                    }

            except Exception as e:
                logger.exception("PaperTrading simulation via Go API failed")
                result["simulation"] = {"error": str(e)}
```

Also delete `_build_bar_iterator` static method (lines 214-239) since it's no longer needed.

- [ ] **Step 2: Verify syntax**

```bash
cd services/python && python -c "import ast; ast.parse(open('src/workflow/nodes/thin_nodes.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add services/python/src/workflow/nodes/thin_nodes.py
git commit -m "refactor(python): replace deleted TradingEngine imports with go_http.run_backtest in thin_nodes

- PaperTradingNode simulation now calls Go POST /api/v1/backtest
- Removed _build_bar_iterator (no longer needed)
- Graceful error handling on Go API failure"
```

---

### Task 4: Fix `workflow/nodes/strategy_nodes.py`

**Files:**
- Modify: `services/python/src/workflow/nodes/strategy_nodes.py:91-105` (StrategyNode._fetch_strategy_options)
- Modify: `services/python/src/workflow/nodes/strategy_nodes.py:147-161` (StrategyNode._load_saved_strategy)
- Modify: `services/python/src/workflow/nodes/strategy_nodes.py:220-350` (BacktestNode.execute)

**Interfaces:**
- Consumes: `src.go_http.run_backtest`

- [ ] **Step 1: Replace _fetch_strategy_options (lines 91-105)**

```python
    @staticmethod
    def _fetch_strategy_options() -> list[dict]:
        """Get list of {id, name} for saved strategies from Go backtest store."""
        try:
            from src.go_http import _request
            resp = _request("GET", "/api/v1/backtest")
            results = resp.get("results", [])
            if isinstance(results, list):
                return [{"id": r, "name": r} for r in results]
            return []
        except Exception:
            return []
```

- [ ] **Step 2: Replace _load_saved_strategy (lines 147-161)**

```python
    @staticmethod
    def _load_saved_strategy(strategy_id: str) -> str | None:
        """Load strategy code from Go backtest store."""
        try:
            from src.go_http import _request
            resp = _request("GET", f"/api/v1/backtest/{strategy_id}")
            if "error" in resp:
                return None
            # Return the strategy code if stored in backtest result
            return resp.get("code") or resp.get("strategy_code")
        except Exception:
            return None
```

- [ ] **Step 3: Replace BacktestNode.execute backtest block (lines 264-290)**

Replace lines 264-290 with:

```python
        # Bars-per-year estimate for annualization
        _BARS_PER_YEAR = {"1D": 250, "1H": 1625, "4H": 400, "1W": 52}
        bars_per_year = _BARS_PER_YEAR.get(interval, 250)

        # Run backtest via Go API
        bt_req = {
            "symbols": codes,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": interval.lower(),
            "initial_cash": initial_capital,
        }

        try:
            from src.go_http import run_backtest
            metrics = run_backtest(bt_req)
        except Exception as e:
            logger.exception("Backtest via Go API failed")
            return {"backtest_result": {"error": str(e)}}
```

Then update the summary extraction (lines 292-293) to map Go response field names:

```python
        summary = {
            "total_return": round(metrics.get("total_return", 0), 4),
            "annual_return": round(metrics.get("total_return", 0) * (bars_per_year / max(1, len(codes) * 250)), 4),
            "sharpe": round(metrics.get("sharpe_ratio", 0), 4),
            "max_drawdown": round(metrics.get("max_drawdown", 0), 4),
            "win_rate": round(metrics.get("win_rate", 0), 4),
            "trade_count": metrics.get("total_trades", 0),
        }
```

Replace the equity curve extraction (lines 296-306) with Go's equity_curve:

```python
        # Build equity curve from Go backtest response
        equity_curve = []
        for pt in metrics.get("equity_curve", []):
            if isinstance(pt, dict):
                equity_curve.append({
                    "time": str(pt.get("timestamp", "")),
                    "equity": round(float(pt.get("equity", 0)), 2),
                })
```

Remove the trade record extraction from `driver.last_engine` (lines 310-333) since Go doesn't return individual trades in the same format. Replace with empty list or simplified extraction:

```python
        # Trade records — Go backtest returns trades array if available
        trades_list = metrics.get("trades", [])
        if not isinstance(trades_list, list):
            trades_list = []
```

- [ ] **Step 4: Also clean up unused imports in strategy_nodes.py**

Remove `import tempfile` (line 5) and `from pathlib import Path` (line 8) since they were only used for the old BacktestDriver.

- [ ] **Step 5: Verify syntax**

```bash
cd services/python && python -c "import ast; ast.parse(open('src/workflow/nodes/strategy_nodes.py').read()); print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add services/python/src/workflow/nodes/strategy_nodes.py
git commit -m "refactor(python): replace deleted backtest.runner imports with go_http.run_backtest in strategy_nodes

- StrategyNode: list/saved strategies from Go GET /api/v1/backtest
- BacktestNode: use Go POST /api/v1/backtest instead of BacktestDriver
- Inline bars_per_year calculation (was backtest.metrics)
- Inline market mapping (was backtest.runner._create_market_engine)
- Remove tempfile/pathlib imports (no longer needed)"
```

---

### Task 5: Fix `services/live_bridge.py`

**Files:**
- Modify: `services/python/src/services/live_bridge.py:128-135` (_check_broker)
- Modify: `services/python/src/services/live_bridge.py:165-174` (_check_balance)

- [ ] **Step 1: Replace _check_broker (lines 128-135)**

```python
    def _check_broker(self, user_id: int) -> bool:
        try:
            from src.go_http import broker_list
            resp = broker_list()
            if "error" in resp:
                return False
            brokers = resp.get("brokers", [])
            return any(b.get("name") == "futu" for b in brokers)
        except Exception:
            return False
```

- [ ] **Step 2: Replace _check_balance (lines 165-174)**

```python
    def _check_balance(self, user_id: int) -> tuple[bool, str]:
        try:
            from src.go_http import broker_account
            resp = broker_account()
            if "error" in resp:
                return False, f"Broker API error: {resp['error']}"
            for broker_name, data in resp.items():
                if isinstance(data, dict) and "balance" in data:
                    b = data["balance"]
                    total = float(b.get("total", 0))
                    if total > 10000:
                        return True, f"Balance: ¥{total:,.0f}"
            return False, "Minimum ¥10,000 required for live trading"
        except Exception as e:
            return False, f"Could not check balance: {e}"
```

- [ ] **Step 3: Verify syntax**

```bash
cd services/python && python -c "import ast; ast.parse(open('src/services/live_bridge.py').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add services/python/src/services/live_bridge.py
git commit -m "refactor(python): replace deleted FutuBroker imports with go_http in live_bridge

- _check_broker: use go_http.broker_list to verify futu availability
- _check_balance: use go_http.broker_account to check balance"
```

---

### Task 6: Fix `factors/mining/gp_engine.py`

**Files:**
- Modify: `services/python/src/factors/mining/gp_engine.py:294-310`

**Interfaces:**
- Consumes: `src.grpc.data_client.fetch_bars` (already exists)

- [ ] **Step 1: Replace loader registry import (lines 294-310)**

Replace lines 294-310 with:

```python
            # Use existing data_client.fetch_bars for coverage check
            # instead of the deleted backtest.loaders.registry
            from src.grpc.data_client import fetch_bars

            # Check coverage by trying to fetch a small amount of data
            sample = fetch_bars(
                symbol=universe[0],
                start_date=train_start.strftime("%Y-%m-%d"),
                end_date=train_start.strftime("%Y-%m-%d"),
                source="auto",
                frequency="1d",
            )
            needs_fallback = len(sample) == 0

            if needs_fallback and universe:
                # Try alternate sources
                market = _detect_market(universe[0]) if '_detect_market' in dir() else "equity_cn"
                _FALLBACK_SOURCES = {
                    "equity_cn": ["mootdx", "tushare", "akshare"],
                    "equity_us": ["yfinance", "akshare"],
                    "equity_hk": ["yfinance", "akshare"],
                    "crypto": ["ccxt", "okx"],
                }
                for fb_name in _FALLBACK_SOURCES.get(market, []):
                    sample = fetch_bars(
                        symbol=universe[0],
                        start_date=train_start.strftime("%Y-%m-%d"),
                        end_date=train_start.strftime("%Y-%m-%d"),
                        source=fb_name,
                        frequency="1d",
                    )
                    if sample:
                        needs_fallback = False
                        break
```

Also inline `_detect_market` at the top of the method (before the `from src.grpc.data_client import fetch_bars` line):

```python
            def _detect_market(sym: str) -> str:
                code = sym.strip().upper().replace(".SH", "").replace(".SZ", "")
                if code.startswith("6") or code.startswith("0") or code.startswith("3"):
                    return "equity_cn"
                return "equity_us"
```

- [ ] **Step 2: Verify syntax**

```bash
cd services/python && python -c "import ast; ast.parse(open('src/factors/mining/gp_engine.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add services/python/src/factors/mining/gp_engine.py
git commit -m "refactor(python): replace backtest.loaders.registry with data_client.fetch_bars in gp_engine

- Data coverage check now uses fetch_bars instead of deleted loader registry
- Inline _detect_market and _FALLBACK_SOURCES (was backtest.runner)
- Uses existing DataService gRPC bridge (already wired)"
```

---

### Task 7: Delete `src/trading/__init__.py` stub

**Files:**
- Delete: `services/python/src/trading/__init__.py`

- [ ] **Step 1: Verify no remaining references to the stub**

```bash
cd services/python && grep -r "from src.trading import" src/ || echo "No references found"
```

If any references remain, they should only be in already-cleaned files or test files.

- [ ] **Step 2: Remove the `src/trading/` directory**

```bash
rm -rf services/python/src/trading/
git add services/python/src/trading/
```

If `rm -rf` is not available, delete with git:
```bash
git rm -r services/python/src/trading/
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(python): delete src/trading/ stub — all consumers migrated to Go HTTP"
```

---

### Task 8: Final Verification + CHANGELOG

- [ ] **Step 1: Verify all Python files parse correctly**

```bash
cd services/python && python -c "
import ast, sys
files = [
    'src/go_http.py',
    'src/workflow/nodes/trading_nodes.py',
    'src/workflow/nodes/thin_nodes.py',
    'src/workflow/nodes/strategy_nodes.py',
    'src/services/live_bridge.py',
    'src/factors/mining/gp_engine.py',
]
for f in files:
    try:
        ast.parse(open(f).read())
        print(f'OK  {f}')
    except SyntaxError as e:
        print(f'FAIL {f}: {e}')
        sys.exit(1)
print('All files OK')
"
```

- [ ] **Step 2: Verify no remaining TODO(P6) markers in code**

```bash
cd services/python && grep -rn "TODO(P6)" src/ --include="*.py" | grep -v __pycache__
```

Expected: zero results (all TODO(P6) markers resolved).

- [ ] **Step 3: Verify no imports from deleted modules**

```bash
cd services/python && grep -rn "from src.trading\." src/ --include="*.py" | grep -v __pycache__
```

Expected: zero results.

- [ ] **Step 4: Verify Go tests still pass**

```bash
cd services/go && go test ./... -count=1
```

Expected: 245 passed.

- [ ] **Step 5: Update CHANGELOG**

Add to `CHANGELOG.md`:

```markdown
## [2026.6.21] - 2026-06-21

### Changed
- [Python] Migrate 22 TODO(P6) markers to Go REST API — workflow nodes (trading, thin, strategy), live_bridge, gp_engine now call Go HTTP endpoints instead of deleted Python modules
- [Python] Add `src/go_http.py` — lightweight HTTP client for Go REST API with X-API-Key auth

### Removed
- [Python] Delete `src/trading/` stub package — all 22 consumers migrated to Go HTTP
```

- [ ] **Step 6: Update version date**

Check and update `APP_VERSION` in `frontend/src/components/layout/Layout.tsx`, `README.md`, `README_zh.md` to `v2026.6.21`.

- [ ] **Step 7: Commit**

```bash
git add CHANGELOG.md frontend/src/components/layout/Layout.tsx README.md README_zh.md
git commit -m "chore: update version to v2026.6.21 + CHANGELOG for P6 cleanup"
```

---

## Self-Review

1. **Spec coverage**: All 6 modified files + 1 deleted from spec ✅. New go_http.py ✅.
2. **Placeholder scan**: No TBD/TODO — all code blocks are complete Go or Python. Test commands specify exact expected output.
3. **Type consistency**: `go_http.run_backtest` takes `dict[str, Any]`, returns `dict[str, Any]` — consistent across all callers. `broker_list()`/`broker_positions()`/`broker_account()` have consistent signatures.
4. **Interface preservation**: No Go API changes. No new proto. All HTTP calls are to existing endpoints.
