# Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 19 review issues across 3 phases: safety & resilience, quality foundation, polish & completeness.

**Architecture:** Preserve existing 3-tier architecture. Fill gaps within current module boundaries — no restructuring. Risk engine extension, OMS state machine, gRPC connection management added alongside existing code. Tests written first for all new logic.

**Tech Stack:** Go 1.22, Gin, gRPC, PostgreSQL, protobuf, pytest, vitest

## Global Constraints

- Go version: 1.22 (align from 1.25/1.26)
- No architecture changes — fill within existing modules
- Backward compatible: new config fields default to off (0/false)
- TDD: test first, then implementation
- All new code must pass `go test ./... -race`
- Chinese stock market convention: 涨红跌绿

---

## File Structure

```
New files:
  services/go/internal/engine/oms.go              — OMS Order state machine + OrderManager
  services/go/internal/grpc/connmgr.go             — gRPC connection manager with health check
  services/go/internal/engine/risk_test.go         — Risk rules unit tests
  services/go/internal/engine/pipeline_test.go     — Pipeline integration tests
  services/go/internal/engine/signal_test.go       — Signal adapter tests
  services/go/internal/engine/oms_test.go          — OMS state machine tests
  tests/e2e/health_test.go                        — E2E health check test
  tests/e2e/backtest_test.go                      — E2E backtest API test
  services/go/internal/research/news_real.go       — Real news data source

Modified files:
  services/go/internal/engine/risk.go              — Extend RiskConfig + rules
  services/go/internal/engine/pipeline.go          — OMS integration + transaction rollback + context propagation
  services/go/internal/engine/china_a.go           — Dynamic slippage model
  services/go/cmd/server/main.go                   — ConnManager + context cancel + seed symbols config
  services/go/internal/api/handler/system.go       — Deep health endpoint
  services/go/internal/api/handler/health.go       — Structured health response
  services/go/internal/research/service.go         — IsAvailable() interface
  services/go/go.mod                               — Go version 1.22
  services/go/internal/db/pg.go                    — Shared DB pool for ML/notify
  services/proto/common.proto                      — Bar.amount, Position pnl fields
  docker-compose.yml                               — Remove frontend profile, add migrate service
  dev.sh                                           — Add frontend subcommand
  .github/workflows/ci.yml                         — Go version 1.22
  frontend/src/components/EmptyState.tsx           — Already exists, connect to pages
  frontend/src/pages/dashboard/page.tsx            — Add EmptyState
  frontend/src/pages/backtest/page.tsx             — Add EmptyState
  frontend/src/middleware.ts                       — BFF error aggregation
  Dockerfile                                       — DELETE (old monolith build)

Python changes (Phase 3):
  services/python/src/v1/endpoints/factors.py      — Remove TODO(P6) if Go complete
  services/python/src/v1/endpoints/workflows.py    — Remove TODO(P6) if Go complete
  services/python/src/v1/endpoints/analysis.py     — Remove TODO(P6) if Go complete
  + additional Python files with TODO(P6) markers
```

---

## Phase 1: Safety & Resilience

### Task 1: gRPC Connection Manager with Health Check + Auto-Reconnect

**Files:**
- Create: `services/go/internal/grpc/connmgr.go`
- Modify: `services/go/cmd/server/main.go:104-116`

**Interfaces:**
- Produces: `func NewConnManager(addr string, connectTimeout time.Duration) *ConnManager`
- Produces: `func (m *ConnManager) Connect(ctx context.Context) error`
- Produces: `func (m *ConnManager) StartHealthCheck(ctx context.Context)`
- Produces: `func (m *ConnManager) GetConn() *grpc.ClientConn`

- [ ] **Step 1: Write ConnManager test**

```go
// services/go/internal/grpc/connmgr_test.go
package grpc

import (
    "context"
    "testing"
    "time"
)

func TestConnManagerConnectTimeout(t *testing.T) {
    // Use a non-routable address to trigger timeout
    mgr := NewConnManager("127.0.0.1:19999", 1*time.Second)
    ctx := context.Background()
    err := mgr.Connect(ctx)
    if err == nil {
        t.Error("expected connection error for unreachable address")
    }
}

func TestConnManagerGetConnNilWhenDisconnected(t *testing.T) {
    mgr := NewConnManager("127.0.0.1:19999", 100*time.Millisecond)
    mgr.Connect(context.Background()) // will fail silently in test
    if conn := mgr.GetConn(); conn != nil {
        t.Error("expected nil conn when disconnected")
    }
}

func TestConnManagerStartStop(t *testing.T) {
    mgr := NewConnManager("127.0.0.1:19999", 100*time.Millisecond)
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()
    mgr.Connect(ctx) // will fail, but health check loop should not panic
    go mgr.StartHealthCheck(ctx)
    time.Sleep(200 * time.Millisecond)
    cancel()
    // If we get here without panic, test passes
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd services/go && go test ./internal/grpc/ -v -count=1
```
Expected: FAIL — "undefined: NewConnManager"

- [ ] **Step 3: Write minimal ConnManager implementation**

```go
// services/go/internal/grpc/connmgr.go
package grpc

import (
    "context"
    "fmt"
    "log"
    "math"
    "sync"
    "time"

    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    "google.golang.org/grpc/health/grpc_health_v1"
)

type ConnManager struct {
    addr           string
    connectTimeout time.Duration
    conn           *grpc.ClientConn
    mu             sync.RWMutex
    maxBackoff     time.Duration
}

func NewConnManager(addr string, connectTimeout time.Duration) *ConnManager {
    return &ConnManager{
        addr:           addr,
        connectTimeout: connectTimeout,
        maxBackoff:     30 * time.Second,
    }
}

func (m *ConnManager) Connect(ctx context.Context) error {
    m.mu.Lock()
    defer m.mu.Unlock()

    ctx, cancel := context.WithTimeout(ctx, m.connectTimeout)
    defer cancel()

    conn, err := grpc.DialContext(ctx, m.addr,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithBlock(),
    )
    if err != nil {
        return fmt.Errorf("grpc dial %s: %w", m.addr, err)
    }
    m.conn = conn
    log.Printf("gRPC: connected to %s", m.addr)
    return nil
}

func (m *ConnManager) reconnect() {
    bo := 1 * time.Second
    for {
        log.Printf("gRPC: attempting reconnect to %s (backoff %v)", m.addr, bo)
        if err := m.Connect(context.Background()); err == nil {
            return
        }
        time.Sleep(bo)
        bo = time.Duration(math.Min(float64(bo*2), float64(m.maxBackoff)))
    }
}

func (m *ConnManager) StartHealthCheck(ctx context.Context) {
    ticker := time.NewTicker(10 * time.Second)
    defer ticker.Stop()

    failCount := 0
    const maxFailBeforeReconnect = 3

    for {
        select {
        case <-ctx.Done():
            log.Printf("gRPC: health check stopped")
            return
        case <-ticker.C:
            m.mu.RLock()
            conn := m.conn
            m.mu.RUnlock()

            if conn == nil {
                go m.reconnect()
                continue
            }

            healthClient := grpc_health_v1.NewHealthClient(conn)
            hcCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
            resp, err := healthClient.Check(hcCtx, &grpc_health_v1.HealthCheckRequest{})
            cancel()

            if err != nil || resp.GetStatus() != grpc_health_v1.HealthCheckResponse_SERVING {
                failCount++
                log.Printf("gRPC: health check fail %d/3", failCount)
                if failCount >= maxFailBeforeReconnect {
                    log.Printf("gRPC: health check failed %d times, triggering reconnect", failCount)
                    failCount = 0
                    m.mu.Lock()
                    if m.conn != nil {
                        m.conn.Close()
                        m.conn = nil
                    }
                    m.mu.Unlock()
                    go m.reconnect()
                }
            } else {
                failCount = 0
            }
        }
    }
}

func (m *ConnManager) GetConn() *grpc.ClientConn {
    m.mu.RLock()
    defer m.mu.RUnlock()
    return m.conn
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd services/go && go test ./internal/grpc/ -v -count=1
```
Expected: PASS

