# Performance Optimization Spec

> **Date**: 2026-06-23  
> **Scope**: 7 performance improvements across Go/Python/前端

---

## 1. Go — singleflight 去重

**File**: `services/go/internal/market/store.go`  
**Fix**: 用 `golang.org/x/sync/singleflight.Group` 包装 `GetBars` 和 `GetLatestBars` 的 DB 查询路径。同 key 并发调用只执行一次。Key 格式: `symbols:start:end:freq`。

## 2. Python — GP 进化 ProcessPoolExecutor

**File**: `services/python/src/factors/mining/gp_engine.py:892-907`  
**Fix**: `ThreadPoolExecutor` → `ProcessPoolExecutor(max_workers=...)`。适应度评估函数需确保可 pickle。添加 `if __name__ == "__main__"` 保护。

## 3. Go — Composite 引擎工厂缓存

**File**: `services/go/internal/engine/composite.go`  
**Fix**: 添加 `sync.Map` 缓存 `ForSymbol` 创建的引擎实例。key: `symbol+engineType`。

## 4. Python — ExpressionTree to_callable LRU 缓存

**File**: `services/python/src/factors/mining/expression_tree.py:561-569`  
**Fix**: `to_callable()` 加 `@functools.lru_cache(maxsize=4096)`。

## 5. 前端 — 图表组件代码分割

**Files**: `app/page.tsx`, `app/analysis/*/page.tsx`, `components/financial/*.tsx`  
**Fix**: CandlestickChart、EquityChart、DrawdownChart、CorrelationMatrix、WorkflowCanvas 用 `next/dynamic(() => import(...), { ssr: false })` 懒加载，添加 Suspense fallback。

## 6. Python — IC 适应度矢量化

**File**: `services/python/src/factors/mining/fitness.py:68-80`  
**Fix**: 逐行 `pearsonr` 循环 → `pd.DataFrame.corrwith()` 批量计算。

## 7. 前端 — font 配置 + SidebarLayout padding 修复

**Files**: `app/layout.tsx`, `components/layout/SidebarLayout.tsx`  
**Fix**: layout.tsx 中加载的 Fira 字体对齐 globals.css 中的 `--font-sans: 'Inter'`；SidebarLayout 中第二个 `padding` 简写覆盖问题。

---

## 验证

- Go: `go build ./... && go test ./... -race -count=1`
- Python: `pytest tests/test_factor_kb.py tests/test_sandbox.py -v`
- Frontend: `pnpm build`（零错误）+ `pnpm test`（156 用例无回归）
