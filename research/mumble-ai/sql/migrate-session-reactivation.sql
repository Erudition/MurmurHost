-- Migration: Add session reactivation configuration
-- This adds support for reactivating idle sessions when users return
-- Run this on existing databases to enable session reactivation feature

-- Add session reactivation configuration value
INSERT INTO bot_config (key, value) VALUES
    ('session_reactivation_minutes', '10')
ON CONFLICT (key) DO NOTHING;

-- Verify the configuration was added
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM bot_config WHERE key = 'session_reactivation_minutes') THEN
        RAISE NOTICE 'Session reactivation configuration added successfully!';
        RAISE NOTICE 'Default reactivation window: 10 minutes';
        RAISE NOTICE 'Idle sessions can be reactivated if user returns within this window.';
    ELSE
        RAISE WARNING 'Failed to add session reactivation configuration';
    END IF;
END $$;

-- Display current session-related configuration
SELECT key, value, updated_at 
FROM bot_config 
WHERE key LIKE 'session_%'
ORDER BY key;