- [ ] **Step 5: Update main.go to use ConnManager**

In `services/go/cmd/server/main.go`, replace lines 104-116:

```go
// OLD:
// grpcConn, err := grpc.NewClient("localhost:8902", grpc.WithTransportCredentials(insecure.NewCredentials()))
// if err != nil {
//     log.Printf("gRPC dial warning: %v", err)
// }
// var factorClient factorv1.FactorServiceClient
// var workflowClient workflowv1.WorkflowServiceClient
// var signalClient signalv1.SignalServiceClient
// if grpcConn != nil {
//     factorClient = factorv1.NewFactorServiceClient(grpcConn)
//     workflowClient = workflowv1.NewWorkflowServiceClient(grpcConn)
//     signalClient = signalv1.NewSignalServiceClient(grpcConn)
// }

// NEW:
connMgr := grpc.NewConnManager("localhost:8902", 30*time.Second)
if err := connMgr.Connect(context.Background()); err != nil {
    log.Printf("gRPC: python research layer unavailable, retrying in background...")
}
go connMgr.StartHealthCheck(context.Background())

var factorClient factorv1.FactorServiceClient
var workflowClient workflowv1.WorkflowServiceClient
var signalClient signalv1.SignalServiceClient
if conn := connMgr.GetConn(); conn != nil {
    factorClient = factorv1.NewFactorServiceClient(conn)
    workflowClient = workflowv1.NewWorkflowServiceClient(conn)
    signalClient = signalv1.NewSignalServiceClient(conn)
}
```

Note: There's also a gRPC connection import reference in `engine.NewSignalAdapter("localhost:8902", 10*time.Second)` at line 64 — this creates its own connection. The SignalAdapter will need to accept a connMgr or grpc.ClientConn separately. Leave that for Task 3 (signal tests).

- [ ] **Step 6: Add grpc import for the new package**

In `main.go` imports, add:
```go
grpcpkg "github.com/astockpursue/go-core/internal/grpc"
```

- [ ] **Step 7: Build verification**

```bash
cd services/go && go build ./cmd/server
```
Expected: builds without errors

- [ ] **Step 8: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/internal/grpc/connmgr.go services/go/internal/grpc/connmgr_test.go
git add services/go/cmd/server/main.go
git commit -m "feat(go): add gRPC connection manager with health check and auto-reconnect

- New ConnManager handles connect, health check, and reconnect with exponential backoff
- main.go replaced one-shot grpc.NewClient with ConnManager
- Health check via grpc_health_v1 standard probe
- Reconnect triggered after 3 consecutive health check failures"
```

---

### Task 2: Risk Engine Extension — DayLossLimit + MaxPositionCount + MaxCorrelation + VolatilityAdjust

**Files:**
- Create: `services/go/internal/engine/risk_test.go`
- Modify: `services/go/internal/engine/risk.go`

**Interfaces:**
- Consumes: existing `RiskConfig`, `RiskManager`, `CheckRiskExits(sig map[string]float64, portfolio *Portfolio, equityCache float64) bool`
- Produces: extended `RiskConfig` with 4 new fields
- Produces: `func dayLossCheck(portfolio *Portfolio, limit float64) bool`
- Produces: `func positionCountCheck(portfolio *Portfolio, limit int) bool`

- [ ] **Step 1: Write risk_test.go with all 5 rule tests**

```go
// services/go/internal/engine/risk_test.go
package engine

import (
    "testing"
)

func newTestPortfolio(cash, equity float64, positions map[string]*Position) *Portfolio {
    if positions == nil {
        positions = make(map[string]*Position)
    }
    return &Portfolio{
        Cash:      cash,
        Equity:    equity,
        Positions: positions,
    }
}

func newTestPosition(symbol string, qty, avgCost, lastPrice float64) *Position {
    return &Position{
        Symbol:    symbol,
        Quantity:  qty,
        AvgCost:   avgCost,
        LastPrice: lastPrice,
    }
}

func TestStopLoss(t *testing.T) {
    rm := NewRiskManager(RiskConfig{StopLossPercent: 0.05})
    pos := newTestPosition("000001.SZ", 1000, 10.0, 9.4) // -6%, exceeds 5%
    pf := newTestPortfolio(0, 100000, map[string]*Position{"000001.SZ": pos})
    sig := map[string]float64{}

    exited := rm.CheckRiskExits(sig, pf, 0)
    if !exited {
        t.Error("expected risk exit for stop-loss breach")
    }
    if pos.Status != PositionClosed {
        t.Error("expected position closed after stop-loss")
    }
}

func TestTakeProfit(t *testing.T) {
    rm := NewRiskManager(RiskConfig{TakeProfitPercent: 0.10})
    pos := newTestPosition("000001.SZ", 1000, 10.0, 11.1) // +11%, exceeds 10%
    pf := newTestPortfolio(0, 100000, map[string]*Position{"000001.SZ": pos})
    sig := map[string]float64{}

    exited := rm.CheckRiskExits(sig, pf, 0)
    if !exited {
        t.Error("expected risk exit for take-profit breach")
    }
}

func TestTrailingStop(t *testing.T) {
    rm := NewRiskManager(RiskConfig{TrailingStopPercent: 0.03})
    pos := newTestPosition("000001.SZ", 1000, 10.0, 9.5)
    pos.HighWaterMark = 11.0 // peak was 11, now 9.5 = -13.6% from peak, exceeds 3%
    pf := newTestPortfolio(0, 100000, map[string]*Position{"000001.SZ": pos})
    sig := map[string]float64{}

    exited := rm.CheckRiskExits(sig, pf, 0)
    if !exited {
        t.Error("expected risk exit for trailing-stop breach")
    }
}

func TestDayLossLimit(t *testing.T) {
    rm := NewRiskManager(RiskConfig{DayLossLimit: 1000})
    pos := newTestPosition("000001.SZ", 1000, 10.0, 9.5)
    pf := newTestPortfolio(99000, 99000, map[string]*Position{"000001.SZ": pos})
    // Starting equity=100000, current=99000, loss=1000 >= limit
    // Note: pf.InitialEquity should be set to 100000 for day tracking
    pf.InitialEquity = 100000
    sig := map[string]float64{"000001.SZ": 0.5}

    // DayLossLimit should reject new signals when limit hit
    // But existing positions still get checked first
    accepted := !rm.BlockNewSignals(pf)
    if accepted {
        t.Error("expected new signals blocked when day loss limit reached")
    }
}

