# Final Cleanup Plan

## Global Constraints
- Go: `go build ./... && go test ./... -race -count=1` 零回归
- Frontend: `pnpm build` 零错误, `pnpm test` 172 用例无回归

---

### Task 1: C2 — ScreenerGrid formatPercent 修复

**File:** `frontend/components/financial/ScreenerGrid.tsx`

Find `formatPercent(row.change_pct / 100)` → change to `formatPercent(row.change_pct)`. `pnpm build && pnpm test`. Commit.

### Task 2: B1 — config.go 移除硬编码凭证

**File:** `services/go/internal/config/config.go`

DATABASE_URL 和 REDIS_URL 未设置时返回错误。`DEVELOPMENT=true` 时允许 localhost 默认值。`go build ./... && go test`. Commit.

### Task 3: B3 — 安全 Headers

**File:** `frontend/middleware.ts`

在现有 NextAuth middleware 后添加响应头。`pnpm build`. Commit.

### Task 4: C1 — OKX JSON 结构体

**File:** `services/go/internal/broker/okx.go`

查找 URL-encoded body 拼接处，改为结构体 + `json.Marshal`。`go build && go test ./internal/broker/ -v`. Commit.

### Task 5: A3 — optimizePackageImports

**File:** `frontend/next.config.ts`

添加 `experimental.optimizePackageImports`。`pnpm build`. Commit.

### Task 6: A1 + A2 — Dashboard RSC + Metadata

**Files:** `frontend/app/page.tsx`, `frontend/app/layout.tsx`

page.tsx: 拆客户端组件 + Suspense。layout.tsx: metadata 导出。`pnpm build && pnpm test`. Commit.

### Task 7: B2 — API 密钥轮换

**File:** `services/go/internal/api/handler/broker.go`, `services/go/internal/api/router.go`

`POST /broker/credentials/rotate` + 路由注册。`go build && go test ./internal/api/handler/`. Commit.

---

## 验证
- [ ] Go: `go build ./... && go test ./... -race -count=1`
- [ ] Frontend: `pnpm build && pnpm test`
