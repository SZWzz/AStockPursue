# AStockPursue 重构规范 —— Go + Python 混合架构

> 日期：2026-06-20 | 状态：已确认

## 1. 架构总览

### 1.1 目标

将当前 Python (FastAPI) + React (Vite) 单体重构为 **Go + Python 混合微服务架构**，前端迁移至 Next.js (App Router)。

### 1.2 核心分工

| 层 | 语言 | 职责 |
|----|------|------|
| **Go Core Services** | Go | 回测引擎、实时行情管道、订单执行、数据加载、REST API、风控、组合管理 |
| **Python Research Layer** | Python | 因子研究/挖掘、AI/LLM Agent、策略信号生成、分析报告、MCP 服务器、工作流引擎 |
| **Frontend** | TypeScript (Next.js) | SSR 页面、API 代理层、可视化、UI 交互 |

### 1.3 通信

- Go ↔ Python：**gRPC + Protobuf**（`services/proto/`）
- Go → Frontend：REST JSON (通过 Go 的 HTTP API)
- 事件推送：Redis Pub/Sub + Server-Sent Events

### 1.4 数据层

| 组件 | 用途 |
|------|------|
| PostgreSQL 16 | 业务数据（用户、订单、回测配置等） |
| TimescaleDB (PG 扩展) | 时序数据（K线、因子值、仓位历史） |
| Redis 7 | 缓存、实时行情分发、lock、pub/sub |

---

## 2. 目录结构

```
astockpursue/
├── services/
│   ├── go/                    # Go 核心服务
│   │   ├── cmd/server/        # 入口 main.go
│   │   ├── internal/
│   │   │   ├── api/           # REST API (gin)
│   │   │   ├── engine/        # 回测+实盘引擎管线
│   │   │   ├── market/        # 数据加载器 + 行情
│   │   │   ├── broker/        # 券商网关
│   │   │   ├── portfolio/     # 组合管理
│   │   │   ├── papertrade/    # 模拟交易
│   │   │   ├── grpc/          # gRPC 客户端/服务端
│   │   │   ├── db/            # PG + Timescale + Redis
│   │   │   └── config/
│   │   ├── Dockerfile
│   │   ├── go.mod / go.sum
│   │   └── Makefile
│   ├── python/                # Python 研究层（原 backend/）
│   │   ├── mcp_server.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile.python
│   │   ├── src/
│   │   │   ├── factors/       # 因子框架 + 452 alpha
│   │   │   ├── agent/         # LLM agent loop
│   │   │   ├── skills/        # 89 skill packs
│   │   │   ├── swarm/         # 多智能体
│   │   │   ├── tools/         # MCP 35 工具
│   │   │   ├── services/      # 分析服务
│   │   │   ├── workflow/      # 工作流引擎
│   │   │   ├── session/       # 会话管理
│   │   │   ├── memory/        # 持久记忆
│   │   │   ├── grpc/          # gRPC server
│   │   │   ├── auth/          # JWT
│   │   │   ├── config/        # 配置
│   │   │   ├── db/            # 数据库连接
│   │   │   └── notify/        # 通知通道
│   │   └── tests/
│   ├── proto/                 # 共享 Protobuf 定义
│   │   ├── common.proto
│   │   ├── signal.proto
│   │   ├── factor.proto
│   │   ├── llm.proto
│   │   ├── analysis.proto
│   │   └── workflow.proto
│   └── frontend/              # Next.js 前端（原 frontend/）
│       ├── app/               # App Router 页面
│       ├── components/        # 共享组件
│       ├── lib/               # 工具函数
│       ├── stores/            # 状态管理 (Zustand)
│       ├── package.json
│       ├── Dockerfile
│       └── next.config.ts
├── migrations/                # SQL 迁移（语言无关，Python 管理）
├── docs/
├── docker-compose.yml
├── Dockerfile                 # (可选) 统一构建
├── README.md / README_zh.md
├── CHANGELOG.md
├── CLAUDE.md
└── pyproject.toml             # 仅 Python 部分
```

