-- ============================================================================
-- Scheduled Tasks — cron-based automation engine
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_scheduled_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    task_type       VARCHAR(32) NOT NULL CHECK (task_type IN ('auto_backtest', 'data_health_check', 'watchlist_alert', 'signal_report', 'factor_mining', 'screener_run')),
    cron_expression TEXT NOT NULL,
    config          JSONB DEFAULT '{}',
    enabled         BOOLEAN DEFAULT true,
    next_run        TIMESTAMPTZ,
    last_run        TIMESTAMPTZ,
    last_status     VARCHAR(16),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sched_tasks_user ON vt_scheduled_tasks(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS vt_scheduled_task_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID REFERENCES vt_scheduled_tasks(id) ON DELETE CASCADE,
    status          VARCHAR(16) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    started_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    output_log      TEXT DEFAULT '',
    error_message   TEXT DEFAULT '',
    result          JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sched_exec_task ON vt_scheduled_task_executions(task_id, started_at DESC);
