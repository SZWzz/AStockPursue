# Code Review Remediation — Phase 2 Spec & Plan

**Date**: 2026-06-22 | **Status**: Executing
**Scope**: Remaining Important/Minor issues from fullstack review

---

## Group A: Go Engine Correctness (5 issues)

### A1: Multi-symbol backtest — process all symbols at same timestamp

**File**: `services/go/internal/engine/backtest.go:119`
**Current**: `break` after matching first symbol. Only one asset processes per timestamp slice.
**Fix**: Remove `break`, let all symbols with bars at this timestamp process.

### A2: Record partial position reductions as trades

**File**: `services/go/internal/engine/backtest.go:164`
**Current**: TradeRecord only logged on size increase (buy/add). Partial sells ignored.
**Fix**: Generate TradeRecord for any size change (increase or decrease).

### A3: Pipeline cash check use slippage-adjusted price

**File**: `services/go/internal/engine/pipeline.go:131`
**Current**: Cash availability checked with `bar.Close`. Execution uses post-slippage price. Mismatch.
**Fix**: Apply engine slippage/commission to price BEFORE cash check.

### A4: LiveTrading Stop/Start race

**File**: `services/go/internal/engine/live.go:130`
**Current**: `stopCh` overwritten with `make(chan struct{})` while old goroutines still reading from closed channel.
**Fix**: Guard `stopCh` lifecycle with mutex. Only create new channel when previous goroutines confirmed stopped.

### A5: MemoryCache FIFO ordering

**File**: `services/go/internal/market/cache.go:55`
**Current**: `SetBars` deletes oldest 20% by insertion order, but keys don't reorder on update. Frequently-accessed keys evicted early.
**Fix**: Move updated key to end of order list (simple LRU approximation).

---

## Group B: Frontend Architecture (6 issues)

### B1: Unified SWR fetcher — stop overriding per-hook

**Files**: `hooks/usePositions.ts`, `useOrders.ts`, `useBacktests.ts`, `useBacktest.ts`, `useMarketData.ts`, `useKlines.ts`, `usePaperAccounts.ts`, `useScheduler.ts`, `useSystemStatus.ts`, `useFactors.ts`, `useSettings.ts`
**Current**: Each hook defines `const fetcher = (url) => fetch(url).then(r => r.json())`, bypassing global SWR config.
**Fix**: Remove local `fetcher` from all hooks. Rely on global `SWRConfig` from `swr-config.tsx`.

### B2: WebSocket exponential backoff

**File**: `lib/ws.ts:48`
**Current**: `setTimeout(() => this.connect(this.token!), 3000)` — fixed 3s retry.
**Fix**: Implement exponential backoff: `min(baseDelay * 2^attempt, maxDelay)` starting at 1s, max 30s.

### B3: Symbol catalog from API

**File**: `app/trading/page.tsx:25-30`
**Current**: 4-market symbol list hardcoded in component.
**Fix**: Replace with API fetch to `/api/market/symbols`. Fallback to empty array on error.

### B4: Remove unused themeStore state

**File**: `stores/themeStore.ts`
**Current**: `layoutPreset` and `fontSize` are stored but never consumed by any component.
**Fix**: Remove dead fields, keep only active `theme` toggle.

### B5: Fix i18n hardcoded English fallbacks

**Files**: `app/workflow/page.tsx:181`, `components/financial/*`, `app/settings/page.tsx`
**Current**: `t('key') || 'English fallback'` pattern defeats i18n — English always shows as fallback regardless of locale.
**Fix**: Remove `|| '...'` fallback text. If key missing, use `t('key')` which falls back to key name (visible indication of missing translation).

### B6: Move middleware error map to lib/

**File**: `middleware.ts:13-21`
**Current**: `ERROR_MAP` and `translateError` defined in middleware but unrelated to routing.
**Fix**: Extract to `lib/errors.ts`, import in middleware.

---

## Group C: Cleanup (Python + Go + Frontend small fixes)

### C1: Python dead code cleanup

**File**: `services/python/src/workflow/workflow_engine.py:400`
**Fix**: Remove duplicate `except asyncio.TimeoutError` (already caught at line 390).

**File**: `services/python/src/backtest_tool.py:65`
**Fix**: `s.split(",")` → `[x.strip() for x in s.split(",")]` to handle spaces.

### C2: Go minor fixes

**File**: `services/go/internal/db/timescale.go:216`
**Fix**: Replace `fmt.Sprintf(" LIMIT %d", q.Limit)` with parameterized `$N` in query string and add param to args slice.

**File**: `services/go/internal/grpc/connmgr.go:86`
**Fix**: Return cancel func from `StartHealthCheck`, store in `ConnManager`, call on `Close()`.

### C3: Frontend minor fixes

**File**: `hooks/index.ts` — add `export { } from` per hook instead of barrel re-export that forces all hooks to load together. Or simply remove barrel file and have consumers import directly.

**File**: `lib/api-client.ts` — remove unused `_token` module variable and `setApiToken()` function. Confirm no consumers before deleting.

**File**: `lib/bff-proxy.ts` — add max body size check (e.g., 10MB) to prevent large payload proxying.

---

## Execution

Three parallel agents dispatched: Group A (Go), Group B (Frontend), Group C (Cleanup). No cross-group dependencies.
