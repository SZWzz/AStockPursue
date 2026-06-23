# Phase 2 Code Quality Improvements Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Eliminate Go `interface{}` misuse (engine/api/log), add frontend TypeScript API types, and expand test coverage from 38 to 150+.

**Tech Stack:** Go 1.22+, Next.js 15/React 19/TypeScript 5.6, Vitest + Testing Library + MSW

## Global Constraints

- Go: `go build ./... && go test ./... -race -count=1` 零回归
- Frontend: `pnpm test` 150+ 通过, `pnpm build` 零类型错误
- 无 API 破坏性变更
- Git commit per task

---

### Task 1: Go engine/ — `bar interface{}` → `bar *Bar` (Tier A)

**Files:**
- Modify: `engine/engine.go:8` — Engine 接口
- Modify: `engine/pipeline.go:13,98,160` — RiskPipeline, Pipeline.executeOrder
- Modify: `engine/risk.go:30` — RiskManager.CheckExits
- Modify: `engine/china_a.go:75`, `engine/crypto.go:34`, `engine/forex.go:27`, `engine/futures_base.go:46`, `engine/global_equity.go:51`, `engine/options.go:29` — 各引擎 ApplySlippage
- Modify: `engine/composite.go:162` — 委托
- Modify: `engine/pipeline_test.go`, engine 下所有 `*_test.go` — test mocks

**Steps:**

- [ ] **Step 1: 修改 Engine 接口**

`engine/engine.go:8`:
```go
// Before:
ApplySlippage(order *Order, bar interface{}) float64
// After:
ApplySlippage(order *Order, bar *Bar) float64
```

- [ ] **Step 2: 修改 RiskPipeline 接口 + 提升 BlockNewSignals**

`engine/pipeline.go:13` — 接口:
```go
type RiskPipeline interface {
    CheckExits(portfolio *Portfolio, bar *Bar) []*Order
    BlockNewSignals(portfolio *Portfolio) bool
}
```

`engine/pipeline.go:98` — 删除类型断言包装，直接调用:
```go
// Before:
if rm, ok := interface{}(p.Risk).(interface{ BlockNewSignals(*Portfolio) bool }); ok && rm.BlockNewSignals(...) {
// After:
if p.Risk.BlockNewSignals(p.Portfolio) {
```

- [ ] **Step 3: 修改 executeOrder 签名**

`engine/pipeline.go:160`:
```go
// Before:
func (p *Pipeline) executeOrder(order *Order, bar interface{}) {
// After:
func (p *Pipeline) executeOrder(order *Order, bar *Bar) {
```

- [ ] **Step 4: 删除 7 个引擎实现中的不安全类型断言**

每个引擎的 `ApplySlippage` 方法：
```go
// Before:
func (e *ChinaAEngine) ApplySlippage(order *Order, bar interface{}) float64 {
    b := bar.(*Bar)
    ...
// After:
func (e *ChinaAEngine) ApplySlippage(order *Order, bar *Bar) float64 {
    ...
```
涉及: china_a.go, crypto.go, forex.go, futures_base.go, global_equity.go, options.go, composite.go

- [ ] **Step 5: 更新 risk.go**

`engine/risk.go:30`:
```go
// Before:
func (rm *RiskManager) CheckExits(portfolio *Portfolio, bar interface{}) []*Order {
    b := bar.(*Bar)
// After:
func (rm *RiskManager) CheckExits(portfolio *Portfolio, bar *Bar) []*Order {
```
同时删除 `bar.(*Bar)` 行，直接使用 `bar`。

添加 `BlockNewSignals` 方法到 RiskManager（如果还没有）。

- [ ] **Step 6: 更新所有 engine test 文件中的 mock 实现**

将 test mocks 中的 `bar interface{}` 改为 `bar *Bar`，移除 mock 中的 `bar.(*Bar)` 断言。添加 `BlockNewSignals` mock 方法。

- [ ] **Step 7: 构建和测试**

```bash
cd services/go && go build ./... && go test ./internal/engine/ -v -race -count=1
```

- [ ] **Step 8: Commit**

```
fix: engine types — bar interface{} → *Bar, BlockNewSignals promoted to interface
```

---

### Task 2: Go API/log — interface{} → any/struct (Tier B)

**Files:**
- Modify: `api/ws.go` — WSMessage, Broadcast
- Modify: `api/handler/broker.go` — credentials structs
- Modify: `log/logger.go` — variadic params

**Steps:**

- [ ] **Step 1: ws.go — Data 和 Broadcast 改为 any**

