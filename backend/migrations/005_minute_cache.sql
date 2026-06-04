-- 005_minute_cache.sql
-- Minute-line cache (分时图).  Applied automatically by init_database() on startup.

CREATE TABLE IF NOT EXISTS minute_line_cache (
    code       VARCHAR(16) NOT NULL,
    trade_date DATE        NOT NULL,
    bar_time   VARCHAR(5)  NOT NULL,   -- HH:MM
    price      DOUBLE PRECISION NOT NULL,
    volume     DOUBLE PRECISION DEFAULT 0,
    amount     DOUBLE PRECISION DEFAULT 0,
    updated_at TIMESTAMPTZ  DEFAULT NOW(),
    PRIMARY KEY (code, trade_date, bar_time)
);

CREATE INDEX IF NOT EXISTS idx_minute_code_date
    ON minute_line_cache(code, trade_date);
