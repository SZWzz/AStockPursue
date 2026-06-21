# Expert Review Remediation Plan

**Date:** 2026-06-21
**Status:** Draft
**Trigger:** Five-expert comprehensive review (Code / Frontend Design / Backend Architecture / Quantitative / Operations)
**Overall Grade:** B- → Target B+ after Phase 1-3

## 1. Review Summary

Five domain experts audited the entire codebase. The project has solid architectural foundations but systemic implementation gaps across all layers. Below is the consolidated remediation plan ordered by severity and dependency.

---

## Phase 1: Fix Critical (3 days)

Issues that make the system fundamentally broken or insecure. Must be resolved before any other work.

### 1a. JWT Secret Hardcoded → Environment Variable

**File:** `services/go/internal/api/handler/auth.go:18`
**Severity:** 🔴 CRITICAL — security vulnerability
**Problem:** `jwtSecret = []byte("astockpursue-jwt-secret-change-in-production")` committed to Git. The `init()` function at L20-25 has dead code — the env-var override check `if s := ""; s != ""` will never be true.
**Fix:**
- Remove the `init()` dead code block
- Read `JWT_SECRET` from `os.Getenv("JWT_SECRET")` with a hard fail if unset in production
- Add fallback default only when `os.Getenv("GO_ENV") == "development"`
- Regenerate the secret, add to `.env.example`, rotate immediately
**Backend:** Go auth handler
**Test:** Verify token generation/validation with env-sourced secret

### 1b. Backtest Signal Adapter is Always Noop

**File:** `services/go/internal/api/handler/backtest.go:119`
**Severity:** 🔴 CRITICAL — renders backtesting useless
**Problem:** `Signal: engine.NewNoopSignalAdapter()` — all REST-initiated backtests run with zero signals. No trades are ever generated.
**Fix:**
- Thread an `*engine.SignalAdapter` through `BacktestHandler` (acceptable interim: `engine.NewSignalAdapterFromConnMgr(cm)`)
- Fall back to Noop only when the gRPC connection is unavailable, and return a clear warning in the response
- Add `signal_adapter` field to `BacktestRequest` to allow users to specify signal source
**Backend:** Go backtest handler, signal adapter
**Test:** Manual backtest with signal generation endpoint returning non-zero weights

### 1c. Day Loss Limit Never Triggers

**File:** `services/go/internal/engine/risk.go:81`
**Severity:** 🔴 CRITICAL — risk management silently disabled
**Problem:** `pf.InitialEquity` is never set (remains 0). The check `pf.InitialEquity - currentEquity >= DayLossLimit` is effectively `-currentEquity >= DayLossLimit`, which only fires for negative equity (impossible in backtest).
**Fix:**
- Initialize `Portfolio.InitialEquity = req.InitialCash` in backtest handler L115
- Initialize `Portfolio.InitialEquity = ...` in live trading runner startup
- Add test: verify day loss limit triggers when equity drops below threshold
**Backend:** Go engine (risk.go, backtest.go, types.go), backtest handler
**Test:** Unit test with InitialEquity=100000, currentEquity=80000, DayLossLimit=20000 → should trigger

### 1d. Sharpe Ratio Assumes Daily Frequency

**File:** `services/go/internal/engine/backtest.go:238`
**Severity:** 🔴 CRITICAL — all non-daily backtest metrics are wrong
**Problem:** `r.SharpeRatio = mean / std * math.Sqrt(252)` — hardcoded for daily. 1-minute Sharpe would be inflated by sqrt(60480/252) ≈ 15.5×.
**Fix:**
```go
var periodsPerYear float64
switch freq {
case "1m":  periodsPerYear = 252 * 240   // ~60480
case "5m":  periodsPerYear = 252 * 48    // ~12096
case "15m": periodsPerYear = 252 * 16    // ~4032
case "30m": periodsPerYear = 252 * 8     // ~2016
case "1h":  periodsPerYear = 252 * 6.5   // ~1638
case "4h":  periodsPerYear = 252 * 1.625 // ~409
case "1d":  periodsPerYear = 252
case "1w":  periodsPerYear = 52
default:    periodsPerYear = 252
}
r.SharpeRatio = mean / std * math.Sqrt(periodsPerYear)
```
Apply same frequency-aware annualization to Sortino and Calmar ratios.
**Backend:** Go engine backtest.go
**Test:** Verify Sharpe for 1m backtest ≈ Sharpe for 1d backtest on same data (after resampling)

