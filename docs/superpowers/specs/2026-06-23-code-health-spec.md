# Code Health Improvement Spec — 2026-06-23

> **来源**: Go/Python/Frontend 三端全面审计报告  
> **共计**: 18 个改进项，分 4 个 Wave

---

## 全局约束

| 层 | 验证命令 | 基线 |
|----|---------|------|
| Go | `cd services/go && go build ./... && go test ./... -race -count=1` | 零回归 |
| Python | `cd services/python && python -m pytest tests/ -v` | 零回归 |
| Frontend | `cd frontend && npx next build && npx vitest run` | 零构建错误 + 199 测试通过 |

---

## Wave 1 — P0 立即修复（阻塞一切）

### Task 1.1 — FutuBroker 锁管理（Go, P0）

**文件**: `services/go/internal/broker/futu.go:224-258`

**问题**: `reconnectLocked()` 持锁返回时调用方 `ensureConnected()` 会再次 `Unlock`，导致多释放一次锁。

**修复**:
1. 修改 `reconnectLocked()` — 失败时在返回前释放锁
2. 或者修改 `ensureConnected()` — 不在 `reconnectLocked()` 返回后无条件 Unlock
3. 推荐方案：`reconnectLocked()` 内部不再释放/重获取锁，改为在 I/O 前用局部变量保存状态，I/O 后持锁写回
4. `go test ./internal/broker/ -race -run TestFutu -v -count=5` 验证无竞态
5. Commit: `fix: FutuBroker ensureConnected lock management — prevent double-unlock`

---

### Task 1.2 — WebSocket Feed 竞态（Go, P0）

**文件**: `services/go/internal/market/feed/feed.go:97-102`, `feed/binance.go:89-93`

**问题**: `Connect()` 写 `f.conn` 未持锁，`Subscribe()`/`Unsubscribe()` 读时持锁 — 数据竞争。

**修复**:
1. `feed.go` `Connect()`: 在写 `f.conn` 前 `f.mu.Lock()`，写后 `f.mu.Unlock()`
2. `binance.go` `Connect()`: 同上
3. `go test ./internal/market/feed/ -race -v -count=5` 验证
4. Commit: `fix: WebSocket feed Connect mutex on f.conn — prevent data race`

---

### Task 1.3 — Python 错误吞没消除（Python, P0）

**文件**: 19 个位置，分布在 13 个文件

**问题**: `except Exception: pass` 静默丢弃关键错误。

**修复**: 分轻重：
- **HIGH（必须修）**: alpha_nodes.py:65, delivery_nodes.py:270, llm_miner.py:341+398, factor_validator.py:179+212, progress.py:118+182, remember_analysis.py:97 — 改为 `logger.warning("操作名 failed: %s", e, exc_info=True)`
- **MEDIUM（加日志）**: hybrid_init.py:329, sector_mapper.py:425, trade_journal_parsers.py:354 — 改为 `logger.warning(...)`
- **LOW（可保留）**: sandbox.py:242+267（超时清理）、cli_handlers.py:41、skills 示例 — 改为 `logger.debug(...)`

1. 逐一修改 13 个文件的 19 处
2. `python -m pytest tests/ -v` 验证零回归
3. Commit: `fix: replace silent except Exception:pass with logged warnings`

---

## Wave 2 — P1 类型安全 + 测试补充

### Task 2.1 — Go interface{} 清理（Go, P1）

