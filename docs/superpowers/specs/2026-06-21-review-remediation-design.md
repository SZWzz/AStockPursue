# Review Remediation Design

> 来源：[2026-06-21 项目评审](./2026-06-21-project-review.md)
> 定位：个人量化研究 + 开源项目 | 无硬性时间约束

---

## 总览

基于项目评审发现的 19 个问题（P1~P5），三阶段分层推进，不动架构、只做填充加固补齐。

```
Phase 1: 安全与韧性 (4-5d)  → Phase 2: 质量基础 (3-4d)  → Phase 3: 完整性打磨 (3-4d)
```

---

## 影响范围

```
services/go/internal/engine/       — Phase 1 核心改动 (risk.go, pipeline.go, signal.go)
services/go/internal/engine/oms.go — Phase 1 新增 OMS 状态机
services/go/internal/grpc/         — Phase 1 新增 gRPC 连接管理器
services/go/cmd/server/            — gRPC 重连, 健康检查, 协程管理
services/go/internal/api/handler/  — 深度健康检查
services/go/internal/research/     — 真实数据源替代 mock
services/go/go.mod                 — Go 版本对齐
Dockerfile, docker-compose.yml     — 构建路径统一
services/proto/                    — protobuf 字段补充
services/python/                   — TODO(P6) 清理
frontend/                          — EmptyState, BFF 错误聚合
tests/                             — 新增单元测试 + E2E
.github/workflows/                 — CI go-version 对齐
```

---

## Phase 1：安全与韧性

### 1.1 风控扩展

**文件：** `services/go/internal/engine/risk.go`

扩展 `RiskConfig` 结构体：

```go
type RiskConfig struct {
    // 现有字段保持不变
    StopLossPercent     float64
    TakeProfitPercent   float64
    TrailingStopPercent float64

    // 新增
    DayLossLimit     float64  // 日最大亏损金额 (绝对值, 如 -5000)
    MaxPositionCount int      // 最大持仓数 (0=不限制)
    MaxCorrelation   float64  // 单标的与现有持仓 Pearson 相关系数阈值 (0=不限制)
    VolatilityAdjust bool     // 是否启用波动率自适应仓位 (调用 Kelly)
}
```

`CheckRiskExits()` 流水线扩展：

```
stop-loss → take-profit → trailing-stop → day-loss-check → position-count-check
```

- **日亏损熔断**：当日累计已实现亏损超过 `DayLossLimit` 时，拒绝所有新开仓信号
- **持仓数限制**：当前持仓数 >= `MaxPositionCount` 时，拒绝新开仓信号
- **相关性检查**：新标的与现有持仓的 Pearson 相关系数超过 `MaxCorrelation` 时拒绝
- **波动率自适应**：`VolatilityAdjust=true` 时调用 `portfolio/` 中已有 Kelly 公式调整仓位比例

**向后兼容：** 新增字段默认值（0/false）等价于不启用。

**验证：** 回测模式下用历史数据确认日亏损熔断和持仓限制行为。

---

### 1.2 OMS 订单状态机

**新文件：** `services/go/internal/engine/oms.go`

订单生命周期：

```
create → pending → submit → submitted
                                ├── fill → partial → fill → filled
                                ├── cancel → cancelled
                                └── reject → rejected

终态: filled | cancelled | rejected
```

核心接口：

```go
type Order struct {
    ID        string
    Symbol    string
    Side      OrderSide   // Buy / Sell
    Type      OrderType   // Market / Limit
    Qty       float64
    Price     float64
    FilledQty float64
    Status    OrderStatus
    CreatedAt time.Time
    UpdatedAt time.Time
}

type OrderManager struct {
    orders map[string]*Order
    mu     sync.RWMutex
}

func (om *OrderManager) Submit(order *Order) error
func (om *OrderManager) Fill(orderID string, qty, price float64) error
func (om *OrderManager) Cancel(orderID string) error
func (om *OrderManager) Reject(orderID string, reason string) error
```

**集成到 Pipeline：**

