# AStockPursue 全面项目评审

> 评审日期：2026-06-21 | 仓库版本：v2026.6.21

---

## 一、项目概览

**AStockPursue** — AI 驱动的量化研究工作流平台，面向 A 股及全球市场。

**技术栈：**
- **前端**：Next.js 15 App Router, React 19, TypeScript, Tailwind CSS 4, Zustand 5, Recharts + D3, @xyflow/react 12, Monaco Editor / CodeMirror 6, next-intl
- **Go Core**：Go 1.25, Gin, pgx/v5, rueidis, gorilla/websocket, golang-jwt, modernc.org/sqlite, google.golang.org/grpc
- **Python Research**：Python 3.11+, FastAPI, gRPC, LangChain/LangGraph, PyTorch, scikit-learn, pandas/NumPy/SciPy/DuckDB, pgvector, ccxt, FastMCP
- **数据层**：PostgreSQL 16 + TimescaleDB + Redis 7 + Parquet 本地存储

**架构：**
```
Frontend (Next.js, :5899)
  → HTTP REST API (BFF 代理)
    → Go Core (:8899) — 交易引擎, 风控, API 处理器, 券商网关
      → gRPC + Protobuf
        → Python Research (:8902) — 信号, 因子挖掘, AI Agent, 工作流, 分析
      → SQL + Pub/Sub
        → PostgreSQL + TimescaleDB + Redis
```

**仓库规模：** 403 commits, 156 Go 文件, 838 Python 文件, ~400 TSX 源文件。日均多次提交，项目近一个月极度活跃。

---

## 二、架构评审

### 2.1 优点

**1. 架构分层清晰**
三层的职责边界明确：前端只做 UI/BFF 代理，Go 负责交易引擎+风控+HTTP API，Python 负责 AI/因子挖掘/工作流/gRPC 服务。Go→Python 通信由 protobuf 契约严格定义。

**2. 统一交易流水线** (`pipeline.go`)
`OnBar()` 的 7 步流水线设计精良：
```
gap 检测 → suspension 检测 → 信号生成(gRPC→Python) → 风控退出 → OMS 执行 → 权益记录
```
EquityCache 的缓存顺序保证了**无前瞻偏差**，这是之前 P0 缺陷修复的成果。

**3. 引擎层次结构健全**
8 种引擎类型覆盖主要市场：
- ChinaAEngine (A 股: T+1/涨跌停/印花税)
- CryptoEngine (永续合约: 资金费率/清算)
- GlobalEquityEngine (美股/港股)
- ForexEngine (外汇现货/CFD)
- ChinaFuturesEngine / GlobalFuturesEngine
- OptionsEngine (欧式/美式 Black-Scholes)
- CompositeEngine (跨市场共享资金池)

通过 `EngineFactory.ForSymbol()` 根据 symbol 前缀路由。

**4. 三阶数据存储 + 8 源降级链**
```
MemoryCache → TimescaleDB → LocalStore → Loader(8 源并发降级)
```
A 股 8 源降级：mootdx → tushare → eastmoney → tencent → futu → baidu → twelvedata → akshare。Go goroutine 并发回退，设计健壮。

**5. gRPC 数据桥接模式**
Python-only SDK（mootdx/tushare/akshare/futu）通过 DataService gRPC 桥接到 Go。既不强制 Go 依赖 Python SDK，又最大化数据源可用性。

**6. 因子挖掘系统完整**
- ExpressionTree SHA256 公式去重
- GP 进化引擎（混合初始化/复合适应度/分层操作符）
- 三层安全验证器（AST whitelist + 类型校验 + RuntimeCircuitBreaker）
- FDR 校正（Benjamini-Yekutieli 优于 BH）
- Walk-forward OOS 验证
- 因子知识库全生命周期管理（discovered→validating→approved→...→archived）

**7. 工作流引擎强大**
51+ 节点类型，支持 DAG + 拓扑排序 + 异步并行调度 + 运行时快照 + 58 个因子原子节点。节点自注册 + 可视化画布编辑器。

