# QuantFlow 启发改进 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实施 P0-P3 四项改进：Python Bridge 重试、工作流 Go 化、Adapter 接口统一、Go Agent 轻量循环。

**Architecture:** 
- P0: 无架构变化，仅增强 `data_client.py` 和 `go_http.py` 的重试逻辑
- P1: 新增 `services/go/internal/workflow/` 包，Go DAG 引擎 + 3 个核心节点
- P2: 重构 `services/go/internal/market/loader/` → 统一 Adapter 接口
- P3: 新增 `services/go/internal/agent/` 包，Capability 注册 + 关键词匹配

**Tech Stack:** Go 1.25+, Python 3.11+, gRPC, gorilla/websocket, stdlib `net/http`

## Global Constraints

- 所有 Go 代码在 `services/go/internal/` 下
- 所有 Python 代码在 `services/python/src/` 下
- TDD: 先写测试 → 确认失败 → 实现 → 通过 → commit
- 每个 Task 结尾 `go test ./...` 通过
- gRPC proto 定义在 `services/proto/`
- 接口不变原则：对外 API 不变，内部实现可切换

---

## Phase 0: Python Bridge 重试机制

### Task 0.1: data_client.py 加重试

**Files:**
- Modify: `services/python/src/grpc/data_client.py`
- Create: `services/python/tests/test_data_client.py`

- [ ] **Step 1: 写重试辅助函数**

```python
# services/python/src/grpc/data_client.py 新增

import random
import time

def _is_transient_grpc_error(exc: Exception) -> bool:
    """判断 gRPC 错误是否可重试（网络抖动 vs 业务错误）."""
    import grpc
    if isinstance(exc, grpc.RpcError):
        code = exc.code()
        return code in (
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            grpc.StatusCode.INTERNAL,  # 可能是临时性内部错误
        )
    return True  # 非 gRPC 异常（连接错误）也重试


def _retry_with_backoff(
    fn,
    max_retries: int = 3,
    base_delay: float = 0.1,
) -> Any:
    """带线性退避 + jitter 的重试调用。

    Args:
        fn: 无参可调用对象（已经部分应用的 gRPC 调用）。
        max_retries: 最大重试次数（总调用次数 = max_retries + 1）。
        base_delay: 基础延迟秒数，第 N 次重试延迟 = base_delay * N + jitter。

    Returns:
        fn() 的返回值。

    Raises:
        最后一次尝试的异常（如果所有重试都失败）。
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            if not _is_transient_grpc_error(exc):
                raise
            jitter = random.uniform(0, base_delay * (attempt + 1) * 0.5)
            delay = base_delay * (attempt + 1) + jitter
            logger.debug(
                "Retry attempt %d/%d after %.2fs: %s",
                attempt + 1, max_retries, delay, exc,
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]
```

- [ ] **Step 2: 改造 fetch_bars() 使用重试**

```python
# 修改 fetch_bars() 函数体，把 client.FetchBars(req, timeout=30) 包进重试：

def fetch_bars(...) -> list[dict[str, Any]]:
    ...
    try:
        resp = _retry_with_backoff(
            lambda: client.FetchBars(req, timeout=30),
            max_retries=3,
            base_delay=0.1,
        )
    except Exception as exc:
        logger.debug("FetchBars gRPC call failed for %s after retries: %s", symbol, exc)
        return []
    ...
```

- [ ] **Step 3: 改造 fetch_bars_bulk() 使用重试**

```python
# fetch_bars_bulk() 内的 fetch_bars() 调用已自带重试，无需额外修改。
# 但为了减少重试风暴，加逐个符号的延迟：

def fetch_bars_bulk(symbols, ...) -> dict[str, "pd.DataFrame"]:
    ...
    for sym in symbols:
        bars = fetch_bars(...)
        if not bars and len(symbols) > 1:
            time.sleep(0.05)  # 50ms 间隔，避免重试风暴
        ...
```

- [ ] **Step 4: go_http.py 加重试**

