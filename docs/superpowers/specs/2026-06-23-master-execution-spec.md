# Master Execution Spec — 2026-06-23

> **整合版**: 将当前所有活跃计划合并成一份可执行的 Spec，消除重复、明确依赖、排定优先级。
> **执行方式**: 用 `subagent-driven-development` 技能，每个 Wave 内的任务可并行。

---

## 全局约束

| 层 | 验证命令 | 基线 |
|----|---------|------|
| Go | `cd services/go && go build ./... && go test ./... -race -count=1` | 零回归 |
| Python | `cd services/python && python -m pytest tests/ -v` | 零回归 |
| Frontend | `cd frontend && pnpm build && pnpm test` | `pnpm build` 零错误，`pnpm test` 172+ 用例通过 |

每个 Task 完成后必须跑对应层的验证命令，不通过不进行下一个。

---

## Wave 1 — 安全 P0/P1 修复（阻塞一切后续工作）

> **来源**: `2026-06-23-security-fixes-design.md` + `2026-06-23-security-fixes.md`  
> **优先级**: 最高，有些是运行时 crash，有些是高危安全漏洞  
> **并行**: Task 1.1–1.3 可并行（Python），Task 1.4–1.7 可并行（Go）

### Task 1.1 — factor_kb.py `setdefault` Typo（Python, P0）

**文件**: `services/python/src/factors/mining/factor_kb.py`  
**问题**: 第 314 和 738 行有拼写错误，调用了不存在的方法，运行时 `AttributeError`。

**实现**:
1. 读取 factor_kb.py lines 310-320 和 734-744
2. 确认两处 `setdefault` 调用的实际拼写（已有 spec 称"同名"但可能是字符看起来像的 typo，需实际读取）
3. 修复两处调用
4. 扩展 `services/python/tests/test_factor_kb.py`，新增：
   - `test_register_adds_to_source_version_index`
   - `test_load_populates_source_version_index`
5. 运行 `python -m pytest tests/test_factor_kb.py -v`
6. Commit: `fix: factor_kb setdefault typo — prevents runtime AttributeError`

---

### Task 1.2 — LLM Miner eval() Sandbox 强化（Python, P1）

**文件**: 
- `services/python/src/factors/mining/sandbox_pandas.py`（已存在，需修改）
- `services/python/src/factors/mining/llm_miner.py`

**问题**: `eval(formula, {"__builtins__": {}}, safe_locals)` 中 `pd` 是真实 pandas，允许 `pd.read_csv("/etc/passwd")`。

**实现**:
1. 读取 `sandbox_pandas.py` 当前内容
2. 修改 `SandboxPandas.__getattr__` — 如果属性在 I/O 黑名单或不在 `_PD_WHITELIST` 中，抛 `SandboxError`（当前版本已有但需确认 I/O 方法是否完整屏蔽）
3. 修复 `_NP_WHITELIST` 中重复的 `"sign"` 条目
4. 删除未使用的 `_PD_SERIES_WHITELIST` 和 `wrap_panel()` 死代码
5. 读取 `llm_miner.py` lines 425-445，找到 `safe_locals` 字典定义
6. 将 `"pd": pd` 替换为 `"pd": SandboxPandas()`, `"np"` 替换为 `SandboxNumpy()`
7. 将 `eval(formula, {"__builtins__": {}}, safe_locals)` 改为使用 `safe_builtins` 字典（只含 True/False/None/abs/min/max/round/len）
8. 扩展 `services/python/tests/test_sandbox.py`：
   - `test_sandbox_pandas_blocks_io` — read_csv/to_parquet 等被拒绝
   - `test_sandbox_pandas_allows_safe_ops` — DataFrame/Series/concat 可用
   - `test_eval_sandbox_blocks_file_read` — eval 中调用 pd.read_csv 被拦截
9. `python -m pytest tests/test_sandbox.py -v`
10. Commit: `fix: SandboxPandas/SandboxNumpy restrict LLM miner eval to whitelist`

---

### Task 1.3 — gRPC TLS 证书验证（Go, P0）

**文件**:
- 新建 `services/go/internal/grpc/tls.go`
- 修改 `services/go/internal/engine/signal.go`
- 修改 `services/go/internal/grpc/connmgr.go`
- 新建 `services/go/internal/grpc/tls_test.go`

