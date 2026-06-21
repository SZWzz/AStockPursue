# Frontend Pages Audit & Remediatoin

**Date:** 2026-06-21
**Status:** Draft

## Audit Methodology

All 29 frontend page files + 18 API route handlers reviewed. Each page checked against:
- What the backend actually provides vs what the frontend displays
- Loading / error / empty state coverage
- i18n coverage
- Real-time data integration
- User interaction completeness (CRUD, filters, actions, navigation)

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 3 | Broken/empty — data fetched but not rendered, mock data used, misleading form |
| **MAJOR** | 52 | Missing key features across all page categories |
| **MINOR** | 34 | Missing i18n, no pagination, no skeletons, hardcoded strings |

---

## CRITICAL Fixes (3 items)

### C1. Signals Page — Data Fetched But Not Rendered

**File:** `frontend/app/signals/page.tsx:37-42`

The page fetches `/api/signals` but renders an empty container when data arrives. No signal table, no columns, no actions.

**Fix:** Implement full signal table with: signal type, symbol, direction (buy/sell), strength (0-100), timestamp, source, status (new/acknowledged/acted/expired), action buttons (acknowledge, dismiss, create order from signal).

**Backend needed:** `PUT /api/v1/signals/:id/ack`, `PUT /api/v1/signals/:id/dismiss`

### C2. Dashboard — EquityChart Uses Hardcoded Mock Data

**File:** `frontend/app/page.tsx:196-200`

The equity chart renders `[{ time: '9:30', equity: 100000 }]` regardless of actual portfolio data. The `/api/portfolio` response likely includes an `equity_curve` array that should drive this chart.

**Fix:** Use real equity curve data from portfolio API response. If not available in the API, add `equity_curve` field to `/api/v1/portfolio` response.

### C3. Backtest New Form — No Actual Strategy Selection

**File:** `frontend/app/backtest/new/page.tsx`

The `name` field is labeled as `t('backtest.strategy')` but is just a free-text name input. User has no way to select from existing strategies, engine types, or signal templates.

**Fix:** Add strategy selector (dropdown or searchable list of saved strategies), engine type selector (ChinaA / Crypto / GlobalEquity / etc.), and signal name input.

---

## MAJOR Issues by Page

### Dashboard (`page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| D1 | Portfolio detail fields missing | Add cards for: total PnL, daily PnL, unrealized PnL, position count, margin used |
| D2 | Northbound flow hardcoded to `SH000001` | Add index selector for northbound flow |

### Trading (`trading/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| T1 | Symbol selector is plain text input | Add autocomplete with symbol search (`/api/v1/market/search`) |
| T2 | No order submission feedback | Handle `onSuccess`/`onError` callbacks from OrderForm |
| T3 | Default symbol hardcoded `'000001.SZ'` | Use user's default_symbols from settings |

### Orders (`trading/orders/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| OR1 | No order cancellation | Add "Cancel" button per open order → `DELETE /api/v1/trading/orders/{id}` |
| OR2 | No filter/search | Add filters: status (open/filled/cancelled), symbol search, date range |
| OR3 | No pagination | Add paginated table with page size selector |

### Positions (`trading/positions/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| PO1 | No close-position actions | Add "Close" button per position |
| PO2 | No aggregate stats | Add total exposure, buying power, concentration %, sector distribution |

### Paper Trading (`paper-trading/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| PT1 | Table header label mismatch | Fix: header says "Symbol" but renders `acct.name` |
| PT2 | Create uses hardcoded values | Add create form with name, initial capital, strategy inputs |
| PT3 | No delete/archive action | Add delete button per row |

### Paper Trading Detail (`paper-trading/[id]/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| PD1 | Start/Stop not i18n | Wrap in `t()` |
| PD2 | No config modification | Add edit capability for capital, strategy params |
| PD3 | No order history | Add order history tab alongside trade timeline |
| PD4 | No auto-refresh | Call `mutate()` after start/stop actions |

### Backtest List (`backtest/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| BL1 | No search/filter | Add name search, date range, strategy filter, min/max return filter |

