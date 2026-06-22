# Code Review Remediation — Phase 1 Spec

**Date**: 2026-06-22
**Status**: Approved
**Scope**: All Critical issues + top-priority Important issues from the 2026-06-22 fullstack review

---

## Overview

Fix the 12 highest-priority issues discovered in the fullstack code review of AStockPursue v2026.6.20. The fixes span three independent layers: Go Core, Python Research, and Next.js Frontend. They are parallelizable with no cross-layer dependencies.

---

## Go Core (5 issues)

### C1: API Secret Encryption

**File**: `services/go/internal/api/handler/broker.go:155`

**Current behavior**: Broker credentials (API Key + Secret) are stored as plaintext JSON in `user_settings.settings` JSONB column, constructed via `fmt.Sprintf` string formatting. Special characters in keys/secrets break the JSON.

**Fix**:
1. Create `services/go/internal/crypto/crypto.go`:
   - `Encrypt(plaintext string) (string, error)` — AES-256-GCM, key from env `ENCRYPTION_KEY`
   - `Decrypt(ciphertext string) (string, error)` — reverse
   - `GenerateKey() string` — for setup.sh to generate and persist
2. Rewrite `broker.go` save: build structured map, encrypt `api_secret` field, `json.Marshal` the whole thing
3. Rewrite `broker.go` read: `json.Unmarshal`, decrypt `api_secret`, return to caller
4. Add to `config/config.go`: load `ENCRYPTION_KEY` env var, error if empty

### C2: User Isolation

**File**: `services/go/internal/api/handler/settings.go:144`

**Current behavior**: `getUserID(c *gin.Context)` returns `1` for all authenticated users. All settings/credentials shared.

**Fix**:
1. Parse `user_id` from JWT claims (`sub` field) in `getUserID`
2. JWT middleware must store user_id in gin context during auth
3. If no user_id in context (unlikely but defensive), return error instead of default `1`
4. Audit all handlers for hardcoded `user_id = 1` and replace with `h.getUserID(c)`

### C3: Auth Default-Deny

**File**: `services/go/internal/api/middleware/auth.go:39`

**Current behavior**: When `API_KEY` env var is not set, ALL requests pass without authentication.

**Fix**:
1. Split auth into two strategies: API Key mode and JWT mode
2. API Key mode: require `Authorization: Bearer <API_KEY>` header
3. JWT mode: require valid JWT in `Authorization: Bearer <token>`
4. Neither provided → `401 Unauthorized`. No fallthrough.
5. Remove the `// No auth configured — allow all` branch entirely

### I1: Pipeline Instance Per Run

**File**: `services/go/cmd/server/main.go:91`

**Current behavior**: One `Pipeline` instance created at startup, shared between live trading and backtests. State cross-contamination risk.

**Fix**:
1. Extract `NewPipeline(portfolio, signalAdapter, riskManager, oms)` factory function in `engine/pipeline.go`
2. `main.go` creates a pipeline for live trading via factory
3. `BacktestRunner.Run()` creates its own pipeline instance at the start of each run
4. Pipeline is garbage-collected when backtest completes

### I2: Backtest Date Validation

**Files**: `services/go/internal/api/handler/scheduler.go:373,435`

**Current behavior**: `time.Parse("2006-01-02", job.StartDate)` errors are silently discarded with `_`, leading to zero-value time and potential OOM.

**Fix**:
1. Capture the error, return `400 Bad Request` with message `"invalid date: expected YYYY-MM-DD"`
2. Apply same fix to both `runOnce` and `executeRun` functions

---

## Python Research (2 issues)

### I1: CPU_POOL Race Condition

**File**: `services/python/src/workflow/workflow_engine.py:34-45`

**Current behavior**: `_CPU_POOL` module-level variable assigned outside the `async with` lock, allowing duplicate `ProcessPoolExecutor` creation under ASGI multi-worker.

**Fix**:
1. Move `_CPU_POOL = ...` assignment inside the `async with _CPU_POOL_LOCK` block
2. Add double-check: after acquiring lock, re-check `if _CPU_POOL is None` before creating

### I2: gRPC serve() Return Type

**File**: `services/python/src/grpc/server.py:148,199`

**Current behavior**: `serve()` returns a plain 7-tuple; `__main__` discards all but `server` with `*_`. Callers cannot access service implementations.

