CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER DEFAULT 1,
    type VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    direction VARCHAR(8) DEFAULT 'buy',
    strength DOUBLE PRECISION DEFAULT 0,
    source VARCHAR(64) DEFAULT '',
    status VARCHAR(16) DEFAULT 'new',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflows (
    id SERIAL PRIMARY KEY,
    user_id INTEGER DEFAULT 1,
    name VARCHAR(128) NOT NULL,
    nodes JSONB DEFAULT '[]',
    edges JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER DEFAULT 1,
    name VARCHAR(128) NOT NULL,
    job_type VARCHAR(32) DEFAULT 'backtest',
    cron_expr VARCHAR(64) NOT NULL,
    config JSONB DEFAULT '{}',
    status VARCHAR(16) DEFAULT 'pending',
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY DEFAULT 1,
    settings JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS paper_trading_runs (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128),
    strategy VARCHAR(64),
    status VARCHAR(16),
    initial_capital DOUBLE PRECISION,
    equity DOUBLE PRECISION,
    pnl DOUBLE PRECISION,
    pnl_pct DOUBLE PRECISION,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS factor_results (
    id SERIAL PRIMARY KEY,
    factor_name VARCHAR(128) NOT NULL,
    symbol VARCHAR(32),
    value DOUBLE PRECISION,
    ic DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    status VARCHAR(32) DEFAULT 'production',
    computed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_factor_results_name ON factor_results(factor_name);
