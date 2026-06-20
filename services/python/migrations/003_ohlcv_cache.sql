-- 003_ohlcv_cache.sql
-- K-line cache for OHLCV data (market data caching layer).
-- Applied automatically by init_database() on startup.

CREATE TABLE IF NOT EXISTS ohlcv_cache (
    code       VARCHAR(16) NOT NULL,
    interval   VARCHAR(8)  NOT NULL,
    bar_date   DATE        NOT NULL,
    open       DOUBLE PRECISION,
    high       DOUBLE PRECISION,
    low        DOUBLE PRECISION,
    close      DOUBLE PRECISION,
    volume     DOUBLE PRECISION,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (code, interval, bar_date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_code_intv
    ON ohlcv_cache(code, interval);

CREATE INDEX IF NOT EXISTS idx_ohlcv_updated
    ON ohlcv_cache(updated_at);
