# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build, Test, and Run Commands

```bash
# Full deploy
docker compose up -d --build              # backend (8899) + MCP (8900)
docker compose --profile pg up -d --build # also auto-deploy PostgreSQL
docker compose --profile frontend up -d   # frontend dev server (5899)

# Backend dev
cd agent && pip install -r requirements.txt
cp .env.example .env
python api_server.py --port 8899          # FastAPI server
python mcp_server.py                      # MCP (stdio)
python mcp_server.py --transport sse      # MCP (SSE, port 8900)

# Frontend dev
cd frontend && npm install && npx vite --port 5899

# Tests
cd frontend && npx tsc --noEmit           # TypeScript type-check
cd agent && python -m pytest tests/ -x -q # backend tests
```

## Architecture

### Core Pipeline: `TradingEngine.on_bar()`

The unified engine processes every bar through the same pipeline for both backtest and live trading:

```
on_bar(bar, ts)
  ├─ 0a. Gap detection (overnight stop/trailing/target checks on open positions)
  ├─ 0b. Suspension detection (flat close + zero vol for ≥2 bars → force-close)
  ├─ 0.5 Market hooks (funding fees, liquidation — per-market)
  ├─ 1. SignalAdapter → target weights (tick mode or batch generate())
  ├─ 1.5 OptimizerAdapter → adjusted weights (optional)
  ├─ 2. RiskPipeline → forced exits (stop-loss / trailing-stop / take-profit)
  ├─ 3. Process signals → open/close positions
  └─ 4. Record equity snapshot
```

**Critical ordering constraint**: `_record_bars()` MUST run AFTER `_generate_signals()` to prevent look-ahead bias. `equity_for_sizing` MUST be cached BEFORE `_check_risk_exits()` (which updates `_last_bar_prices` with today's close).

Key files: `agent/src/trading/engine.py`, `agent/src/trading/risk_pipeline.py`, `agent/src/trading/signal_adapter.py`

### SignalAdapter Dispatch

The `SignalAdapter` auto-detects the strategy's capability:
- **Tick mode** (`TickHandler` protocol): `on_bar(bar, state)` called per bar — O(n)
- **Batch mode** (fallback): `generate(data_map)` computes from the full history, then the adapter extracts `iloc[-1]`. The strategy NEVER sees the current bar (look-ahead prevention).

### Backtest Engine Hierarchy

```
BaseEngine (base.py)
  ├─ ChinaAEngine (china_a.py)      — A-share: T+1, price limits, stamp duty
  ├─ GlobalEquityEngine              — US/HK markets
  ├─ CryptoEngine (crypto.py)       — perpetuals: funding rate, liquidation
  ├─ ForexEngine (forex.py)          — FX spot/CFD
  ├─ FuturesBase (futures_base.py)   — contract multiplier awareness
  │   ├─ ChinaFuturesEngine          — CFFEX/SHFE/DCE/ZCE/INE/GFEX
  │   └─ GlobalFuturesEngine         — CME/ICE/Eurex
  ├─ OptionsPortfolioEngine          — European/American via Black-Scholes
  └─ CompositeEngine (composite.py)  — cross-market with shared capital pool
```

Each engine overrides market-rule methods: `can_execute()`, `round_size()`, `calc_commission()`, `apply_slippage()`, `_calc_margin()`, `_calc_pnl()`.

### Data Loading: 3-Tier Access + Fallback Chains

```
DataStore (data_store.py)
  ├─ Tier 1: PostgreSQL cache
  ├─ Tier 2: Parquet local store
  └─ Tier 3: Loader API (live fetch)
```

A-share 8-source fallback: `mootdx → tushare → eastmoney → tencent → futu → baidu → twelvedata → akshare`

Loaders self-register via `@register` decorator. `is_available()` must do a real connectivity check (not just `import requests`).

Key files: `agent/backtest/data_store.py`, `agent/backtest/loaders/`

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

Key files: `agent/src/factors/mining/`, `agent/src/factors/registry.py`

### Frontend State Management

Zustand stores: `agent.ts`, `auth.ts`, `paperTradingStore.ts`, `tradingStore.ts`, `factorMiningStore.ts`, `schedulerStore.ts`, `screenerStore.ts`, `sentimentStore.ts`, `attributionStore.ts`

i18n: `useI18n()` hook → `t.keyName`. Add keys to both `en` and `zh` in `lib/i18n.tsx`. Direction-specific colors use `text-up`/`text-down` (auto-swaps red/green for zh locale).

Charts: ECharts via `CandlestickChart` / `EquityChart` components. Monaco Editor for code editing.

### Skills System

89 skill packs under `agent/src/skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`, `category`). Auto-discovered on server start. Each skill can include `example_signal_engine.py`, `references/`, `scripts/`. Skills are the AI agent's domain knowledge — they guide LLM behavior for specific trading topics.

### Multi-User Isolation

Per-user: orders (PG `user_id` FK), broker context (independent FutuOpenD cache), WS subscriptions, notify/indices/optimize config. JWT auth with PBKDF2 password hashing.

## Development Rules

### Version Date Check

**Before every commit and push, verify that the project version matches the current date.**  The version is defined in three places and must be kept in sync:

1. `frontend/src/components/layout/Layout.tsx` — `APP_VERSION` (format: `vYYYY.M.D`)
2. `README.md` — version badge in the top badge strip
3. `README_zh.md` — version badge in the top badge strip

Update all three to match today's date if stale.  For example, if today is 2026-06-03, the version should be `v2026.6.3`.

```
APP_VERSION = "v2026.6.3"   // <-- update before commit if today's date doesn't match
README.md badge:             Version-v2026.6.3-blueviolet
README_zh.md badge:          版本-v2026.6.3-blueviolet
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

Detailed analysis in `13-核心缺陷分析.md`.
