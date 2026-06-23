# Remaining Improvements Spec

> **Date**: 2026-06-23  
> **Scope**: 10 items across three tiers

---

## Tier A — 小改动/高价值（4 项）

### A1 — Python rank_ic_fitness 矢量化
**File**: `services/python/src/factors/mining/fitness.py:97-112`  
Spearman 循环 → `pd.DataFrame.corrwith(method="spearman")`。与已完成的 ic_fitness 矢量化同理。

### A2 — sandbox 死代码清理
**File**: `services/python/src/factors/mining/sandbox_pandas.py`  
移除未使用的 `_PD_SERIES_WHITELIST` 和空操作 `wrap_panel()`，修复 `_NP_WHITELIST` 中重复的 `"sign"`。

### A3 — futu.go getFloat 错误忽略
**File**: `services/go/internal/broker/futu.go`  
`getFloat` 返回 `(float64, bool)`，调用方忽略 bool。改为 `(float64, error)`，与 binance/okx 的 `safeParseFloat` 对齐。

### A4 — ws.go broadcast 满 channel 警告
**File**: `services/go/internal/api/ws.go:81-84`  
当前 `select default:` 静默丢弃消息。改为 `default: log.Printf("ws: broadcast channel full, dropping message for channel %s", ...)`。

---

## Tier B — 中改动（3 项）

### B1 — 安全端点 Go 测试
**Files**: `services/go/internal/api/handler/auth_test.go`, `broker_test.go`(新建)  
AdminSetup 端点测试、RevealCredentials 限流测试、RotateCredentials 测试。目标 +15 用例。

### B2 — 前端 RSC 迁移
**Files**: `app/market/page.tsx`, `app/backtest/page.tsx`, `app/trading/page.tsx`  
已有 Dashboard 的 RSC 模式推广到这三个核心页面：Server Component 壳 + Suspense + 客户端内容组件。

### B3 — 剩余前端 any 替换
**Files**: 搜索 `: any` 匹配处  
TradeTimeline、IndexTickerBar、PriceTicker、CodeEditor 等组件中的 `any` 替换为具体类型。

---

## Tier C — 大改动（3 项）

### C1 — workflow/research 强类型
**Files**: `services/go/internal/workflow/`, `services/go/internal/research/`  
`map[string]any` → 结构化接口。定义 `WorkflowInput`/`WorkflowOutput` 接口类型，各节点实现对应类型。

### C2 — E2E 测试（Playwright）
**Files**: `frontend/e2e/`  
核心流程：登录→仪表盘→创建策略→回测→查看结果。3 个 spec 文件。

### C3 — OpenAPI/Swagger 文档
**Files**: `docs/api/`  
基于 Go gin handler 注解生成 API 文档。覆盖 auth、broker、trading、backtest、market 端点。

---

## 验证

- Go: `go build ./... && go test ./... -race -count=1`
- Python: `pytest tests/ -v`（sandbox + fitness 测试）
- Frontend: `pnpm build` 零错误 + `pnpm test` 172+ 无回归 + `pnpm exec playwright test` 通过
