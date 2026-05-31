-- ============================================================================
-- Strategy Marketplace — share/discover strategies
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_strategy_marketplace (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    code            TEXT NOT NULL,
    market          VARCHAR(32) DEFAULT 'equity_cn',
    asset_class     VARCHAR(32) DEFAULT 'stock',
    category        VARCHAR(32) DEFAULT 'trend',
    tags            TEXT[] DEFAULT '{}',
    backtest_sharpe DOUBLE PRECISION,
    backtest_return DOUBLE PRECISION,
    backtest_drawdown DOUBLE PRECISION,
    installs_count  INTEGER DEFAULT 0,
    rating_sum      INTEGER DEFAULT 0,
    rating_count    INTEGER DEFAULT 0,
    is_public       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_marketplace_rating ON vt_strategy_marketplace(rating_count DESC, rating_sum DESC);
CREATE INDEX IF NOT EXISTS idx_marketplace_installs ON vt_strategy_marketplace(installs_count DESC);
CREATE INDEX IF NOT EXISTS idx_marketplace_user ON vt_strategy_marketplace(user_id);

CREATE TABLE IF NOT EXISTS vt_strategy_ratings (
    id              SERIAL PRIMARY KEY,
    strategy_id     UUID REFERENCES vt_strategy_marketplace(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    rating          INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(strategy_id, user_id)
);
