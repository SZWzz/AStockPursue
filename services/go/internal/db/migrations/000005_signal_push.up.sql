-- Signal push subscription settings
-- Adds signal_push_enabled and push_channels to user_settings

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' AND column_name = 'signal_push_enabled'
    ) THEN
        ALTER TABLE user_settings 
        ADD COLUMN signal_push_enabled BOOLEAN NOT NULL DEFAULT false;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' AND column_name = 'push_channels'
    ) THEN
        ALTER TABLE user_settings 
        ADD COLUMN push_channels JSONB NOT NULL DEFAULT '{}';
    END IF;
END $$;
