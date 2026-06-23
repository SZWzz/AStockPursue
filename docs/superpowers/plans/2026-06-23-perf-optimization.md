# Performance Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 7 performance optimizations across Go/Python/前端 — no API changes, zero regression.

## Global Constraints

- Go: `go build ./... && go test ./... -race -count=1` 零回归
- Python: `pytest tests/test_factor_kb.py tests/test_sandbox.py -v` 零回归
- Frontend: `pnpm build` 零错误, `pnpm test` 156 用例无回归

---

### Task 1: Go singleflight for market store

**Files:** Modify `services/go/internal/market/store.go`

- [ ] Add `golang.org/x/sync/singleflight` import
- [ ] Add `sfGroup singleflight.Group` to DataStore struct
- [ ] Wrap DB query in `GetBars` with `sfGroup.Do(key, func()...)`
- [ ] Same for `GetLatestBars`
- [ ] Key format: `fmt.Sprintf("bars:%s:%s:%s", strings.Join(symbols,","), start, end)`
- [ ] `go build ./... && go test ./internal/market/ -v -race -count=1`
- [ ] Commit: `perf: singleflight dedup for market store GetBars/GetLatestBars`

---

### Task 2: Python GP ProcessPoolExecutor

**Files:** Modify `services/python/src/factors/mining/gp_engine.py`

- [ ] Read current code around line 892-907
- [ ] Replace `ThreadPoolExecutor` with `ProcessPoolExecutor`
- [ ] Ensure fitness functions are top-level (picklable)
- [ ] Add `if __name__ == "__main__"` guard if missing
- [ ] `python -m pytest tests/ -k "gp" -v` if gp tests exist, else just verify import works
- [ ] Commit: `perf: GP evaluation uses ProcessPoolExecutor for true parallelism`

---

### Task 3: Go composite engine caching

**Files:** Modify `services/go/internal/engine/composite.go`

- [ ] Add `engineCache sync.Map` to CompositeEngine
- [ ] In `ForSymbol`: check cache before creating new engine
- [ ] Cache key: symbol string
- [ ] `go build ./... && go test ./internal/engine/ -v -race -count=1`
- [ ] Commit: `perf: cache composite engine instances with sync.Map`

---

### Task 4: Python ExpressionTree to_callable LRU cache

**Files:** Modify `services/python/src/factors/mining/expression_tree.py`

- [ ] Add `from functools import lru_cache`
- [ ] On `to_callable()` method, add `@lru_cache(maxsize=4096)` 
- [ ] Note: needs careful handling since self is passed — use cached property or wrap
- [ ] `python -m pytest tests/test_formula_consistency.py -v`
- [ ] Commit: `perf: lru_cache for ExpressionTree.to_callable()`

---

### Task 5: Frontend chart lazy loading

**Files:** Modify `app/page.tsx`, `app/analysis/*/page.tsx`

- [ ] Read current chart imports in page files
- [ ] Replace static imports with `next/dynamic`:
  ```tsx
  const CandlestickChart = dynamic(() => import('@/components/financial/CandlestickChart'), { 
    ssr: false, 
    loading: () => <Skeleton className="h-[400px]" />
  })
  ```
- [ ] Apply to: CandlestickChart, EquityChart, DrawdownChart, CorrelationMatrix
- [ ] `cd frontend && pnpm build && pnpm test`
- [ ] Commit: `perf: lazy load chart components with next/dynamic`

---

### Task 6: Python IC fitness vectorization

**Files:** Modify `services/python/src/factors/mining/fitness.py`

- [ ] Read current `ic_fitness` function around line 68-80
- [ ] Replace Python loop with `factor_vals.corrwith(forward_returns, axis=1, method='pearson')`
- [ ] Handle edge cases: NaN, insufficient data
- [ ] `python -m pytest tests/ -k "fitness" -v`
- [ ] Commit: `perf: vectorize ic_fitness with DataFrame.corrwith`

---

### Task 7: Frontend font + SidebarLayout fixes

**Files:** Modify `app/layout.tsx`, `components/layout/SidebarLayout.tsx`

- [ ] layout.tsx: align Google Fonts load with globals.css CSS variables (Inter → Inter, or update globals.css)
- [ ] SidebarLayout.tsx: fix `padding` shorthand override issue — separate properties
- [ ] `cd frontend && pnpm build`
- [ ] Commit: `fix: align font config and fix SidebarLayout padding override`

---

## Final Verification

- [ ] `cd services/go && go build ./... && go test ./... -race -count=1`
- [ ] `cd services/python && python -m pytest tests/test_factor_kb.py tests/test_sandbox.py tests/ -k "fitness or formula or gp" -v`
- [ ] `cd frontend && pnpm build && pnpm test`