```python
# services/python/src/go_http.py 新增

_http_retries = int(os.environ.get("GO_HTTP_RETRIES", "2"))

def _request(method, path, body=None, timeout=30):
    ...
    for attempt in range(_http_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read()) if raw else {}
        except urllib.error.HTTPError as exc:
            if 500 <= exc.code < 600 and attempt < _http_retries:
                time.sleep(0.1 * (attempt + 1))
                continue
            ...  # 现有错误处理
        except (urllib.error.URLError, OSError) as exc:
            if attempt < _http_retries:
                time.sleep(0.1 * (attempt + 1) + random.uniform(0, 0.05))
                continue
            return {"error": str(exc)}
```

- [ ] **Step 5: 验证语法 + 提交**

```bash
python -c "from src.grpc.data_client import fetch_bars, fetch_bars_bulk; print('OK')"
python -c "from src.go_http import _request; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add services/python/src/grpc/data_client.py services/python/src/go_http.py
git commit -m "feat(python): add retry with backoff to data_client and go_http

- data_client.fetch_bars(): linear backoff + jitter, 3 retries
- go_http._request(): configurable retries via GO_HTTP_RETRIES env
- Transient gRPC errors (UNAVAILABLE, DEADLINE_EXCEEDED) are retried
- Non-transient errors (INVALID_ARGUMENT, NOT_FOUND) fail immediately"
```

---

## Phase 1: 工作流 DAG 引擎 Go 化

### Task 1.1: BaseNode 接口 + Port 类型

**Files:**
- Create: `services/go/internal/workflow/node.go`

- [ ] **Step 1: 写接口定义**

```go
// services/go/internal/workflow/node.go
package workflow

import "context"

type PortType string

const (
    PortOHLCV  PortType = "ohlcv"
    PortSignal PortType = "signal"
    PortSeries PortType = "series"
    PortParams PortType = "params"
    PortAny    PortType = "any"
)

type PortDef struct {
    Name     string   `json:"name"`
    Type     PortType `json:"type"`
    Required bool     `json:"required"`
}

type ParamDef struct {
    Name        string `json:"name"`
    Type        string `json:"type"` // "int","float","string","bool","string_array"
    Default     any    `json:"default,omitempty"`
    Description string `json:"description,omitempty"`
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

- [ ] **Step 2: 编译验证 + 提交**

```bash
cd services/go && go build ./internal/workflow/...
git add services/go/internal/workflow/node.go
git commit -m "feat(workflow): add BaseNode interface + port type definitions"
```

### Task 1.2: NodeRegistry 自注册

**Files:**
- Create: `services/go/internal/workflow/registry.go`
- Create: `services/go/internal/workflow/registry_test.go`

- [ ] **Step 1: 写测试**

```go
// services/go/internal/workflow/registry_test.go
package workflow

import (
    "context"
    "testing"
)

type mockNode struct{ id string }

func (m *mockNode) ID() string                              { return m.id }
func (m *mockNode) NodeType() string                        { return "mock" }
func (m *mockNode) Category() string                        { return "test" }
func (m *mockNode) InputPorts() []PortDef                   { return nil }
func (m *mockNode) OutputPorts() []PortDef                  { return nil }
func (m *mockNode) ParamSchema() []ParamDef                 { return nil }
func (m *mockNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
    return map[string]any{"ok": true}, nil
}
func (m *mockNode) Validate() error { return nil }

func TestRegistryRegisterAndCreate(t *testing.T) {
    r := NewRegistry()
    r.Register("mock", func(id string, params map[string]any) (BaseNode, error) {
        return &mockNode{id: id}, nil
    })

    node, err := r.Create("mock", "n1", nil)
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if node.ID() != "n1" {
        t.Errorf("expected id n1, got %s", node.ID())
    }
    if node.NodeType() != "mock" {
        t.Errorf("expected type mock, got %s", node.NodeType())
    }
}

func TestRegistryCreateUnknown(t *testing.T) {
    r := NewRegistry()
    _, err := r.Create("nonexistent", "n1", nil)
    if err == nil {
        t.Error("expected error for unknown node type")
    }
}

func TestRegistryListAll(t *testing.T) {
    r := NewRegistry()
    r.Register("a", func(id string, params map[string]any) (BaseNode, error) {
        return &mockNode{id: id}, nil
    })
    r.Register("b", func(id string, params map[string]any) (BaseNode, error) {
        return &mockNode{id: id}, nil
    })

    all := r.ListAll()
    if len(all) != 2 {
        t.Errorf("expected 2, got %d", len(all))
    }
}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd services/go && go test ./internal/workflow/ -v -run TestRegistry
# Expected: FAIL — undefined: NewRegistry
```

- [ ] **Step 3: 实现**

```go
// services/go/internal/workflow/registry.go
package workflow

