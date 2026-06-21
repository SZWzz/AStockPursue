# P6 TODO 清理 — Python 节点迁移至 Go REST API

> 日期：2026-06-21 | 状态：已确认 | 方案 C：Python → Go HTTP

## 1. 背景

P6 阶段删除了 `backtest/engines/`、`backtest/runner.py`、`src/trading/`（brokers/engine/oms/signal_adapter/risk_pipeline/backtest_driver）、`src/api/` 路由文件。剩余 Python 消费者中有 22 处 `TODO(P6)` marker，其 import 全部失败（静默 try/except），导致对应功能节点不可用。

## 2. 方案

Python 节点改为调用 Go HTTP REST API（port 8899），不再依赖已删除的 Python 模块。

## 3. 映射关系

| Python 旧 import | 新方式 | Go 端点 |
|---|---|---|
| `src.trading.brokers.create_broker(exchange, {testnet})` | HTTP `GET /api/v1/broker/list` + `GET /api/v1/broker/positions` | broker handler |
| `src.trading.brokers.futu_broker.FutuBroker(user_id)` | HTTP `GET /api/v1/broker/list` (futu availability) | broker handler |
| `src.trading.engine.TradingEngine` + `SignalAdapter` + `RiskPipeline` | HTTP `POST /api/v1/backtest` | backtest handler |
| `src.trading.backtest_driver.BacktestDriver` | HTTP `POST /api/v1/backtest` | backtest handler |
| `backtest.runner._create_market_engine` + `_detect_market` | 内联简单逻辑 (market → engine type 映射) | — |
| `backtest.metrics.calc_bars_per_year` | 内联计算 (简单公式) | — |
| `backtest.engines.{china_a,global_equity,crypto}` | 无需创建 engine — Go 内部处理 | — |
| `backtest.loaders.registry.*` (gp_engine) | `src.grpc.data_client.fetch_bars()` (已有) | DataService gRPC |
| `backtest.runner._data_covers_range` (gp_engine) | 删除 — 用 `fetch_bars()` 替代 | — |
| `src.api.strategy_lab_routes._get_repo` | HTTP `GET /api/v1/backtest` (list) 或内联 | — |

## 4. 新增文件

### 4.1 `services/python/src/go_http.py` — Go HTTP 客户端

```python
"""Lightweight HTTP client for calling Go REST API from Python workflow nodes."""
import os
import json
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)

GO_BASE = os.environ.get("GO_API_URL", "http://localhost:8899")

def _request(method: str, path: str, body: dict | None = None, timeout: int = 30) -> dict:
    """Make an HTTP request to Go API. Returns decoded JSON dict or {"error": ...}."""
    url = f"{GO_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

def broker_list() -> dict:
    return _request("GET", "/api/v1/broker/list")

def broker_positions() -> dict:
    return _request("GET", "/api/v1/broker/positions")

def broker_account() -> dict:
    return _request("GET", "/api/v1/broker/account")

def run_backtest(config: dict) -> dict:
    return _request("POST", "/api/v1/backtest", config)

def get_market_bars(symbol: str, start: str, end: str, freq: str = "1d") -> dict:
    params = f"symbol={symbol}&start={start}&end={end}&frequency={freq}"
    return _request("GET", f"/api/v1/market/bars?{params}")
```

## 5. 修改文件

### 5.1 `workflow/nodes/trading_nodes.py`
- 替换 `src.trading.brokers.create_broker` → `go_http.broker_positions()` / `go_http.broker_account()`
- 替换 `src.trading.oms.OrderManager` → `go_http._request("POST", "/api/v1/trading/orders", ...)`
- 删除 `backtest.loaders.fundamentals_enhanced` + `backtest.data_store` lazy imports (移到独立 data node)

### 5.2 `workflow/nodes/thin_nodes.py`
- 替换整个 simulation 分支 (TradingEngine + SignalAdapter + RiskPipeline + ChinaAEngine/...) → `go_http.run_backtest(config)`
- 简化为 ∼20 行 HTTP 调用

### 5.3 `workflow/nodes/strategy_nodes.py`
- 替换 `backtest.runner._create_market_engine` + `backtest.metrics.calc_bars_per_year` + `BacktestDriver` → `go_http.run_backtest(config)`
- 内联 `bars_per_year` 计算 (250 for daily, 6.5*250 for hourly)
- 内联 `_MARKET_TO_SOURCE` 映射

### 5.4 `services/live_bridge.py`
- 替换 `FutuBroker(user_id)` import → `go_http.broker_list()` 检查 futu 是否可用

### 5.5 `factors/mining/gp_engine.py`
- 替换 `backtest.loaders.registry` + `backtest.runner._data_covers_range` → `data_client.fetch_bars()`

### 5.6 `src/trading/__init__.py`
- 删除整个桩包

## 6. 自审

- 无新增 protobuf 或 gRPC 服务
- Go HTTP API 已全部就绪，无需改动
- Python 改动仅限 import 替换，逻辑简化
- 保留优雅降级 (HTTP 失败返回 error dict)
- Go API 无 auth 即用 (workflow 节点在服务端内部调用，无需 JWT)