### Backtest New (`backtest/new/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| BN1 | Missing commission/slippage | Add commission rate, slippage model selector |
| BN2 | Missing engine type | Add engine type selector (ChinaA/Crypto/GlobalEquity/etc.) |
| BN3 | Missing form validation | Validate start < end, symbol exists, capital > 0 |
| BN4 | Frequency limited | Add all frequencies: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w |

### Backtest Detail (`backtest/[id]/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| BD1 | Missing key metrics | Add Sortino, Calmar, volatility, alpha, beta, profit factor |
| BD2 | No trade table | Add sortable, filterable trade log table |
| BD3 | No export | Add CSV/PDF export button |

### Factors List (`factors/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| FL1 | Search placeholder not i18n | Use `t()` |
| FL2 | Column headers not i18n | Use `t()` for Name, Formula, IC, Sharpe |
| FL3 | Search has no debounce | Add 300ms debounce to search input |

### Factor Detail (`factors/[id]/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| FD1 | KPI labels not i18n | Use `t()` for IC, IR, Sharpe, Max DD, Turnover |
| FD2 | Section titles not i18n | Use `t()` for Formula, IC History |
| FD3 | No IC history chart label i18n | Use `t()` |
| FD4 | KPI format inconsistency | Normalize decimal vs percentage display |

### Workflow List (`workflow/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| WL1 | Import button is no-op | Implement file picker for JSON workflow import |
| WL2 | Create has no user input | Add create dialog with name and template selector |
| WL3 | Column headers not i18n | Use `t()` |

### Workflow Editor (`workflow/[id]/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| WE1 | No workflow data loading | Fetch workflow by ID on mount |
| WE2 | No save button | Add save button → `PUT /api/v1/workflow/{id}` |
| WE3 | Node config panel too basic | Add per-node-type configuration fields |

### Agent Chat (`agent/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| AC1 | No streaming response | Implement SSE/streaming for token-by-token display |
| AC2 | No conversation history | Persist messages to backend, support thread selection |
| AC3 | No skill selection | Add skill selector panel (89 skill packs available) |
| AC4 | Send button not i18n | Use `t()` |
| AC5 | Welcome message hardcoded | Use `t()` |

### Strategy Lab (`strategy-lab/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| SL1 | Title not i18n | Use `t()` |
| SL2 | No code validation | Add linter/syntax check before submit |
| SL3 | No strategy save/load | Add save current → POST, load existing → GET |
| SL4 | ChartPanel labels not i18n | Use `t()` |
| SL5 | BacktestPanel labels not i18n | Use `t()` |

### Research (`research/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| RS1 | Sentiment labels not i18n | Use `t()` |
| RS2 | News has no date range filter | Add date range + pagination |
| RS3 | Fetch always enabled | Disable when symbol is empty |

### ML Models (`ml/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| ML1 | No train button | Add "Train" button → `POST /api/v1/ml/models/{id}/train` |
| ML2 | No model comparison | Add multi-select comparison view |
| ML3 | Archive uses `confirm()` | Replace with modal dialog |

### Market Overview (`market/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| MK1 | No symbol search | Add search bar that navigates to `/market/{symbol}` |
| MK2 | No sector breakdown | Add sector filter and sector performance table |
| MK3 | Rows not clickable | Make rows navigate to `/market/{symbol}` |

### Symbol Detail (`market/[symbol]/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| SD1 | Order book hardcoded empty | Subscribe to WS order book channel for the symbol |
| SD2 | No technical indicators | Add volume profile, MA overlay, RSI/MACD toggle |
| SD3 | No company fundamentals | Add fundamentals tab (P/E, P/B, ROE, revenue, etc.) |
| SD4 | Limited frequencies | Add monthly, tick-level |

### Screener (`screener/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| SR1 | Limited filter fields | Add market cap, dividend yield, beta, sector, industry |
| SR2 | No AND/OR logic | Add condition grouping with AND/OR toggle |
| SR3 | Score/rank modes show same UI | Adapt UI per mode |
| SR4 | Labels not i18n | Use `t()` |
| SR5 | Presets lost on refresh | Persist to backend → `GET/POST /api/v1/screener/presets` |