`api/ws.go:19-21`:
```go
type WSMessage struct {
    Channel string `json:"channel"`
    Data    any    `json:"data"`
}
```
`api/ws.go:108`: `func (h *WSHub) Broadcast(channel string, data any) {`

- [ ] **Step 2: broker.go — 定义凭证结构体**

在 `broker.go` 顶部添加:
```go
type BrokerCredential struct {
    APIKey    string `json:"api_key"`
    APISecret string `json:"api_secret"`
}

type BrokerSettings struct {
    BrokerCredentials map[string]BrokerCredential `json:"broker_credentials,omitempty"`
}
```
替换 GetCredentials/RevealCredentials 中的 `map[string]interface{}` 遍历为结构体读写。

- [ ] **Step 3: logger.go — interface{} → any**

`log/logger.go` 4 个方法:
```go
func (l *Logger) Info(format string, v ...any)
func (l *Logger) Error(format string, v ...any)
func (l *Logger) Warn(format string, v ...any)
func (l *Logger) Debug(format string, v ...any)
```

- [ ] **Step 4: 构建和测试**

```bash
cd services/go && go build ./... && go test ./internal/api/ ./internal/log/ -v -count=1
```

- [ ] **Step 5: Commit**

```
fix: Go API/log — interface{} → any, broker credential structs
```

---

### Task 3: Frontend — 创建 API 类型定义

**Files:**
- Create: `frontend/types/api.ts`
- Create: `frontend/types/index.ts` (re-export)

**Steps:**

- [ ] **Step 1: 创建 `frontend/types/api.ts`**

```typescript
// Market types
export interface MarketRow {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
  turnover?: number;
  high: number;
  low: number;
  open: number;
  prev_close: number;
}

// Portfolio types
export interface Position {
  symbol: string;
  side: 'long' | 'short';
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
}

export interface Portfolio {
  total_value: number;
  cash: number;
  market_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  positions: Position[];
  equity_curve?: EquityPoint[];
}

export interface EquityPoint {
  timestamp: number;
  equity: number;
  cash: number;
  position_count: number;
}

// Order types
export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type OrderStatus = 'pending' | 'filled' | 'partially_filled' | 'cancelled' | 'rejected';

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  price: number;
  quantity: number;
  filled: number;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
}

// KPI
export interface KpiData {
  label: string;
  value: number;
  change: number;
  change_pct?: number;
  format?: 'currency' | 'percent' | 'number' | 'volume';
}

// Factor
export interface FactorSummary {
  id: string;
  name: string;
  formula: string;
  ic: number;
  rank_ic: number;
  sharpe: number;
  turnover: number;
}

// Backtest
export interface BacktestResult {
  id: string;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_equity: number;
  total_return: number;
  annual_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  equity_curve: EquityPoint[];
}

// API wrapper
export interface ApiResponse<T> {
  data: T;
  error?: string;
}

// WebSocket
export interface WSMessage {
  channel: string;
  data: unknown;
}

export interface TickerData {
  symbol: string;
  price: number;
  change: number;
  change_pct: number;
}
```

- [ ] **Step 2: 创建 `frontend/types/index.ts`**

```typescript
export * from './api';
```

- [ ] **Step 3: 替换组件中的 any — 优先高频组件**

PositionTable: `pos: any` → `pos: Position`
ScreenerGrid: `row: any` → `row: MarketRow`
DashboardPage: `portfolio: any` → `portfolio: Portfolio`
KpiCard: 使用 `KpiData`

- [ ] **Step 4: 类型检查**

```bash
cd frontend && pnpm build 2>&1 | head -50
```

- [ ] **Step 5: Commit**

```
feat: add frontend API types — MarketRow, Position, Order, Portfolio, etc.
```

---

### Task 4: Frontend — 工具函数测试补充 (20 → 35+)

**Files:**
- Modify: `frontend/__tests__/utils.test.ts`

**Steps:**

- [ ] **Step 1: 读取现有测试了解格式**

- [ ] **Step 2: 补充边界值测试**

