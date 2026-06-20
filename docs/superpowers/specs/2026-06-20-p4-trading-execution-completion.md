# P4 交易执行补齐设计

> 日期：2026-06-20 | 状态：已确认 | 依赖：[重构规范](2026-06-20-go-python-hybrid-refactoring-design.md) 第 6 节 P4

## 1. 目标

补齐 P4 交易执行阶段的 4 个缺口：Futu broker、Broker-Engine 适配器、Papertrade 引擎包、Binance WebSocket Feed。

## 2. 现状

| 组件 | 已完成 | 缺失 |
|------|--------|------|
| Broker 接口 | `broker/broker.go`（8 方法） | — |
| Binance broker | `broker/binance.go`（REST，已测试） | — |
| OKX broker | `broker/okx.go`（REST，已测试） | — |
| **Futu broker** | — | TCP 连接 FutuOpenD，实现 Broker 接口 |
| Broker 工厂 | `broker/factory.go`（自注册） | — |
| **Broker→Engine 适配器** | — | `broker.Broker` → `engine.BrokerExecutor` |
| MarketFeed 接口 | `market/feed/feed.go` | — |
| OKX Feed | `market/feed/feed.go`（WS + 自动重连） | — |
| **Binance Feed** | — | Binance kline WebSocket |
| LiveTradingRunner | `engine/live.go`（poll + feed + broker） | — |
| **Papertrade 引擎** | — | `papertrade/` 包：状态机 + 持久化 + 独立引擎 |
| Paper API | `api/handler/papertrade.go`（内存 CRUD） | 需重构为调用 papertrade 包 |

## 3. 设计

### 3.1 Futu Broker（TCP 直连）

Futu 协议特点：需要本地运行 FutuOpenD 网关（TCP 端口 11111），使用 Protobuf 编码。

```
FutuBroker
  ├─ 连接：TCP dial → FutuOpenD (host:port, 默认 localhost:11111)
  ├─ 认证：UnlockTrade(password) 解锁交易
  ├─ PlaceOrder → Trd_PlaceOrder (PB 编码)
  ├─ CancelOrder → Trd_ModifyOrder
  ├─ GetOrder / GetOpenOrders → Trd_GetOrderList
  ├─ GetPosition / GetPositions → Trd_GetPositionList
  ├─ GetBalance → Trd_GetFunds
  └─ TestConnection → Trd_GetAccList (轻量验证)
```

关键约束：
- 连接断开自动重连（3 次，间隔 2s/5s/10s）
- 交易密码可配置（环境变量 `FUTU_TRADE_PASSWORD`）
- 实现 `broker.Broker` 接口，注册到工厂：`Register("futu", NewFutuBroker)`

文件：`services/go/internal/broker/futu.go`

### 3.2 Broker→Engine 适配器

`engine/live.go` 定义了 `BrokerExecutor` 接口（3 方法），`broker/` 包定义了 `Broker` 接口（8 方法）。需要一个适配器把后者转成前者：

```go
// broker/adapter.go
type EngineAdapter struct { b broker.Broker }

func (a *EngineAdapter) PlaceOrder(ctx, symbol, side, orderType string, qty, price float64) (*engine.BrokerOrder, error)
func (a *EngineAdapter) GetPositions(ctx) ([]*engine.BrokerPosition, error)
```

文件：`services/go/internal/broker/adapter.go`

### 3.3 Papertrade 引擎包

从 `api/handler/papertrade.go` 提取业务逻辑到独立包 `papertrade/`：

```
papertrade/
├── engine.go         # PapertradeEngine：管理多个 Run，状态机逻辑
├── state_machine.go  # 状态转换：created→running→paused→stopped→error
├── repository.go     # PG 持久化接口 + 实现（保存/加载 Run 配置和状态）
└── engine_test.go    # 单元测试
```

状态机：
```
     ┌─────────┐   Start()   ┌─────────┐
     │ created │───────────→│ running │
     └─────────┘            └─────────┘
                                │  ↑
                    Pause()│    │  │Resume()
                           ↓    │  │
                         ┌─────────┐
                         │ paused  │
                         └─────────┘
                                │
                    Stop()│     │     │OnError()
                           ↓     ↓     ↓
                         ┌─────────┐
                         │ stopped │  (terminal)
                         └─────────┘
```

API handler 重构为调用 `papertrade.Engine` 的方法，保持 HTTP 接口不变。

持久化：Run 的配置（name, symbols, frequency, initial_cash）和当前状态（status, equity, pnl）写入 PG `paper_trading_runs` 表。

文件：
- `services/go/internal/papertrade/engine.go`
- `services/go/internal/papertrade/state_machine.go`
- `services/go/internal/papertrade/repository.go`

### 3.4 Binance WebSocket Feed

实现 `MarketFeed` 接口，连接 Binance WebSocket kline 流：

- URL：`wss://stream.binance.com:9443/ws`
- 订阅格式：`{method: "SUBSCRIBE", params: ["btcusdt@kline_1m", ...], id: 1}`
- 解析返回的 kline 数据（t, o, h, l, c, v）→ `feed.Bar`
- 自动重连（与 OKXFeed 相同模式）
- 频率映射：`"1m"/"5m"/"15m"/"1h"/"4h"/"1d"`

文件：`services/go/internal/market/feed/binance.go`

---

## 4. 接口不变性

- `broker.Broker` 接口不变
- `MarketFeed` 接口不变
- `engine.BrokerExecutor` / `engine.FeedHandler` 接口不变
- HTTP API 路由不变（handler 内部实现可改）

## 5. 测试要求

| 组件 | 测试类型 | 范围 |
|------|---------|------|
| Futu broker | 单元 + mock | 连接/重连逻辑、订单编解码（mock FutuOpenD） |
| Broker adapter | 单元 | 类型转换正确性 |
| Papertrade engine | 单元 | 状态机转换、CRUD 操作 |
| Binance feed | 单元 + mock | 连接/订阅/解析（mock WebSocket） |

## 6. 自审

- 无 TBD，所有接口、文件路径、架构决策已确定
- 接口不变性保证不破坏现有代码
- 4 项独立，可并行实现