- `executeOrder()` 改为调用 `OrderManager.Submit(order)` 创建订单
- 当前版本：`Submit` 后立即 `Fill` 全量（行为不变）
- 后续实盘接入：券商回调触发 `Fill`/`Cancel`/`Reject`

**向后兼容：** 所有调用 `executeOrder()` 的地方行为不变，API 表面无变化。

---

### 1.3 gRPC 健康检查与自动重连

**新文件：** `services/go/internal/grpc/connmgr.go`

连接管理器：

```go
type ConnManager struct {
    conn   *grpc.ClientConn
    mu     sync.RWMutex
    addr   string
}

func NewConnManager(addr string, connectTimeout time.Duration) *ConnManager
func (m *ConnManager) Connect(ctx context.Context) error
func (m *ConnManager) StartHealthCheck(ctx context.Context)
func (m *ConnManager) GetConn() *grpc.ClientConn
```

**健康检查策略：**
- 启动时：`grpc.WithBlock()` + 30s 超时，连不上持续重试（指数退避 1s→2s→4s→…→max 30s）
- 运行时：每 10s 调 grpc-health-probe 标准检查，连续失败 3 次触发重连
- 重连期间：SignalClient 等返回明确错误 "python research layer unavailable"

**main.go 改动：**

```go
// 旧: grpcConn, err := grpc.NewClient("localhost:8902", ...)
// 新:
connMgr := grpc.NewConnManager("localhost:8902", 30*time.Second)
if err := connMgr.Connect(context.Background()); err != nil {
    log.Printf("gRPC: python research layer unavailable, retrying in background...")
}
go connMgr.StartHealthCheck(context.Background())
```

**安全：** `insecure.NewCredentials()` 暂时保留，加注释标记技术债务，生产部署时需替换为 mTLS。

---

## Phase 2：质量基础

### 2.1 事务保障

**文件：** `services/go/internal/engine/pipeline.go`

- `processOrders` 前保存 Portfolio 快照（`Cash`, `Equity`, `Positions` 深拷贝）
- 信号开仓失败 → 回滚 Portfolio 到快照状态
- 不引入数据库事务（回测模式无 DB），使用内存快照回滚

### 2.2 深度健康检查

**文件：** `services/go/internal/api/handler/system.go`, `health.go`

- `/health` → 检查 DB 连接池（`pgx.Ping`）、gRPC 连通性、Redis ping
- 返回结构化 JSON：`{"status":"ok|degraded","db":"ok|error","grpc":"ok|error","redis":"ok|error"}`
- `/api/v1/system/ping` 保持不变（轻量 livenessProbe）
- `/health` 用作 readinessProbe

### 2.3 核心路径单元测试

| 新文件 | 覆盖内容 |
|--------|---------|
| `services/go/internal/engine/risk_test.go` | 5 种风控规则：stop-loss, take-profit, trailing-stop, day-loss, position-count |
| `services/go/internal/engine/pipeline_test.go` | mock gRPC 信号 + mock bar，完整 `OnBar()` 流程 |
| `services/go/internal/engine/signal_test.go` | SignalAdapter 超时、重连、错误码 |

### 2.4 Go 版本对齐

- `go.mod`：`go 1.25.0` → `go 1.22`
- CI：`go-version: "1.26"` → `go-version: "1.22"`
- `golangci-lint` 版本与 Go 1.22 对应

### 2.5 Docker 构建统一

- 淘汰根目录 `Dockerfile`（旧单体式构建）
- 仅保留 `docker-compose.yml` 的多服务构建路径

### 2.6 SQLite → PostgreSQL

- Notifications 和 ML 从 `sql.Open("sqlite", ":memory:")` 改为从 `cfg.DatabaseURL` 获取连接
- 与 TimescaleDB 共用 PostgreSQL 实例
- fallback 仍为 in-memory（当 DB 不可用时）

---

## Phase 3：完整性打磨

### 3.1 Research 真实数据源

**文件：** `services/go/internal/research/`