### 1e. CandlestickChart is a Line Chart in Disguise

**File:** `frontend/components/financial/CandlestickChart.tsx`
**Severity:** 🔴 CRITICAL — core trading chart is fake
**Problem:** Uses `<Line>` + `<Bar>` instead of OHLC rectangles. Shows only `close` price. No open/high/low visible.
**Fix:** Full rewrite using custom SVG rectangles:
- Each bar renders as a vertical line (high→low) + rectangle (open→close)
- Green/red fill based on close vs open
- Volume bars on secondary Y axis
- Tooltip showing O/H/L/C/V
- Respect `[lang="zh"]` red/green convention via CSS variables `var(--up)` / `var(--down)`
- Add MA5/MA10/MA20 overlay lines (optional, toggled)
**Frontend:** CandlestickChart.tsx full rewrite
**Test:** Visual verification with real OHLC data

### 1f. gRPC No TLS

**File:** `services/python/src/grpc/server.py:169`
**Severity:** 🔴 CRITICAL — plaintext inter-service traffic
**Problem:** `grpc.add_insecure_port(...)` — all Go↔Python traffic is unencrypted.
**Fix:**
- Generate self-signed certs for development: `openssl req -newkey rsa:2048 -nodes -keyout server.key -x509 -days 365 -out server.crt`
- Use `grpc.ssl_server_credentials(...)` on Python side
- Use `grpc.WithTransportCredentials(credentials.NewClientTLSFromCert(...))` on Go side
- Skip TLS only when `GO_ENV=development` flag is set
**Backend:** Python gRPC server, Go ConnManager

---

## Phase 2: Harden (5 days)

Fixes for systemic code quality, type safety, and architectural issues.

### 2a. Replace `interface{}` with Type-Safe Bar Types

**Files:** `services/go/internal/engine/pipeline.go`, `signal.go`, `pipeline.go`
**Severity:** 🟡 MAJOR — systemic type-unsafety
**Problem:** `LastBars map[string]interface{}` and `Generate(bars []interface{}, ...)` require runtime type assertions everywhere. A single type mismatch causes a panic.
**Fix:**
- Define `type BarWindow map[string]*Bar`
- Change `Signal.Generate()` signature to `Generate(bars BarWindow, ...)`
- Update all call sites; remove all type assertions
- Add compile-time interface check
**Backend:** Go engine pipeline, signal, scheduler, workflow nodes
**Test:** All existing pipeline tests must pass unchanged

### 2b. Refactor main.go into Dependency Injection

**File:** `services/go/cmd/server/main.go`
**Severity:** 🟡 MAJOR — 232-line monolithic main
**Problem:** All handler initialization, broker creation, DB setup, gRPC connections, mock data seeding, and goroutine launching live in main(). Untestable and fragile.
**Fix:**
- Extract a `Server` struct with constructor `NewServer(cfg *config.Config) (*Server, error)`
- `Server.Start()` starts HTTP + gRPC + health check + mock data
- `Server.Shutdown(ctx)` handles graceful cleanup (close DB pool, stop goroutines, drain WS)
- Move mock ticker goroutine to `DevMode` feature flag
- Wire dependencies explicitly in constructor (no DI framework needed)
**Backend:** Go cmd/server

### 2c. Global SWR Configuration

**File:** `frontend/app/layout.tsx`
**Severity:** 🟡 MAJOR — inconsistent data fetching
**Problem:** Each `useSWR` call uses ad-hoc fetcher with no error handling, no dedup interval, no revalidation strategy. Some have `refreshInterval` (usePositions), most don't.
**Fix:**
- Create `lib/swr-config.ts` with a global `SWRConfig`:
  - `dedupingInterval: 2000`
  - `errorRetryCount: 3`
  - Custom fetcher with error normalization
