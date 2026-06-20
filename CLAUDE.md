# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **New to the project?** See `docs/` for user-facing documentation: [architecture.md](docs/architecture.md), [getting-started.md](docs/getting-started.md), [testing.md](docs/testing.md).

## Build, Test, and Run Commands

```bash
# Full deploy
docker compose up -d --build              # Go core (8899) + Python (8900/8902)
docker compose --profile pg up -d --build # also auto-deploy PostgreSQL
docker compose --profile frontend up -d   # frontend dev server (5899)

# Go core dev
cd services/go && go run ./cmd/server     # HTTP API + gRPC

# Python research layer dev
cd services/python && pip install -r requirements.txt
python mcp_server.py                      # MCP (stdio/SSE, port 8900)
python -m src.grpc.server                 # gRPC server (port 8902)

# Frontend dev
cd frontend && npm run dev

# Tests
cd services/go && go test ./...           # Go unit tests
cd services/python && python -m pytest tests/ -x -q # Python tests
cd frontend && npx vitest                 # Frontend tests
```

## Architecture (Go + Python Hybrid)

```
┌─ Frontend (Next.js, port 5899) ───────────────────────────┐
│  SSR pages → API Routes → REST (Go core)                  │
└───────────────────────────────────────────────────────────┘
                              │ HTTP JSON
┌─ Go Core Services (port 8899) ────────────────────────────┐
│  ├─ HTTP API (gin) — trading, backtest, auth, market      │
│  ├─ Trading Engine — on_bar() pipeline, 7 engine types    │
│  ├─ Market Data — 32 loaders, 3-tier store, WS feed       │
│  ├─ Broker Gateways — Binance, Futu, OKX                  │
│  ├─ Portfolio/Risk — sizing, margin, stop-loss            │
│  └─ gRPC Client → Python Research Layer                   │
└───────────────────────────────────────────────────────────┘
                              │ gRPC + Protobuf
┌─ Python Research Layer (port 8900/8902) ──────────────────┐
│  ├─ MCP Server — 22 tools, 89 skills, swarm presets       │
│  ├─ Factor Mining — GP evolution, 452 alpha zoo           │
│  ├─ AI Agent — LLM agent, langgraph loop, memory          │
│  ├─ Analysis — attribution, sentiment, correlation        │
│  ├─ Workflow Engine — 25 node types, visual pipeline      │
│  └─ gRPC Server — factor, signal, LLM, analysis services  │
└───────────────────────────────────────────────────────────┘
                              │ SQL + Pub/Sub
┌─ Data Layer ──────────────────────────────────────────────┐
│  PostgreSQL 16 + TimescaleDB (时序) + Redis 7 (缓存)      │
└───────────────────────────────────────────────────────────┘
```

### Core Pipeline: `TradingEngine.on_bar()`

The unified engine (Go) processes every bar through the same pipeline for both backtest and live trading:

```
on_bar(bar, ts)  [Go]
  ├─ 0a. Gap detection (overnight stop/trailing/target checks on open positions)
  ├─ 0b. Suspension detection (flat close + zero vol for ≥2 bars → force-close)
  ├─ 0.5 Market hooks (funding fees, liquidation — per-market)
  ├─ 1. SignalAdapter → gRPC call Python → target weights
  ├─ 1.5 OptimizerAdapter → adjusted weights (optional, Go)
  ├─ 2. RiskPipeline → forced exits (stop-loss / trailing-stop / take-profit)
  ├─ 3. Process signals → open/close positions (OMS)
  └─ 4. Record equity snapshot
```