---

### 2.2 问题

#### P1 — 交易引擎风控过于简化

`risk.go` 只支持百分比 stop-loss/take-profit/trailing-stop，缺少：

| 缺失功能 | 影响 |
|---------|------|
| 每日最大亏损 (DayLossLimit) | 连续亏损时无法熔断 |
| 最大持仓数量 (MaxPositionCount) | 过度分散降低资金效率 |
| 相关性风控 | 已有 correlation service 但未接入风控流水线 |
| 波动率自适应仓位 | Kelly 在 `portfolio/` 中但 RiskPipeline 未使用 |
| 固定金额止损 | 目前只有百分比模式 |

**位置：** `services/go/internal/engine/risk.go:6-8`

```go
type RiskConfig struct {
    StopLossPercent     float64
    TakeProfitPercent   float64
    TrailingStopPercent float64
    // 缺少: DayLossLimit, MaxPositionCount, MaxCorrelation, VolatilityAdjust
}
```

#### P1 — 缺少真正的 OMS（订单管理系统）

`executeOrder()` 直接操作 Portfolio 状态，缺少：

- 订单生命周期管理（pending→partial→filled→cancelled→rejected）
- 订单簿匹配
- 部分成交
- 撤单逻辑
- 成交回报回执

**位置：** `services/go/internal/engine/pipeline.go:139-174`

```go
func (p *Pipeline) executeOrder(order *Order, bar interface{}) {
    // 直接操作 portfolio 状态
    // 没有订单簿、没有部分成交、没有撤单
    // order.Status = OrderFilled 直接完成
}
```

#### P2 — 缺少事务保障

`processOrders` 顺序执行风控退出 → 信号开仓，但：
- 如果信号开仓失败，风控退出已经执行，Portfolio 进入不一致状态
- 没有回滚机制
- 没有使用数据库事务

**位置：** `services/go/internal/engine/pipeline.go:86-93`

#### P2 — gRPC 连接缺少健康检查和自动重连

`main.go` 中 gRPC 客户端只在启动时创建一次，如果 Python 服务重启则连接状态未知：

```go
grpcConn, err := grpc.NewClient("localhost:8902", grpc.WithTransportCredentials(insecure.NewCredentials()))
if err != nil {
    log.Printf("gRPC dial warning: %v", err)
}
```

问题：
- 连接错误只打日志**不重试**
- 使用 `insecure.NewCredentials()` 生产环境不安全
- 缺少 `grpc.WithBlock()` + 健康检查 + 自动重连机制

#### P2 — gRPC SignalService 调用是同步阻塞的

`GenerateSignals()` 是 unary RPC（非 streaming），`main.go` 设置 10s 超时：

```go
Signal: engine.NewSignalAdapter("localhost:8902", 10*time.Second),
```

如果 Python 端计算耗时 > 10s（如批量处理大量数据），整个 pipeline 会阻塞或超时。

#### P2 — 缺少真正的健康检查

`/health` 和 `/api/v1/system/ping` 只返回 `200 OK`，没有检查下游依赖：
- 数据库连接池状态
- gRPC 连接状态
- Redis 可用性

K8s livenessProbe / readinessProbe 无法正确反映服务真实状态。

**位置：** `services/go/internal/api/handler/system.go`, `services/go/internal/api/handler/health.go`

#### P3 — Research 服务全部使用 mock 数据

4 个 Research 服务（Financials, Geopolitics, Northbound, News）全部使用 `hashFloat()` 确定性模拟数据回退，连 `IsAvailable()` 都返回 `true`：

```go
func NewGeopoliticsService(repo db.CacheRepository, httpClient *http.Client) *GeopoliticsService {
    // both nil — 无真实数据源
    return &GeopoliticsService{
        repo:       repo,
        httpClient: httpClient,
    }
}
```

**风险：** 用户看到看似真实的研究数据，实际是模拟数据，可能做出错误决策。