- Wrap app in `<SWRConfig value={swrConfig}>` in layout.tsx
- Remove duplicate inline `fetcher` definitions from pages
- Add `revalidateOnFocus: false` for financial data (stale revalidation preferred)
**Frontend:** lib/swr-config.ts, app/layout.tsx, hooks/*.ts

### 2d. Fix Dark Mode

**File:** `frontend/app/globals.css:159-187`
**Severity:** 🟡 MAJOR — feature is dead
**Problem:** `.dark` block copies identical values from `:root`. Switching to dark mode changes nothing.
**Fix:**
- Define proper dark palette:
  - `--background: #0A0B0D`
  - `--foreground: #F5F5F5`
  - `--surface-1: #141518`, `--surface-2: #1A1D21`, `--surface-3: #252830`
  - `--border: #2D3038`, `--border-subtle: #1F2228`
  - Adjust `--up`/`--down` for dark readability
  - Keep `[lang="zh"]` overrides consistent with dark mode
**Frontend:** globals.css

### 2e. Fix Tailwind Config Paths

**File:** `frontend/tailwind.config.ts:5`
**Severity:** 🟡 MAJOR — references non-existent directory
**Problem:** `content: ["./index.html", "./src/**/*.{ts,tsx}"]` — `./src/` does not exist; actual source is `./app/` and `./components/`.
**Fix:**
- Change content to `["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts}"]`
- Remove non-existent `./index.html`
- Verify with `npx tailwindcss -i app/globals.css --dry-run` to ensure all classes are detected
**Frontend:** tailwind.config.ts

### 2f. ARIA Accessibility Baseline

**Files:** All frontend pages and components
**Severity:** 🟡 MAJOR — zero accessibility
**Problem:** No `aria-label`, `aria-current`, `role`, keyboard navigation, or skip-to-content link anywhere in the codebase.
**Fix (minimum viable):**
- Sidebar: `<nav aria-label="Main navigation">` + `aria-current="page"` on active link
- Header breadcrumbs: `<nav aria-label="Breadcrumb">` + `aria-current="location"`
- Table headers: add `<caption>` describing the table
- OrderForm Buy/Sell: use `role="radio"` + `aria-checked` instead of `data-active`
- Add hidden skip-to-content link: `<a href="#main-content" className="sr-only focus:not-sr-only">Skip to content</a>`
- Trading symbol search: add `role="combobox"` + `aria-expanded`
**Frontend:** Sidebar.tsx, Header.tsx, OrderForm.tsx, trading/page.tsx

### 2g. Consolidated BFF Proxy Utility

**File:** `frontend/app/api/*/route.ts` (18 nearly identical files)
**Severity:** 🟡 MAJOR — code duplication, no timeout/retry
**Problem:** Every API route file is an identical copy-paste. No request timeout, no retry logic, no AbortSignal propagation.
**Fix:**
- Create `lib/bff-proxy.ts`:
  ```ts
  export async function bffProxy(req: NextRequest, method: string): Promise<NextResponse> {
    const session = await auth()
    const token = (session as any)?.accessToken
    if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    const path = req.nextUrl.pathname.replace('/api/', '/api/v1/')
    const url = `${API_BASE}${path}${req.nextUrl.search}`
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000)
    try {
      const res = await fetch(url, { method, headers: ..., body: ..., signal: controller.signal })
      ...
    } finally { clearTimeout(timeout) }
  }
  ```
