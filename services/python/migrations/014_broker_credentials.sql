-- Broker API credentials — encrypted storage for multi-exchange support.
-- Each row stores encrypted API keys for one exchange connection per user.

CREATE TABLE IF NOT EXISTS broker_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exchange_id VARCHAR(20) NOT NULL,         -- binance | okx | futu
    label VARCHAR(100) DEFAULT '',            -- user-defined nickname
    api_key_enc TEXT NOT NULL,                -- Fernet-encrypted API key
    secret_key_enc TEXT NOT NULL,             -- Fernet-encrypted secret
    passphrase_enc TEXT,                      -- Fernet-encrypted passphrase (OKX)
    testnet BOOLEAN DEFAULT TRUE,             -- use testnet / demo trading
    is_active BOOLEAN DEFAULT TRUE,           -- user can disable without deleting
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, exchange_id, label)
);

CREATE INDEX IF NOT EXISTS idx_broker_cred_user ON broker_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_broker_cred_exchange ON broker_credentials(exchange_id);
