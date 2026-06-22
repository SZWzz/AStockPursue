# Quant Workflow Pipeline Remediation — Spec & Plan

**Date**: 2026-06-22 | **Status**: Executing
**Goal**: Connect the quant workflow pipeline end-to-end: Discovery→Strategy→Backtest→Optimize→Paper→Live→Monitor

---

## Stream A: Frontend Navigation & Cross-Page Links (P1)

### A1: Sidebar reorganization by quant stages

**File**: `frontend/lib/navigation.ts`
**Change**: Reorder from `main→trade→research→market→system` to quant workflow:

```
discovery       Market, Screener
strategy        Strategy Lab, Workflow, Factors  
backtest        Backtest, Optimization, Research
trading         Paper Trading, Live Trading, Orders, Positions, Signals
monitor         Dashboard, Analysis, Notifications, Scheduler
system          Broker, ML, Agent, Settings, System
```

### A2: Add orphaned pages to navigation

**Files**: `frontend/lib/navigation.ts`
Add entries for: Correlation (`/analysis/correlation`), Drawdown (`/analysis/drawdown`), Stress Test (`/analysis/stress-test`), Signals (`/signals`)

### A3: Cross-page links with query params

| From | To | Mechanism |
|------|----|-----------|
| `ScreenerGrid` row click | `/trading?symbol=X` | `onRowClick` prop |
| `Strategy Lab` "View Report" | `/backtest/${id}` | Link button |
| `Backtest Detail` "Paper Trade" | `/paper-trading` (POST create) | Action button |
| `Paper Detail` "Go Live" | `/trading?deploy=Y` | Action button |
| `Notifications` item click | Relevant target page | `href` on notification |
| `Market Overview` row click | `/market/${symbol}` + "Trade" button | Dual action |

---

## Stream B: Backend Data Pipeline (P1+P2)

### B1: Backtest results → PostgreSQL persistence

**Files**: `services/go/internal/db/backtest.go`, `services/db/migrations/`
- Create `backtest_results` table migration
- Replace `MemoryBacktestStore` with PG implementation
- Add `POST /api/v1/backtest` saves to DB, `GET /api/v1/backtest` reads from DB

### B2: Unify stock symbol format

**Files**: `services/go/internal/api/handler/market.go`, `screener.go`, `config.go`, Python `data_nodes.py`
- Adopt `{code}.{exchange}` universally (e.g., `000001.SZ`, `600519.SH`)
- Add normalization function in Go: `NormalizeSymbol(code, exchange)`
- Update Python gRPC data service to accept/return unified format

### B3: Backtest→Paper→Live promotion chain

**Files**: `services/go/internal/api/handler/papertrade.go`, `trading.go`
- `POST /api/v1/backtest/:id/promote-to-paper` — clones strategy config to paper trading
- `POST /api/v1/paper-trading/:id/promote-to-live` — deploys to live runner

### B4: Strategy CRUD

**Files**: `services/go/internal/api/handler/strategy.go` (new), `router.go`
- `POST /api/v1/strategy` — create with name, code, params, symbols
- `GET /api/v1/strategy` — list
- `GET /api/v1/strategy/:id` — detail
- `PUT /api/v1/strategy/:id` — update
- `DELETE /api/v1/strategy/:id` — delete
- DB table: `strategies(id, user_id, name, code, params, symbols, created_at, updated_at)`

---

## Stream C: Runtime & Integration Fixes (P1+P2)

### C1: Fix EvolutionNode — create optimize module

**File**: `services/python/src/optimize/evolution.py` (new)
- Implement minimal `StrategyEvolution` class with grid search + walk-forward
- Replace hardcoded placeholder `backtest_fn` with actual gRPC call to Go backtest

### C2: Signal gRPC — send actual market data

**Files**: `services/go/internal/engine/signal.go`, `services/go/internal/api/handler/signal.go`
- Load actual bars from market store before gRPC call
- Pass bars as `repeated Bar` in SignalRequest
- Python side: use actual bars for strategy execution

### C3: Attribution API — connect gRPC

**Files**: `services/go/internal/api/handler/analysis.go`
- Replace placeholder response with actual gRPC call to Python AnalysisService
- Python side: implement Brinson attribution calculation

### C4: Workflow Run button (Frontend)

**File**: `frontend/app/workflow/[id]/page.tsx`
- Add Run button with mode selector (backtest / paper / live)
- POST to `/api/v1/workflow/:id/run?mode=backtest`
- Show progress/results inline

---

## Execution

Three parallel agents: Stream A (frontend), Stream B (Go backend), Stream C (Python+Go integration). No cross-stream dependencies.
