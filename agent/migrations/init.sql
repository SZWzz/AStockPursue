-- ============================================================================
-- vibe-Research PostgreSQL Schema (idempotent: CREATE TABLE IF NOT EXISTS)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Users & Auth (Phase 4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_users (
    id              SERIAL PRIMARY KEY,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL DEFAULT '',
    email           TEXT UNIQUE,
    role            TEXT DEFAULT 'user',
    token_version   INTEGER DEFAULT 1,
    llm_config      JSONB DEFAULT '{}',
    data_source_config JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 2. Sessions (Phase 3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_sessions (
    id              TEXT PRIMARY KEY,
    user_id         INTEGER DEFAULT 1,
    title           TEXT DEFAULT '',
    status          TEXT DEFAULT 'active',
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 3. Messages (Phase 3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_messages (
    id              TEXT PRIMARY KEY,
    session_id      TEXT REFERENCES vt_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    linked_attempt_id TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON vt_messages(session_id, created_at);
-- Full-text search index for message content
CREATE INDEX IF NOT EXISTS idx_messages_fts ON vt_messages USING GIN (to_tsvector('english', content));

-- ---------------------------------------------------------------------------
-- 4. Attempts (Phase 3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_attempts (
    id              TEXT PRIMARY KEY,
    session_id      TEXT REFERENCES vt_sessions(id) ON DELETE CASCADE,
    parent_attempt_id TEXT,
    status          TEXT DEFAULT 'pending',
    prompt          TEXT,
    run_dir         TEXT,
    summary         TEXT,
    react_trace     JSONB DEFAULT '[]',
    metrics         JSONB DEFAULT '{}',
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_attempts_session ON vt_attempts(session_id, created_at);

-- ---------------------------------------------------------------------------
-- 5. Backtest Runs (Phase 2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_backtest_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER DEFAULT 1,
    run_name        TEXT DEFAULT '',
    run_type        TEXT DEFAULT 'strategy',
    config          JSONB DEFAULT '{}',
    metrics         JSONB DEFAULT '{}',
    status          TEXT DEFAULT 'success',
    error_message   TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_user ON vt_backtest_runs(user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 6. Backtest Equity (Phase 2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_backtest_equity (
    id              SERIAL PRIMARY KEY,
    run_id          UUID REFERENCES vt_backtest_runs(id) ON DELETE CASCADE,
    point_time      TIMESTAMPTZ,
    equity          DOUBLE PRECISION,
    drawdown        DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_equity_run ON vt_backtest_equity(run_id);

-- ---------------------------------------------------------------------------
-- 7. Backtest Trades (Phase 2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_backtest_trades (
    id              SERIAL PRIMARY KEY,
    run_id          UUID REFERENCES vt_backtest_runs(id) ON DELETE CASCADE,
    symbol          TEXT,
    entry_time      TIMESTAMPTZ,
    exit_time       TIMESTAMPTZ,
    side            TEXT,
    pnl             DOUBLE PRECISION,
    return_pct      DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_trades_run ON vt_backtest_trades(run_id);

-- ---------------------------------------------------------------------------
-- 8. Indicators (Phase 4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_indicators (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES vt_users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    code            TEXT NOT NULL,
    params          JSONB DEFAULT '[]',
    strategy_config JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_indicators_user ON vt_indicators(user_id);

-- ---------------------------------------------------------------------------
-- 9. Strategies (Phase 4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_strategies (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES vt_users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    code            TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_strategies_user ON vt_strategies(user_id);

-- ---------------------------------------------------------------------------
-- 10. Watchlist (user-curated symbols)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_watchlist (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES vt_users(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    name            TEXT DEFAULT '',
    market          TEXT DEFAULT '',
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, symbol)
);

-- ---------------------------------------------------------------------------
-- 11. Indicator Versions (Phase 4, replaces git versioning)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vt_indicator_versions (
    id              SERIAL PRIMARY KEY,
    indicator_id    INTEGER REFERENCES vt_indicators(id) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    change_message  TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_indicator_versions ON vt_indicator_versions(indicator_id);
