# QuantFlow 启发改进设计

> 日期：2026-06-21 | 状态：已确认 | 参考：[重构规范](2026-06-20-go-python-hybrid-refactoring-design.md)

## 0. 背景

对比 QuantFlow 项目（Go 275 文件 + Python 75 文件）后，识别出 AStockPursue 可借鉴的 4 项改进：
- **P0**: Python gRPC/HTTP Bridge 重试机制
- **P1**: 工作流 DAG 引擎 Go 化
- **P2**: Go 市场数据适配器接口统一
- **P3**: Go 原生 AI Agent 轻量循环

---

## P0 — Python Bridge 重试+退避 (30 min)

### 现状

`data_client.py` 和 `go_http.py` 的请求都是单次调用，网络抖动即失败：
```python
resp = client.FetchBars(req, timeout=30)  # 一次失败就返回 []
```

### 设计

参考 QuantFlow `internal/python/data_client.go` 的线性退避 + jitter 模式：

```python
def _retry_with_backoff(fn, max_retries=3, base_delay=0.1):
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (grpc.RpcError, urllib.error.URLError) as e:
            if attempt == max_retries or not _is_transient(e):
                raise
            jitter = random.uniform(0, base_delay * (attempt + 1) * 0.5)
            time.sleep(base_delay * (attempt + 1) + jitter)
```

### 改动文件

| 文件 | 改动 |
|------|------|
| `src/grpc/data_client.py` | `fetch_bars()` 加 `_retry_with_backoff` |
| `src/go_http.py` | `_request()` 加重试逻辑 |
| `tests/test_data_client.py` | 新增重试测试 |

### 接口不变

`fetch_bars()` 和 `_request()` 的签名和返回值不变。

---

## P1 — 工作流 DAG 引擎 Go 化 (2-3 天)

### 现状

AStockPursue 工作流引擎在 Python 侧：
- `src/workflow/workflow_engine.py` — DAG 拓扑排序 + 执行
- `src/workflow/node_base.py` — 节点基类（asyncio 执行）
- `src/workflow/nodes/` — 25 个节点（数据/策略/交易/分析…）

问题：
- Python asyncio 单线程，DAG 层内节点无法真正并行
- 执行速度受 GIL 限制
- 节点类型定义松散（dict schema vs 编译期检查）

### 设计

参考 QuantFlow `internal/workflow/` (101 文件) 的精简版：

```
services/go/internal/workflow/    ← 新增
├── node.go          # BaseNode 接口
├── registry.go      # 自注册工厂
├── dag.go           # 拓扑排序 + 并行层执行
├── engine.go        # WorkflowEngine 运行时
└── nodes/           # 逐批迁移
    ├── data.go      # 数据加载 (取代 Python data_nodes)
    ├── signal.go    # 信号生成 (取代 Python signal_nodes)
    └── backtest.go  # 回测 (取代 Python strategy_nodes 的 BacktestNode)
```

#### 2.1 BaseNode 接口

```go
type PortType string

const (
    PortOHLCV  PortType = "ohlcv"
    PortSignal PortType = "signal"
    PortSeries PortType = "series"
    PortParams PortType = "params"
    PortAny    PortType = "any"
)

type PortDef struct {
    Name     string
    Type     PortType
    Required bool
}

type ParamDef struct {
    Name    string
    Type    string // "int","float","string","bool","string_array"
    Default any
}

type BaseNode interface {
    ID() string
    NodeType() string
    Category() string
    InputPorts() []PortDef
    OutputPorts() []PortDef
    ParamSchema() []ParamDef
    Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error)
    Validate() error
}
```

#### 2.2 DAG 并行执行

```go
// TopoSort returns layers of nodes that can execute in parallel.
func TopoSort(edges []Edge) ([][]string, error)

// Engine.Execute runs a workflow: topo sort → layer-by-layer parallel execution.
func (e *Engine) Execute(ctx context.Context, wf *Workflow) (*WorkflowResult, error)
```

核心逻辑：拓扑排序产生层级 → 同层节点 goroutine 并发执行 → 等整层完成后进入下一层。

#### 2.3 注册模式

```go
// nodes/data.go
func init() {
    workflow.Register("data_loader", func(id string, params map[string]any) (workflow.BaseNode, error) {
        return &DataLoaderNode{id: id}, nil
    })
}
```

Python workflow engine 保持不变 → 未来逐步迁移节点到 Go，Go engine 通过 gRPC 暴露 `ExecuteWorkflow` 给 Python workflow service。

#### 2.4 迁移策略

Go engine 先实现核心节点，然后逐步替代 Python `workflow_engine.py`：
1. Go 实现 `dag.go` → `engine.go` → 注册机制
2. 迁移 3 个核心节点：`data_loader`, `signal`, `backtest`
3. Python `WorkflowService` 调用 Go gRPC `ExecuteWorkflow` 而非本地 Python engine
4. 其余 22 个节点逐步迁移

### 改动文件

| 文件 | 操作 |
|------|------|
| `services/go/internal/workflow/node.go` | 新建 |
| `services/go/internal/workflow/registry.go` | 新建 |
| `services/go/internal/workflow/dag.go` | 新建 |
| `services/go/internal/workflow/dag_test.go` | 新建 |
| `services/go/internal/workflow/engine.go` | 新建 |
| `services/go/internal/workflow/engine_test.go` | 新建 |
| `services/go/internal/workflow/nodes/data.go` | 新建 |
| `services/go/internal/workflow/nodes/signal.go` | 新建 |
| `services/go/internal/workflow/nodes/backtest.go` | 新建 |
| `services/proto/workflow.proto` | 修改（加 ExecuteWorkflow RPC） |
| `services/python/src/grpc/workflow_service.py` | 修改（调用 Go engine） |