**Critical ordering constraint**: `RecordBars()` MUST run AFTER `GenerateSignals()` to prevent look-ahead bias. `equity_for_sizing` MUST be cached BEFORE `CheckRiskExits()` (which updates last-bar prices with today's close).

Key files: `services/go/internal/engine/pipeline.go`, `services/go/internal/engine/risk.go`, `services/go/internal/engine/signal.go`

### SignalAdapter Flow

**Go side**: `SignalAdapter` in Go calls Python via gRPC:
- **Tick mode**: Go streams each `OnBar` → Python returns `weights` in streaming response
- **Batch mode**: Go sends window of bars → Python's strategy `generate()` computes, returns weights for `iloc[-1]`

Protobuf: `services/proto/signal.proto` → `SignalService`

### Engine Hierarchy (Go)

```
Engine (interface in services/go/internal/engine/)
  ├─ ChinaAEngine      — A-share: T+1, price limits, stamp duty
  ├─ CryptoEngine      — perpetuals: funding rate, liquidation
  ├─ GlobalEquityEngine— US/HK markets
  ├─ ForexEngine       — FX spot/CFD
  ├─ FuturesBase       — contract multiplier awareness
  │   ├─ ChinaFuturesEngine  — CFFEX/SHFE/DCE/ZCE/INE/GFEX
  │   └─ GlobalFuturesEngine — CME/ICE/Eurex
  ├─ OptionsEngine     — European/American via Black-Scholes
  └─ CompositeEngine   — cross-market with shared capital pool
```

Each engine implements the `Engine` interface: `CanExecute()`, `RoundSize()`, `CalcCommission()`, `ApplySlippage()`, `CalcMargin()`, `CalcPnL()`.

### Data Loading: 3-Tier Access + Fallback Chains (Go)

```
DataStore (services/go/internal/market/store.go)
  ├─ Tier 1: TimescaleDB
  ├─ Tier 2: Parquet local store
  └─ Tier 3: Loader API (live fetch, concurrent goroutine fallback)
```

A-share 8-source fallback (Go goroutines for concurrent fallback):
`mootdx → tushare → eastmoney → tencent → futu → baidu → twelvedata → akshare`

Loaders implement `Loader` interface and self-register. `IsAvailable()` must do a real connectivity check.

Key files: `services/go/internal/market/loader/`, `services/go/internal/market/store.go`

### Factor Mining System

```
ExpressionTree (single source of truth)
  ├─ formula_hash (SHA256 of canonical form)
  ├─ normalized_formula (canonical string)
  ├─ to_callable() → compute_fn(panel) → DataFrame
  └─ to_formula() → display string (non-canonical — use formula_hash for identity)

GPEvolution (gp_engine.py)
  ├─ Hybrid init: 30% skeletons + 40% mutations + 30% random
  ├─ Composite fitness: IC × cost × orthogonality × A-share × stability × complexity
  ├─ Tiered operators: basic → advanced → alternative (progressive unlock)
  ├─ FDR correction every generation (BY preferred over BH for correlated tests)
  ├─ Walk-forward OOS IC via rolling non-overlapping windows
  └─ Thread-safe KB access (self._kb_lock for parallel evaluation)

FactorKnowledgeBase (factor_kb.py)
  ├─ SHA256 formula_hash dedup
  ├─ Lifecycle: discovered → validating → approved → paper_trading → production → deprecated → archived
  └─ pgvector semantic search (embeddings must be written by save_entry)

SafetyValidator (safety_validator.py)
  ├─ Layer 1: AST operator whitelist
  ├─ Layer 2: Type/arity validation per operator
  └─ Layer 3: RuntimeCircuitBreaker (512MB/30s) — uses threading, not SIGALRM
```

**Key rule**: Always use `ind.tree.formula_hash` for identity, never `ind.formula` (display string varies with operand order for commutative ops).

Key files: `services/python/src/factors/mining/`, `services/python/src/factors/registry.py`

### Frontend State Management

Zustand stores: `agent.ts`, `auth.ts`, `paperTradingStore.ts`, `tradingStore.ts`, `factorMiningStore.ts`, `schedulerStore.ts`, `screenerStore.ts`, `sentimentStore.ts`, `attributionStore.ts`

i18n: `useI18n()` hook → `t.keyName`. Add keys to both `en` and `zh` in `lib/i18n.tsx`. Direction-specific colors use `text-up`/`text-down` (auto-swaps red/green for zh locale).

Charts: Recharts + D3 via custom financial chart components. CodeMirror 6 for code editing.

### Skills System

89 skill packs under `services/python/src/skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`, `category`). Auto-discovered on server start. Each skill can include `example_signal_engine.py`, `references/`, `scripts/`. Skills are the AI agent's domain knowledge — they guide LLM behavior for specific trading topics.

### Multi-User Isolation

Per-user: orders (PG `user_id` FK), broker context (independent FutuOpenD cache), WS subscriptions, notify/indices/optimize config. JWT auth with PBKDF2 password hashing.

## Development Rules

### Spec → Plan → Test → Development Flow

**Before writing ANY code, the following three artifacts MUST be completed and reviewed in order:**

1. **Spec** — design document saved to `docs/superpowers/specs/`
2. **Plan** — implementation plan with phases and milestones, saved to `docs/superpowers/plans/`
3. **Test cases** — test specification listing all test cases, edge cases, and expected outputs

Only after all three are reviewed by the user and explicitly approved may implementation begin.

Any modification that touches engine logic, financial calculations, or data pipelines must follow this flow. Trivial changes (typos, CSS, config) may skip with user consent.

### Go 实现后删除 Python 旧代码

**当 Go 端实现了 Python 端已有的功能模块后，必须删除 Python 端的对应代码**，保证项目脉络清晰、代码无冗余。