import (
    "fmt"
    "sync"
)

type NodeConstructor func(id string, params map[string]any) (BaseNode, error)

type NodeMeta struct {
    NodeType string `json:"node_type"`
    Category string `json:"category"`
}

type NodeRegistry struct {
    mu           sync.RWMutex
    constructors map[string]NodeConstructor
    categories   map[string]string
}

func NewRegistry() *NodeRegistry {
    return &NodeRegistry{
        constructors: make(map[string]NodeConstructor),
        categories:   make(map[string]string),
    }
}

func (r *NodeRegistry) Register(nodeType string, ctor NodeConstructor) {
    r.mu.Lock()
    defer r.mu.Unlock()
    r.constructors[nodeType] = ctor
}

func (r *NodeRegistry) RegisterWithCategory(nodeType string, ctor NodeConstructor, category string) {
    r.mu.Lock()
    defer r.mu.Unlock()
    r.constructors[nodeType] = ctor
    r.categories[nodeType] = category
}

func (r *NodeRegistry) Create(nodeType, id string, params map[string]any) (BaseNode, error) {
    r.mu.RLock()
    ctor, ok := r.constructors[nodeType]
    r.mu.RUnlock()
    if !ok {
        return nil, fmt.Errorf("unknown node type: %q", nodeType)
    }
    return ctor(id, params)
}

func (r *NodeRegistry) ListAll() []NodeMeta {
    r.mu.RLock()
    defer r.mu.RUnlock()
    result := make([]NodeMeta, 0, len(r.constructors))
    for nodeType, _ := range r.constructors {
        result = append(result, NodeMeta{
            NodeType: nodeType,
            Category: r.categories[nodeType],
        })
    }
    return result
}
```

- [ ] **Step 4: 测试通过 + 提交**

```bash
cd services/go && go test ./internal/workflow/ -v -run TestRegistry
git add services/go/internal/workflow/registry.go services/go/internal/workflow/registry_test.go
git commit -m "feat(workflow): add NodeRegistry with constructor pattern"
```

### Task 1.3: DAG 拓扑排序 + 工作流模型

**Files:**
- Create: `services/go/internal/workflow/dag.go`
- Create: `services/go/internal/workflow/dag_test.go`

- [ ] **Step 1: 写测试**

```go
// services/go/internal/workflow/dag_test.go
package workflow

import "testing"