**问题**: `credentials.NewClientTLSFromCert(nil, "")` 不校验服务端证书，等同于明文传输。

**实现**:
1. 新建 `tls.go`，实现 `loadTLSCredentials() (credentials.TransportCredentials, error)`:
   - 若 `GRPC_CA_CERT` 有值，从文件加载 CA cert
   - 否则用 `x509.SystemCertPool()`
   - 返回 `credentials.NewTLS(&tls.Config{RootCAs: cp, MinVersion: tls.VersionTLS12})`
   - 若 `GRPC_TLS_REQUIRED=true`，任何加载失败均 fatal
2. 修改 `signal.go`：`GRPC_TLS_ENABLED=true` 时调用 `loadTLSCredentials()` 替换 `NewClientTLSFromCert`
3. 修改 `connmgr.go`：同上
4. 新建测试文件，覆盖：
   - 系统 CA pool 正常加载
   - 无效 CA cert 路径时的错误处理
   - `GRPC_TLS_REQUIRED=true` 时无证书则失败
5. `go build ./... && go test ./internal/grpc/ -v -race -count=1`
6. Commit: `fix: gRPC TLS proper certificate verification via system CA pool`

---

### Task 1.4 — FutuBroker TOCTOU 竞态（Go, P0）

**文件**: `services/go/internal/broker/futu.go`

**问题**: `ensureConnected()` 释放锁后调用 `reconnect()`，并发时两个 goroutine 都看到 conn==nil 并竞争重连。

**实现**:
1. 读取 futu.go lines 200-240
2. 修改 `ensureConnected()` — 持锁期间直接调用 `reconnectLocked()`（不释放锁再调用 reconnect）
3. 提取 `reconnectLocked()` — 内部需在 I/O 操作前释放锁、I/O 后重新获取锁（锁内 I/O 模式）
4. 验证 `reconnect()` 公共方法依然可用（由非持锁调用方调用）
5. `go test ./internal/broker/ -race -run TestFutu -v -count=1`
6. Commit: `fix: FutuBroker TOCTOU race in ensureConnected`

---

### Task 1.5 — WebSocket Origin 校验（Go, P1）

**文件**:
- 修改 `services/go/internal/api/ws.go`
- 新建 `services/go/internal/api/ws_test.go`

**问题**: `CheckOrigin: func(r *http.Request) bool { return true }` — 任何域名都能建立 WebSocket 连接。

**实现**:
1. 读取 `ws.go` 的 `upgrader` 变量定义（约 lines 14-16）
2. 在包级别用 `init()` 函数构建 `wsAllowedOrigins map[string]bool`：
   - 读取 `WS_ALLOWED_ORIGINS` 环境变量（逗号分隔）
   - 默认值：`http://localhost:5899,http://127.0.0.1:5899`
3. 修改 `CheckOrigin`：空 Origin 头允许（同域请求），否则查 whitelist
4. 新建测试：localhost:5899 允许，evil.com 拒绝，无 Origin 头允许
5. `go test ./internal/api/ -run TestWebSocket -v -count=1`
6. Commit: `fix: WebSocket origin check — WS_ALLOWED_ORIGINS whitelist`

---

### Task 1.6 — ParseFloat 错误忽略（Go, P1）

**文件**:
- 新建 `services/go/internal/broker/parse.go`（`safeParseFloat` 辅助函数）
- 修改 `services/go/internal/broker/binance.go`
- 修改 `services/go/internal/broker/okx.go`
- 新建 `services/go/internal/broker/parse_test.go`

**问题**: `qty, _ := strconv.ParseFloat(...)` 全部静默丢弃错误，API 返回异常格式时数据无声损坏。

**实现**:
1. 新建 `parse.go`：
   ```go
   func safeParseFloat(s string) (float64, error)
   ```
2. `grep -n "ParseFloat" internal/broker/binance.go` 找所有调用点（约 10 处）
3. `grep -n "ParseFloat" internal/broker/okx.go` 找所有调用点（约 6 处）
4. 逐一替换 `strconv.ParseFloat(s, 64)` → `safeParseFloat(s)`，错误向上传播（GetPositions 中 continue 跳过该仓位，GetBalance/PlaceOrder 中 return error）
5. 新建 `parse_test.go`：valid/negative/empty/invalid/whitespace 5 个用例
6. `go test ./internal/broker/ -v -count=1`
7. Commit: `fix: safeParseFloat — no more silent ParseFloat error swallowing`