具体对应关系（来自重构规范 `docs/superpowers/specs/2026-06-20-go-python-hybrid-refactoring-design.md` 第 2.2 节）：

| Go 实现 | Python 删除 |
|---------|------------|
| `services/go/internal/engine/` | `services/python/backtest/engines/` |
| `services/go/internal/market/loader/` | `services/python/backtest/loaders/` |
| `services/go/internal/market/store.go` | `services/python/backtest/loaders/store.py` |
| `services/go/internal/engine/risk.go` | `services/python/src/trading/risk_pipeline.py` |
| `services/go/internal/api/handler/` | `services/python/src/api/` 对应 route |
| `services/go/internal/engine/pipeline.go` | `services/python/src/trading/engine.py` |
| `services/go/internal/broker/` | `services/python/src/trading/brokers/` |
| `services/go/internal/papertrade/` | `services/python/papertrade/` |

删除前必须满足：
- Go 端实现**功能完整**（测试覆盖、与 Python 输出回归比对通过）
- 所有调用方已切换到 Go 端
- CHANGELOG 记录删除

### Version Date Check

**Before every commit and push, verify that the project version matches the current date.**  The version is defined in three places and must be kept in sync:

1. `frontend/src/components/layout/Layout.tsx` — `APP_VERSION` (format: `vYYYY.M.D`)
2. `README.md` — version badge in the top badge strip
3. `README_zh.md` — version badge in the top badge strip

Update all three to match today's date if stale.  For example, if today is 2026-06-03, the version should be `v2026.6.3`.

```
APP_VERSION = "v2026.6.20"   // <-- update before commit if today's date doesn't match
README.md badge:             Version-v2026.6.20-blueviolet
README_zh.md badge:          版本-v2026.6.20-blueviolet
```

This ensures the version number reflects when the code was actually shipped.

### Changelog Maintenance

**Every change must be recorded in `CHANGELOG.md`.**  This is non-negotiable.  The changelog follows [Keep a Changelog](https://keepachangelog.com/) conventions:

- `### Added` — new features, capabilities, files
- `### Changed` — changes to existing functionality
- `### Fixed` — bug fixes (reference the defect ID where applicable, e.g., P0-1)
- `### Removed` — deprecated or removed features

Each entry should include the scope (e.g., `[Engine]`, `[FactorMining]`, `[Frontend]`, `[Docs]`) and a concise description of what changed and why.  Group related changes under a version header with the date: `## [YYYY.M.D] - YYYY-MM-DD`.

### Documentation Requirements

**Critical implementation code MUST carry documentation.**  "Critical" means:

1. **Security boundaries** — AST sandboxes, code validators, input sanitizers, auth flows
2. **Financial correctness** — P&L calculations, position sizing, commission/slippage models, price-limit logic
3. **Data integrity** — look-ahead bias prevention, data alignment, survivorship-bias guards
4. **Concurrency** — thread-safe access, parallel evaluation, shared mutable state
5. **Algorithmic complexity** — GP evolution, factor evaluation, FDR correction, walk-forward windows

Minimum documentation for critical code:

- **Module-level docstring**: Purpose, key abstractions, and cross-references to related modules
- **Class docstring**: Role in the architecture, ownership of state, lifecycle
- **Public/private method docstrings**: One-line summary + `Args`/`Returns` for any method with non-trivial logic
- **Inline comments**: Explain *why* for non-obvious decisions, especially ordering constraints, magic numbers, and workarounds

Non-critical code (simple CRUD, data transformation, route wiring) should have at minimum a one-line docstring describing intent.

## Known Defect History

This codebase has undergone 5 rounds of P0-P3 defect fixes (see git log `39c4294` through `1f24383`). Key patterns to avoid reintroducing:

- **Look-ahead bias**: Never let `_data_map` include the current bar before `_generate_signals()` runs. Cache `equity_for_sizing` before risk exits update `_last_bar_prices`.
- **Thread safety**: All KB access during parallel GP evaluation must hold `self._kb_lock`.
- **Column alignment**: `np.where()` with `.values` loses column labels — use `_safe_if_else()` instead.
- **KB provenance**: Check `data_source_version` and `train_date_range` before reusing cached KB metrics.
- **FDR correction**: Use Benjamini-Yekutieli (BY) for correlated GP candidates, not BH. Non-overlapping walk-forward windows ensure OOS IC independence.
- **Commission rates**: A-share is 3 bps per side (万三), not 0.3 bps. Double-check all cost constants.
- **Intraday timestamps**: Use `pd.infer_freq()` not `Timedelta(days=1)` for bar timestamp inference.
- **SIGALRM**: Only works on Unix main thread. Use `threading.Thread + join(timeout)` for circuit breakers.

See `CHANGELOG.md` for the full defect fix history.
