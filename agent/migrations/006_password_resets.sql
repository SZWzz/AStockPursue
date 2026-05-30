-- 006_password_resets.sql
-- Password reset tokens (dev mode — no email, token returned in API response).
-- Applied automatically by init_database() on startup.

CREATE TABLE IF NOT EXISTS vt_password_resets (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES vt_users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_password_resets_token
    ON vt_password_resets(token_hash);

CREATE INDEX IF NOT EXISTS idx_password_resets_user
    ON vt_password_resets(user_id);
