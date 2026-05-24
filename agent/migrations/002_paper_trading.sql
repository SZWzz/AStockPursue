-- ============================================================================
-- Paper Trading Schema (AStockPursue v5.1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_papertrading_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER DEFAULT 1,
    run_name        TEXT NOT NULL,
    market          TEXT NOT NULL DEFAULT 'a_share',
    status          TEXT DEFAULT 'stopped',
    config          JSONB DEFAULT '{}',
    risk_config     JSONB DEFAULT '{}',
    strategy_code   TEXT NOT NULL,
    tick_mode       BOOLEAN DEFAULT FALSE,
    state           TEXT DEFAULT 'flat',
    current_capital DOUBLE PRECISION DEFAULT 0,
    start_time      TIMESTAMPTZ,
    last_bar_time   TIMESTAMPTZ,
    error_message   TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pt_runs_user ON vt_papertrading_runs(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS vt_papertrading_equity (
    id              SERIAL PRIMARY KEY,
    run_id          UUID REFERENCES vt_papertrading_runs(id) ON DELETE CASCADE,
    point_time      TIMESTAMPTZ NOT NULL,
    equity          DOUBLE PRECISION NOT NULL,
    capital         DOUBLE PRECISION NOT NULL,
    unrealized      DOUBLE PRECISION DEFAULT 0,
    drawdown        DOUBLE PRECISION DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pt_equity_run ON vt_papertrading_equity(run_id, point_time);

CREATE TABLE IF NOT EXISTS vt_papertrading_positions (
    id              SERIAL PRIMARY KEY,
    run_id          UUID REFERENCES vt_papertrading_runs(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    direction       INTEGER NOT NULL,
    entry_price     DOUBLE PRECISION NOT NULL,
    entry_time      TIMESTAMPTZ NOT NULL,
    size            DOUBLE PRECISION NOT NULL,
    leverage        DOUBLE PRECISION DEFAULT 1.0,
    entry_commission DOUBLE PRECISION DEFAULT 0,
    UNIQUE(run_id, symbol)
);

CREATE TABLE IF NOT EXISTS vt_papertrading_trades (
    id              SERIAL PRIMARY KEY,
    run_id          UUID REFERENCES vt_papertrading_runs(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    direction       INTEGER NOT NULL,
    entry_price     DOUBLE PRECISION NOT NULL,
    exit_price      DOUBLE PRECISION NOT NULL,
    entry_time      TIMESTAMPTZ NOT NULL,
    exit_time       TIMESTAMPTZ NOT NULL,
    size            DOUBLE PRECISION NOT NULL,
    leverage        DOUBLE PRECISION DEFAULT 1.0,
    pnl             DOUBLE PRECISION NOT NULL,
    pnl_pct         DOUBLE PRECISION NOT NULL,
    exit_reason     TEXT NOT NULL,
    holding_bars    INTEGER DEFAULT 0,
    commission      DOUBLE PRECISION DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pt_trades_run ON vt_papertrading_trades(run_id);