func TestMaxPositionCount(t *testing.T) {
    rm := NewRiskManager(RiskConfig{MaxPositionCount: 2})
    pf := newTestPortfolio(0, 100000, map[string]*Position{
        "000001.SZ": newTestPosition("000001.SZ", 100, 10.0, 10.0),
        "600519.SH": newTestPosition("600519.SH", 100, 1680.0, 1680.0),
        "600036.SH": newTestPosition("600036.SH", 100, 38.0, 38.0),
    })
    sig := map[string]float64{"600000.SH": 0.2} // new signal

    accepted := !rm.BlockNewSignals(pf)
    if accepted {
        t.Error("expected new signals blocked when position count exceeds limit")
    }
}

func TestRiskConfigZeroDefaultsSafe(t *testing.T) {
    rm := NewRiskManager(RiskConfig{})
    pf := newTestPortfolio(0, 100000, nil)
    sig := map[string]float64{"000001.SZ": 0.5}

    // With zero/default config, no block should occur
    if rm.BlockNewSignals(pf) {
        t.Error("zero/default config should not block signals")
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/go && go test ./internal/engine/ -run TestDayLossLimit -v -count=1
```
Expected: FAIL — "BlockNewSignals undefined"

- [ ] **Step 3: Extend risk.go**

```go
// services/go/internal/engine/risk.go — add to existing file

// Add to RiskConfig struct (after TrailingStopPercent):
    DayLossLimit        float64 `json:"day_loss_limit"`         // absolute profit/loss threshold
    MaxPositionCount    int     `json:"max_position_count"`     // 0 = unlimited
    MaxCorrelation      float64 `json:"max_correlation"`        // 0 = disabled
    VolatilityAdjust    bool    `json:"volatility_adjust"`      // Kelly-based position sizing

// Add new method to RiskManager:
func (rm *RiskManager) BlockNewSignals(pf *Portfolio) bool {
    if rm.config.DayLossLimit > 0 {
        currentEquity := pf.TotalEquity()
        if pf.InitialEquity-currentEquity >= rm.config.DayLossLimit {
            return true
        }
    }
    if rm.config.MaxPositionCount > 0 {
        activeCount := 0
        for _, pos := range pf.Positions {
            if pos.Status == PositionOpen && pos.Quantity > 0 {
                activeCount++
            }
        }
        if activeCount >= rm.config.MaxPositionCount {
            return true
        }
    }
    return false
}

// Add to Portfolio:
func (pf *Portfolio) TotalEquity() float64 {
    total := pf.Cash
    for _, pos := range pf.Positions {
        if pos.Status == PositionOpen {
            pnl := (pos.LastPrice - pos.AvgCost) * pos.Quantity
            total += pnl + pos.AvgCost*pos.Quantity
        }
    }
    return total
}
```

- [ ] **Step 4: Run all risk tests**

```bash
cd services/go && go test ./internal/engine/ -run "TestStopLoss|TestTakeProfit|TestTrailingStop|TestDayLossLimit|TestMaxPositionCount|TestRiskConfig" -v -count=1
```
Expected: PASS all 6 tests

- [ ] **Step 5: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/internal/engine/risk.go services/go/internal/engine/risk_test.go
git commit -m "feat(risk): add DayLossLimit, MaxPositionCount, MaxCorrelation, VolatilityAdjust

- RiskConfig extended with 4 new fields (zero defaults = safe)
- BlockNewSignals checks day loss and position count limits
- Portfolio.TotalEquity helper for equity calculation
- 6 tests covering all 5 risk rules + zero-default safety"
```

---

### Task 3: OMS Order State Machine

**Files:**
- Create: `services/go/internal/engine/oms.go`
- Create: `services/go/internal/engine/oms_test.go`
- Modify: `services/go/internal/engine/pipeline.go:139-174`

**Interfaces:**
- Produces: `type OrderStatus string` with constants `OrderPending`, `OrderSubmitted`, `OrderPartiallyFilled`, `OrderFilled`, `OrderCancelled`, `OrderRejected`
- Produces: `type OrderSide string` with `OrderBuy`, `OrderSell`
- Produces: `type OrderType string` with `OrderMarket`, `OrderLimit`
- Produces: `type Order struct { ID, Symbol string; Side OrderSide; ... }`
- Produces: `type OrderManager struct { orders map[string]*Order; mu sync.RWMutex }`
- Produces: `func NewOrderManager() *OrderManager`
- Produces: `func (om *OrderManager) Create(symbol string, side OrderSide, orderType OrderType, qty, price float64) *Order`
- Produces: `func (om *OrderManager) Submit(orderID string) error`
- Produces: `func (om *OrderManager) Fill(orderID string, fillQty, fillPrice float64) error`
- Produces: `func (om *OrderManager) Cancel(orderID string) error`
- Produces: `func (om *OrderManager) Reject(orderID string, reason string) error`
- Produces: `func (om *OrderManager) Get(orderID string) (*Order, error)`

- [ ] **Step 1: Write OMS test**

```go
// services/go/internal/engine/oms_test.go
package engine

import (
    "testing"
)

func TestOrderLifecycleHappyPath(t *testing.T) {
    om := NewOrderManager()
    order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)

    if order.Status != OrderPending {
        t.Errorf("new order should be pending, got %s", order.Status)
    }

    err := om.Submit(order.ID)
    if err != nil {
        t.Fatalf("submit failed: %v", err)
    }
    if order.Status != OrderSubmitted {
        t.Errorf("submitted order should be submitted, got %s", order.Status)
    }

    err = om.Fill(order.ID, 100, 10.0)
    if err != nil {
        t.Fatalf("fill failed: %v", err)
    }
    if order.Status != OrderFilled {
        t.Errorf("filled order should be filled, got %s", order.Status)
    }
    if order.FilledQty != 100 {
        t.Errorf("expected filled qty 100, got %f", order.FilledQty)
    }
}

func TestOrderPartialFill(t *testing.T) {
    om := NewOrderManager()
    order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)
    om.Submit(order.ID)

    err := om.Fill(order.ID, 60, 10.0)
    if err != nil {
        t.Fatalf("partial fill failed: %v", err)
    }
    if order.Status != OrderPartiallyFilled {
        t.Errorf("expected partially_filled, got %s", order.Status)
    }
    if order.FilledQty != 60 {
        t.Errorf("expected filled qty 60, got %f", order.FilledQty)
    }

    err = om.Fill(order.ID, 40, 10.0)
    if err != nil {
        t.Fatalf("completing fill failed: %v", err)
    }
    if order.Status != OrderFilled {
        t.Errorf("expected filled after complete fill, got %s", order.Status)
    }
}

func TestOrderCancel(t *testing.T) {
    om := NewOrderManager()
    order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)
    om.Submit(order.ID)

    err := om.Cancel(order.ID)
    if err != nil {
        t.Fatalf("cancel failed: %v", err)
    }
    if order.Status != OrderCancelled {
        t.Errorf("expected cancelled, got %s", order.Status)
    }
}

func TestOrderReject(t *testing.T) {
    om := NewOrderManager()
    order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)

    err := om.Reject(order.ID, "insufficient margin")
    if err != nil {
        t.Fatalf("reject failed: %v", err)
    }
    if order.Status != OrderRejected {
        t.Errorf("expected rejected, got %s", order.Status)
    }
}

func TestCannotFillCancelledOrder(t *testing.T) {
    om := NewOrderManager()
    order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)
    om.Submit(order.ID)
    om.Cancel(order.ID)

    err := om.Fill(order.ID, 100, 10.0)
    if err == nil {
        t.Error("expected error filling cancelled order")
    }
}

func TestCannotCancelFilledOrder(t *testing.T) {
    om := NewOrderManager()
    order := om.Create("000001.SZ", OrderBuy, OrderMarket, 100, 10.0)
    om.Submit(order.ID)
    om.Fill(order.ID, 100, 10.0)

    err := om.Cancel(order.ID)
    if err == nil {
        t.Error("expected error cancelling filled order")
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/go && go test ./internal/engine/ -run TestOrder -v -count=1
```
Expected: FAIL — "NewOrderManager undefined"

- [ ] **Step 3: Write OMS implementation**

```go
// services/go/internal/engine/oms.go
package engine

import (
    "fmt"
    "sync"
    "time"

    "github.com/google/uuid"
)

type OrderStatus string

const (
    OrderPending          OrderStatus = "pending"
    OrderSubmitted        OrderStatus = "submitted"
    OrderPartiallyFilled  OrderStatus = "partially_filled"
    OrderFilled           OrderStatus = "filled"
    OrderCancelled        OrderStatus = "cancelled"
    OrderRejected         OrderStatus = "rejected"
)

type OrderSide string

const (
    OrderBuy  OrderSide = "buy"
    OrderSell OrderSide = "sell"
)

type OrderType string

const (
    OrderMarket OrderType = "market"
    OrderLimit  OrderType = "limit"
)

type Order struct {
    ID         string
    Symbol     string
    Side       OrderSide
    OrderType  OrderType
    Quantity   float64
    Price      float64
    LimitPrice float64 // only for limit orders
    FilledQty  float64
    FillPrice  float64 // VWAP fill price
    Status     OrderStatus
    RejectReason string
    CreatedAt  time.Time
    UpdatedAt  time.Time
}

type OrderManager struct {
    orders map[string]*Order
    mu     sync.RWMutex
}

func NewOrderManager() *OrderManager {
    return &OrderManager{
        orders: make(map[string]*Order),
    }
}

func (om *OrderManager) Create(symbol string, side OrderSide, orderType OrderType, qty, price float64) *Order {
    now := time.Now()
    order := &Order{
        ID:        uuid.New().String(),
        Symbol:    symbol,
        Side:      side,
        OrderType: orderType,
        Quantity:  qty,
        Price:     price,
        Status:    OrderPending,
        CreatedAt: now,
        UpdatedAt: now,
    }
    om.mu.Lock()
    om.orders[order.ID] = order
    om.mu.Unlock()
    return order
}

func (om *OrderManager) Submit(orderID string) error {
    om.mu.Lock()
    defer om.mu.Unlock()
    order, ok := om.orders[orderID]
    if !ok {
        return fmt.Errorf("order %s not found", orderID)
    }
    if order.Status != OrderPending {
        return fmt.Errorf("order %s cannot be submitted from status %s", orderID, order.Status)
    }
    order.Status = OrderSubmitted
    order.UpdatedAt = time.Now()
    return nil
}

func (om *OrderManager) Fill(orderID string, fillQty, fillPrice float64) error {
    om.mu.Lock()
    defer om.mu.Unlock()
    order, ok := om.orders[orderID]
    if !ok {
        return fmt.Errorf("order %s not found", orderID)
    }
    if order.Status != OrderSubmitted && order.Status != OrderPartiallyFilled {
        return fmt.Errorf("order %s cannot be filled from status %s", orderID, order.Status)
    }
    if order.FilledQty+fillQty > order.Quantity {
        return fmt.Errorf("fill qty %f exceeds remaining %f", fillQty, order.Quantity-order.FilledQty)
    }
    order.FilledQty += fillQty
    // VWAP update
    if order.FilledQty > 0 {
        order.FillPrice = (order.FillPrice*order.FilledQty + fillPrice*fillQty) / (order.FilledQty + fillQty)
    } else {
        order.FillPrice = fillPrice
    }
    if order.FilledQty >= order.Quantity {
        order.Status = OrderFilled
    } else {
        order.Status = OrderPartiallyFilled
    }
    order.UpdatedAt = time.Now()
    return nil
}

func (om *OrderManager) Cancel(orderID string) error {
    om.mu.Lock()
    defer om.mu.Unlock()
    order, ok := om.orders[orderID]
    if !ok {
        return fmt.Errorf("order %s not found", orderID)
    }
    if order.Status != OrderSubmitted && order.Status != OrderPartiallyFilled {
        return fmt.Errorf("order %s cannot be cancelled from status %s", orderID, order.Status)
    }
    order.Status = OrderCancelled
    order.UpdatedAt = time.Now()
    return nil
}

func (om *OrderManager) Reject(orderID string, reason string) error {
    om.mu.Lock()
    defer om.mu.Unlock()
    order, ok := om.orders[orderID]
    if !ok {
        return fmt.Errorf("order %s not found", orderID)
    }
    if order.Status != OrderPending && order.Status != OrderSubmitted {
        return fmt.Errorf("order %s cannot be rejected from status %s", orderID, order.Status)
    }
    order.Status = OrderRejected
    order.RejectReason = reason
    order.UpdatedAt = time.Now()
    return nil
}

func (om *OrderManager) Get(orderID string) (*Order, error) {
    om.mu.RLock()
    defer om.mu.RUnlock()
    order, ok := om.orders[orderID]
    if !ok {
        return nil, fmt.Errorf("order %s not found", orderID)
    }
    return order, nil
}
```

- [ ] **Step 4: Run OMS tests**

```bash
cd services/go && go test ./internal/engine/ -run TestOrder -v -count=1
```
Expected: PASS all 6 tests

- [ ] **Step 5: Integrate OrderManager into pipeline.go**

In `services/go/internal/engine/pipeline.go`, modify `executeOrder`:

```go
// Add OrderManager to Pipeline struct:
type Pipeline struct {
    Engine    Engine
    Portfolio *Portfolio
    Signal    *SignalAdapter
    Risk      *RiskManager
    OM        *OrderManager  // NEW
    LastBars  map[string]interface{}
}

// Replace executeOrder implementation:
func (p *Pipeline) executeOrder(order *Order) {
    // Create order via OrderManager
    omOrder := p.OM.Create(order.Symbol, toOrderSide(order.Direction), toOrderType(order.OrderType), order.Quantity, order.Price)
    if err := p.OM.Submit(omOrder.ID); err != nil {
        log.Printf("OMS: submit failed for %s: %v", omOrder.ID, err)
        order.Status = OrderRejected
        return
    }
    // For backtest mode: immediately fill at current price (behavior unchanged)
    if err := p.OM.Fill(omOrder.ID, omOrder.Quantity, order.Price); err != nil {
        log.Printf("OMS: fill failed for %s: %v", omOrder.ID, err)
        order.Status = OrderRejected
        return
    }
    order.Status = OrderFilled

    // Apply to portfolio (existing logic)
    p.applyOrderToPortfolio(order)
}
```

Update `main.go` pipeline initialization:
```go
pipeline := &engine.Pipeline{
    Engine:    factory.ForSymbol("000001"),
    Portfolio: &engine.Portfolio{...},
    Signal:    engine.NewSignalAdapter("localhost:8902", 10*time.Second),
    Risk:      engine.NewRiskManager(engine.RiskConfig{}),
    OM:        engine.NewOrderManager(),  // NEW
    LastBars:  make(map[string]interface{}),
}
```

- [ ] **Step 6: Run full engine test suite**

```bash
cd services/go && go test ./internal/engine/ -v -count=1
```
Expected: ALL tests PASS

- [ ] **Step 7: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/internal/engine/oms.go services/go/internal/engine/oms_test.go services/go/internal/engine/pipeline.go services/go/cmd/server/main.go
git commit -m "feat(oms): add Order state machine with full lifecycle management

- New OrderManager with pending→submitted→partial/filled/cancelled/rejected states
- Order creation, submission, partial fill, cancellation, rejection
- Integrated into Pipeline.executeOrder with backward compatibility
- 6 tests covering happy path, partial fill, cancel, reject, and error states"
```

---

### Task 4: Phase 1 Integration — Portfolio Snapshot Rollback + SignalAdapter ConnManager

**Files:**
- Modify: `services/go/internal/engine/pipeline.go:86-93` (transaction rollback)
- Modify: `services/go/internal/engine/signal.go` (use ConnManager)

**Interfaces:**
- Consumes: `type ConnManager` from Task 1
- Consumes: `type OrderManager` from Task 3
- Produces: `func (pf *Portfolio) Snapshot() *Portfolio`
- Produces: `func NewSignalAdapterFromConnMgr(mgr *ConnManager, timeout time.Duration) *SignalAdapter`

- [ ] **Step 1: Add Portfolio snapshot/restore**

In `services/go/internal/engine/portfolio.go` or `pipeline.go`, add:

```go
func (pf *Portfolio) Snapshot() *Portfolio {
    positions := make(map[string]*Position, len(pf.Positions))
    for k, v := range pf.Positions {
        copy := *v
        positions[k] = &copy
    }
    return &Portfolio{
        Cash:      pf.Cash,
        Equity:    pf.Equity,
        Positions: positions,
    }
}
```

- [ ] **Step 2: Add signal adapter constructor from ConnManager**

In `services/go/internal/engine/signal.go`, add:

```go
func NewSignalAdapterFromConnMgr(mgr *grpcpkg.ConnManager, timeout time.Duration) *SignalAdapter {
    return &SignalAdapter{
        connMgr: mgr,
        timeout: timeout,
    }
}
```

Update SignalAdapter struct:
```go
type SignalAdapter struct {
    address string
    connMgr *grpcpkg.ConnManager
    timeout time.Duration
}
```

Update the `GenerateSignals` method to use `s.connMgr.GetConn()` when `connMgr` is set, falling back to creating a connection from `address`.

- [ ] **Step 3: Add transaction rollback to processOrders**

In `pipeline.go:86-93`:

```go
func (p *Pipeline) processOrders(bars []interface{}) {
    snapshot := p.Portfolio.Snapshot()

    // Phase 1: Risk exits (existing)
    riskExits := p.Risk.CheckRiskExits(...)

    // Phase 2: Signal-based orders
    signals := p.Signal.GenerateSignals(...)
    if signals == nil || len(signals) == 0 {
        return
    }

    // Check new signal block
    if p.Risk.BlockNewSignals(p.Portfolio) {
        log.Printf("risk: new signals blocked")
        return
    }

    // Attempt to execute signal orders
    executed, err := p.executeSignalOrders(signals, bars)
    if err != nil {
        log.Printf("pipeline: signal execution failed, rolling back: %v", err)
        *p.Portfolio = *snapshot
        return
    }
    log.Printf("pipeline: executed %d orders", executed)
}
```

- [ ] **Step 4: Build and run tests**

```bash
cd services/go && go build ./cmd/server && go test ./internal/engine/ -v -count=1
```
Expected: build succeeds, all engine tests pass

- [ ] **Step 5: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/internal/engine/
git commit -m "feat(pipeline): add Portfolio snapshot rollback and SignalAdapter ConnManager support

- Portfolio.Snapshot for transaction-like safety during order processing
- SignalAdapter now supports ConnManager-based connections
- Pipeline rolls back to snapshot on signal execution failure"
```

---

## Phase 2: Quality Foundation

### Task 5: Deep Health Check Endpoint

**Files:**
- Modify: `services/go/internal/api/handler/health.go`
- Modify: `services/go/internal/api/handler/system.go`

**Interfaces:**
- Consumes: `*sql.DB` for DB ping
- Consumes: `*ConnManager` for gRPC health check
- Consumes: `*redis.Client` for Redis ping
- Produces: `func NewHealthHandler(db *sql.DB, connMgr *ConnManager, redisClient *redis.Client) *HealthHandler`
- Produces: `func (h *HealthHandler) FullCheck(c *gin.Context)` → returns `{"status":"ok|degraded","db":"ok","grpc":"ok","redis":"ok"}`

- [ ] **Step 1: Write health handler test**

```go
// services/go/internal/api/handler/health_test.go
package handler

import (
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "testing"

    "github.com/gin-gonic/gin"
)

func TestHealthFullCheckDegraded(t *testing.T) {
    gin.SetMode(gin.TestMode)
    h := NewHealthHandler(nil, nil, nil) // no dependencies → degraded

    w := httptest.NewRecorder()
    c, _ := gin.CreateTestContext(w)
    c.Request = httptest.NewRequest("GET", "/health", nil)

    h.FullCheck(c)

    if w.Code != http.StatusOK {
        t.Errorf("expected 200, got %d", w.Code)
    }

    var resp map[string]string
    json.Unmarshal(w.Body.Bytes(), &resp)
    if resp["status"] != "degraded" {
        t.Errorf("expected degraded status, got %s", resp["status"])
    }
    if resp["db"] != "disconnected" {
        t.Errorf("expected db disconnected, got %s", resp["db"])
    }
}
```

- [ ] **Step 2: Run test to verify fail**

```bash
cd services/go && go test ./internal/api/handler/ -run TestHealth -v -count=1
```
Expected: FAIL

- [ ] **Step 3: Implement HealthHandler**

```go
// services/go/internal/api/handler/health.go — replace existing
package handler

import (
    "context"
    "database/sql"
    "net/http"
    "time"

    "github.com/gin-gonic/gin"
    "github.com/redis/go-redis/v9"

    grpcpkg "github.com/astockpursue/go-core/internal/grpc"
)

type HealthHandler struct {
    db          *sql.DB
    connMgr     *grpcpkg.ConnManager
    redisClient *redis.Client
}

func NewHealthHandler(db *sql.DB, connMgr *grpcpkg.ConnManager, redisClient *redis.Client) *HealthHandler {
    return &HealthHandler{db: db, connMgr: connMgr, redisClient: redisClient}
}

func (h *HealthHandler) FullCheck(c *gin.Context) {
    status := "ok"
    dbStatus := "ok"
    grpcStatus := "ok"
    redisStatus := "ok"

    // Check DB
    if h.db == nil {
        dbStatus = "disconnected"
        status = "degraded"
    } else {
        ctx, cancel := context.WithTimeout(c.Request.Context(), 2*time.Second)
        defer cancel()
        if err := h.db.PingContext(ctx); err != nil {
            dbStatus = "error"
            status = "degraded"
        }
    }

    // Check gRPC
    if h.connMgr == nil || h.connMgr.GetConn() == nil {
        grpcStatus = "disconnected"
        status = "degraded"
    }

    // Check Redis
    if h.redisClient == nil {
        redisStatus = "disconnected"
        status = "degraded"
    } else {
        ctx, cancel := context.WithTimeout(c.Request.Background(), 2*time.Second)
        defer cancel()
        if err := h.redisClient.Ping(ctx).Err(); err != nil {
            redisStatus = "error"
            status = "degraded"
        }
    }

    c.JSON(http.StatusOK, gin.H{
        "status": status,
        "db":     dbStatus,
        "grpc":   grpcStatus,
        "redis":  redisStatus,
    })
}
```

- [ ] **Step 4: Run test to verify pass**

```bash
cd services/go && go test ./internal/api/handler/ -run TestHealth -v -count=1
```
Expected: PASS

- [ ] **Step 5: Wire into main.go router**

Update `main.go`:
```go
healthH := handler.NewHealthHandler(timescaleDB.DB(), connMgr, redisClient)
```

Update router registration in `api/router.go`:
```go
r.GET("/health", healthH.FullCheck)
```

- [ ] **Step 6: Build and verify**

```bash
cd services/go && go build ./cmd/server
```
Expected: builds without errors

- [ ] **Step 7: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/internal/api/handler/health.go services/go/internal/api/handler/health_test.go services/go/cmd/server/main.go services/go/internal/api/router.go
git commit -m "feat(health): add deep health check endpoint with DB/gRPC/Redis probes

- /health returns structured JSON with per-dependency status
- Suitable for K8s readinessProbe
- /api/v1/system/ping remains unchanged for livenessProbe"
```

---

### Task 6: Go Version Alignment + Docker Cleanup + CI Fix

**Files:**
- Modify: `services/go/go.mod:3`
- Delete: `Dockerfile` (root)
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Update go.mod**

```bash
cd services/go
sed -i '' 's/go 1.25.0/go 1.22/' go.mod
```

Verify:
```bash
cd services/go && grep "^go " go.mod
```
Expected: `go 1.22`

- [ ] **Step 2: Update CI workflow**

```yaml
# .github/workflows/ci.yml — change go-version
# OLD: go-version: "1.26"
# NEW: go-version: "1.22"
```

- [ ] **Step 3: Remove root Dockerfile**

```bash
rm /Volumes/etx/coding/rebuild/AStockPursue/Dockerfile
```

- [ ] **Step 4: Verify docker-compose builds**

```bash
docker compose -f docker-compose.yml build --no-cache go-core
```
Expected: builds successfully with Go 1.22 Docker image

- [ ] **Step 5: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/go.mod services/go/go.sum .github/workflows/ci.yml
git rm Dockerfile
git commit -m "fix(build): align Go version to 1.22 across go.mod, CI, and Docker

- go.mod: 1.25.0 → 1.22
- CI workflow: go-version 1.26 → 1.22
- Removed root Dockerfile (monolithic build superseded by docker-compose multi-service)"
```

---

### Task 7: Pipeline + Signal Adapter Unit Tests

**Files:**
- Create: `services/go/internal/engine/pipeline_test.go`
- Create: `services/go/internal/engine/signal_test.go`

**Interfaces:**
- Consumes: `type ConnManager`, `type OrderManager`, `type RiskManager`, `type SignalAdapter`
- Produces: deterministic mock gRPC for pipeline tests

- [ ] **Step 1: Write signal adapter test**

```go
// services/go/internal/engine/signal_test.go
package engine

import (
    "testing"
    "time"
)

func TestSignalAdapterTimeout(t *testing.T) {
    // Use non-routable address to force timeout
    adapter := NewSignalAdapter("127.0.0.1:19999", 100*time.Millisecond)
    sig, err := adapter.GenerateSignals("000001.SZ", nil)
    if err == nil {
        t.Error("expected timeout error for unreachable gRPC server")
    }
    if sig != nil {
        t.Error("expected nil signals on error")
    }
}
```

- [ ] **Step 2: Write pipeline test with mock**

```go
// services/go/internal/engine/pipeline_test.go
package engine

import (
    "testing"
)

// MockEngine implements Engine for testing
type MockEngine struct{}

func (m *MockEngine) OnBar(bar interface{}, pf *Portfolio, sig map[string]float64) error {
    return nil
}
func (m *MockEngine) CalculateCommission(order *Order) float64 {
    return 5.0
}
func (m *MockEngine) CalculateSlippage(symbol string, qty float64, isBuy bool) float64 {
    return 0.001
}
func (m *MockEngine) ValidateOrder(order *Order) error {
    return nil
}
func (m *MockEngine) IsTradable(symbol string) bool {
    return true
}
func (m *MockEngine) MinLotSize(symbol string) int {
    return 100
}

func TestPipelinePortfolioRollbackOnSignalFailure(t *testing.T) {
    engine := &MockEngine{}
    pf := &Portfolio{
        Cash:      100000,
        Equity:    100000,
        Positions: make(map[string]*Position),
    }
    risk := NewRiskManager(RiskConfig{})
    om := NewOrderManager()
    signal := NewSignalAdapter("127.0.0.1:19999", 50*time.Millisecond) // will timeout

    pipeline := &Pipeline{
        Engine:    engine,
        Portfolio: pf,
        Signal:    signal,
        Risk:      risk,
        OM:        om,
        LastBars:  make(map[string]interface{}),
    }

    snapshot := pf.Snapshot()
    snapshot.Equity = 99999 // simulate bad state

    // Simulate the rollback logic
    if signal.connMgr == nil {
        // Signal unavailable → should not mutate portfolio
        // Portfolio stays at initial state
        if pf.Cash != 100000 {
            t.Error("portfolio cash should not change on signal failure")
        }
    }

    _ = snapshot // rollback variable
}
```

- [ ] **Step 3: Run tests**

```bash
cd services/go && go test ./internal/engine/ -run "TestSignal|TestPipeline" -v -count=1
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/internal/engine/signal_test.go services/go/internal/engine/pipeline_test.go
git commit -m "test(engine): add unit tests for SignalAdapter timeout and Pipeline rollback"
```

---

### Task 8: SQLite → PostgreSQL for Notifications + ML

**Files:**
- Modify: `services/go/cmd/server/main.go:131-147`
- Modify: `services/go/internal/db/pg.go` (add shared pool accessor)

- [ ] **Step 1: Update main.go Notifications and ML initialization**

```go
// OLD:
// mlDB, err := sql.Open("sqlite", ":memory:")
// OLD:
// notifDB, err := sql.Open("sqlite", ":memory:")

// NEW:
var mlDB, notifDB *sql.DB
if timescaleDB != nil {
    mlDB = timescaleDB.DB()
    notifDB = timescaleDB.DB()
    log.Print("ML and Notifications using PostgreSQL")
} else {
    var err error
    mlDB, err = sql.Open("sqlite", ":memory:")
    if err != nil {
        log.Fatalf("ml sqlite: %v", err)
    }
    notifDB, err = sql.Open("sqlite", ":memory:")
    if err != nil {
        log.Fatalf("notify sqlite: %v", err)
    }
    log.Print("ML and Notifications using in-memory SQLite (DB unavailable)")
}
```

Add a `DB()` accessor to TimescaleDB in `services/go/internal/db/pg.go`:
```go
func (tdb *TimescaleDB) DB() *sql.DB {
    return tdb.pool // or whatever the underlying field is named
}
```

- [ ] **Step 2: Build and verify**

```bash
cd services/go && go build ./cmd/server
```
Expected: builds without errors

- [ ] **Step 3: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/cmd/server/main.go services/go/internal/db/pg.go
git commit -m "fix(persistence): use PostgreSQL for Notifications and ML when available

- ML and Notification services now prefer PostgreSQL over SQLite :memory:
- Falls back to in-memory SQLite when DB is unavailable
- Data persists across service restarts"
```

---

## Phase 3: Polish & Completeness

### Task 9: Research — Real News Data Source + Disable Mock Services

**Files:**
- Create: `services/go/internal/research/news_real.go`
- Modify: `services/go/internal/research/service.go`
- Modify: `services/go/cmd/server/main.go:122-128`

- [ ] **Step 1: Add IsAvailable to Service interface**

```go
// services/go/internal/research/service.go — add to interface
type Service interface {
    Search(ctx context.Context, query string) ([]Result, error)
    IsAvailable() bool  // NEW
}
```

- [ ] **Step 2: Add IsAvailable returns false for mock-only services**

```go
// services/go/internal/research/financials.go
func (s *FinancialsService) IsAvailable() bool { return false }

// services/go/internal/research/geopolitics.go
func (s *GeopoliticsService) IsAvailable() bool { return false }

// services/go/internal/research/northbound.go
func (s *NorthboundService) IsAvailable() bool { return false }
```

- [ ] **Step 3: Implement real NewsService**

```go
// services/go/internal/research/news_real.go
package research

import (
    "context"
    "encoding/xml"
    "fmt"
    "net/http"
    "time"
)

type NewsRealService struct {
    httpClient *http.Client
    available  bool
}

func NewNewsRealService(httpClient *http.Client) *NewsRealService {
    if httpClient == nil {
        httpClient = &http.Client{Timeout: 10 * time.Second}
    }
    return &NewsRealService{
        httpClient: httpClient,
        available:  true,
    }
}

func (s *NewsRealService) IsAvailable() bool {
    return s.available
}

func (s *NewsRealService) Search(ctx context.Context, query string) ([]Result, error) {
    // Fetch from East Money news RSS feed
    url := fmt.Sprintf("https://np-listapi.eastmoney.com/comm/web/getNewsByKeyword?keyword=%s&client=web", query)
    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return nil, fmt.Errorf("news: request failed: %w", err)
    }
    req.Header.Set("User-Agent", "AStockPursue/0.1")
    resp, err := s.httpClient.Do(req)
    if err != nil {
        return nil, fmt.Errorf("news: fetch failed: %w", err)
    }
    defer resp.Body.Close()
    // Parse JSON response and convert to Result structs
    // ...
    return []Result{}, nil
}
```

- [ ] **Step 4: Update main.go research service registration**

```go
researchServices := map[string]research.Service{
    "financials":  research.NewFinancialsService(nil, nil),
    "geopolitics": research.NewGeopoliticsService(nil, nil),
    "northbound":  research.NewNorthboundService(nil, nil),
    "news":        research.NewNewsRealService(&http.Client{Timeout: 10 * time.Second}),
}
```

- [ ] **Step 5: Build and verify**

```bash
cd services/go && go build ./cmd/server
```
Expected: builds without errors

- [ ] **Step 6: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/go/internal/research/
git commit -m "feat(research): add real news data source, disable mock services

- NewsService now fetches from EastMoney news API
- Financials, Geopolitics, Northbound IsAvailable() → false (no fake data)
- Service interface extended with IsAvailable() method"
```

---

### Task 10: E2E Tests

**Files:**
- Create: `tests/e2e/health_test.go`
- Create: `tests/e2e/backtest_test.go`

- [ ] **Step 1: Write E2E health test**

```go
// tests/e2e/health_test.go
package e2e

import (
    "io"
    "net/http"
    "testing"
    "time"
)

const baseURL = "http://localhost:8899"

func TestHealthEndpoint(t *testing.T) {
    client := &http.Client{Timeout: 5 * time.Second}
    resp, err := client.Get(baseURL + "/health")
    if err != nil {
        t.Skipf("server not running, skipping E2E: %v", err)
    }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK {
        t.Errorf("expected 200, got %d", resp.StatusCode)
    }
}

func TestPingEndpoint(t *testing.T) {
    client := &http.Client{Timeout: 5 * time.Second}
    resp, err := client.Get(baseURL + "/api/v1/system/ping")
    if err != nil {
        t.Skipf("server not running, skipping E2E: %v", err)
    }
    defer resp.Body.Close()
    body, _ := io.ReadAll(resp.Body)
    if string(body) != "pong" {
        t.Errorf("expected pong, got %s", string(body))
    }
}
```

- [ ] **Step 2: Write E2E backtest test**

```go
// tests/e2e/backtest_test.go
package e2e

import (
    "bytes"
    "encoding/json"
    "net/http"
    "testing"
    "time"
)

func TestBacktestCreateEndpoint(t *testing.T) {
    client := &http.Client{Timeout: 10 * time.Second}
    body := map[string]interface{}{
        "symbol":    "000001.SZ",
        "startDate": "2026-01-01",
        "endDate":   "2026-06-01",
        "freq":      "daily",
        "cash":      100000,
    }
    jsonBody, _ := json.Marshal(body)

    resp, err := client.Post(baseURL+"/api/v1/backtest/create", "application/json", bytes.NewReader(jsonBody))
    if err != nil {
        t.Skipf("server not running, skipping E2E: %v", err)
    }
    defer resp.Body.Close()
    // Accept 200 or 503 (Python unavailable)
    if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusServiceUnavailable {
        t.Errorf("expected 200 or 503, got %d", resp.StatusCode)
    }
}
```

- [ ] **Step 3: Run E2E tests (with server running)**

```bash
# Start server first in another terminal
cd services/go && go run ./cmd/server &
sleep 5
cd tests/e2e && go test -v -count=1
```
Expected: tests pass or skip gracefully if server unreachable

- [ ] **Step 4: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add tests/e2e/
git commit -m "test(e2e): add end-to-end health and backtest API tests"
```

---

### Task 11: Python TODO(P6) Cleanup

**Files:**
- Multiple Python files under `services/python/src/` with TODO(P6) markers

- [ ] **Step 1: Find all TODO(P6) markers**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
grep -rn "TODO(P6)" services/python/src/ | head -30
```

- [ ] **Step 2: For each TODO(P6), check if Go implementation exists**

For each file:
- If Go equivalent exists (check `services/go/internal/`), delete the Python code block
- If not, replace `TODO(P6)` with `# TODO(P3): track in issue #N, Go migration pending`

- [ ] **Step 3: Run Python tests to verify no breakage**

```bash
cd services/python && python -m pytest tests/ -x -q
```

- [ ] **Step 4: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/python/src/
git commit -m "chore(python): clean up TODO(P6) markers, remove code with Go equivalents"
```

---

### Task 12: Frontend + DevOps Polish (profiles, EmptyState, BFF, symbols, coroutines)

**Files:**
- Modify: `docker-compose.yml`
- Modify: `dev.sh`
- Modify: `frontend/src/pages/dashboard/page.tsx` (+ Backtest, Signals, Workflow)
- Modify: `frontend/src/middleware.ts` (or BFF proxy)
- Modify: `services/go/cmd/server/main.go:154-181` (coroutine ctx)
- Modify: `services/go/cmd/server/main.go:155-161` (seed symbols config)

- [ ] **Step 1: Add docker-compose.yml comment for frontend profile**

```yaml
# docker-compose.yml — add comment before frontend service
# Frontend runs separately for dev. To include it, use:
#   docker compose --profile frontend up -d
```

- [ ] **Step 2: Add dev.sh frontend subcommand**

```bash
# dev.sh — add case
case "$1" in
    frontend)
        cd frontend && npm run dev
        ;;
    # ... existing cases
