-- ============================================================================
-- Strategy Version Control — diff-based version history
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_strategy_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     INTEGER NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    version_num     INTEGER NOT NULL,
    code            TEXT NOT NULL,
    title           TEXT DEFAULT '',
    change_note     TEXT DEFAULT '',
    diff_prev       TEXT DEFAULT '',  -- unified diff from previous version
    code_size       INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(strategy_id, version_num)
);
CREATE INDEX IF NOT EXISTS idx_strategy_ver ON vt_strategy_versions(strategy_id, version_num DESC);