**位置：** `services/go/internal/research/`

#### P3 — Python 端仍有 TODO(P6) 标记未清理

CHANGELOG 记录仍有 22 处 TODO(P6) 消费端指向未完成的 Go 迁移。当 Go 端功能不完整时，Python 调用 `go_http.py` 访问 Go API 但 Go 端可能返回 503 或 mock 数据。

#### P3 — frontend 使用 `profiles` 导致默认不启动

```yaml
frontend:
    profiles:
      - frontend
```

`docker compose up -d` 不会启动前端，需显示 `--profile frontend`。新用户易困惑。

**位置：** `docker-compose.yml:56-57`

#### P4 — Go 版本不统一

| 位置 | 版本 | 问题 |
|------|------|------|
| `services/go/go.mod` | `go 1.25.0` | Go 1.25 尚未正式发布（未来版本） |
| `.github/workflows/ci.yml` | `go-version: "1.26"` | 与 go.mod 不一致 |
| CI lint | golangci-lint goinstall | 可能因版本不匹配导致构建失败 |
| Dockerfile | `golang:1.22-alpine`（推测） | 与 go.mod 不兼容 |

#### P4 — Notifications 和 ML 使用 SQLite in-memory

```go
notifDB, err := sql.Open("sqlite", ":memory:")
```

服务重启后通知历史丢失。生产环境应使用 PostgreSQL 持久化存储。

**位置：** `services/go/cmd/server/main.go:142-147`

#### P4 — 双 Docker 构建路径

根目录 `Dockerfile`（旧单体式构建）与 `docker-compose.yml`（多服务构建）并存且不同步。

#### P4 — 前端空状态需统一

CHANGELOG P3-20 创建了 `EmptyState` 组件，但只有 Projects 页面接入，其余页面尚未统一。

#### P5 — gRPC protobuf 字段省略

`common.proto` 中 Bar 缺少 `amount`（成交额），A 股高级分析的关键维度。Position 缺少 `unrealized_pnl` 和 `realized_pnl` 区分。

**位置：** `services/proto/common.proto:5-10`

#### P5 — 滑点模型过于简单

ChinaAEngine 使用 0.1% 固定滑点，没有基于成交量、波动率或订单簿深度的动态滑点模型。

#### P5 — Frontend BFF 代理缺少错误聚合

BFF 代理透传 Go 后端 HTTP 状态码。Go 返回 503（Python gRPC 不可用）时，前端没有提示"Python 研究层离线"等用户友好信息。

#### P5 — 缺少端到端 E2E 测试

Go 有单元测试（`go test ./... -race`），Python 有 pytest，frontend 有 vitest，但缺少跨服务的端到端测试。三方（frontend→Go→gRPC→Python）的集成错误只能手动发现。

#### P5 — 协程管理不严谨

`main.go` 中的 seed data goroutine 和 ticker goroutine 缺少退出机制，优雅关闭时不会等待它们完成：

```go
go func() { /* seed data */ }()  // 无退出信号
go func() { /* ticker */ }()     // 无 ctx 取消
```

**位置：** `services/go/cmd/server/main.go:154-181`

---

## 三、代码质量评审

### 3.1 优点

- **Go 接口设计干净**：`Engine` 接口只有 6 个方法，风格统一
- **缺陷历史文档化**：CLAUDE.md "Known Defect History" 记录 8 个关键修复模式，防止回归
- **CHANGELOG 规范详尽**：Keep a Changelog 格式，Added/Changed/Fixed/Removed 齐全，scope 标签清晰
- **重构纪律严格**：Go 实现后 Python 旧代码必须删除，对应关系表明确
- **CI 管道完整**：Go lint+vet+test+race + Python ruff+pytest+coverage + Dependabot

### 3.2 不足

- **核心代码测试不足**：
  - `pipeline.go`（186 行关键逻辑）— **无单元测试**
  - `risk.go`（70 行风控逻辑）— **无单元测试**
  - `signal.go`（信号适配器）— **无单元测试**