### Signals (`signals/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| SG1 | CRITICAL: No rendering | See C1 |
| SG2 | No actions | Add acknowledge, dismiss, create-order actions |
| SG3 | Chinese fallback text | Use `t()` |

### Broker (`broker/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| BR1 | No connect/disconnect | Add connect/disconnect button per broker |
| BR2 | No credential config | Add API key/secret configuration inline or dialog |
| BR3 | No refresh button | Add manual refresh button |

### Scheduler (`scheduler/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| SC1 | No add job | Add create job dialog (name, type, cron, config) |
| SC2 | No schedule description | Parse cron → human-readable text |
| SC3 | No job history | Add last-run duration, execution log |
| SC4 | Start/Pause/Delete not i18n | Use `t()` |

### Notifications (`notifications/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| NT1 | No "Mark All Read" | Add bulk action button |
| NT2 | Time labels hardcoded English | Use library like `date-fns` or `intl` |
| NT3 | No WS real-time push | Subscribe to WS notification channel |

### Analysis — Drawdown (`analysis/drawdown/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| AD1 | No drawdown stats table | Add max DD duration, avg DD, worst periods list |
| AD2 | "Run" not i18n | Use `t()` |

### Analysis — Correlation (`analysis/correlation/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| AC1 | No timeframe selector | Add lookback period dropdown |
| AC2 | "Run" not i18n | Use `t()` |

### Analysis — Stress Test (`analysis/stress-test/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| AS1 | Scenarios hardcoded client-side | Fetch from backend → `GET /api/v1/analysis/scenarios` |
| AS2 | No portfolio subset selection | Add position multi-select |
| AS3 | "Run" not i18n | Use `t()` |

### Login (`login/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| LI1 | "Invalid credentials" not i18n | Use `t()` |

### Register (`register/page.tsx`)

| # | Issue | Fix |
|---|-------|-----|
| RE1 | Error messages not i18n | Use `t()` for all error states |
| RE2 | No password strength | Add min length (8), require mixed case/digit feedback |

---

## Cross-Cutting Issues

### X1. i18n Coverage

**Scope:** All pages use `useTranslations()` hook but ~40% of visible strings remain hardcoded English.

**Fix:** Audit every page's JSX text nodes and wrap in `t()`. Add missing keys to both `en.json` and `zh.json`.

Priority pages (most violations): `factors/[id]`, `screener`, `scheduler`, `strategy-lab`, `analysis/*`, `login`, `register`.

### X2. Pagination

**Scope:** 0 of 29 pages implement pagination for list views. With live data these will render hundreds/thousands of rows, causing performance degradation and unusable UI.

**Fix pattern** (apply to all list pages):

```
┌─ Search ───────────────┬── Page: 1 of 12 ─┬─ [<] [>] ─┐
├──────────────────────────────────────────────────────────┤
│ table body...                                            │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ Showing 1-20 of 231 total                      20 per page ██│
└──────────────────────────────────────────────────────────┘
```

Pages needing pagination: orders, backtests, paper accounts, workflows, factors, scheduler, notifications, signals, research news.

### X3. Loading Skeletons

**Scope:** All pages show `<div className="... text-center py-12">{t('common.loading')}</div>` — a single line of text.

**Fix:** Replace with skeleton components matching the page layout. For tables: skeleton rows with shimmer. For KPI cards: skeleton card blocks. For charts: skeleton rectangle.

### X4. WebSocket Real-Time Updates

**Scope:** Only `trading/page.tsx` and `dashboard/page.tsx` subscribe to WS. Pages that benefit from live data don't.

**Fix:** Extend WS subscriptions to:
- `market/[symbol]` — order book depth, trades
- `trading/orders` — order status changes
- `trading/positions` — P&L updates
- `notifications` — real-time push
- `paper-trading/[id]` — equity/PnL updates

### X5. Error Handling Consistency

**Scope:** Error states are handled per-page with inconsistent patterns. Some use `toast.error()`, some show inline error, some show nothing.

**Pattern:** All forms show inline error + toast. All data fetches show inline error with retry button. All mutations show toast with result.

### X6. Form Validation