---

### Task 1.7 — 移除硬编码 Admin 密码（Go, P1）

**文件**:
- 修改 `services/go/internal/api/handler/auth.go`
- 修改 `services/go/internal/api/router.go`
- 扩展 `services/go/internal/api/handler/auth_test.go`

**问题**: `"admin": {Username: "admin", Password: hashPassword("admin123")}` 硬编码在源码中。

**实现**:
1. 读取 auth.go `NewAuthHandler` 函数（约 lines 139-155）
2. 修改：移除硬编码 admin 用户
3. 新增 `initAdminUser()` 方法，读取 `ADMIN_PASSWORD` 环境变量创建 admin（不存在则不创建）
4. 新增 `AdminSetup(c *gin.Context)` 端点（POST /admin/setup）：
   - Admin 不存在时允许创建
   - 已存在时返回 409
5. 修改 `generateToken` 中硬编码 `"user_id": "1"` → `"user_id": username`
6. 在 router.go 注册 `POST /api/v1/admin/setup`
7. 扩展 auth_test.go：`TestNoHardcodedAdmin`、`TestAdminFromEnv`
8. `go test ./internal/api/handler/ -run TestAuth -v -count=1`
9. Commit: `fix: remove hardcoded admin/admin123, use ADMIN_PASSWORD env var`

---

### Task 1.8 — Broker API Key 脱敏（Go, P1）

**文件**:
- 修改 `services/go/internal/api/handler/broker.go`
- 修改 `services/go/internal/api/router.go`

**问题**: `GET /api/broker/credentials` 返回完整明文 API Key 和 Secret。

**实现**:
1. 读取 broker.go `GetCredentials` 函数（约 lines 197-243）
2. 添加 `maskString(s string) string` 辅助函数（显示前3后4，中间替换为 `****`）
3. 修改 `GetCredentials`：返回前对 api_key 和 api_secret 调用 `maskString`
4. 新增 `RevealCredentials(c *gin.Context)` 端点：
   - 需要 `current_password` body
   - 验证密码后返回完整明文
   - 记录 audit log（user_id + timestamp + broker）
5. 在 BrokerHandler struct 中添加 `passwordVerifier func(userID int, password string) bool` 字段
6. 在 router.go 注册 `POST /api/v1/broker/credentials/reveal`
7. `go build ./... && go test ./internal/api/handler/ -run TestBroker -v -count=1`
8. Commit: `fix: mask broker API keys in GET response, add reveal endpoint with password check`

---

### Task 1.9 — TimescaleDB 可选化（Go, P1）

**文件**: `services/go/internal/db/timescale.go`

**问题**: `create_hypertable()` 在标准 PostgreSQL 上会失败，应用无法启动。

**实现**:
1. 读取 `timescale.go` 的 `InitSchema` 函数（约 lines 75-100）
2. 新增 `hasTimescaleDBExtension(ctx) bool` 私有方法，查询 `pg_extension`
3. 修改 `InitSchema`：
   - 先执行 `CREATE TABLE IF NOT EXISTS`（不含 hypertable）
   - 再调用 `ensureHypertable(ctx, tableName)` — 有 extension 时创建，没有时 log + 跳过
4. hypertable 失败改为非 fatal（log.Printf 警告，继续运行）
5. `go build ./... && go test ./internal/db/ -v -count=1`
6. Commit: `fix: TimescaleDB hypertable non-fatal on standard PostgreSQL`

---

## Wave 2 — 代码质量（Wave 1 完成后执行）

> **来源**: `2026-06-23-code-quality.md` + 部分 remaining-improvements  
> **并行**: Task 2.1–2.2 可并行（Go），Task 2.3 独立（Frontend types），Task 2.4–2.6 可并行（Frontend tests）

### Task 2.1 — Go engine `bar interface{}` → `*Bar`（Go）

**文件**: `services/go/internal/engine/` 下多个文件

**问题**: `ApplySlippage(order *Order, bar interface{})` 在 7 个引擎实现中用 `bar.(*Bar)` 强转，既不安全也失去类型检查。

