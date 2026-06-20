-- ============================================================================
-- Trading Dashboard — Orders table (multi-user isolated)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_trading_orders (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type      TEXT NOT NULL DEFAULT 'market' CHECK (order_type IN ('market', 'limit')),
    qty             DOUBLE PRECISION NOT NULL CHECK (qty > 0),
    price           DOUBLE PRECISION NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'filled', 'cancelled')),
    filled_qty      DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_price       DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_trading_orders_user ON vt_trading_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trading_orders_status ON vt_trading_orders(user_id, status);