### 2.1 Go 模块详解

```
services/go/internal/
├── api/
│   ├── handler/               # 每个资源一个 handler
│   │   ├── auth.go
│   │   ├── trading.go
│   │   ├── backtest.go
│   │   ├── papertrade.go
│   │   ├── factor.go          # 代理到 Python gRPC
│   │   ├── signal.go          # 代理到 Python gRPC
│   │   ├── workflow.go        # 代理到 Python gRPC
│   │   ├── analysis.go        # 代理到 Python gRPC
│   │   ├── market.go
│   │   ├── scheduler.go
│   │   ├── settings.go
│   │   └── admin.go
│   ├── middleware/
│   │   ├── auth.go            # JWT validation
│   │   ├── ratelimit.go
│   │   └── cors.go
│   └── router.go              # 路由注册
├── engine/
│   ├── pipeline.go            # on_bar() 统一管线
│   ├── risk.go                # RiskPipeline (stop-loss, trailing, take-profit)
│   ├── signal.go              # SignalAdapter (gRPC 调用 Python)
│   ├── oms.go                 # Order Management System
│   ├── china_a.go             # ChinaAEngine (T+1, price limits, stamp duty)
│   ├── crypto.go              # CryptoEngine (funding rate, liquidation)
│   ├── futures_base.go        # FuturesBase (contract multiplier)
│   ├── china_futures.go       # ChinaFuturesEngine
│   ├── global_equity.go       # GlobalEquityEngine
│   ├── global_futures.go      # GlobalFuturesEngine
│   ├── forex.go               # ForexEngine
│   ├── options.go             # OptionsPortfolioEngine
│   └── composite.go           # CompositeEngine
├── market/
│   ├── loader/
│   │   ├── interface.go       # Loader interface
│   │   ├── registry.go        # 自注册机制
│   │   ├── akshare.go
│   │   ├── tushare.go
│   │   ├── eastmoney.go
│   │   ├── tencent.go
│   │   ├── futu.go
│   │   ├── baidu.go
│   │   ├── yfinance.go
│   │   ├── ccxt.go
│   │   └── ...
│   ├── cache.go               # 多级缓存 (mem + Redis)
│   ├── store.go               # DataStore (3-tier: PG → Parquet → Loader)
│   └── feed.go                # WS 实时行情馈送
├── broker/
│   ├── interface.go
│   ├── binance.go
│   ├── futu_broker.go
│   ├── okx.go
│   └── factory.go
├── portfolio/
│   ├── sizing.go              # 仓位计算
│   └── margin.go              # 保证金管理
├── papertrade/
│   ├── engine.go
│   ├── scheduler.go
│   └── state_machine.go
├── grpc/
│   ├── client.go              # → Python 端 gRPC 客户端
│   └── server.go              # ← Python/前端通过 Envoy 调用
├── db/
│   ├── postgres.go
│   ├── timescale.go
│   └── redis.go
└── config/
    └── config.go
```

### 2.2 Python 层保留 + 新增

Python 层 **删除** 以下模块（已迁移至 Go）：
- `backend/src/trading/`（含 brokers/、risk_pipeline.py 等）
- `backend/backtest/`（含 engines/、loaders/ 等）
- `backend/papertrade/`
- `backend/src/api/`（route 层 → Go HTTP API）

Python 层 **新增** gRPC 服务端：

```
services/python/src/grpc/
├── __init__.py
├── server.py                    # gRPC server 入口 (port 8902)
├── factor_service.py            # FactorService: 因子计算、GP 进化
├── signal_service.py            # SignalService: 策略信号生成
├── llm_service.py               # LLMService: LLM 聊天、Agent 推理
├── analysis_service.py          # AnalysisService: attribution, correlation, stress test
└── workflow_service.py          # WorkflowService: 工作流节点执行
```

### 2.3 Frontend 完全重写

前端同后端一样 **完全重写**，不保留任何现有代码和样式。使用 Next.js (App Router) 从头搭建：