**实现**:
1. 读取 `engine/engine.go` 找 `Engine` 接口定义
2. 修改接口：`ApplySlippage(order *Order, bar *Bar) float64`
3. 修改 `RiskPipeline` 接口：`CheckExits(portfolio *Portfolio, bar *Bar) []*Order`；`BlockNewSignals` 提升到接口
4. 修改 `pipeline.go`：删除 `interface{}` 包装调用
5. 修改 7 个引擎实现（china_a/crypto/forex/futures_base/global_equity/options/composite）：删除 `b := bar.(*Bar)` 断言
6. 修改 `risk.go`：同上
7. 更新所有 `*_test.go` 中的 mock 实现
8. `go build ./... && go test ./internal/engine/ -v -race -count=1`
9. Commit: `refactor: engine bar interface{} → *Bar, BlockNewSignals promoted to interface`

---

### Task 2.2 — Go API/log `interface{}` → `any`（Go）

**文件**: `api/ws.go`, `api/handler/broker.go`, `log/logger.go`

**实现**:
1. `ws.go`：`Data interface{}` → `Data any`；`Broadcast(channel string, data interface{})` → `data any`
2. `broker.go`：新增 `BrokerCredential` 和 `BrokerSettings` 结构体，替换 `map[string]interface{}` 遍历
3. `log/logger.go`：4 个方法的 `interface{}` → `any`
4. `go build ./... && go test ./internal/api/ ./internal/log/ -v -count=1`
5. Commit: `refactor: interface{} → any in api/ws, broker, logger`

---

### Task 2.3 — Frontend API 类型定义（Frontend）

**文件**:
- 新建 `frontend/types/api.ts`
- 新建 `frontend/types/index.ts`

**实现**:
1. 创建 `api.ts`，包含完整类型（参考 code-quality plan Task 3）：
   - `MarketRow`, `Position`, `Portfolio`, `EquityPoint`
   - `Order`, `OrderSide`, `OrderType`, `OrderStatus`
   - `KpiData`, `FactorSummary`, `BacktestResult`
   - `ApiResponse<T>`, `WSMessage`, `TickerData`
2. 创建 `index.ts` re-export
3. 替换高频组件中的 `any`：PositionTable(`pos: Position`)、ScreenerGrid(`row: MarketRow`)
4. `pnpm build` 验证零类型错误
5. Commit: `feat: add frontend API types — Position/Order/Portfolio/MarketRow etc`

---

### Task 2.4 — 前端工具函数测试补充（Frontend）

**文件**: `frontend/__tests__/utils.test.ts`

**实现**:
1. 读取当前测试文件了解格式
2. 补充边界值测试（参考 code-quality plan Task 4）：
   - `formatPrice`：整数/小数/零/负数/NaN/Infinity
   - `formatPercent`：正/负/零/极小值
   - `formatVolume`：K/M/B/小值
   - `colorForChange`：正/负/零
3. `pnpm test __tests__/utils.test.ts`（目标 35+ 用例）
4. Commit: `test: expand utils tests to 35+ — formatPrice/Percent/Volume edge cases`

---

### Task 2.5 — SWR Hooks 测试（Frontend）

**文件**: 新建 `frontend/__tests__/hooks.test.tsx`

**实现**:
1. 确认是否已安装 `msw`（`cat frontend/package.json | grep msw`）
2. 未安装则 `pnpm add -D msw@latest`
3. 编写 hooks 测试（参考 code-quality plan Task 5）：
   - `usePositions`, `useOrders`, `useMarketData`, `useKlines`, `usePortfolio`
   - 每个 hook 测试：loading 状态、成功返回、错误处理、空数据
4. `pnpm test __tests__/hooks.test.tsx`（目标 30+ 用例）
5. Commit: `test: SWR hooks tests — usePositions/Orders/MarketData/Portfolio (30+ tests)`

---

### Task 2.6 — 核心组件测试（Frontend）

**文件**: 新建多个测试文件

**实现**:
1. `__tests__/PositionTable.test.tsx`（15 用例）：渲染/空数据/排序/格式化/关闭确认
2. `__tests__/OrderForm.test.tsx`（扩展至 10 用例）：买卖切换/验证/提交禁用/清空
3. `__tests__/KpiCard.test.tsx`（6 用例）：正/负/零/大数/货币/百分比格式
4. `__tests__/OrderBook.test.tsx`（5 用例）：买卖盘/空盘口/深度/价差
5. `pnpm test`（目标 172+ 用例通过）
6. Commit: `test: PositionTable/OrderForm/KpiCard/OrderBook component tests (36+ new tests)`

