-- ============================================================================
-- Stock Screener — presets and run results
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_screener_presets (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    conditions      JSONB NOT NULL,
    universe        JSONB DEFAULT '[]',
    sort_by         TEXT,
    is_system       BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_screener_presets_user ON vt_screener_presets(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS vt_screener_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    preset_id       INTEGER REFERENCES vt_screener_presets(id) ON DELETE SET NULL,
    conditions      JSONB NOT NULL,
    universe        JSONB DEFAULT '[]',
    result_count    INTEGER DEFAULT 0,
    status          VARCHAR(16) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vt_screener_results (
    id              SERIAL PRIMARY KEY,
    run_id          UUID REFERENCES vt_screener_runs(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    rank            INTEGER,
    score           DOUBLE PRECISION,
    condition_values JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);