**文件**: arena.go, futu.go, feed/binance.go, research/*.go, factor.go, analysis.go, broker.go, marketplace.go

**问题**: 非生成代码中残余 `map[string]interface{}` 和 `adapter interface{}`。

**修复**:
1. `engine/arena.go:39` — `Parameters map[string]interface{}` → `Parameters map[string]any`
2. `broker/futu.go` — 定义 `futuRequest`/`futuResponse` struct 替代 `map[string]interface{}`
3. `feed/binance.go:125+138` — 定义 `binanceWSSub` struct 替代 `map[string]interface{}`
4. `research/` 4 个文件 — `adapter interface{}` → 定义 `ResearchAdapter` interface
5. `handler/factor.go`, `analysis.go`, `broker.go`, `marketplace.go` — `map[string]interface{}` → `map[string]any`
6. `go build ./... && go test ./... -count=1` 验证
7. Commit: `refactor: replace remaining interface{} with any or concrete types`

---

### Task 2.2 — Research 缓存错误传播（Go, P1）

**文件**: `research/geopolitics.go:127`, `news.go:57`, `northbound.go:47`, `financials.go:24`

**问题**: 缓存读取错误被 `_, _` 忽略，数据库损坏时静默使用 mock 数据。

**修复**:
1. 4 个文件各一处：`cached, _ := s.repo.GetCategory(...)` → 改为检查 error
2. 若 cache miss（pgx.ErrNoRows）→ 正常生成 mock 数据
3. 若 cache 读取失败（DB 损坏）→ log warning + 降级到 mock
4. `go test ./internal/research/ -v -count=1` 验证
5. Commit: `fix: propagate cache read errors in research services`

---

### Task 2.3 — Go research 包测试补充（Go, P1）

**文件**: 新建 `services/go/internal/research/research_test.go`

**修复**: 为 7 个源文件中 4 个核心模块添加基础测试：
1. `TestMockFinancialReport` — 验证 mock 数据生成非空
2. `TestMockGeopoliticalRisk` — 同上
3. `TestMockNewsSentiment` — 同上
4. `TestMockNorthboundFlow` — 同上
5. `TestResearchService_CacheSaveLoad` — mock repo，验证 save/load 循环
6. `TestResearchService_EmptyRepo` — 空 repo 时返回 mock 数据
7. `go test ./internal/research/ -v -count=1` — 目标 6+ 通过
8. Commit: `test: research service cache and mock data tests`

---

### Task 2.4 — Python agent trace 缓冲（Python, P1）

**文件**: `services/python/src/agent/loop.py`

**问题**: trace.write() 在热路径中同步写入 10+ 处，每次 3-5 次文件 I/O。

**修复**:
1. 在 AgentLoop 类中添加 `_trace_buffer: list[str]` 列表
2. 将 `trace.write(line)` → `self._trace_buffer.append(line)`
3. 每隔 10 条批量 flush：`if len(self._trace_buffer) >= 10: self._flush_trace()`
4. 在 `_finalize()` 或 `__exit__()` 中强制 flush 剩余
5. `python -m pytest tests/test_agent_loop.py -v` 验证
6. Commit: `perf: buffer agent trace writes — reduce sync I/O in hot path`

---

### Task 2.5 — Python factors/mining 测试框架（Python, P1）

**文件**: 新建 `services/python/tests/test_factor_kb.py`（若不存在则新建）

**说明**: 完整的 12 文件测试覆盖工作量极大，先搭建框架 + 覆盖 core 模块。

**修复**:
1. 新建/扩展 tests 覆盖 3 个核心模块：
   - `test_factor_kb.py` — 测试 factor KB 的 register/load/source_version_index（若已有则确认覆盖度）
   - `test_fitness.py` — 测试 IC/rank_IC/Sharpe 计算（若已有则确认覆盖度）
   - `test_sandbox.py` — 测试 sandbox pandas/numpy 安全限制（若已有则确认覆盖度）
2. 若上述测试已存在，则验证 `python -m pytest tests/ -k "factor or fitness or sandbox" -v` 通过
3. 若不存在，各补 4-6 个基础测试
4. Commit: `test: factor mining core module test coverage`

---

## Wave 3 — P2 快速修复

### Task 3.1 — Go 硬编码 URL 可配置化（Go, P2）

**文件**: `config/config.go` + `feed/feed.go` + `feed/binance.go` + `broker/okx.go` + `broker/binance.go`

**修复**:
1. `config.go` 新增字段：`BinanceWSURL`, `OKXWSURL`, `BinanceAPIURL`, `OKXAPIURL`, `FutuHost`, `FutuPort`
2. 环境变量：`BINANCE_WS_URL`, `OKX_WS_URL`, `BINANCE_API_URL`, `OKX_API_URL`, `FUTU_HOST`, `FUTU_PORT`
3. 默认值使用原硬编码值
4. 修改 5 个文件使用 config 值
5. `go build ./... && go test ./... -count=1` 验证
6. Commit: `refactor: make broker/feed URLs configurable via env vars`

---

### Task 3.2 — Go 日志标准化（Go, P2）

**文件**: `broker/futu.go`, `market/store.go`, `market/feed/*.go`, `notify/manager.go`, `db/timescale.go`

**问题**: 广泛使用 `log.Printf` 而非结构化 `internal/log` Logger。

**修复**:
1. 不强制全部替换（工作量大），改为关键路径替换：
   - `market/store.go` — 数据保存失败：`log.Printf` → 注入 logger
   - `notify/manager.go` — 推送失败：`log.Printf` → 注入 logger
   - `market/feed/` — 重连日志：`log.Printf` → 注入 logger
2. 约 10 处关键 `log.Printf` → `logger.Warn(...)` 或 `logger.Error(...)`
3. `go build ./...` 验证
4. Commit: `refactor: use structured logger in critical paths`

---

### Task 3.3 — Go config/log 包测试（Go, P2）

**文件**: 新建 `services/go/internal/config/config_test.go`, `services/go/internal/log/logger_test.go`

**修复**:
1. `config_test.go` (4 tests):
   - `TestDefaultConfig` — 无环境变量时的默认值
   - `TestDevelopmentMode` — DEVELOPMENT=true 时允许默认 DB
   - `TestProductionRequiresDB` — 生产模式缺失 DATABASE_URL 报错
   - `TestEnvOverride` — 环境变量覆盖默认值
2. `logger_test.go` (4 tests):
   - `TestNewLogger` — 创建 logger 不 panic
   - `TestLogLevels` — Info/Warn/Error/Debug 正确输出
   - `TestEmptyMessage` — 空消息不 panic
   - `TestSpecialCharacters` — 特殊字符正确输出
3. `go test ./internal/config/ ./internal/log/ -v -count=1`
4. Commit: `test: config and logger package unit tests`

---

### Task 3.4 — Frontend 死代码清理（Frontend, P2）

**文件**: 删除 7 个未使用的 shadcn UI 组件

**修复**:
1. 删除 `components/ui/command.tsx`
2. 删除 `components/ui/input-group.tsx`
3. 删除 `components/ui/popover.tsx`
4. 删除 `components/ui/scroll-area.tsx`
5. 删除 `components/ui/separator.tsx`
6. 删除 `components/ui/tooltip.tsx`
7. 删除 `components/financial/SymbolSearch.tsx`
8. `npx next build` 验证无引用错误
9. Commit: `chore: remove unused shadcn UI components`

---

### Task 3.5 — vitest 配置 + npm audit（Frontend, P2）

**文件**: `frontend/vitest.config.ts`, `frontend/package.json`

**修复**:
1. `vitest.config.ts` 添加 exclude: `'e2e/**'`
2. `npm audit fix` 修复中低危漏洞
3. `npx vitest run` 验证 199 测试通过（无 e2e 误报）
4. Commit: `chore: exclude e2e from vitest, npm audit fix`

---

### Task 3.6 — Python 依赖升级（Python, P2）

**文件**: `services/python/pyproject.toml`

**修复**:
1. 升级 `langchain-core` → 先保持 0.3.x，记录为后续单独评估（1.x 有 breaking changes）
2. 升级 `protobuf` → 先保持 6.33.x，记录为后续单独评估（7.x 有 breaking changes）
3. 升级安全的次要/补丁版本：`numpy>=2.4,<2.5`、`pandas`、`pydantic` 等
4. `python -m pytest tests/ -v --no-header | tail -3` 验证无回归
5. Commit: `chore: bump safe minor/patch dependency versions`

---

## Wave 4 — 大规模重构（按需执行）

### Task 4.1 — Python gp_engine.py 拆分（Python, P2, 大工程）

**文件**: `services/python/src/factors/mining/gp_engine.py` (1800行)

**问题**: `GPEvolution` 类 1373 行，`run()` 函数 250 行。

**方案**: 拆分为 4 个模块（不改变外部 API）：
- `gp_engine.py` — 保留 `GPEvolution` 入口类，委托给子模块
- `gp_config.py` — `GPConfig` + `GPHyperparameters`
- `gp_operators.py` — `crossover()` / `mutate()` / `select_parents()` 
- `gp_evaluator.py` — `evaluate_population()` (已有 ProcessPoolExecutor)

**工作量**: 大（2-3 小时），建议单独安排。

---

### Task 4.2 — Python factor_atoms/output_nodes 拆分（Python, P2）

**文件**: `workflow/nodes/factor_atoms.py` (1121行), `output_nodes.py` (1055行)

**方案**: 按功能拆分为子模块：
- `workflow/nodes/atoms/` — 每个因子原子一个文件
- `workflow/nodes/outputs/` — 每个输出类型一个文件

**工作量**: 中（1-2 小时），建议单独安排。

---

## 执行顺序

```
Wave 1 (P0) ──► Wave 2 (P1) ──► Wave 3 (P2) ──► Wave 4 (重构，按需)
  3 tasks        5 tasks          6 tasks          2 tasks
```

- Wave 1 内部：Task 1.1 + 1.2（Go 可并行）+ Task 1.3（Python 独立）
- Wave 2 内部：Task 2.1-2.3（Go）+ Task 2.4-2.5（Python）可并行
- Wave 3 内部：Task 3.1-3.3（Go）+ Task 3.4-3.5（Frontend）+ Task 3.6（Python）可全部并行
- Wave 4 单独安排

---

## Task 数汇总

| Wave | 任务数 | Go | Python | Frontend | 工作量 |
|------|:---:|:---:|:---:|:---:|:---:|
| Wave 1 | 3 | 2 | 1 | 0 | 中 |
| Wave 2 | 5 | 3 | 2 | 0 | 中高 |
| Wave 3 | 6 | 3 | 1 | 2 | 中 |
| Wave 4 | 2 | 0 | 2 | 0 | 高（按需） |
| **总计** | **16** | **8** | **6** | **2** | — |