```
services/frontend/
├── app/
│   ├── layout.tsx               # 根布局 (dark OLED theme)
│   ├── page.tsx                 # 首页 / Dashboard
│   ├── login/page.tsx
│   ├── trading/page.tsx
│   ├── backtest/
│   │   ├── page.tsx             # 回测列表
│   │   └── [id]/page.tsx        # 回测详情
│   ├── factors/page.tsx         # 因子挖掘
│   ├── workflow/
│   │   ├── page.tsx             # 工作流编辑器
│   │   └── [id]/page.tsx
│   ├── agent/page.tsx
│   ├── paper-trading/page.tsx
│   ├── settings/page.tsx
│   └── api/                     # API Routes (代理到 Go)
│       ├── trading/route.ts
│       ├── backtest/route.ts
│       └── ...
├── components/                  # 全新 UI 组件库
├── lib/                         # 工具函数、API client
├── stores/                      # 状态管理 (Zustand)
└── ...
```

原则：
- **零迁移**：所有页面、组件、样式全部从零开始
- 仅复用业务逻辑层面的概念（页面路由结构、API 接口格式）
- 之前前端的样式 token、组件代码、状态管理模式均不保留，按新设计决策重新实现
- 前端作为独立的发包阶段（P5），不影响 Go 和 Python 的核心功能验证

---

## 3. gRPC Protobuf 定义

### 3.1 common.proto

```protobuf
syntax = "proto3";
package astockpursue.common;

message Bar {
  string symbol = 1;
  double open = 2; double high = 3; double low = 4; double close = 5;
  int64 volume = 6; int64 timestamp = 7;
  string frequency = 8;  // "1d", "60m", "5m", "1m"
}

message Position {
  string symbol = 1;
  double size = 2;
  double entry_price = 3;
  double current_price = 4;
  double pnl = 5;
  string side = 6;  // "long" / "short"
}

message Order {
  string id = 1; string symbol = 2; string side = 3; string type = 4;
  double price = 5; double quantity = 6; string status = 7;
}
```

### 3.2 signal.proto

```protobuf
service SignalService {
  // Tick 模式：Go 逐 bar 推送，Python 返回权重
  rpc OnBar(stream OnBarRequest) returns (stream OnBarResponse);
  // Batch 模式：Go 发送窗口数据，Python 计算并返回
  rpc GenerateSignals(SignalRequest) returns (SignalResponse);
}

message SignalRequest {
  string strategy_name = 1;
  repeated Bar bars = 2;
  string mode = 3;  // "tick" | "batch"
  map<string, string> params = 4;
}
message SignalResponse {
  map<string, double> weights = 1;  // symbol -> target weight
  string error = 2;
}
```

### 3.3 factor.proto

```protobuf
service FactorService {
  rpc ComputeFactor(FactorRequest) returns (FactorResponse);
  rpc StartGPMining(GPRequest) returns (stream GPResult);
}

message FactorRequest {
  string formula = 1;
  repeated string symbols = 2;
  string start_date = 3;
  string end_date = 4;
}
message FactorResponse {
  map<string, double> values = 1;  // date -> value
  string error = 2;
}

message GPRequest {
  string pool = 1;
  int32 generations = 2;
  int32 population_size = 3;
  string fitness_metric = 4;
}
message GPResult {
  string formula = 1;
  double ic = 2;
  double sharpe = 3;
  int32 generation = 4;
}
```

### 3.4 llm.proto

```protobuf
service LLMService {
  rpc Chat(ChatRequest) returns (ChatResponse);
  rpc AgentDecide(AgentRequest) returns (AgentResponse);
}

message ChatRequest { string message = 1; }
message ChatResponse { string reply = 1; }

message AgentRequest {
  string query = 1;
  map<string, string> context = 2;
}
message AgentResponse {
  string action = 1;
  map<string, string> params = 2;
}
```

### 3.5 analysis.proto

