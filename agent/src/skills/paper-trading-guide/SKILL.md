---
name: paper-trading-guide
description: 模拟盘操作指南 — 创建运行、启动/停止/暂停、查看实时K线、持仓和成交数据，以及通过SSE获取实时更新的完整工作流。
category: flow
---

# 模拟盘操作指南 (Paper Trading Guide)

## 概述

模拟盘允许在真实市场数据上运行策略，使用虚拟资金进行模拟交易。策略代码与回测完全一致（`SignalEngine`），但执行方式不同：

- **回测**：一次性运行历史数据，输出 metrics
- **模拟盘**：持续运行，每个交易日拉取新 bar 并执行交易，通过 SSE 推送实时更新

## 创建模拟盘运行

通过前端 Paper Trading 页面操作，或调用 API：

```
POST /v1/paper-trading/runs
{
  "run_name": "我的策略",
  "market": "a_share",
  "codes": ["000001.SZ", "600519.SH"],
  "interval": "1D",
  "initial_capital": 100000,
  "strategy_code": "class SignalEngine: ...",
  "risk_config": {
    "stop_loss_pct": 5.0,
    "take_profit_pct": 10.0,
    "trailing_stop_pct": 0.0,
    "max_daily_loss_pct": 3.0,
    "max_position_pct": 30.0,
    "use_intraday_stop": true
  }
}
```

### 风控参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `stop_loss_pct` | 5.0 | 止损阈值 (%) |
| `take_profit_pct` | 10.0 | 止盈阈值 (%) |
| `trailing_stop_pct` | 0.0 | 追迹止损距离 (%)，0=禁用 |
| `max_daily_loss_pct` | 3.0 | 日内最大亏损 (% of 初始资金) |
| `max_position_pct` | 30.0 | 单仓位最大占比 (%) |
| `use_intraday_stop` | true | 是否用 bar 内高低价检测止损（更精确） |

## 生命周期

```
stopped → [start] → running → [pause] → paused → [resume] → running
  ↓                    ↓                      ↓
  └────── [stop] ←─────┴──────────────────────┘
```

对应 API：
- `POST /v1/paper-trading/runs/{run_id}/start`
- `POST /v1/paper-trading/runs/{run_id}/stop?close_positions=true`
- `POST /v1/paper-trading/runs/{run_id}/pause`
- `POST /v1/paper-trading/runs/{run_id}/resume`

## 实时数据获取

### 1. 历史 K 线（引擎内存中的 bar 数据）

```
GET /v1/paper-trading/runs/{run_id}/bars?codes=000001.SZ&limit=500
```

返回 `{code: [{time, open, high, low, close, volume}, ...]}`。

### 2. SSE 实时流

```
GET /v1/paper-trading/runs/{run_id}/stream
```

事件类型：

| 事件 | 包含字段 | 触发时机 |
|------|----------|----------|
| `bar` | timestamp, equity, capital, unrealized, drawdown, positions[], **bars** | 每个新 bar 处理后 |
| `trade` | symbol, direction, entry/exit_price, pnl, exit_reason | 每次成交 |
| `signal` | symbol, direction, price, reason | 每次信号生成 |
| `status` | status (running/stopped/error) | 状态变化 |
| `heartbeat` | timestamp | 无新 bar 时的心跳 |

**`bar` 事件中的 `bars` 字段**：包含当前 bar 的 OHLCV 数据 `{code: {open, high, low, close, volume}}`，前端直接追加到 K 线图表实现实时更新。

### 3. 静态数据端点

| 端点 | 说明 |
|------|------|
| `GET /runs/{run_id}` | 运行详情（含 positions, recent_trades, data_source） |
| `GET /runs/{run_id}/equity` | 权益曲线 |
| `GET /runs/{run_id}/trades` | 历史成交记录 |

## 运行详情中的字段解读

- `data_source`：实际使用的数据源（如 `akshare`、`tencent`），注意与回测时可能不同
- `positions[].current_price`：当前最新价格（来自引擎 `_last_bar_prices`）
- `positions[].unrealized_pnl`：浮动盈亏

## 注意事项

1. 模拟盘和回测可能使用不同的数据源（loader fallback 链不同）→ 同一时间的 OHLCV 可能略有差异
2. 服务器重启后所有运行自动标记为 `stopped`，需手动重新启动
3. 模拟盘的 K 线数据来自引擎实时 bar，不是从外部 OHLCV 接口拉取的
4. 风控参数可在运行中通过「风控」tab 修改并保存
