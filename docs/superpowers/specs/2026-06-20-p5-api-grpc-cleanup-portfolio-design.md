# P5 API 补齐 + Python gRPC 服务 + 旧代码清理 + Portfolio 包 设计

> 日期：2026-06-20 | 状态：已确认 | 依赖：[重构规范](2026-06-20-go-python-hybrid-refactoring-design.md) 第 6 节 P5

## 1. 目标

补齐 P5 的 4 条工作线，实现 Go↔Python 全栈通信闭环，为前端 27 个页面提供完整 API。

## 2. 架构总览

```
Frontend (Next.js) ──REST──▶ Go API handlers ──gRPC──▶ Python gRPC services
                              │                              │
                              ├─ factor.go ──────────▶ FactorService (GP进化/因子计算)
                              ├─ workflow.go ────────▶ WorkflowService (DAG执行)
                              ├─ signal.go ──────────▶ SignalService (已有✅)
                              ├─ analysis.go ────────▶ AnalysisService (归因/相关性/压力测试)
                              └─ portfolio/          (Go本地，不调Python)
```

## 3. Track 1：Go API handler 补齐

### 3.1 factor.go — FactorHandler

**结构**：注入 `factorv1.FactorServiceClient`

| 端点 | HTTP | gRPC 方法 |
|------|------|----------|
| `POST /api/v1/factor/compute` | JSON request/response | `client.ComputeFactor(ctx, req)` |
| `POST /api/v1/factor/gp-mining` | SSE streaming | `client.StartGPMining(ctx, req)` 流式推送 |

**GP Mining 流式模式**：Go 侧调用 `StartGPMining` 获取 `grpc.ServerStream`，逐条读取 `GPResult` 后通过 SSE 推送给前端。这是 Go 代码库中首个 server-streaming gRPC 处理，参考 gin SSE 的 `c.Stream()` 方法。

### 3.2 workflow.go — WorkflowHandler

**结构**：注入 `workflowv1.WorkflowServiceClient`

| 端点 | HTTP | gRPC 方法 |
|------|------|----------|
| `POST /api/v1/workflow/execute` | JSON | `client.ExecuteWorkflow(ctx, req)` |
| `GET /api/v1/workflow/node/:id` | JSON | `client.GetNodeResult(ctx, req)` |
| `GET /api/v1/workflow/status/:id` | JSON | 本地查询（PG workflow_store） |

### 3.3 signal.go — SignalHandler

**结构**：注入 `signalv1.SignalServiceClient`

| 端点 | HTTP | gRPC 方法 |
|------|------|----------|
| `POST /api/v1/signal/generate` | JSON | `client.GenerateSignals(ctx, req)` |

### 3.4 路由注册

在 `router.go` 新增 3 个 group（挂 `/api/v1`，受 JWT 保护），`main.go` 注入 gRPC 连接。

---

## 4. Track 2：Python gRPC 服务补齐

### 4.1 factor_service.py — FactorServiceServicer

包裹 `factors/mining/gp_engine.py` + `factor_kb.py`。

| gRPC 方法 | 实现逻辑 |
|-----------|---------|
| `ComputeFactor` | 解析 formula → `ExpressionTree` → `to_callable()` → 对 symbols 面板计算 → 返回 values map |
| `StartGPMining` | 构建 `GPEvolutionConfig` → `GPEvolution(config).run()` → 逐代 yield `GPResult` |

**注意事项**：
- GP 进化是 CPU 密集型任务，在 ThreadPoolExecutor 中运行（`grpc.server` 默认 10 workers）
- `FactorKnowledgeBase` 通过 `get_kb()` 单例访问，线程安全（已有 `threading.Lock`）

### 4.2 llm_service.py — LLMServiceServicer

包裹 `agent/loop.py` + `agent/context.py` + `agent/tools.py`。

| gRPC 方法 | 实现逻辑 |
|-----------|---------|
| `Chat` | 创建 `ToolRegistry` → `AgentLoop.run(prompt)` → 返回 reply |
| `AgentDecide` | 带 context map 的结构化决策 → 返回 action + params |

**注意事项**：
- LLM 调用有速率限制和 token 预算控制（`agent/loop.py` 已有）
- 调用方 Go handler 需设置较长的 timeout（建议 60s）

### 4.3 analysis_service.py — AnalysisServiceServicer

包裹 `workflow/workflow_engine.py`（组合分析节点）。

| gRPC 方法 | 实现逻辑 |
|-----------|---------|
| `CalcAttribution` | 创建归因 DAG → `WorkflowEngine.execute()` → 提取归因结果 |
| `CalcCorrelation` | 计算相关性矩阵 → 返回扁平化的 `map[string]float64` |
| `StressTest` | 对指定场景运行压力测试节点 → 返回结果 |

### 4.4 workflow_service.py — WorkflowServiceServicer

包裹 `workflow/workflow_engine.py` + `workflow/workflow_store.py`。

| gRPC 方法 | 实现逻辑 |
|-----------|---------|
| `ExecuteWorkflow` | 加载 workflow → `WorkflowEngine.execute()` → 返回 status |
| `GetNodeResult` | 从 `WorkflowStore` 读取 `save_node_results` 持久化数据 |