- Refactor all 18 route files to one-liners: `export async function GET(req: NextRequest) { return bffProxy(req, 'GET') }`
**Frontend:** lib/bff-proxy.ts, all app/api/*/route.ts

---

## Phase 3: Production-Ready (8 days)

Fixes for observability, testing, data integrity, and user-facing quality.

### 3a. Frontend Test Suite

**Files:** `frontend/__tests__/`
**Severity:** 🟡 MAJOR — 1 existing test
**Problem:** Only `KpiCard.test.tsx` and `utils.test.ts` exist. Zero hook tests, zero store tests, zero integration tests.
**Fix:**
- Add tests for every Zustand store (useUIStore, useWSStore, useOrderFormStore, etc.)
- Add tests for SWR hooks (mock fetch with MSW)
- Add tests for key components: OrderForm, PositionTable, PriceTicker, CandlestickChart
- Add snapshot tests for major page layouts
- Target: 60%+ component coverage
- Run in CI: `npm run test -- --coverage`
**Frontend:** __tests__/ directory
**Test:** `npx vitest run`

### 3b. Structured Logging

**Files:** `services/go/` (all files using `log.Printf`)
**Severity:** 🟡 MAJOR — no observability
**Problem:** Entire Go codebase uses bare `log.Printf`. No log levels, no context propagation, no request tracing.
**Fix:**
- Add `go.uber.org/zap` as dependency
- Create `internal/log/logger.go` with `NewProduction()` / `NewDevelopment()` constructors
- Add request-ID middleware that injects a correlation ID into context
- Replace all `log.Printf` / `log.Fatal` with structured logging
- Add HTTP request logging middleware (method, path, status, duration)
**Backend:** Go internal/log/, cmd/server, all handlers

### 3c. PostgreSQL Migration Framework

**Files:** `services/go/internal/db/timescale.go`
**Severity:** 🟡 MAJOR — no schema versioning
**Problem:** DDL is hardcoded Go strings. No up/down migrations, no version tracking, no rollback.
**Fix:**
- Add `golang-migrate/migrate` as dependency
- Create `migrations/` directory with versioned SQL files: `000001_create_bars.up.sql`, `000001_create_bars.down.sql`, etc.
- Embed migrations into binary with `embed` package
- Run migrations at startup: `migrate.Up(connString, migrationsFS)`
- Keep `InitSchema` as a one-shot for fresh installs
**Backend:** Go internal/db/migrations/

### 3d. Responsive Layout

**Files:** `frontend/components/layout/Sidebar.tsx`, `SidebarLayout.tsx`, `Header.tsx`
**Severity:** 🟡 MAJOR — mobile unusable
**Problem:** Sidebar is `fixed` at 240px. No collapse toggle. No responsive breakpoints anywhere.
**Fix:**
- Add hamburger button to Header (visible `< lg` breakpoint)
- Sidebar: `lg:translate-x-0` with `-translate-x-full` when collapsed on mobile
- Add overlay backdrop when sidebar is open on mobile
- Dashboard KPI grid: `grid-cols-5 lg:grid-cols-5 md:grid-cols-3 sm:grid-cols-2`
- Trading layout: `grid-cols-12 lg:grid-cols-12 md:grid-cols-1` (stack columns on mobile)
- Update `useUIStore` to manage sidebar open state + collapse
**Frontend:** Sidebar.tsx, SidebarLayout.tsx, Header.tsx, trading/page.tsx, page.tsx, useUIStore

### 3e. PostgreSQL User Storage (replace in-memory)

**Files:** `services/go/internal/api/handler/auth.go`
**Severity:** 🟡 MAJOR — users lost on restart
**Problem:** `type UserStore struct { mu sync.RWMutex; users map[string]*User }` — all registrations vanish on restart.
**Fix:**
- Create `users` table: `id SERIAL, username VARCHAR UNIQUE, password_hash VARCHAR, salt VARCHAR, email VARCHAR, created_at TIMESTAMPTZ`
- Implement `UserRepository` interface with PG-backed methods
- Add admin seed user on first startup
- Keep in-memory store as dev fallback only
**Backend:** Go auth handler, db migrations
**Test:** Registration persists across server restart

### 3f. Quantitative Fixes

**Composite Engine in Backtest:**
- `services/go/internal/api/handler/backtest.go:113` — replace `factory.ForSymbol(req.Symbols[0])` with `engine.NewCompositeEngine(factory)` for multi-symbol backtests

**Risk Config Wiring:**
- `services/go/internal/api/handler/backtest.go:120` — accept `risk_config` in `BacktestRequest`, pass to `engine.NewRiskManager(config)` instead of empty `RiskConfig{}`

**Frequency-Aware Metrics (extend 1d):**
- `services/go/internal/engine/backtest.go` — apply frequency-aware annualization to ALL metrics (Sharpe, Sortino, Calmar)

### 3g. User Guidance Improvements

**Skeleton Loading States:**
- Replace all plain-text loading states in list pages with `<SkeletonTable>` (component already exists, just not used)
- Pages: orders, backtest, paper-trading, scheduler, factors, signals

**Empty State Guidance:**
- Add actionable messages to empty states: "No backtests yet. Create your first backtest." with a link button
- Pages: backtest, paper-trading, signals, scheduler, factors, screener, notifications

**Confirmation Dialogs:**
- Add `<Dialog>` confirmation for all destructive actions (delete paper trading run, cancel order, close position, delete backtest, delete scheduler job, archive ML model)
- Already done for ML archive and scheduler delete

---

## Phase 4: Polish (5 days, lower priority)

### 4a. Financial Chart Enhancements

- Add MA5/MA10/MA20/MA60 overlay toggles to CandlestickChart
- Add MACD/RSI indicator panels below chart
- Add crosshair/cursor tracking to EquityChart and CandlestickChart
- Implement real OrderBook depth visualization (horizontal bars for bid/ask levels)
- Fix all chart hardcoded colors → use CSS variables consistently

### 4b. Performance Optimization

- Add React.memo to PositionTable, OrderBook, ScreenerGrid
- Implement virtual scrolling for large lists (react-window or @tanstack/virtual)
- Add request deduplication in SWR config
- Code-split heavy pages (StrategyLab with Monaco, Workflow with xyflow)

### 4c. Security Hardening

- Add rate limiting to `/api/auth/login` (e.g., 5 attempts per minute per IP)
- Add account lockout after N failed attempts
- Implement password strength validation on registration (already in frontend, add backend)
- Add CSRF protection to all mutation endpoints
- Security audit of all user-input sanitization

### 4d. Documentation

- Generate OpenAPI 3.0 spec from Go router (use swaggo/gin-swagger)
- Write data dictionary for TimescaleDB tables
- Add architecture decision records (ADRs) for key design choices
- Create deployment guide for bare-metal Linux production

### 4e. CI/CD Pipeline

- Add GitHub Actions workflow:
  - Go: `go vet`, `go test ./...`, `golangci-lint run`
  - Python: `pytest`, `ruff check`, `mypy`
  - Frontend: `tsc --noEmit`, `vitest run`, `next build`
- Add Docker multi-stage builds
- Add pre-commit hooks (husky for frontend, lefthook for Go/Python)

---

## 5. Dependency Graph

```
Phase 1 (Critical Fixes)
  ├─ 1a JWT Secret ───────────── independent
  ├─ 1b Signal Noop ──────────── depends on gRPC connection
  ├─ 1c Day Loss Limit ───────── independent
  ├─ 1d Sharpe Annualization ─── independent
  ├─ 1e Candlestick Chart ────── independent
  └─ 1f gRPC TLS ─────────────── independent
       ↓
Phase 2 (Harden)
  ├─ 2a Type Safety ──────────── independent (refactors pipeline)
  ├─ 2b main.go Refactor ─────── depends on 2a (type changes)
  ├─ 2c SWR Config ───────────── independent
  ├─ 2d Dark Mode ────────────── independent
  ├─ 2e Tailwind Config ──────── independent
  ├─ 2f ARIA Baseline ────────── independent
  └─ 2g BFF Proxy ────────────── independent
       ↓
Phase 3 (Production)
  ├─ 3a Frontend Tests ───────── independent
  ├─ 3b Structured Logging ───── depends on 2b (main.go refactor)
  ├─ 3c Migrations ───────────── independent
  ├─ 3d Responsive Layout ────── independent
  ├─ 3e User Storage ─────────── depends on 3c (migration framework)
  ├─ 3f Quant Fixes ──────────── depends on 1d, 1c
  └─ 3g User Guidance ────────── independent
       ↓
Phase 4 (Polish)
  └─ All items independent
```

## 6. Estimated Timeline

| Phase | Work Days | Cumulative |
|-------|-----------|------------|
| Phase 1 — Critical Fixes | 3 | 3 |
| Phase 2 — Harden | 5 | 8 |
| Phase 3 — Production-Ready | 8 | 16 |
| Phase 4 — Polish | 5 | 21 |

**Total: ~21 working days** to go from B- to A- production readiness.

## 7. Success Criteria

- [ ] All 5 critical issues resolved and verified
- [ ] Go test suite: 0 failures
- [ ] Python test suite: 0 failures
- [ ] Frontend TypeScript: 0 errors, 0 warnings
- [ ] Frontend test coverage: >60%
- [ ] Dark mode: visually verified
- [ ] Responsive layout: functional on mobile/tablet/desktop
- [ ] JWT secret: environment-sourced, rotated
- [ ] gRPC: TLS enabled
- [ ] CandlestickChart: renders real OHLC bars
- [ ] Backtest with signals: generates actual trades
- [ ] Structured logging: correlation IDs in all request logs
- [ ] DB migrations: versioned, up/down tested
