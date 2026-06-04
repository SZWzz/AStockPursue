-- Add skill_config column to vt_users (per-user skill enable/disable)
ALTER TABLE vt_users ADD COLUMN IF NOT EXISTS skill_config JSONB DEFAULT '{}';