- **Python 死代码积累**：删除 28 个 API 文件后，`try/except ImportError` 在多个模块中存在，长期增加认知负担

- **Magic strings**：`main.go` 中硬编码 symbol
  ```go
  seedSymbols := []string{
      "000001.SZ", "600519.SH", "000300.SH", // ...
  }
  ```

- **错误处理不一致**：部分地方 `log.Fatal`（如 mlDB 打开失败），部分地方只打 warn 继续运行

---

## 四、安全评审

### 4.1 好的方面

- JWT + PBKDF2 密码哈希
- AST 操作符白名单安全验证器（因子挖掘部分）
- pip-audit + npm audit CI 安全扫描
- 错误消息已脱敏（P0-3 修复）

### 4.2 存在的问题

| 问题 | 位置 | 风险 |
|------|------|------|
| gRPC 无认证 | `main.go` 使用 `insecure.NewCredentials()` | 内网中间人攻击 |
| 无速率限制 | API 路由无 rate limiting | DoS 攻击面 |
| 无请求体大小限制 | gin 默认不限制 | 大 payload 内存耗尽 |
| npm 已知漏洞忽略 | `pip-audit` 忽略 6 个 CVE | 供应链风险（LangGraph 生态） |

---

## 五、改进路线图

### 5.1 最高优先级修复

| # | 问题 | 风险 | 建议 | 估算 |
|---|------|------|------|------|
| 1 | RiskPipeline 缺日亏损/持仓限制 | 实盘资金损失 | 在 `risk.go` 添加 DayLossLimit + MaxPositionCount | 2d |
| 2 | OMS 订单状态管理缺失 | 实盘风控失效 | 添加 Order 状态机和部分成交逻辑 | 3d |
| 3 | gRPC 无重连/无 TLS | 生产系统瘫痪 | 添加健康检查+自动重连+mTLS | 2d |
| 4 | Research 服务全 mock | 生产无意义数据 | 至少实装 1 个真实数据源 | 2-3d |
| 5 | 无 E2E 测试 | 集成错误无法发现 | 添加 frontend→Go→Python e2e 测试 | 3d |

### 5.2 中期改进

| 事项 | 估算 |
|------|------|
| 补上 `pipeline.go` / `risk.go` / `signal.go` 单元测试 | 2d |
| 统一 Docker 构建路径，淘汰根目录 Dockerfile | 0.5d |
| Notifications/ML 使用 PostgreSQL 而非 SQLite in-memory | 1d |
| 支持批量 bar 处理（当前只支持逐根） | 2d |
| 完成所有 TODO(P6) 迁移标记清理 | 1d |
| BFF 代理添加错误聚合和用户友好消息 | 1d |
| 统一前端 EmptyState 组件使用 | 0.5d |

### 5.3 技术债务跟踪

- Go 版本对齐（go.mod 1.25 vs CI 1.26 vs Dockerfile 1.22）
- 双 Dockerfile 维护（根目录 vs docker-compose）
- Python ImportError 死代码积累
- SQLite in-memory 数据持久化
- 前端 EmptyState 组件未全面接入
- 协程退出机制不完整

---

## 六、项目亮点总结

尽管上述问题存在，**AStockPursue 在功能完整性和架构设计上在开源量化项目中属于顶级水平**：

1. **Go+Python 混合架构**决策正确——高性能交易管道用 Go，AI/研究灵活层用 Python
2. **8 源数据降级链**设计精良，单点故障不会导致数据不可用
3. **GP 因子挖掘系统**完整（SHA256 去重/3 层安全验证/FDR BY 校正/walk-forward OOS）
4. **工作流引擎**51+ 节点类型覆盖完整，可构建复杂研究管线并可视化
5. **代码重构纪律严格**——Go 实现后 Python 旧代码立即删除，项目不积累冗余
6. **版本/CHANGELOG 纪律**——日期版本检查 + 详尽 CHANGELOG，可追溯性强
