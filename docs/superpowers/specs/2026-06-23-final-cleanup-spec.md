# Full Cleanup Spec — RSC + Security + Debt

> **Date**: 2026-06-23  
> **Scope**: 9 items across RSC optimization, production security, and code debt

---

## A. RSC 优化

### A1 — Dashboard RSC 拆分
**File**: `frontend/app/page.tsx`  
Wrap data sections in `<Suspense fallback={<Skeleton />}>`. Move OnboardingWizard check to client sub-component so the shell can be server-rendered.

### A2 — Metadata
**File**: `frontend/app/layout.tsx`  
Add `export const metadata: Metadata = { title: "AStockPursue", description: "..." }`

### A3 — Package Import 优化
**File**: `frontend/next.config.ts`  
Add `experimental: { optimizePackageImports: ['recharts', 'd3', '@xyflow/react'] }`

---

## B. 安全加固

### B1 — 移除硬编码 DB/Redis 凭证
**File**: `services/go/internal/config/config.go`  
`DATABASE_URL` 和 `REDIS_URL` 环境变量改为必填。未设置时启动报错，不再回退到 `postgres:postgres@localhost`。保留 `DEVELOPMENT=true` 时的宽松模式。

### B2 — API 密钥轮换
**File**: `services/go/internal/api/handler/broker.go`  
新增 `POST /broker/credentials/rotate` — 接收新 api_key/api_secret，替换旧值，记录轮换审计日志。

### B3 — 安全 Headers
**File**: `frontend/middleware.ts`  
添加响应头：`Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`（基础策略）。

---

## C. 债务清理

### C1 — OKX JSON 结构体序列化
**File**: `services/go/internal/broker/okx.go`  
查找 `fmt.Sprintf` 拼接 JSON body 处，改为定义结构体 + `json.Marshal`。

### C2 — ScreenerGrid formatPercent 双重转换
**File**: `frontend/components/financial/ScreenerGrid.tsx`  
`formatPercent(row.change_pct / 100)` 中 formatPercent 内部会 `×100`，导致 `5% → 0.05 → 0.05%`。修复为 `formatPercent(row.change_pct)`。

### C3 — config.go（与 B1 合并）

---

## 验证

- Go: `go build ./... && go test ./... -race -count=1`
- Frontend: `pnpm build` 零错误 + `pnpm test` 172 用例无回归