```typescript
describe('formatPrice', () => {
  it('formats integer', () => expect(formatPrice(100)).toBe('¥100.00'));
  it('formats decimal', () => expect(formatPrice(123.456)).toBe('¥123.46'));
  it('formats zero', () => expect(formatPrice(0)).toBe('¥0.00'));
  it('formats negative', () => expect(formatPrice(-50)).toBe('-¥50.00'));
  it('handles NaN', () => expect(formatPrice(NaN)).toBe('--'));
  it('handles Infinity', () => expect(formatPrice(Infinity)).toBe('--'));
});

describe('formatPercent', () => {
  it('formats positive', () => expect(formatPercent(5.678)).toBe('+5.68%'));
  it('formats negative', () => expect(formatPercent(-3.2)).toBe('-3.20%'));
  it('formats zero', () => expect(formatPercent(0)).toBe('0.00%'));
  it('formats small value', () => expect(formatPercent(0.001)).toBe('+0.00%'));
});

describe('formatVolume', () => {
  it('K units', () => expect(formatVolume(5000)).toBe('5.00K'));
  it('M units', () => expect(formatVolume(5000000)).toBe('5.00M'));
  it('B units', () => expect(formatVolume(5000000000)).toBe('5.00B'));
  it('small value', () => expect(formatVolume(500)).toBe('500'));
});

describe('colorForChange', () => {
  it('positive returns up color', () => expect(colorForChange(5)).toBe('var(--up)'));
  it('negative returns down color', () => expect(colorForChange(-3)).toBe('var(--down)'));
  it('zero returns neutral', () => expect(colorForChange(0)).toBe('var(--foreground)'));
});
```

- [ ] **Step 3: 运行测试**

```bash
cd frontend && pnpm test __tests__/utils.test.ts
```

- [ ] **Step 4: Commit**

```
test: expand utils tests to 35+ — edge cases for formatPrice/Percent/Volume/colorForChange
```

---

### Task 5: Frontend — SWR Hooks 测试 (新增 30+ 用例)

**Files:**
- Create: `frontend/__tests__/hooks.test.tsx`

**Steps:**

- [ ] **Step 1: 安装 MSW**

```bash
cd frontend && pnpm add -D msw@latest
```

- [ ] **Step 2: 创建 hooks 测试**

```typescript
// __tests__/hooks.test.tsx
import { renderHook, waitFor } from '@testing-library/react';
import { SWRConfig } from 'swr';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(/* handlers */);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const wrapper = ({ children }) => (
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    {children}
  </SWRConfig>
);

describe('usePositions', () => {
  it('returns loading state initially', async () => {
    server.use(http.get('/api/positions', () => HttpResponse.json({ data: [] })));
    const { result } = renderHook(() => usePositions(), { wrapper });
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  it('returns positions on success', async () => { /* ... */ });
  it('returns error on failure', async () => { /* ... */ });
  it('returns empty array for empty response', async () => { /* ... */ });
});

// Similar for: useOrders, useMarketData, useKlines, usePortfolio
// Target: 6 hooks × 5 tests = 30 tests
```

- [ ] **Step 3: 运行测试**

```bash
cd frontend && pnpm test __tests__/hooks.test.tsx
```

- [ ] **Step 4: Commit**

```
test: add SWR hooks tests — usePositions/Orders/MarketData/Klines/Portfolio (30+ tests)
```

---

### Task 6: Frontend — 核心组件测试 (新增 65+ 用例)

**Files:**
- Create: `frontend/__tests__/PositionTable.test.tsx`
- Create: `frontend/__tests__/OrderForm.test.tsx` (扩展)
- Create: `frontend/__tests__/KpiCard.test.tsx` (扩展)
- Create: `frontend/__tests__/OrderBook.test.tsx`

**Steps:**

- [ ] **Step 1: PositionTable — 15 个测试**

渲染、空数据、持仓排序、格式化、平仓确认对话框等。

- [ ] **Step 2: OrderForm — 扩展至 10 个测试**

买/卖切换、输入验证、提交按钮 disabled、输入清空、清仓按钮等。

- [ ] **Step 3: KpiCard — 6 个测试**

正变化、负变化、零值、大数字、货币格式、百分比格式。

- [ ] **Step 4: OrderBook — 5 个测试**

买盘渲染、卖盘渲染、空盘口、深度比例、价差显示。

- [ ] **Step 5: CandlestickChart — 8 个测试**

有数据渲染、空数据、MA5/10/20/60 切换、tooltip 数据等。

- [ ] **Step 6: ScreenerGrid — 10 个测试**

筛选模式、排序模式、评分模式、空结果、预设加载等。

- [ ] **Step 7: 运行全部前端测试**

```bash
cd frontend && pnpm test
```

- [ ] **Step 8: Commit**

```
test: expand component coverage — PositionTable, OrderForm, KpiCard, OrderBook, CandlestickChart, ScreenerGrid (65+ tests)
```

---

## Final Verification

- [ ] `cd services/go && go build ./... && go test ./... -race -count=1`
- [ ] `cd frontend && pnpm test` — 150+ 通过
- [ ] `cd frontend && pnpm build` — 零类型错误