**Scope:** Most forms use only HTML `required` attribute. No client-side validation for: date ranges, number ranges, password strength, symbol format.

**Pattern:** Client-side validation with inline error messages under each field. Validate on blur + on submit.

### X7. BFF Proxy Layer

**Scope:** All 18 API route handlers are identical generic proxies — no request transformation, response normalization, error handling, or caching.

**Fix (optional enhancement):** Add a shared proxy utility that normalizes Go backend errors (HTTP 500 → `{ error: message }`), adds request timeouts, and handles auth token injection consistently.

---

## Implementation Priority

### Phase 1 — CRITICAL (3 items)
| Priority | Item | Est. |
|----------|------|------|
| P0 | C1: Signals page renders data | 1d |
| P0 | C2: Dashboard real equity chart | 0.5d |
| P0 | C3: Backtest new real strategy selection | 1d |

### Phase 2 — Trading Pages (7 items)
| Priority | Item | Est. |
|----------|------|------|
| P1 | T1-T3: Trading page improvements | 1d |
| P1 | OR1-OR3: Orders cancellation + filters | 1.5d |
| P1 | PO1-PO2: Positions close + stats | 1d |
| P1 | PT1-PT3: Paper trading CRUD | 1d |
| P1 | PD1-PD4: Paper detail improvements | 1d |

### Phase 3 — Data Analysis Pages (8 items)
| Priority | Item | Est. |
|----------|------|------|
| P1 | BD1-BD3: Backtest detail metrics | 1d |
| P1 | AD1, AC1, AS1-AS2: Analysis pages | 1.5d |
| P2 | FL1-FL3, FD1-FD4: Factors page | 1d |
| P2 | MK1-MK3: Market overview | 1d |
| P2 | SD1-SD4: Symbol detail | 2d |
| P2 | SR1-SR5: Screener | 2d |

### Phase 4 — System Pages (6 items)
| Priority | Item | Est. |
|----------|------|------|
| P2 | SC1-SC4: Scheduler | 1.5d |
| P2 | NT1-NT3: Notifications | 1d |
| P2 | BR1-BR3: Broker | 1d |
| P2 | WL1-WL3, WE1-WE3: Workflow | 2d |

### Phase 5 — AI/Coding Pages (5 items)
| Priority | Item | Est. |
|----------|------|------|
| P2 | AC1-AC5: Agent chat | 2d |
| P2 | SL1-SL5: Strategy lab | 1.5d |
| P2 | RS1-RS3: Research | 1d |
| P2 | ML1-ML3: ML models | 1d |

### Phase 6 — Cross-Cutting (5 items)
| Priority | Item | Est. |
|----------|------|------|
| P3 | X1: Full i18n audit | 2d |
| P3 | X2: Pagination for all lists | 3d |
| P3 | X3: Loading skeletons | 2d |
| P3 | X4: WebSocket expansion | 2d |
| P3 | X6: Form validation | 2d |

### Phase 7 — Polish (2 items)
| Priority | Item | Est. |
|----------|------|------|
| P3 | LI1, RE1-RE2: Auth page polish | 0.5d |
| P3 | X5: Error handling consistency | 1d |

---

## Backend Dependencies

New/modified Go endpoints needed:

| Endpoint | For Issue | Purpose |
|----------|-----------|---------|
| `PUT /api/v1/signals/:id/ack` | C1 | Acknowledge signal |
| `PUT /api/v1/signals/:id/dismiss` | C1 | Dismiss signal |
| `GET/POST /api/v1/strategies` | C3, SL3 | Strategy CRUD |
| `PUT /api/v1/strategies/:id` | C3, SL3 | Save strategy |
| `POST /api/v1/ml/models/:id/train` | ML1 | Trigger training |
| `GET/POST /api/v1/screener/presets` | SR5 | Screener preset persistence |
| `GET /api/v1/analysis/scenarios` | AS1 | Dynamic stress test scenarios |
| WebSocket: order book channel | SD1 | Real-time depth |
| WebSocket: notification channel | NT3 | Real-time notification push |

Total estimated effort: **~35-40 days** for full remediation across all phases.