---

## Wave 3 — 性能优化（Wave 1 完成后可并行执行）

> **来源**: `2026-06-23-perf-optimization.md`  
> **并行**: Go 和 Python 任务可完全并行

### Task 3.1 — Go singleflight（Go）

**文件**: `services/go/internal/market/store.go`

**实现**:
1. 读取 `store.go`，找 `GetBars` 和 `GetLatestBars` 函数
2. 添加 `singleflight.Group` 字段到 `DataStore` struct
3. 用 `sfGroup.Do(key, func()...)` 包装 DB 查询
4. Key: `fmt.Sprintf("bars:%s:%s:%s:%s", strings.Join(symbols, ","), start, end, freq)`
5. `go build ./... && go test ./internal/market/ -v -race -count=1`
6. Commit: `perf: singleflight dedup for market store GetBars/GetLatestBars`

---

### Task 3.2 — Python GP ProcessPoolExecutor（Python）

**文件**: `services/python/src/factors/mining/gp_engine.py`

**实现**:
1. 读取 `gp_engine.py` lines 885-920
2. 确认适应度函数是否为顶级函数（可 pickle）
3. 将 `ThreadPoolExecutor` 替换为 `ProcessPoolExecutor(max_workers=os.cpu_count())`
4. 添加 `if __name__ == "__main__"` 保护
5. `python -m pytest tests/ -k "gp" -v`（若无 gp 测试，验证 import 成功即可）
6. Commit: `perf: GP evaluation uses ProcessPoolExecutor for true parallelism`

---

### Task 3.3 — Go Composite 引擎缓存（Go）

**文件**: `services/go/internal/engine/composite.go`

**实现**:
1. 读取 `composite.go` 的 `ForSymbol` 方法
2. 在 `CompositeEngine` struct 中添加 `engineCache sync.Map`
3. `ForSymbol` 先查 cache（key: symbol string），未命中再创建并存入
4. `go test ./internal/engine/ -v -race -count=1`
5. Commit: `perf: cache composite engine instances with sync.Map`

---

### Task 3.4 — Python ExpressionTree LRU 缓存（Python）

**文件**: `services/python/src/factors/mining/expression_tree.py`

**实现**:
1. 读取 `expression_tree.py` 找 `to_callable()` 方法（约 lines 561-569）
2. 由于 `self` 不可直接 lru_cache，采用 `cached_property` 或在模块级缓存（key: formula string）
3. 推荐方案：在 `Node.__init__` 完成后生成 `self._cache_key = self.to_expr_string()`，然后：
   ```python
   @functools.lru_cache(maxsize=4096)
   def _cached_callable(expr_key: str, ...) → Callable
   ```
4. `python -m pytest tests/ -k "formula" -v`
5. Commit: `perf: lru_cache for ExpressionTree.to_callable`

---

### Task 3.5 — 前端图表懒加载（Frontend）

**文件**: `frontend/app/page.tsx`, `frontend/app/analysis/*/page.tsx`

**实现**:
1. 读取当前 page.tsx 和 analysis 页面的图表 import
2. 替换为 `next/dynamic`：
   ```tsx
   const CandlestickChart = dynamic(
     () => import('@/components/financial/CandlestickChart'), 
     { ssr: false, loading: () => <Skeleton className="h-[400px]" /> }
   )
   ```
3. 目标组件：CandlestickChart, EquityChart, DrawdownChart, CorrelationMatrix, WorkflowCanvas
4. `pnpm build && pnpm test`
5. Commit: `perf: lazy load chart components with next/dynamic`

---

### Task 3.6 — Python IC 适应度矢量化（Python）

**文件**: `services/python/src/factors/mining/fitness.py`

**实现**:
1. 读取 `fitness.py` lines 68-80（ic_fitness）和 97-112（rank_ic_fitness）
2. ic_fitness：逐行 `pearsonr` 循环 → `factor_vals.corrwith(forward_returns, axis=1, method='pearson')`
3. rank_ic_fitness：逐行 `spearmanr` 循环 → `factor_vals.corrwith(forward_returns, axis=1, method='spearman')`
4. 处理 NaN 和数据不足的边界情况
5. `python -m pytest tests/ -k "fitness" -v`
6. Commit: `perf: vectorize ic/rank_ic fitness with DataFrame.corrwith`

