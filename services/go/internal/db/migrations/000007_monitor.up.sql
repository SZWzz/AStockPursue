CREATE TABLE IF NOT EXISTS strategy_drift (
    id BIGSERIAL PRIMARY KEY,
    strategy_id INT NOT NULL,
    bar_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    live_cumulative_return DOUBLE PRECISION,
    backtest_expected_return DOUBLE PRECISION,
    drift_pct DOUBLE PRECISION,
    slippage_ratio DOUBLE PRECISION,
    max_drawdown_current DOUBLE PRECISION,
    max_drawdown_historical DOUBLE PRECISION,
    factor_ic_current DOUBLE PRECISION,
    factor_ic_days_below_threshold INT DEFAULT 0,
    alert_level TEXT NOT NULL DEFAULT 'OK'
);

CREATE INDEX IF NOT EXISTS idx_strategy_drift_strategy_time
    ON strategy_drift(strategy_id, bar_time DESC);

CREATE TABLE IF NOT EXISTS monitor_alerts (
    id BIGSERIAL PRIMARY KEY,
    strategy_id INT NOT NULL,
    alert_level TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_monitor_alerts_strategy_time
    ON monitor_alerts(strategy_id, created_at DESC);
