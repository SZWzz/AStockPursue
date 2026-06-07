-- 016_backtest_tags: add tags column and performance indexes to vt_backtest_runs
ALTER TABLE vt_backtest_runs ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_bt_runs_tags ON vt_backtest_runs USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_bt_runs_sharpe ON vt_backtest_runs((metrics->>'sharpe_ratio'));