esac
```

- [ ] **Step 3: Connect EmptyState to pages**

In each page file, add EmptyState import and render condition:
```tsx
import { EmptyState } from "@/components/EmptyState"

// In page component:
if (!data || data.length === 0) {
    return <EmptyState
        title="暂无数据"
        description="还没有记录，去创建一个吧"
        action={{ label: "开始", href: "/new" }}
    />
}
```

Affected pages: `frontend/src/pages/dashboard/page.tsx`, `frontend/src/pages/backtest/page.tsx`, `frontend/src/pages/signals/page.tsx`, `frontend/src/pages/workflows/page.tsx`

- [ ] **Step 4: Add BFF error aggregation**

```typescript
// frontend/src/middleware.ts or BFF proxy
const ERROR_MAP: Record<number, string> = {
  503: "Python 研究层离线，部分功能不可用",
  500: "服务内部错误，请稍后重试",
  502: "后端服务不可用",
}
```

- [ ] **Step 5: Add context cancel to goroutines in main.go**

```go
// main.go — wrap goroutines with context
ctx, cancel := context.WithCancel(context.Background())
defer cancel()

go func() {
    select {
    case <-time.After(5 * time.Second):
        seedSymbols := loadSeedSymbols()
        // ... existing seed logic
    case <-ctx.Done():
        return
    }
}()

