-- AI analysis memory — store agent decisions for reflection learning.
-- The ReflectionWorker validates decisions against actual outcomes
-- after a configurable holding period (default: 7 days).

CREATE TABLE IF NOT EXISTS analysis_memory (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(64),
    market VARCHAR(20) NOT NULL,                -- CN_A / CRYPTO / US_EQUITY
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(20) NOT NULL,              -- bullish / bearish / neutral
    confidence INTEGER DEFAULT 50,              -- 0-100
    price_at_analysis DECIMAL(16, 4),
    reasoning TEXT,                             -- Agent reasoning summary
    context_snapshot JSONB,                     -- Market data snapshot at analysis time
    agent_response TEXT,                        -- Full agent output
    -- Validation fields (populated by ReflectionWorker)
    validated_at TIMESTAMP,
    actual_outcome VARCHAR(20),                 -- correct / incorrect / partial
    actual_return_pct DECIMAL(10, 4),           -- Actual return over holding period
    was_correct BOOLEAN,                        -- Whether the decision was correct
    user_feedback VARCHAR(20),                  -- user_correct / user_incorrect / null
    feedback_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_am_user_symbol ON analysis_memory(user_id, symbol);
CREATE INDEX IF NOT EXISTS idx_am_validated ON analysis_memory(validated_at) WHERE validated_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_am_created ON analysis_memory(created_at);
CREATE INDEX IF NOT EXISTS idx_am_decision ON analysis_memory(decision);
