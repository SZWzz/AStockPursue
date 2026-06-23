# Residual Features — Spec

**Date**: 2026-06-22 | **Status**: Design
**Scope**: Three new features identified as gaps in quant workflow completeness

---

## 1. Risk Dashboard

### Problem
VaR/CVaR/Beta/exposure calculations exist (as Python workflow nodes + gRPC service) but have no unified UI. Risk data is scattered: Dashboard shows basic KPI, Stress Test is orphaned in `/analysis/stress-test`, Drawdown is in `/analysis/drawdown`.

### Design

**Page**: `/monitor/risk` (new route, under Monitor nav group)

**Layout**: Dashboard grid with 6 cards:
1. **VaR Card** — Historical VaR (95%, 99%) + Parametric VaR. Sparkline of daily VaR over last 30 days.
2. **CVaR Card** — Conditional VaR (expected shortfall) with tail risk visualization.
3. **Beta Exposure Card** — Portfolio beta vs benchmark (CSI300 default). Sector-level beta breakdown as horizontal bar chart.
4. **Concentration Card** — Top 5 holdings % of portfolio. Pie/treemap chart.
5. **Stress Test Card** — Quick-run scenarios: 2008 crash, 2015 A-share crash, COVID 2020. Table with projected loss per scenario.
6. **Drawdown Card** — Current drawdown from peak, max drawdown history chart.

**Data flow**:
- Frontend calls `GET /api/v1/analysis/risk` — new endpoint
- Go handler calls Python `AnalysisService.CalcRisk` via gRPC
- Python implements `CalcRisk` rpc: computes VaR (historical+parametric), CVaR, Beta, concentration, stress test

**Backend changes**:
- New proto: `risk/v1/risk.proto` with `CalcRisk` rpc
- Go: `handler/analysis.go` — add `RiskHandler`
- Python: `grpc/risk_service.py` — implement RiskService

**Frontend files**:
- `app/monitor/risk/page.tsx` — new page
- `lib/navigation.ts` — add Risk under monitor group
- `hooks/useRisk.ts` — SWR hook

---

## 2. Trade Journal

### Problem
Trade records exist in three places (backtest detail, paper trading, live orders) but have no unified, searchable view. Quant traders need to answer: "show all trades for strategy X in Q1 2024" or "what was my win rate on tech stocks?"

### Design

**Page**: `/monitor/journal` (new route, under Monitor nav group)

**Layout**:
1. **Filter Bar**: strategy dropdown, symbol search, date range picker, trade type (buy/sell/all), source (backtest/paper/live)
2. **Summary Bar**: total trades, win rate, avg PnL, total PnL, Sharpe (of displayed trades)
3. **Trade Table**: symbol, strategy, direction, entry price, exit price, PnL, PnL%, holding period, source. Sortable columns. Pagination.
4. **Export**: CSV download of filtered trades

**Data flow**:
- `GET /api/v1/journal?strategy=X&symbol=Y&from=Z&to=W&source=backtest|paper|live`
- Results from `trade_journal` table (new migration)
- Backtest trades written on completion; paper/live trades written in real-time via OMS hooks

**Backend changes**:
- New migration: `000005_trade_journal.up.sql`
  ```sql
  CREATE TABLE trade_journal (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    strategy_name TEXT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL, -- 'buy' or 'sell'
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC,
    quantity NUMERIC NOT NULL,
    pnl NUMERIC,
    pnl_pct NUMERIC,
    holding_period INTERVAL,
    source TEXT NOT NULL, -- 'backtest', 'paper', 'live'
    source_id TEXT,        -- backtest_id / paper_run_id / order_id
    traded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );
  ```
- Go: `handler/journal.go` — query with filters
- Go: `engine/backtest.go` — write trades on backtest completion
- Go: `engine/oms.go` — write trades on order fill (paper + live)

**Frontend files**:
- `app/monitor/journal/page.tsx` — new page
- `lib/navigation.ts` — add Journal under monitor group
- `hooks/useJournal.ts` — SWR hook with filter params

---

## 3. JWT Refresh

### Problem
JWT `accessToken` is set once at login and never refreshed. If the backend token expires (e.g., 7-day default), all BFF proxy calls return 401 with no automatic recovery. User must manually re-login.

### Design

**Backend**:
- Add `POST /api/v1/auth/refresh` endpoint that accepts current (even expired-within-grace) token, returns new token with extended expiry.
- Go: `handler/auth.go` — validate current token with grace period (expired ≤24h ago still accepted for refresh), issue new token.

**Frontend**:
- In `lib/auth.config.ts` JWT callback: store `expires_at` alongside `accessToken`.
- In SWR global config or BFF proxy: on 401 response, attempt `POST /api/v1/auth/refresh` with stored token. If refresh succeeds, update session and retry original request. If refresh fails, redirect to login.
- Use NextAuth's `signIn` callback or a custom interceptor in `lib/bff-proxy.ts`.

**Grace period rule**: Token expired ≤24 hours → refresh allowed. Expired >24 hours → must re-login.

**Files**:
- Go: `handler/auth.go` — add `RefreshHandler`
- Go: `router.go` — register `/api/v1/auth/refresh`
- Frontend: `lib/auth.config.ts` — store expiry
- Frontend: `lib/bff-proxy.ts` — 401 interceptor with refresh retry

---

## Order of Implementation

Recommended order: **JWT Refresh → Trade Journal → Risk Dashboard**

Rationale: JWT refresh fixes a reliability issue first. Trade Journal has DB migration dependency that should land early. Risk Dashboard is the most UI-heavy and depends on Journal data for some metrics.

## Out of Scope (explicitly)

- Real-time risk alerts / push notifications
- Multi-portfolio risk aggregation
- Trade journal machine learning insights
- OAuth2/Social login for JWT refresh