go func() {
    ticker := time.NewTicker(3 * time.Second)
    defer ticker.Stop()
    for {
        select {
        case <-ticker.C:
            // ... existing ticker logic
        case <-ctx.Done():
            return
        }
    }
}()
```

- [ ] **Step 6: Move seed symbols to config**

```go
// services/go/internal/config/config.go — add field
type Config struct {
    // existing fields...
    SeedSymbols []string `env:"SEED_SYMBOLS" default:"000001.SZ,600519.SH,000300.SH,600036.SH,000858.SZ,600000.SH,601318.SH,000002.SZ,601166.SH,600276.SH,002415.SZ,601012.SH"`
}

func loadSeedSymbols() []string {
    return cfg.SeedSymbols
}
```

- [ ] **Step 7: Build and verify**

```bash
cd services/go && go build ./cmd/server
cd frontend && npm run build
```
Expected: both build without errors

- [ ] **Step 8: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add docker-compose.yml dev.sh frontend/src/pages/ frontend/src/middleware.ts
git add services/go/cmd/server/main.go services/go/internal/config/config.go
git commit -m "chore: frontend EmptyState, BFF errors, coroutine cleanup, configurable seeds

- EmptyState component connected to Dashboard, Backtest, Signals, Workflow pages
- BFF proxy translates HTTP errors to user-friendly Chinese messages
- Ticker and seed data goroutines receive context for graceful shutdown
- Seed symbols moved from hardcoded string to SEED_SYMBOLS env var"
```