```protobuf
service AnalysisService {
  rpc CalcAttribution(AttributionRequest) returns (AttributionResponse);
  rpc CalcCorrelation(CorrelationRequest) returns (CorrelationResponse);
  rpc StressTest(StressTestRequest) returns (StressTestResponse);
}
```

### 3.6 workflow.proto

```protobuf
service WorkflowService {
  rpc ExecuteWorkflow(WorkflowRequest) returns (WorkflowResponse);
  rpc GetNodeResult(NodeQuery) returns (NodeResult);
}
```

---

## 4. 引擎管线核心设计（Go）

### 4.1 on_bar() 管线

Go 实现保留 Python 原版的关键顺序约束：

```go
func (e *Engine) OnBar(bar Bar, ts time.Time) {
    // 0a. Gap detection — 隔夜跳空检查
    // 0b. Suspension detection — 停牌检测
    // 0.5 Market hooks — 资金费率/清算
    // 1. SignalAdapter → gRPC 调用 Python 获取权重
    // 1.5 OptimizerAdapter → 优化器调整（可选，Go 实现）
    // 2. RiskPipeline → 止损/跟踪止盈 (Go 本地计算)
    // 3. Process signals → 开平仓 (OMS)
    // 4. Record equity snapshot
}
```

**关键约束**（继承 Python 版本的已知缺陷修复）：
- `RecordBars()` 必须在 `GenerateSignals()` **之后**，防止前视偏差
- `equity_for_sizing` 必须在 `CheckRiskExits()` **之前** 缓存
- 线程安全：Race pipeline 各阶段用 `sync.Mutex` 保护共享状态

### 4.2 引擎层级

```
BaseEngine (interface)
  ├─ ChinaAEngine      — T+1, 涨跌停, 印花税
  ├─ CryptoEngine      — 永续合约: 资金费率, 强平
  ├─ GlobalEquityEngine— US/HK 股票
  ├─ ForexEngine       — FX spot/CFD
  ├─ FuturesBase       — 合约乘数
  │   ├─ ChinaFuturesEngine — CFFEX/SHFE/DCE/ZCE/INE/GFEX
  │   └─ GlobalFuturesEngine— CME/ICE/Eurex
  ├─ OptionsEngine     — BS 定价
  └─ CompositeEngine   — 跨市场，共享资金池
```

每个引擎实现接口方法：
```go
type Engine interface {
    CanExecute(order Order) bool
    RoundSize(size float64) float64
    CalcCommission(order Order) float64
    ApplySlippage(price float64, side string) float64
    CalcMargin(position Position) float64
    CalcPnL(position Position) float64
}
```

### 4.3 数据加载器（Go）

复用 Python 的 8 源 A 股回退链设计：

```go
type Loader interface {
    Name() string
    IsAvailable() bool
    FetchBars(symbol string, start, end time.Time) ([]Bar, error)
}

type DataStore struct {
    tiers []Loader   // 按优先级排序
    cache *Cache     // Redis + 内存
}

func (ds *DataStore) GetBars(symbol string, start, end time.Time) ([]Bar, error) {
    // Tier 1: TimescaleDB
    // Tier 2: Parquet 本地存储
    // Tier 3: Loader fallback chain
    for _, loader := range ds.tiers {
        if loader.IsAvailable() {
            bars, err := loader.FetchBars(...)
            if err == nil { return bars }
        }
    }
    return nil, ErrAllLoadersFailed
}
```

Go 推荐使用 goroutine 并发 fallback（而非 Python 的串行回退），大幅加速数据获取。

---

## 5. CI/CD & 部署

### 5.1 Docker Compose

```yaml
services:
  go-core:
    build: services/go
    ports: ["8899:8899", "8901:8901"]  # HTTP + gRPC
    depends_on: [postgres, redis]

  python-research:
    build: services/python
    ports: ["8900:8900", "8902:8902"]  # MCP + gRPC
    depends_on: [postgres, redis, go-core]

  frontend:
    build: services/frontend
    ports: ["5899:5899"]
    depends_on: [go-core]

  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### 5.2 开发环境

```bash
# Go 开发
cd services/go && go run ./cmd/server

