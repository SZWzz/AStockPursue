# Phase 2 Code Quality Improvements Spec

> **Date**: 2026-06-23  
> **Status**: Approved  
> **Scope**: #7 Go interface{} → 强类型 + #8 前端 TypeScript 类型 + #6 前端测试补充

---

## #7: Go 层 interface{} → 强类型

### Tier A — engine/ 包（必须做）

**目标**：`Engine` 和 `RiskPipeline` 接口的 `bar interface{}` 参数改为 `bar *Bar`

**涉及文件**：

| 文件 | 改动 |
|------|------|
| `engine/engine.go:8` | `ApplySlippage(order *Order, bar interface{})` → `bar *Bar` |
| `engine/pipeline.go:13` | `CheckExits(portfolio *Portfolio, bar interface{})` → `bar *Bar` |
| `engine/pipeline.go:98` | 将 `BlockNewSignals` 提升为 `RiskPipeline` 接口方法 |
| `engine/pipeline.go:160` | `executeOrder(order *Order, bar interface{})` → `bar *Bar` |
| `engine/china_a.go:75` | 移除 `b := bar.(*Bar)` 不安全断言 |
| `engine/crypto.go:34` | 移除 `b := bar.(*Bar)` 不安全断言 |
| `engine/forex.go:27` | 移除 `b := bar.(*Bar)` 不安全断言 |
| `engine/futures_base.go:46` | 移除 `b := bar.(*Bar)` 不安全断言 |
| `engine/global_equity.go:51` | 移除 `b := bar.(*Bar)` 不安全断言 |
| `engine/options.go:29` | 移除 `b := bar.(*Bar)` 不安全断言 |
| `engine/composite.go:162` | 委托调用适配 |
| `engine/risk.go:30` | 移除 `b := bar.(*Bar)` 不安全断言 |
| `engine/pipeline_test.go` | 更新 mock 实现 |
| `engine/*_test.go` | 更新所有引擎测试中的 bar 参数 |

**影响范围**：~14 个文件，无 API 破坏性变更（所有调用方已传递 `*Bar`）

### Tier B — API/日志层（建议做）

| 文件 | 改动 |
|------|------|
| `api/ws.go` | `WSMessage.Data interface{}` → `any`；`Broadcast(channel string, data interface{})` → `data any` |
| `api/handler/broker.go` | 定义 `BrokerCredentials`、`BrokerSettings` 结构体替换 `map[string]interface{}` |
| `log/logger.go` | `...interface{}` → `...any`（4 个方法） |

**不做**：workflow/、research/、agent/ 的 `map[string]any`（架构决策，风险大）；gRPC gen/ 和 jwt-go 第三方接口

---

## #8: 前端 TypeScript API 类型

### 目标

创建 `frontend/types/api.ts`，定义核心 API 响应类型体系，替换组件中 `any` 类型。

### 类型定义

```typescript
// 基础类型
type MarketRow = { symbol: string; price: number; change_pct: number; volume: number; ... }
type KpiData = { label: string; value: number; change: number; ... }
type Portfolio = { total_value: number; cash: number; positions: Position[]; ... }
type Position = { symbol: string; quantity: number; avg_price: number; current_price: number; unrealized_pnl: number; ... }
type Order = { id: string; symbol: string; side: 'buy'|'sell'; type: string; price: number; quantity: number; status: string; ... }
type BacktestResult = { ... }
type FactorSummary = { ... }
```

### 替换范围

优先替换高频使用的 `any` 组件：`PositionTable`、`ScreenerGrid`、`CandlestickChart`、`OrderBook`、`EquityChart`、`DashboardPage`

---

## #8(续): 前端测试补充

### 目标：38 → 150+ 用例

### Phase 1 — 工具函数（现有 20 → 35+）

补充 `formatPrice`、`formatPercent`、`formatVolume`、`colorForChange` 的边界值和国际化测试

### Phase 2 — API/Hooks 层（新增 30+ 用例）

用 MSW (Mock Service Worker) mock API，测试 SWR hooks：`usePositions`、`useOrders`、`useMarketData`、`useKlines`

### Phase 3 — 核心组件（新增 65+ 用例）

| 组件 | 用例数 | 覆盖场景 |
|------|--------|---------|
| `PositionTable` | 15 | 渲染/空数据/平仓确认/虚拟滚动/排序/格式化 |
| `OrderForm` | 10 | 买/卖切换/输入验证/提交/清仓/错误状态 |
| `CandlestickChart` | 8 | 渲染/空数据/MA切换/悬停tooltip |
| `EquityChart` | 6 | 渲染/空数据/基准线/渐变 |
| `DrawdownChart` | 5 | 渲染/空数据/百分比格式 |
| `KpiCard` | 6 | 正负值/零值/大数字格式化 |
| `OrderBook` | 5 | 买盘/卖盘/空盘口/深度比例 |
| `ScreenerGrid` | 10 | 筛选/排序/评分/空结果/预设 |

### 验证

- `cd frontend && pnpm test` — 全部通过
- 用例数 ≥ 150

---

## 验证策略

1. Go: `go build ./... && go test ./... -race -count=1` — 零回归
2. Frontend: `pnpm test` — 150+ 用例通过
3. Frontend: `pnpm build` — 类型检查零错误

---

## 不作范围

| 项目 | 原因 |
|------|------|
| workflow/research/agent `map[string]any` | 架构决策，改动 15+ 节点，风险/收益比差 |
| gRPC gen/ 和 jwt-go `interface{}` | 第三方接口，不可改 |
| E2E 测试 | 本次聚焦单元+集成测试 |
| 前端 RSC 迁移 | 单独 Phase 3 议题 |
