-- 018_trade_fields: add entry_price, exit_price, size, exit_reason to vt_backtest_trades
ALTER TABLE vt_backtest_trades ADD COLUMN IF NOT EXISTS entry_price DOUBLE PRECISION;
ALTER TABLE vt_backtest_trades ADD COLUMN IF NOT EXISTS exit_price  DOUBLE PRECISION;
ALTER TABLE vt_backtest_trades ADD COLUMN IF NOT EXISTS size        DOUBLE PRECISION DEFAULT 0;
ALTER TABLE vt_backtest_trades ADD COLUMN IF NOT EXISTS exit_reason TEXT DEFAULT '';
