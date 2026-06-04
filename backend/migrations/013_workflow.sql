-- ============================================================================
-- Workflow System — n8n-style node-based quant research pipelines
-- ============================================================================

-- Research project container
CREATE TABLE IF NOT EXISTS vt_workflow_projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT DEFAULT '',
    status          VARCHAR(50) DEFAULT 'active',     -- active, archived
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflow_projects_user ON vt_workflow_projects(user_id);

-- Workflow definition (DAG blueprint)
CREATE TABLE IF NOT EXISTS vt_workflows (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES vt_workflow_projects(id) ON DELETE SET NULL,
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT DEFAULT '',
    nodes           JSONB NOT NULL,                    -- [{id, type, position:{x,y}, config:{}}]
    edges           JSONB NOT NULL,                    -- [{id, source, sourcePort, target, targetPort}]
    viewport        JSONB DEFAULT '{"x":0,"y":0,"zoom":1}',
    is_locked       BOOLEAN DEFAULT FALSE,             -- locked during execution
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflows_project ON vt_workflows(project_id);
CREATE INDEX IF NOT EXISTS idx_workflows_user ON vt_workflows(user_id);

-- Workflow execution run (with runtime snapshot for reproducibility)
CREATE TABLE IF NOT EXISTS vt_workflow_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID REFERENCES vt_workflows(id) ON DELETE SET NULL,
    user_id         INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    status          VARCHAR(50) DEFAULT 'pending',    -- pending, running, completed, failed, cancelled
    target_node_id  VARCHAR(100),                     -- if executing only to a specific node

    -- Runtime snapshot: complete DAG state at trigger time
    snapshot_nodes  JSONB NOT NULL,                    -- full nodes with config at run time
    snapshot_edges  JSONB NOT NULL,                    -- full edges at run time

    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    node_results    JSONB DEFAULT '{}',                -- {node_id: {status, artifact_refs, summary, error, duration_ms, retry_count}}
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow ON vt_workflow_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_user ON vt_workflow_runs(user_id, started_at DESC);

-- Node output cache index (references only — raw data lives in shared storage)
CREATE TABLE IF NOT EXISTS vt_workflow_node_cache (
    cache_key       VARCHAR(64) PRIMARY KEY,
    node_type       VARCHAR(100) NOT NULL,
    workflow_id     UUID NOT NULL,
    node_id         VARCHAR(100) NOT NULL,
    storage_path    VARCHAR(500) NOT NULL,             -- path to Parquet file
    format          VARCHAR(20) DEFAULT 'parquet',
    schema_hash     VARCHAR(64),
    row_count       INTEGER DEFAULT 0,
    size_bytes      BIGINT DEFAULT 0,
    summary         JSONB DEFAULT '{}',                -- lightweight statistics
    created_at      TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ DEFAULT (now() + interval '7 days')
);
CREATE INDEX IF NOT EXISTS idx_workflow_cache_expires ON vt_workflow_node_cache(expires_at);