### 向后兼容

- Python `WorkflowService` 对外接口不变
- 内部实现从本地 Python engine 切换到 Go gRPC engine
- Python 节点暂时保留（通过 gRPC adapter 桥接）

---

## P2 — Go 市场数据适配器接口统一 (1 天)

### 现状

AStockPursue 有两套数据接口：
- Go `market/loader/interface.go` — `Loader` 接口
- Python `backtest/loaders/base.py` — `DataLoaderProtocol`

两个接口风格不同，字段命名不一致。

### 设计

参考 QuantFlow 的 `market.Adapter` 接口 + 编译期断言：

```go
// services/go/internal/market/adapter.go (重构现有 interface.go)

type Adapter interface {
    Name() string
    Markets() []string           // ["CN","HK","US","CRYPTO"]
    RequiresAuth() bool
    IsAvailable(ctx context.Context) bool
    Fetch(ctx context.Context, req FetchRequest) ([]Bar, error)
}

type FetchRequest struct {
    Symbol    string
    StartDate time.Time
    EndDate   time.Time
    Frequency string // "1d","1h","1m"
}

// 编译期接口断言
var (
    _ Adapter = (*TushareAdapter)(nil)
    _ Adapter = (*EastMoneyAdapter)(nil)
    _ Adapter = (*MootdxAdapter)(nil)
    _ Adapter = (*AKShareAdapter)(nil)
    _ Adapter = (*FutuAdapter)(nil)
)
```

### 改动文件

| 文件 | 操作 |
|------|------|
| `services/go/internal/market/adapter.go` | 重命名 interface.go，统一接口 |
| `services/go/internal/market/loader/registry.go` | 适配新接口 |
| `services/go/internal/market/loader/*.go` | 各 loader 实现新 Adapter 接口 |

### 接口对应关系

| 旧 Loader 接口 | 新 Adapter 接口 |
|---------------|----------------|
| `Name() string` | `Name() string` |
| `Supports(symbol) bool` | `Markets() []string` |
| `IsAvailable() bool` | `IsAvailable(ctx) bool` |
| `Fetch(symbol, start, end) ([]Bar, error)` | `Fetch(ctx, req) ([]Bar, error)` |

新增 `context.Context` 参数支持超时/取消。

---

## P3 — Go 原生 AI Agent 轻量循环 (1 周)

### 现状

AStockPursue 的 AI Agent 全部在 Python 侧 (`src/agent/loop.py`)，深度依赖 langgraph/langchain。Go 侧没有 agent 能力。

### 设计

不替代 Python Agent，而是在 Go 侧加一个**轻量版 agent loop**，用于无需 LLM 推理的简单任务：

```go
// services/go/internal/agent/   ← 新增
// ├── loop.go       # AgentLoop: 接收任务 → 匹配 Capability → 执行
// ├── registry.go   # CapabilityRegistry: 注册/查找能力
// └── capability.go  # Capability 接口

type Capability interface {
    Name() string
    Description() string
    Match(prompt string) (float64, bool)  // 语义匹配得分
    Execute(ctx context.Context, params map[string]any) (map[string]any, error)
}

type AgentLoop struct {
    registry *CapabilityRegistry
}

func (a *AgentLoop) Run(ctx context.Context, prompt string) (*AgentResult, error) {
    // 1. 匹配最相关的 Capability
    // 2. 如果匹配得分 > 阈值，直接执行
    // 3. 否则 fallback 到 Python Agent (gRPC)
}
```

### 使用场景

- 用户说 "查一下 600519 的最新报价" → Go `QuoteCapability` 直接返回，不走 LLM
- 用户说 "分析最近半年的市场情绪" → 匹配不上，fallback 到 Python LLM Agent

### 改动文件

| 文件 | 操作 |
|------|------|
| `services/go/internal/agent/loop.go` | 新建 |
| `services/go/internal/agent/registry.go` | 新建 |
| `services/go/internal/agent/capability.go` | 新建 |
| `services/go/internal/agent/capabilities/quote.go` | 新建 |
| `services/go/internal/agent/capabilities/backtest.go` | 新建 |
| `services/go/internal/agent/capabilities/screener.go` | 新建 |
| `services/proto/agent.proto` | 修改（加 ExecuteTask RPC） |

---

## 实施路线图

```
Week 1:
  Day 1: P0 — Python Bridge 重试 (30min → 立即可用)
  Day 1-2: P1 — 工作流 DAG 引擎 Go 化 (核心 3 文件: node/registry/dag)
  Day 3: P1 — 3 个核心节点迁移 (data/signal/backtest)
  Day 4: P2 — Adapter 接口统一

Week 2:
  Day 1: P1 — Python workflow_service 切换到 Go engine
  Day 2-4: P3 — Go Agent 轻量循环
  Day 5: 集成测试 + CHANGELOG
```

## 风险评估

| 风险 | 缓解 |
|------|------|
| P1 Go 工作流替换 Python engine 时数据类型不兼容 | ports 用 `map[string]any` 过渡，后续类型化 |
| P2 Adapter 接口改动破坏现有 loader | 新接口是增量，旧接口暂时保留 |
| P3 Agent 语义匹配不准 | 先用关键词匹配，后续加 embedding |