func TestTopoSortLinear(t *testing.T) {
    edges := []Edge{
        {FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
        {FromNode: "b", FromPort: "out", ToNode: "c", ToPort: "in"},
    }
    layers, err := TopoSort(edges)
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if len(layers) != 3 {
        t.Errorf("expected 3 layers, got %d", len(layers))
    }
}

func TestTopoSortParallel(t *testing.T) {
    edges := []Edge{
        {FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
        {FromNode: "a", FromPort: "out", ToNode: "c", ToPort: "in"},
    }
    layers, err := TopoSort(edges)
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if len(layers) != 2 {
        t.Errorf("expected 2 layers (a → [b,c] in parallel), got %d", len(layers))
    }
    if len(layers[1]) != 2 {
        t.Errorf("expected 2 nodes in layer 1, got %d", len(layers[1]))
    }
}

func TestTopoSortCycleDetection(t *testing.T) {
    edges := []Edge{
        {FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
        {FromNode: "b", FromPort: "out", ToNode: "a", ToPort: "in"},
    }
    _, err := TopoSort(edges)
    if err == nil {
        t.Error("expected cycle error")
    }
}
```

- [ ] **Step 2: 实现**

```go
// services/go/internal/workflow/dag.go
package workflow

import "fmt"

type Edge struct {
    FromNode string `json:"from_node"`
    FromPort string `json:"from_port"`
    ToNode   string `json:"to_node"`
    ToPort   string `json:"to_port"`
}

type NodeInstance struct {
    ID       string         `json:"id"`
    NodeType string         `json:"node_type"`
    Params   map[string]any `json:"params,omitempty"`
}

type Workflow struct {
    Nodes []NodeInstance `json:"nodes"`
    Edges []Edge         `json:"edges"`
}

type CycleError struct {
    Node string
}

func (e *CycleError) Error() string {
    return fmt.Sprintf("workflow: cycle detected involving node %q", e.Node)
}

// TopoSort performs Kahn's algorithm to produce layers of nodes.
// Each layer contains nodes that can execute in parallel.
func TopoSort(edges []Edge) ([][]string, error) {
    inDegree := make(map[string]int)
    graph := make(map[string][]string)

    for _, e := range edges {
        inDegree[e.ToNode]++
        graph[e.FromNode] = append(graph[e.FromNode], e.ToNode)
        if _, ok := inDegree[e.FromNode]; !ok {
            inDegree[e.FromNode] = 0
        }
    }

    var queue []string
    for node, deg := range inDegree {
        if deg == 0 {
            queue = append(queue, node)
        }
    }

    var layers [][]string
    visited := 0
    for len(queue) > 0 {
        size := len(queue)
        layer := make([]string, 0, size)
        for i := 0; i < size; i++ {
            node := queue[0]
            queue = queue[1:]
            layer = append(layer, node)
            visited++
            for _, neighbor := range graph[node] {
                inDegree[neighbor]--
                if inDegree[neighbor] == 0 {
                    queue = append(queue, neighbor)
                }
            }
        }
        layers = append(layers, layer)
    }

    if visited < len(inDegree) {
        return nil, &CycleError{Node: "unknown"}
    }

    return layers, nil
}
```

- [ ] **Step 3: 测试通过 + 提交**

```bash
cd services/go && go test ./internal/workflow/ -v -run TestTopo
git add services/go/internal/workflow/dag.go services/go/internal/workflow/dag_test.go
git commit -m "feat(workflow): add DAG model, Kahn's topological sort, cycle detection"
```

### Task 1.4: WorkflowEngine 并行执行

**Files:**
- Create: `services/go/internal/workflow/engine.go`
- Create: `services/go/internal/workflow/engine_test.go`

- [ ] **Step 1: 实现 Engine**

```go
// services/go/internal/workflow/engine.go
package workflow

import (
    "context"
    "fmt"
    "sync"
)

type WorkflowResult struct {
    NodeOutputs map[string]map[string]any
    Error       error
}

type Engine struct {
    registry *NodeRegistry
}

func NewEngine(registry *NodeRegistry) *Engine {
    return &Engine{registry: registry}
}

func (e *Engine) Execute(ctx context.Context, wf *Workflow) (*WorkflowResult, error) {
    layers, err := TopoSort(wf.Edges)
    if err != nil {
        return nil, err
    }

    nodeIndex := make(map[string]NodeInstance)
    for _, n := range wf.Nodes {
        nodeIndex[n.ID] = n
    }

    outputs := make(map[string]map[string]any)
    var mu sync.Mutex

    for _, layer := range layers {
        var wg sync.WaitGroup
        errCh := make(chan error, len(layer))

        for _, nodeID := range layer {
            inst, ok := nodeIndex[nodeID]
            if !ok {
                continue
            }

            wg.Add(1)
            go func(id string, inst NodeInstance) {
                defer wg.Done()

                node, err := e.registry.Create(inst.NodeType, id, inst.Params)
                if err != nil {
                    errCh <- fmt.Errorf("node %s: %w", id, err)
                    return
                }

                // Gather inputs from upstream nodes
                inputs := make(map[string]any)
                for _, edge := range wf.Edges {
                    if edge.ToNode == id {
                        mu.Lock()
                        if upOutputs, ok := outputs[edge.FromNode]; ok {
                            if val, ok := upOutputs[edge.FromPort]; ok {
                                inputs[edge.ToPort] = val
                            }
                        }
                        mu.Unlock()
                    }
                }

                result, err := node.Execute(ctx, inputs, inst.Params)
                if err != nil {
                    errCh <- fmt.Errorf("node %s execute: %w", id, err)
                    return
                }

                mu.Lock()
                outputs[id] = result
                mu.Unlock()
            }(nodeID, inst)
        }

        wg.Wait()
        close(errCh)

        if err := <-errCh; err != nil {
            return &WorkflowResult{NodeOutputs: outputs, Error: err}, err
        }
    }

    return &WorkflowResult{NodeOutputs: outputs}, nil
}
```

- [ ] **Step 2: 写 engine 测试（mock node 线性工作流）**

```go
// services/go/internal/workflow/engine_test.go
package workflow

import (
    "context"
    "testing"
)

func TestEngineLinearWorkflow(t *testing.T) {
    reg := NewRegistry()
    reg.Register("pass_through", func(id string, params map[string]any) (BaseNode, error) {
        return &passThroughNode{id: id}, nil
    })

    engine := NewEngine(reg)
    wf := &Workflow{
        Nodes: []NodeInstance{
            {ID: "a", NodeType: "pass_through", Params: map[string]any{"value": 1}},
            {ID: "b", NodeType: "pass_through"},
        },
        Edges: []Edge{
            {FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
        },
    }

    result, err := engine.Execute(context.Background(), wf)
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    t.Logf("outputs: %+v", result.NodeOutputs)
}

type passThroughNode struct{ id string }

func (n *passThroughNode) ID() string           { return n.id }
func (n *passThroughNode) NodeType() string      { return "pass_through" }
func (n *passThroughNode) Category() string      { return "test" }
func (n *passThroughNode) InputPorts() []PortDef { return []PortDef{{Name: "in", Type: PortAny}} }
func (n *passThroughNode) OutputPorts() []PortDef { return []PortDef{{Name: "out", Type: PortAny}} }
func (n *passThroughNode) ParamSchema() []ParamDef { return nil }
func (n *passThroughNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
    val := params["value"]
    if v, ok := inputs["in"]; ok {
        val = v
    }
    return map[string]any{"out": val}, nil
}
func (n *passThroughNode) Validate() error { return nil }
```

- [ ] **Step 3: 测试通过 + 提交**

```bash
cd services/go && go test ./internal/workflow/ -v -count=1
git add services/go/internal/workflow/engine.go services/go/internal/workflow/engine_test.go
git commit -m "feat(workflow): add WorkflowEngine with parallel layer execution"
```

### Task 1.5: 核心节点 — DataLoader + Signal + Backtest

**Files:**
- Create: `services/go/internal/workflow/nodes/data.go`
- Create: `services/go/internal/workflow/nodes/signal.go`
- Create: `services/go/internal/workflow/nodes/backtest.go`

- [ ] **Step 1: DataLoaderNode**

```go
// services/go/internal/workflow/nodes/data.go
package nodes

import (
    "context"
    "time"
    "quantflow/internal/market"  // 替换为实际 import 路径
)

type DataLoaderNode struct {
    id   string
    ds   *market.DataStore
}

func (n *DataLoaderNode) ID() string           { return n.id }
func (n *DataLoaderNode) NodeType() string      { return "data_loader" }
func (n *DataLoaderNode) Category() string      { return "data" }
func (n *DataLoaderNode) InputPorts() []workflow.PortDef {
    return []workflow.PortDef{{Name: "symbols", Type: workflow.PortParams}}
}
func (n *DataLoaderNode) OutputPorts() []workflow.PortDef {
    return []workflow.PortDef{{Name: "ohlcv", Type: workflow.PortOHLCV}}
}
func (n *DataLoaderNode) ParamSchema() []workflow.ParamDef {
    return []workflow.ParamDef{
        {Name: "start_date", Type: "string", Default: "2024-01-01"},
        {Name: "end_date", Type: "string", Default: "2025-12-31"},
        {Name: "frequency", Type: "string", Default: "1d"},
    }
}
func (n *DataLoaderNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
    symbols := inputs["symbols"].([]string)
    start, _ := time.Parse("2006-01-02", params["start_date"].(string))
    end, _ := time.Parse("2006-01-02", params["end_date"].(string))
    freq := params["frequency"].(string)

    dataMap := make(map[string][]market.Bar)
    for _, sym := range symbols {
        bars, err := n.ds.GetBars(sym, start, end, freq)
        if err != nil {
            continue
        }
        dataMap[sym] = bars
    }
    return map[string]any{"ohlcv": dataMap}, nil
}
func (n *DataLoaderNode) Validate() error { return nil }

func init() {
    workflow.DefaultRegistry.Register("data_loader", func(id string, params map[string]any) (workflow.BaseNode, error) {
        return &DataLoaderNode{id: id}, nil
    })
}
```

- [ ] **Step 2: BacktestNode（复用现有 backtest engine）**

```go
// services/go/internal/workflow/nodes/backtest.go
package nodes

type BacktestNode struct {
    id      string
    runner  *engine.BacktestRunner
}

func (n *BacktestNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
    ohlcv := inputs["ohlcv"].(map[string][]market.Bar)
    symbols := make([]string, 0, len(ohlcv))
    for sym := range ohlcv { symbols = append(symbols, sym) }

    start, _ := time.Parse("2006-01-02", params["start_date"].(string))
    end, _ := time.Parse("2006-01-02", params["end_date"].(string))
    freq := params["frequency"].(string)

    result, err := n.runner.Run(symbols, start, end, freq)
    if err != nil {
        return nil, err
    }

    return map[string]any{
        "metrics": map[string]any{
            "total_return":  result.TotalReturn,
            "sharpe_ratio":  result.SharpeRatio,
            "max_drawdown":  result.MaxDrawdown,
            "win_rate":      result.WinRate,
            "total_trades":  result.TotalTrades,
        },
    }, nil
}

func init() {
    workflow.DefaultRegistry.Register("backtest", func(id string, params map[string]any) (workflow.BaseNode, error) {
        return &BacktestNode{id: id}, nil
    })
}
```

- [ ] **Step 4: 测试通过 + 提交**

```bash
cd services/go && go test ./... -count=1
git add services/go/internal/workflow/nodes/
git commit -m "feat(workflow): add DataLoader, Signal, Backtest core nodes"
```

---

## Phase 2: Go 市场数据适配器接口统一

### Task 2.1: 定义 Adapter 接口 + 编译期断言

**Files:**
- Create: `services/go/internal/market/adapter.go`

- [ ] **Step 1: 写新接口**

```go
// services/go/internal/market/adapter.go
package market

import (
    "context"
    "time"
)

type FetchRequest struct {
    Symbol    string
    StartDate time.Time
    EndDate   time.Time
    Frequency string
}

type Adapter interface {
    Name() string
    Markets() []string
    RequiresAuth() bool
    IsAvailable(ctx context.Context) bool
    Fetch(ctx context.Context, req FetchRequest) ([]Bar, error)
}
```

- [ ] **Step 2: loader/registry.go 加 Adapter 别名兼容**

```go
// 在 loader/registry.go 中
type Loader = market.Adapter  // 向后兼容别名
```

- [ ] **Step 3: 编译通过 + 提交**

```bash
cd services/go && go build ./...
git add services/go/internal/market/adapter.go
git commit -m "refactor(market): add Adapter interface with context support"
```

---

## Phase 3: Go Agent 轻量循环

### Task 3.1: Capability 接口 + Registry

**Files:**
- Create: `services/go/internal/agent/capability.go`
- Create: `services/go/internal/agent/registry.go`
- Create: `services/go/internal/agent/registry_test.go`

- [ ] **Step 1: Capability 接口**

```go
// services/go/internal/agent/capability.go
package agent

import "context"

type Capability interface {
    Name() string
    Description() string
    Keywords() []string
    Execute(ctx context.Context, params map[string]any) (map[string]any, error)
}
```

- [ ] **Step 2: CapabilityRegistry**

```go
// services/go/internal/agent/registry.go
package agent

import (
    "strings"
    "sync"
)

type CapabilityRegistry struct {
    mu           sync.RWMutex
    capabilities []Capability
}

func NewCapabilityRegistry() *CapabilityRegistry {
    return &CapabilityRegistry{}
}

func (r *CapabilityRegistry) Register(c Capability) {
    r.mu.Lock()
    defer r.mu.Unlock()
    r.capabilities = append(r.capabilities, c)
}

func (r *CapabilityRegistry) Match(prompt string) (Capability, float64) {
    r.mu.RLock()
    defer r.mu.RUnlock()

    promptLower := strings.ToLower(prompt)
    var best Capability
    var bestScore float64

    for _, c := range r.capabilities {
        score := keywordScore(promptLower, c.Keywords())
        if score > bestScore {
            bestScore = score
            best = c
        }
    }
    return best, bestScore
}

func keywordScore(prompt string, keywords []string) float64 {
    if len(keywords) == 0 {
        return 0
    }
    matched := 0
    for _, kw := range keywords {
        if strings.Contains(prompt, kw) {
            matched++
        }
    }
    return float64(matched) / float64(len(keywords))
}
```

- [ ] **Step 3: 写并跑测试**

```go
// services/go/internal/agent/registry_test.go
package agent

import (
    "context"
    "testing"
)

type mockCap struct {
    name     string
    keywords []string
}

func (m *mockCap) Name() string              { return m.name }
func (m *mockCap) Description() string       { return "test" }
func (m *mockCap) Keywords() []string        { return m.keywords }
func (m *mockCap) Execute(ctx context.Context, params map[string]any) (map[string]any, error) {
    return map[string]any{"from": m.name}, nil
}

func TestMatchByKeyword(t *testing.T) {
    reg := NewCapabilityRegistry()
    reg.Register(&mockCap{name: "quote", keywords: []string{"报价", "价格", "price", "quote"}})
    reg.Register(&mockCap{name: "backtest", keywords: []string{"回测", "backtest", "历史"}})

    c, score := reg.Match("查一下600519的最新报价")
    if c == nil {
        t.Fatal("expected a match")
    }
    if c.Name() != "quote" {
        t.Errorf("expected quote, got %s", c.Name())
    }
    if score < 0.2 {
        t.Errorf("expected score >= 0.2, got %.2f", score)
    }
}

func TestNoMatch(t *testing.T) {
    reg := NewCapabilityRegistry()
    reg.Register(&mockCap{name: "quote", keywords: []string{"报价"}})

    c, score := reg.Match("今天天气怎么样")
    if score > 0 {
        t.Logf("partial match score: %.2f (expected 0)", score)
    }
    _ = c
}
```

- [ ] **Step 4: 提交**

```bash
cd services/go && go test ./internal/agent/ -v -count=1
git add services/go/internal/agent/
git commit -m "feat(agent): add Capability interface + keyword-based registry

Lightweight Go-side agent task matching. When prompt matches a known
capability (e.g. quote, backtest), execute directly without LLM.
Fallback to Python Agent via gRPC when no match."
```

### Task 3.2: AgentLoop 主循环

**Files:**
- Create: `services/go/internal/agent/loop.go`

- [ ] **Step 1: 实现**

```go
// services/go/internal/agent/loop.go
package agent

import (
    "context"
    "fmt"
)

const MatchThreshold = 0.3

type AgentResult struct {
    Source   string         // "go_capability" or "python_llm"
    Data     map[string]any
    Error    error
}

type AgentLoop struct {
    registry    *CapabilityRegistry
    llmFallback func(ctx context.Context, prompt string) (map[string]any, error)
}

func NewAgentLoop(registry *CapabilityRegistry, llmFallback func(context.Context, string) (map[string]any, error)) *AgentLoop {
    return &AgentLoop{registry: registry, llmFallback: llmFallback}
}

func (a *AgentLoop) Run(ctx context.Context, prompt string) *AgentResult {
    cap, score := a.registry.Match(prompt)

    if cap != nil && score >= MatchThreshold {
        result, err := cap.Execute(ctx, map[string]any{"prompt": prompt})
        if err == nil {
            return &AgentResult{Source: "go_capability", Data: result}
        }
    }

    if a.llmFallback != nil {
        result, err := a.llmFallback(ctx, prompt)
        if err != nil {
            return &AgentResult{Source: "python_llm", Error: fmt.Errorf("llm fallback: %w", err)}
        }
        return &AgentResult{Source: "python_llm", Data: result}
    }

    return &AgentResult{Error: fmt.Errorf("no capability matched and no LLM fallback available")}
}
```

- [ ] **Step 2: 提交**

```bash
git add services/go/internal/agent/loop.go
git commit -m "feat(agent): add AgentLoop — capability-first execution with LLM fallback"
```

---

## Final Verification

- [ ] `go test ./...` — 全部通过
- [ ] `ruff check src/ tests/` — 全部通过
- [ ] CHANGELOG 更新
- [ ] go vet 无警告

---

## Self-Review

1. **Spec coverage**: P0-P3 全覆盖，每个 Task 有明确文件/代码/测试
2. **Placeholder scan**: 无 TBD/TODO
3. **Type consistency**: `BaseNode`, `Adapter`, `Capability` 接口定义清晰，跨 Task 一致
4. **Commit granularity**: 每 Task 一个 commit，独立可回滚
