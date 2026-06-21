CREATE TABLE IF NOT EXISTS bars (
    symbol     TEXT NOT NULL,
    timestamp  TIMESTAMPTZ NOT NULL,
    open       DOUBLE PRECISION NOT NULL,
    high       DOUBLE PRECISION NOT NULL,
    low        DOUBLE PRECISION NOT NULL,
    close      DOUBLE PRECISION NOT NULL,
    volume     BIGINT NOT NULL,
    frequency  TEXT NOT NULL DEFAULT '1d',
    PRIMARY KEY (symbol, timestamp, frequency)
);

SELECT create_hypertable('bars', 'timestamp', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id              UUID PRIMARY KEY,
    symbols         TEXT[] NOT NULL,
    frequency       TEXT NOT NULL DEFAULT '1d',
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    initial_cash    DOUBLE PRECISION NOT NULL,
    final_equity    DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_return    DOUBLE PRECISION NOT NULL DEFAULT 0,
    sharpe_ratio    DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown    DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    win_rate        DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_trades    INT NOT NULL DEFAULT 0,
    winning_trades  INT NOT NULL DEFAULT 0,
    losing_trades   INT NOT NULL DEFAULT 0,
    signal_name     TEXT,
    risk_config     JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS equity_curves (
    run_id          UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    timestamp       TIMESTAMPTZ NOT NULL,
    equity          DOUBLE PRECISION NOT NULL,
    cash            DOUBLE PRECISION NOT NULL,
    position_count  INT NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, timestamp)
);

SELECT create_hypertable('equity_curves', 'timestamp', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS trades (
    id          UUID PRIMARY KEY,
    run_id      UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    quantity    DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION NOT NULL,
    commission  DOUBLE PRECISION NOT NULL DEFAULT 0,
    pnl         DOUBLE PRECISION,
    timestamp   TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id);

CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
