-- 017_backtest_ohlcv: store OHLCV bars per run for K-line chart
CREATE TABLE IF NOT EXISTS vt_backtest_ohlcv (
    id              SERIAL PRIMARY KEY,
    run_id          UUID REFERENCES vt_backtest_runs(id) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    bar_time        TIMESTAMPTZ NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    volume          DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_run_code ON vt_backtest_ohlcv(run_id, code);
CREATE INDEX IF NOT EXISTS idx_ohlcv_run_time ON vt_backtest_ohlcv(run_id, bar_time);
