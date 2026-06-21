# Backend Persistence & Real Operations Spec

**Date:** 2026-06-21
**Status:** Draft
**Trigger:** Audit found 14 handler methods using in-memory storage + 7 stub/placeholder implementations

## 1. Problem Statement

Frontend has 29 fully-featured pages with forms, tables, and actions. Backend has corresponding endpoints, but many store data only in memory (lost on restart) or return hardcoded/placeholder results. The gap between UI polish and backend reality is the largest remaining issue.

## 2. Affected Handlers (by severity)

### 🔴 CRITICAL — Stub returns (7 items)

| # | Handler | Method | Current Behavior | Fix |
|---|---------|--------|-----------------|-----|
| C1 | broker.go | Connect | Returns status immediately, no connection | Read broker config, attempt real connection via `broker.New()` |
| C2 | broker.go | Disconnect | Returns status immediately, no cleanup | Call broker.Close() if connected |
| C3 | broker.go | SaveCredentials | Discards input | Store to `user_settings` JSONB column |
| C4 | analysis.go | StressTest | Returns input pct as output | Load portfolio positions, calculate per-position impact |
| C5 | analysis.go | Attribution | Returns "coming soon" text | Wire to Python gRPC attribution_engine |
| C6 | ml.go | TrainModel | Sets status only, never trains | Launch async goroutine, call Python ML pipeline via gRPC |
| C7 | factor.go | ListFactors | Returns 2 hardcoded entries | Query Python factor registry via gRPC |

### 🟡 MAJOR — In-memory only, lost on restart (7 items)

| # | Handler | What's in memory | PG Table Needed |
|---|---------|-----------------|-----------------|
| M1 | signal.go | signals slice | `signals (id, type, symbol, direction, strength, source, status, created_at, user_id)` |
| M2 | workflow.go | store slice | `workflows (id, name, nodes JSONB, edges JSONB, created_at, updated_at, user_id)` |
| M3 | scheduler.go | jobs map | `scheduled_jobs (id, name, type, cron, config JSONB, status, last_run, next_run)` — already partly in Go struct, persist to PG |
| M4 | settings.go | settings map | `user_settings (user_id, settings JSONB, updated_at)` — already spec'd, need to implement |
| M5 | backtest.go | MemoryBacktestStore | `backtest_runs` table exists, wire the save/get/list through PG |
| M6 | papertrade | Engine in memory | `paper_trading_runs` — persist runs + wire to Python shadow account |
| M7 | factor.go | factor results | `factor_results` — persist computed factors |

### 🟢 MINOR — Wire-up gaps (3 items)

| # | Issue | Fix |
|---|-------|-----|
| L1 | Settings page 5 test-connection buttons are fake | Add real POST endpoints: `/api/v1/data-sources/test`, `/api/v1/llm/test`, `/api/v1/notifications/test-telegram`, `/api/v1/notifications/test-email` |
| L2 | Market ListSymbols hardcoded | Query data store for available symbols |
| L3 | System version hardcoded "0.1.0" | Read from VERSION file at startup |

## 3. Database Schema

### 3a. New Tables

```sql
-- Signals table (M1)
CREATE TABLE IF NOT EXISTS signals (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES vt_users(id),
    type        VARCHAR(32) NOT NULL,
    symbol      VARCHAR(32) NOT NULL,
    direction   VARCHAR(8) NOT NULL DEFAULT 'buy',
    strength    DOUBLE PRECISION DEFAULT 0,
    source      VARCHAR(64) DEFAULT '',
    status      VARCHAR(16) DEFAULT 'new',
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Workflows table (M2)
CREATE TABLE IF NOT EXISTS workflows (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES vt_users(id),
    name        VARCHAR(128) NOT NULL,
    nodes       JSONB DEFAULT '[]',
    edges       JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Scheduled jobs table (M3)
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES vt_users(id),
    name        VARCHAR(128) NOT NULL,
    job_type    VARCHAR(32) NOT NULL DEFAULT 'backtest',
    cron_expr   VARCHAR(64) NOT NULL,
    config      JSONB DEFAULT '{}',
    status      VARCHAR(16) DEFAULT 'pending',
    last_run    TIMESTAMPTZ,
    next_run    TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- User settings (M4)
CREATE TABLE IF NOT EXISTS user_settings (
    user_id     INTEGER PRIMARY KEY REFERENCES vt_users(id),
    settings    JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Factor results (M7)
CREATE TABLE IF NOT EXISTS factor_results (
    id          SERIAL PRIMARY KEY,
    factor_name VARCHAR(64) NOT NULL,
    symbol      VARCHAR(32) NOT NULL,
    value       DOUBLE PRECISION,
    computed_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(factor_name, symbol, computed_at)
);
```

### 3b. Existing Tables to Wire

- `backtest_runs` — already exists, wire MemoryBacktestStore → PG
- `equity_curves` — existing TimescaleDB hypertable
- `trades` — existing table
- `paper_trading_runs` — check if exists, create if not

## 4. Test Connection Endpoints (L1)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/data-sources/test` | Accept `{provider, api_key}`, ping the provider's API |
| `POST /api/v1/llm/test` | Accept `{provider, model, api_key, base_url}`, send a simple prompt, return latency |
| `POST /api/v1/notifications/test-telegram` | Accept `{bot_token, chat_id}`, send test message |
| `POST /api/v1/notifications/test-email` | Accept `{smtp_host, smtp_port, username, password, from, to}`, send test email |

Each returns `{success: true, latency_ms: N}` or `{success: false, error: "..."}`.

## 5. Implementation Phases

### Phase A — PG Persistence (biggest impact)
- M1-M7: Convert all in-memory stores to PG repositories
- Create repository interfaces and PG implementations
- Update main.go wire-up to pass db pool

### Phase B — Real Operations
- C1-C3: Real broker connect/disconnect/credentials
- C4-C5: Real stress test and attribution  
- C6: Real ML training trigger
- C7: Real factor list from Python gRPC

### Phase C — Polish
- L1: Real test connection buttons
- L2: Dynamic symbol list
- L3: Version from file

## 6. Estimated Effort

| Phase | Items | Est. Days |
|-------|-------|-----------|
| Phase A — PG Persistence | 7 handlers | 4 |
| Phase B — Real Operations | 7 handlers | 4 |
| Phase C — Polish | 3 items | 1 |
| **Total** | **17 items** | **9 days** |