# Python 开发
cd services/python && pip install -r requirements.txt
python mcp_server.py
python -m src.grpc.server  # gRPC server

# 前端开发
cd services/frontend && npm run dev

# 单命令启动
docker compose up -d --build
```

### 5.3 测试策略

| 层 | 工具 | 范围 |
|----|------|------|
| Go | `go test` | 引擎管线、OMS、风控、broker 网关、数据加载器 |
| Python | `pytest` | 因子计算、AI Agent、MCP 工具、工作流节点 |
| Frontend | `vitest` | 全新 UI 组件测试、集成测试 |
| Integration | docker compose + gRPC 健康检查 | 全链路回归 |

---

## 6. 迁移计划（5 阶段）

### P1: 基础设施（1 周）

- Go 项目初始化：`go mod init`, 目录脚手架, gin 框架集成
- Protobuf 定义 + buf 代码生成 pipeline
- Docker Compose 更新：go-core service, python-research 改名
- CI/CD：Go lint + test stage
- CLAUDE.md 更新

### P2: 数据管道（2 周）

- `market/loader/`: ~32 个数据加载器移植（先核心 8 个 A 股源）
- `market/store.go`: 3 级 DataStore
- `market/cache.go`: Redis + 内存缓存
- `db/timescale.go`: 时序表创建、批量写入
- **里程碑**：数据加载回归测试通过（与 Python 输出逐行比对）

### P3: 核心引擎（2 周）

- `engine/pipeline.go`: on_bar() 管线骨架
- `engine/risk.go`: RiskPipeline（止损/止盈/跟踪）
- `engine/oms.go`: 订单管理系统
- `engine/signal.go`: SignalAdapter（gRPC 代理到 Python）
- 7 个引擎实现 + `composite.go`
- **里程碑**：回测引擎回归——相同策略输入产生相同 PnL（浮点误差 < 1bp）

### P4: 交易执行（1.5 周）

- `broker/`: Binance/Futu/OKX 网关
- `papertrade/`: 模拟交易引擎
- `market/feed.go`: WebSocket 实时行情馈送
- **里程碑**：实盘信号可以正确生成并提交订单

### P5: API + 前端重写（1.5 周）

- `api/`: 全部 handler 实现
- Frontend: 全新 Next.js 项目搭建，27 个页面全部从零开发
- Python gRPC 服务端实现（5 个 service）
- **里程碑**：全栈回归——用户可完整走通交易流程

---

## 7. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Go Web 框架 | gin | 社区成熟、中间件生态丰富、性能稳定 |
| Go gRPC 工具 | buf + connect-go | 代码生成快、兼容 grpc-web |
| Go DB 库 | pgx + pgxpool | 高性能 PostgreSQL 驱动 |
| Go Redis 库 | rueidis | 高吞吐、线程安全 |
| 时序数据 | TimescaleDB（PG 扩展）| 无需额外服务、复用 PG 连接池 |
| Python gRPC | grpcio + grpcio-tools | 官方支持、成熟稳定 |
| 跨语言测试 | shared test fixtures (JSON) | 确保 Go 和 Python 产生相同结果 |

---

## 8. CLAUDE.md 新增规则

在 `## Development Rules` 下新增第一条：

```
### Spec → Plan → Test → Development Flow

**Before writing ANY code, the following three artifacts MUST be completed and reviewed in order:**

1. **Spec** — design document saved to `docs/superpowers/specs/`
2. **Plan** — implementation plan with phases and milestones, saved to `docs/superpowers/plans/`
3. **Test cases** — test specification listing all test cases, edge cases, and expected outputs

Only after all three are reviewed by the user and explicitly approved may implementation begin.

Any modification that touches engine logic, financial calculations, or data pipelines must follow this flow. Trivial changes (typos, CSS, config) may skip with user consent.
```