---

### Task 3.7 — 前端 font + SidebarLayout 修复（Frontend）

**文件**: `frontend/app/layout.tsx`, `frontend/components/layout/SidebarLayout.tsx`

**实现**:
1. 读取 `layout.tsx` 的字体加载配置和 `globals.css` 的 `--font-sans` CSS 变量
2. 对齐：若 globals.css 用 `'Inter'`，layout 也应加载 Inter（而非 Fira）
3. 读取 `SidebarLayout.tsx`，找重复 `padding` 属性定义处，改为独立属性（`paddingLeft`, `paddingTop` 等）
4. `pnpm build`
5. Commit: `fix: align font config + SidebarLayout padding override`

---

## Wave 4 — 功能增强（可选，仅在 Wave 1-3 全部通过后执行）

> **来源**: `remaining-improvements.md` (Tier B/C), `final-cleanup.md`, `onboarding.md`

### Task 4.1 — RSC 迁移（Frontend）

- `app/market/page.tsx`, `app/backtest/page.tsx`, `app/trading/page.tsx`
- Server Component 壳 + `<Suspense>` + 提取 Client 内容组件
- Commit: `feat: RSC + Suspense for market/backtest/trading pages`

### Task 4.2 — config.go 移除硬编码 DB/Redis 凭证（Go）

- `DATABASE_URL` / `REDIS_URL` 改为必填，未设置时启动报错
- `DEVELOPMENT=true` 时允许 localhost 默认值
- Commit: `fix: require DATABASE_URL and REDIS_URL env vars in production`

### Task 4.3 — OKX JSON 结构体序列化（Go）

- 找 `okx.go` 中 `fmt.Sprintf` 拼 JSON body 处，改为结构体 + `json.Marshal`
- Commit: `refactor: OKX request body via struct + json.Marshal`

### Task 4.4 — 安全 Headers（Frontend middleware）

- `frontend/middleware.ts` 添加 HSTS/X-Content-Type-Options/X-Frame-Options/CSP
- Commit: `feat: add security HTTP response headers in Next.js middleware`

### Task 4.5 — Onboarding Wizard（Frontend）

参考 `2026-06-23-onboarding.md` 的完整 6 步计划：
- `stores/uiStore.ts` 扩展
- `messages/zh.json` + `en.json` 添加 onboarding 命名空间
- 新建 `components/onboarding/OnboardingWizard.tsx`
- `app/page.tsx` 集成
- `app/settings/page.tsx` 重入按钮
- 测试（10+ 用例）

### Task 4.6 — E2E Playwright 测试（Frontend）

- 新建 `frontend/e2e/`，3 个 spec：login-flow / backtest-flow / navigation
- `pnpm exec playwright test`

### Task 4.7 — OpenAPI 文档（Go + Docs）

- `docs/api/openapi.yaml` — 覆盖 auth/broker/trading/backtest/market 端点
- Commit: `docs: OpenAPI spec for all production endpoints`

---

## 执行顺序总结

```
Wave 1（安全）────────────────────► Wave 2（代码质量）── Wave 4（功能）
                └──────────────────► Wave 3（性能）──────┘
```

**Wave 1 内部顺序**: 
- 并行组 A: Task 1.1, 1.2（Python）
- 并行组 B: Task 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9（Go）
- A 和 B 可同时开始

**Wave 2 与 Wave 3 可同时进行**（两者不依赖对方）

**Wave 4 仅在 Wave 1-3 全通过后开始**

---

## Task 数量汇总

| Wave | 任务数 | 层次 | 预估工作量 |
|------|--------|------|-----------|
| Wave 1 | 9 | Go 7 + Python 2 | 高（安全修复，逐文件精确改动） |
| Wave 2 | 6 | Go 2 + Frontend 4 | 中（类型重构 + 测试） |
| Wave 3 | 7 | Go 3 + Python 2 + Frontend 2 | 中（逐处优化） |
| Wave 4 | 7 | Go 2 + Frontend 5 | 中高（新功能） |
| **总计** | **29** | — | — |