- `NewsService` 接入东方财富新闻 RSS/API
- 其余 3 个 service（Financials, Geopolitics, Northbound）`IsAvailable()` → `false`
- 移除 `hashFloat()` 确定性模拟数据生成逻辑

### 3.2 E2E 测试

**新目录：** `tests/e2e/`

- 用 Go `testing` 包 + `httptest` 写集成测试
- 启动 Go 服务 → 发 HTTP 请求 → 验证响应
- 不依赖 Python gRPC，使用 mock gRPC server
- 覆盖：健康检查、回测 API、交易 API、市场数据 API

### 3.3 TODO(P6) 清理

- 遍历 Python 端 22 处 `TODO(P6)` 标记
- Go 端已实现对应的 → 删除 Python 旧代码
- Go 端未实现 → 标记为 P3 技术债务，开 issue 跟踪

### 3.4 前端 profiles 优化

**文件：** `docker-compose.yml`, `dev.sh`

- `docker-compose.yml` 加注释说明 `--profile frontend` 用法
- `dev.sh` 加 `frontend` 子命令便于本地启动

### 3.5 EmptyState 组件统一

- 将已有 `EmptyState` 组件接入 Dashboard、Backtest、Signals、Workflow 页面
- 统一无数据状态展示

### 3.6 协程退出机制

**文件：** `services/go/cmd/server/main.go`

```go
ctx, cancel := context.WithCancel(context.Background())
defer cancel()

go seedData(ctx)  // 接收 ctx，select 监听 ctx.Done()
go tickerFeed(ctx) // 接收 ctx，select 监听 ctx.Done()
```

服务优雅关闭时 cancel → goroutine 退出 → 等待完成。

### 3.7 BFF 错误聚合

**文件：** `frontend/` BFF 代理层

- 解析 Go 后端返回的 HTTP 状态码
- 503 → "Python 研究层离线，部分功能不可用"
- 500 → "服务内部错误"
- 其他错误 → 展示原始错误信息（已脱敏）

### 3.8 protobuf 字段补充

**文件：** `services/proto/common.proto`

```protobuf
message Bar {
    // 现有字段...
    double amount = X;  // 新增：成交额
}

message Position {
    // 现有字段...
    double unrealized_pnl = X;  // 新增：未实现盈亏
    double realized_pnl = X;    // 新增：已实现盈亏
}
```

### 3.9 滑点模型优化

**文件：** `services/go/internal/engine/china_a.go`

- 替换固定 0.1% 滑点为基于日振幅的动态滑点
- `slippage = base_slippage + amplitude_factor * daily_amplitude`
- 不引入复杂订单簿深度模型

### 3.10 硬编码 seed symbols 迁移

**文件：** `services/go/cmd/server/main.go`

- `seedSymbols` 移到配置文件或环境变量 `SEED_SYMBOLS`
- 保留硬编码作为 fallback 默认值

---

## 验证策略

| 阶段 | 验证方式 |
|------|---------|
| Phase 1 风控 | 回测跑历史数据，验证日亏损熔断 + 持仓限制行为 |
| Phase 1 OMS | 单元测试覆盖所有状态转换，回测确认行为不变 |
| Phase 1 gRPC | 手动停止 Python 服务 → 确认重连 + 错误返回正确 |
| Phase 2 测试 | `go test ./... -race` 全部通过 |
| Phase 2 健康检查 | curl `/health` 验证结构化响应 |
| Phase 2 Docker | `docker compose up -d --build` 构建成功 |
| Phase 3 Research | 确认无 mock 数据返回 |
| Phase 3 E2E | `go test ./tests/e2e/...` 全部通过 |

---

## 不计入范围

以下项目评审中提出的问题**不纳入**本次修复计划：

1. gRPC mTLS — 需基础设施整备，标记为技术债务
2. 速率限制 / 请求体大小限制 — 属于运维层面，非代码修复
3. npm CVE 忽略 — 需单独评估供应链风险
4. gRPC SignalService 改为 streaming — 架构变更，需独立评估
5. 批量 bar 处理 — 性能优化，非当前优先级
