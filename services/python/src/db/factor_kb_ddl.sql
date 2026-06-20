-- Phase C P3: FactorKB PostgreSQL DDL (7 tables)
-- Run against the existing AStockPursue PostgreSQL database.
-- Requires: CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 1. Factor Knowledge (core table)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_factor_knowledge (
    id                  SERIAL PRIMARY KEY,
    alpha_id            VARCHAR(64) UNIQUE NOT NULL,
    formula_hash        VARCHAR(64) UNIQUE NOT NULL,       -- SHA256[:16] of normalized_formula
    name                VARCHAR(128),
    formula             TEXT NOT NULL,
    normalized_formula  TEXT,                              -- Canonical form for dedup
    expression_json     JSONB NOT NULL,                    -- ExpressionTree serialization (source of truth)
    theme               VARCHAR(64)[],
    semantic_tags       VARCHAR(64)[],                     -- LLM auto-tagged: "低换手率", "价值反转", "动量突破"
    source              VARCHAR(32),                       -- gp_engine / llm_miner / llm_agent / manual
    source_prompt       TEXT,                              -- LLM prompt used (traceability)
    economic_rationale  TEXT,                              -- LLM-generated economic intuition
    data_source_version VARCHAR(64),                       -- "mootdx_v2.1" / "tushare_pro"

    -- Performance (initial validation)
    train_ic            DOUBLE PRECISION,
    test_ic             DOUBLE PRECISION,
    test_ir             DOUBLE PRECISION,
    sharpe              DOUBLE PRECISION,
    max_drawdown        DOUBLE PRECISION,
    ic_decay_halflife   DOUBLE PRECISION,                  -- IC half-life (days)
    oos_ic_per_window   DOUBLE PRECISION[],                -- ICs from each OOS window

    -- Orthogonality
    orthogonality_score DOUBLE PRECISION,                   -- Incremental info vs Top 50 core factors
    max_corr_with_core  DOUBLE PRECISION,                   -- Max correlation with any core factor

    -- Lifecycle
    status              VARCHAR(16) DEFAULT 'discovered',   -- discovered/validating/approved/paper_trading/production/deprecated/archived
    discovered_at       TIMESTAMPTZ DEFAULT NOW(),
    last_validated_at   TIMESTAMPTZ,
    archived_at         TIMESTAMPTZ,
    archived_reason     VARCHAR(64),

    -- Multi-tenant
    user_id             INT NOT NULL DEFAULT 1,
    is_public           BOOLEAN DEFAULT FALSE,

    -- Complexity
    complexity          INT DEFAULT 0,

    -- pgvector semantic search
    description_embedding VECTOR(1536),                     -- text-embedding-3-small
    formula_embedding     VECTOR(1536)                      -- formula semantic embedding
);

CREATE INDEX IF NOT EXISTS idx_fk_status ON vt_factor_knowledge(status);
CREATE INDEX IF NOT EXISTS idx_fk_theme ON vt_factor_knowledge USING GIN(theme);
CREATE INDEX IF NOT EXISTS idx_fk_user ON vt_factor_knowledge(user_id);
CREATE INDEX IF NOT EXISTS idx_fk_formula_hash ON vt_factor_knowledge(formula_hash);
CREATE INDEX IF NOT EXISTS idx_fk_source ON vt_factor_knowledge(source);
CREATE INDEX IF NOT EXISTS idx_fk_embedding ON vt_factor_knowledge
    USING ivfflat (description_embedding vector_cosine_ops) WITH (lists = 100);


-- ============================================================================
-- 2. Factor Performance Snapshots (periodic collection)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_factor_performance_snapshots (
    id                  SERIAL PRIMARY KEY,
    knowledge_id        INT REFERENCES vt_factor_knowledge(id) ON DELETE CASCADE,
    snapshot_date       DATE NOT NULL,
    ic_mean             DOUBLE PRECISION,
    ic_std              DOUBLE PRECISION,
    sharpe              DOUBLE PRECISION,
    max_drawdown        DOUBLE PRECISION,
    coverage            DOUBLE PRECISION,
    turnover_annual     DOUBLE PRECISION,                   -- Annualised turnover
    transaction_cost_bps DOUBLE PRECISION,                  -- Trading cost in bps
    market_regime       VARCHAR(32),                       -- bull / bear / sideways / volatile / crash
    zoo_status          VARCHAR(16),                       -- alive / reversed / dead
    data_source_used    VARCHAR(64),
    data_start          DATE,
    data_end            DATE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fps_knowledge ON vt_factor_performance_snapshots(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_fps_date ON vt_factor_performance_snapshots(snapshot_date);


-- ============================================================================
-- 3. Factor Similarity Matrix (pre-computed)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_factor_similarities (
    factor_a_id         INT REFERENCES vt_factor_knowledge(id) ON DELETE CASCADE,
    factor_b_id         INT REFERENCES vt_factor_knowledge(id) ON DELETE CASCADE,
    pearson_r           DOUBLE PRECISION,
    spearman_r          DOUBLE PRECISION,
    cosine_similarity   DOUBLE PRECISION,                   -- embedding cosine similarity
    computed_at         TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (factor_a_id, factor_b_id)
);


-- ============================================================================
-- 4. Market Regime → Factor Performance Mapping
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_factor_regime_performance (
    knowledge_id        INT REFERENCES vt_factor_knowledge(id) ON DELETE CASCADE,
    regime              VARCHAR(32),
    avg_ic              DOUBLE PRECISION,
    ic_win_rate         DOUBLE PRECISION,
    sharpe              DOUBLE PRECISION,
    max_dd              DOUBLE PRECISION,
    n_observations      INT,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (knowledge_id, regime)
);


-- ============================================================================
-- 5. GP Subtree Cache (performance optimisation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_gp_subtree_cache (
    subtree_hash        VARCHAR(64) PRIMARY KEY,
    expression_json     JSONB NOT NULL,
    eval_count          INT DEFAULT 0,
    avg_eval_ms         DOUBLE PRECISION,
    last_used_at        TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================================
-- 6. Factor Archive
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_factor_archive (
    LIKE vt_factor_knowledge INCLUDING ALL,
    archived_reason     VARCHAR(64),
    archived_at         TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================================
-- 7. Activity Log (for Dashboard "Recent Activity" feed)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_activity_log (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL DEFAULT 1,
    event_type  VARCHAR(64) NOT NULL,        -- gp_run_completed / bench_completed / factor_promoted / factor_died / strategy_pnl_update / data_cache_refresh
    data        JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_user ON vt_activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_type ON vt_activity_log(event_type);
CREATE INDEX IF NOT EXISTS idx_activity_created ON vt_activity_log(created_at DESC);