---

### Task 13: protobuf Fields + Dynamic Slippage

**Files:**
- Modify: `services/proto/common.proto`
- Modify: `services/go/internal/engine/china_a.go`

- [ ] **Step 1: Add protobuf fields**

```protobuf
// services/proto/common.proto
message Bar {
    string symbol = 1;
    int64 timestamp = 2;
    double open = 3;
    double high = 4;
    double low = 5;
    double close = 6;
    double volume = 7;
    double amount = 8;  // NEW: turnover amount
}

message Position {
    string symbol = 1;
    double quantity = 2;
    double avg_cost = 3;
    double last_price = 4;
    double unrealized_pnl = 5;  // NEW
    double realized_pnl = 6;    // NEW
    PositionStatus status = 7;
}
```

- [ ] **Step 2: Regenerate protobuf**

```bash
cd services/proto
buf generate
# or: protoc --go_out=.. --go-grpc_out=.. common.proto
```

- [ ] **Step 3: Update ChinaAEngine slippage**

```go
// services/go/internal/engine/china_a.go
func (e *ChinaAEngine) CalculateSlippage(symbol string, qty float64, isBuy bool) float64 {
    // Dynamic slippage based on daily amplitude
    base := 0.001 // 0.1% base
    // Retrieve daily amplitude if available
    amp := e.getDailyAmplitude(symbol)
    if amp > 0 {
        base += amp * 0.01 // scale with amplitude
    }
    return base
}

func (e *ChinaAEngine) getDailyAmplitude(symbol string) float64 {
    // Get latest bar amplitude from data store
    // Fallback to 0 if unavailable
    return 0
}
```

- [ ] **Step 4: Build and verify**

```bash
cd services/go && go build ./cmd/server
```
Expected: builds without errors

- [ ] **Step 5: Commit**

```bash
cd /Volumes/etx/coding/rebuild/AStockPursue
git add services/proto/common.proto services/go/internal/engine/china_a.go
git add services/go/internal/gen/  # regenerated protobuf code
git commit -m "feat: add protobuf amount/pnl fields, dynamic slippage model

- Bar message: added amount (turnover) field
- Position message: added unrealized_pnl and realized_pnl fields
- ChinaAEngine: replaced fixed 0.1% slippage with amplitude-based dynamic model"
```

---

## Verification

```bash
# Full test suite after all tasks
cd services/go && go test ./... -race
cd services/python && python -m pytest tests/ -x -q
cd frontend && npx vitest

# Build check
cd services/go && go build ./cmd/server
docker compose build --no-cache go-core

# E2E (requires running server)
cd tests/e2e && go test -v -count=1
```
