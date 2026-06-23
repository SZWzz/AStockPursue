-- Arena: strategy competition with standardized evaluation

CREATE TABLE IF NOT EXISTS arena_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_code TEXT NOT NULL,
    parameters JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS arena_rankings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES arena_submissions(id),
    week TEXT NOT NULL,
    sharpe_ratio DOUBLE PRECISION,
    annual_return DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    win_rate DOUBLE PRECISION,
    alpha DOUBLE PRECISION,
    beta DOUBLE PRECISION,
    total_trades INT DEFAULT 0,
    rank INT,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(submission_id, week)
);

CREATE INDEX IF NOT EXISTS idx_arena_submissions_user_week ON arena_submissions(user_id, submitted_at);
CREATE INDEX IF NOT EXISTS idx_arena_rankings_week_rank ON arena_rankings(week, rank);
