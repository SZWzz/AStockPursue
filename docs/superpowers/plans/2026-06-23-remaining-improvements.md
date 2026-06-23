# Remaining Improvements Plan

## Global Constraints
- Go: `go build ./... && go test ./... -race -count=1` 零回归
- Python: `pytest tests/ -v` 零回归
- Frontend: `pnpm build` 零错误, `pnpm test` 172+ 无回归

---

### A1 — rank_ic vectorize

**File:** `services/python/src/factors/mining/fitness.py`

Replace per-row spearmanr loop with `corrwith(method="spearman")`. `python -m pytest tests/test_factor_kb.py -v`. Commit.

### A2 — sandbox cleanup

**File:** `services/python/src/factors/mining/sandbox_pandas.py`

Remove `_PD_SERIES_WHITELIST` + `wrap_panel()` dead code, fix duplicate `"sign"` in `_NP_WHITELIST`. `python -m pytest tests/test_sandbox.py -v`. Commit.

### A3 — futu getFloat

**File:** `services/go/internal/broker/futu.go`

`getFloat` → `(float64, error)`, update callers. `go test ./internal/broker/ -v`. Commit.

### A4 — ws drop warning

**File:** `services/go/internal/api/ws.go`

Add `log.Printf` in default case. `go build ./...`. Commit.

### B1 — security endpoint tests

**Files:** `services/go/internal/api/handler/auth_test.go`, `broker_test.go`(new)

AdminSetup + RevealCredentials rate-limit + RotateCredentials. `go test ./internal/api/handler/ -v`. Commit.

### B2 — frontend RSC migration

**Files:** `app/market/page.tsx`, `app/backtest/page.tsx`, `app/trading/page.tsx`

Wrap in Suspense + extract client content. `pnpm build && pnpm test`. Commit.

### B3 — remaining any cleanup

**Files:** Search `: any` in components/

Replace in TradeTimeline, PriceTicker, IndexTickerBar, CodeEditor. `pnpm build`. Commit.

### C1 — workflow/research types

**Files:** `workflow/node.go`, `research/service.go`

Define typed interfaces. `go build ./... && go test ./internal/workflow/ ./internal/research/`. Commit.

### C2 — Playwright E2E

**Files:** `frontend/e2e/` (new)

3 specs: login-flow, backtest-flow, navigation. `pnpm exec playwright test`. Commit.

### C3 — OpenAPI docs

**Files:** `docs/api/openapi.yaml`

Document auth/broker/trading/backtest/market endpoints. Commit.

---

## Final Verification
- [ ] Go: `go build ./... && go test ./... -race -count=1`
- [ ] Python: `pytest tests/ -v`
- [ ] Frontend: `pnpm build && pnpm test && pnpm exec playwright test`
