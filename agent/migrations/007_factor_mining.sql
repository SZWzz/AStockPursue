-- ============================================================================
-- Factor Mining — GP evolution runs and discovered candidates
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_factor_mining_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    run_type        VARCHAR(16) NOT NULL CHECK (run_type IN ('gp', 'llm', 'hybrid')),
    config          JSONB DEFAULT '{}',
    status          VARCHAR(16) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    best_formula    TEXT,
    best_ic         DOUBLE PRECISION,
    best_ir         DOUBLE PRECISION,
    generation_history JSONB DEFAULT '[]',
    candidates_count INTEGER DEFAULT 0,
    runtime_seconds DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mining_runs_user ON vt_factor_mining_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mining_runs_status ON vt_factor_mining_runs(user_id, status);

CREATE TABLE IF NOT EXISTS vt_factor_mining_candidates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID REFERENCES vt_factor_mining_runs(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    name            TEXT,
    formula         TEXT NOT NULL,
    expression_json JSONB,
    train_ic        DOUBLE PRECISION,
    test_ic         DOUBLE PRECISION,
    test_ir         DOUBLE PRECISION,
    complexity      INTEGER,
    is_promoted     BOOLEAN DEFAULT false,
    promoted_zoo_id TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mining_candidates_user ON vt_factor_mining_candidates(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mining_candidates_run ON vt_factor_mining_candidates(run_id);