### 4.5 server.py 注册

在 `serve()` 中新增 4 个 servicer 实例化和 `add_*_to_server()` 调用。所有 proto 桩代码已生成，无需重新编译。

---

## 5. Track 3：Python 旧代码调用方迁移

### 5.1 阶段 3a：迁移到 DataService gRPC（本次）

以下 8 个文件将 `loaders.registry` 调用替换为 `DataService.FetchBars` gRPC：

| 文件 | 当前导入 | 迁移方式 |
|------|---------|---------|
| `src/api/stock_routes.py` | `loaders.tencent`, `loaders.mootdx` | DataService gRPC |
| `src/ui_services.py` | `loaders.registry` | DataService gRPC |
| `src/api/system_routes.py` | `loaders.tencent` | DataService gRPC |
| `src/api/dashboard_routes.py` | `loaders.registry` | DataService gRPC |
| `src/swarm/grounding.py` | `loaders.registry` | DataService gRPC |
| `src/factors/mining/gp_engine.py` | `loaders.registry` | DataService gRPC |
| `src/tools/backtest_tool.py` | `loaders.registry` | DataService gRPC |
| `src/api/trading_routes.py` | `loaders.futu`, `loaders.tencent` | DataService gRPC |

### 5.2 阶段 3b：TODO 标记（本次）

以下文件因依赖尚未暴露 gRPC 的 Go 模块（engines、risk、brokers、OMS），本次只加注释标记：

```
# TODO(P5): migrate to Go EngineService gRPC when available
# TODO(P5): migrate to Go RiskService gRPC when available
# TODO(P5): migrate to Go BrokerService gRPC when available
```

涉及文件：`backtest/runner.py`、`papertrade/scheduler.py`、`src/trading/backtest_driver.py`、`src/trading/live_driver.py`、`src/workflow/nodes/strategy_nodes.py`、`src/workflow/nodes/thin_nodes.py`、`src/lab/backtest_bridge.py`、`src/services/live_bridge.py` 等约 15 个文件。

### 5.3 阶段 3c：删除 optimizers（本次）

`backtest/optimizers/` 目录（7 个文件）只有 1 处动态 import：
- `backtest/engines/base.py:161` — `importlib.import_module(f"backtest.optimizers.{opt_name}")`

安全移除步骤：
1. 将 `_load_optimizer()` 改为返回 Go 适配器或直接返回错误
2. 删除 `backtest/optimizers/` 整个目录

---

## 6. Track 4：Go portfolio 包

### 6.1 sizing.go — 仓位计算

```go
// Sizer 接口
type Sizer interface {
    Size(portfolio *engine.Portfolio, weights map[string]float64, prices map[string]float64) map[string]float64
}
```

三种实现：
- **EqualWeightSizer**：等权分配，考虑 RoundSize
- **KellySizer**：Kelly 公式 `f = (p*b - q) / b`
- **RiskParitySizer**：等波动率分配

### 6.2 margin.go — 保证金管理

```go
type MarginCalculator struct {
    Leverage    float64
    MaintMargin float64
}

func (m *MarginCalculator) Required(position *engine.Position) float64
func (m *MarginCalculator) Available(balance *engine.Portfolio) float64
func (m *MarginCalculator) CallLevel(equity float64, required float64) bool
```

---

## 7. 文件清单

### 新建

| 文件 | Track |
|------|-------|
| `services/go/internal/api/handler/factor.go` | 1 |
| `services/go/internal/api/handler/workflow.go` | 1 |
| `services/go/internal/api/handler/signal.go` | 1 |
| `services/python/src/grpc/factor_service.py` | 2 |
| `services/python/src/grpc/llm_service.py` | 2 |
| `services/python/src/grpc/analysis_service.py` | 2 |
| `services/python/src/grpc/workflow_service.py` | 2 |
| `services/go/internal/portfolio/sizing.go` | 4 |
| `services/go/internal/portfolio/margin.go` | 4 |

### 修改

| 文件 | Track |
|------|-------|
| `services/go/internal/api/router.go` | 1 |
| `services/go/cmd/server/main.go` | 1 |
| `services/python/src/grpc/server.py` | 2 |
| 约 8 个 Python 文件（3a 迁移） | 3 |
| 约 15 个 Python 文件（3b 标记） | 3 |
| `services/python/backtest/engines/base.py`（移除动态 import） | 3 |

### 删除

| 目录/文件 | Track |
|-----------|-------|
| `services/python/backtest/optimizers/`（7 文件） | 3c |

---

## 8. 自审

- 无 TBD，所有文件路径、接口方法、依赖关系已确定
- 接口不变性：Go handler 遵循现有 `AnalysisHandler` 模式；Python servicer 遵循 `DataServiceServicer` 模式
- 4 条 Track 可并行执行（仅 Track 1 依赖 Track 2 的 Python servicer 先就绪）
- 没有修改任何现有接口——纯增量
- Python 旧代码安全约束：只删 optimizers（唯一无静态调用方的目录），其余加 TODO 标记