**Fix**:
1. Define a dataclass `GrpcServerHandles` with named fields for each servicer
2. Return an instance of it from `serve()`
3. Update `__main__` to destructure by name

---

## Next.js Frontend (5 issues)

### C1: PnL Display Bug

**File**: `frontend/components/financial/PositionTable.tsx:167,222`

**Current behavior**: `formatPercent(Math.abs(pos.pnl_pct || 0))` forces absolute value. Negative PnL percentages display as positive numbers. The `▼` indicator is correct but the number contradicts it.

**Fix**:
1. Remove `Math.abs` — pass raw `pos.pnl_pct` to `formatPercent`
2. Verify `formatPercent` handles negative values correctly (adds `-` prefix)
3. Keep the `▲`/`▼` direction indicator as-is (it was already correct)

### C2: Dashboard Zero-Division Guard

**File**: `frontend/app/page.tsx:55`

**Current behavior**: `(portfolio.total_value - portfolio.cash) / portfolio.cash * 100` produces `Infinity` or `NaN` when `cash === 0`.

**Fix**:
1. Guard: `portfolio.cash > 0 ? ((portfolio.total_value - portfolio.cash) / portfolio.cash * 100) : 0`
2. Optionally display "N/A" text instead of "0%" when cash is zero (clearer UX)

### C3: BFF Proxy Error Handling

**File**: `frontend/lib/bff-proxy.ts:15-22`

**Current behavior**: `fetch()` in the BFF proxy has no try-catch. Network errors (timeout, DNS failure, connection refused) propagate as opaque 500 errors.

**Fix**:
1. Wrap `fetch()` in try-catch
2. On network error: return `NextResponse.json({ error: 'Backend unavailable', code: 'BACKEND_UNREACHABLE' }, { status: 502 })`
3. On non-2xx response with non-JSON body: return a structured error with the upstream status code
4. Keep the 15s timeout and AbortController logic

### C4: Settings Partial Save

**File**: `frontend/app/settings/page.tsx:186-206`

**Current behavior**: `saveSection` always PUTs the entire settings object, regardless of which section changed. Concurrent edits to other sections are overwritten.

**Fix**:
1. If Go backend supports section-level endpoints: change to `PUT /api/settings/{section}` per tab
2. If Go backend currently only supports full PUT: submit only the current section's fields (merge with empty defaults for other sections? No — better to read-then-save to avoid overwrites)
3. Minimal safe fix: keep full PUT but add a read-before-write: re-fetch settings right before save, merge only the changed section, then PUT

### C5: JWT Type Safety

**File**: `frontend/lib/auth.config.ts:20-22`, `frontend/lib/auth-client.ts:11`

**Current behavior**: `(user as any).accessToken` and `(session as any)?.accessToken` bypass TypeScript.

**Fix**:
1. Declare module augmentation for `next-auth`:
   ```ts
   declare module "next-auth" {
     interface User { accessToken?: string }
     interface Session { accessToken?: string }
   }
   declare module "next-auth/jwt" {
     interface JWT { accessToken?: string }
   }
   ```
2. Remove all `as any` casts
3. Add a `types/next-auth.d.ts` file for the declarations

---

## Acceptance Criteria

Each fix must:
1. Compile / pass type-check without errors
2. Not break existing tests
3. Include a focused test where feasible (esp. crypto, auth, date validation)
4. Not introduce new lint warnings

## Dependencies

**None between layers.** Go, Python, and Frontend fixes can be implemented, tested, and deployed independently. Within Go, crypto (C1) should land before broker rewrite, but the order within the Go batch is natural (crypto first, then broker, then settings/date/auth/pipeline).

## Out of Scope (deferred to Phase 2)

- Go: multi-symbol backtest fix (backtest.go:119 break), trade record completeness, LiveTrading stop/start race, MemoryCache FIFO, SQL LIMIT formatting, health check cleanup, Futu reconnect lock
- Python: duplicate TimeoutError catch, backtest comma-split, mcp loader caching, eval() context, sandbox except, token estimation, DB retry duplication
- Frontend: SWR hook fetcher override, JWT refresh, SSR/server components, symbol catalog, barrel exports, chart library consolidation, Monaco+Codemirror dedup, i18n hardcoded fallbacks, persist middleware versioning
