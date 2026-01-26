-- Migration script to add IMAP and email receiving settings
-- This adds new columns to the email_settings table for existing databases

-- Add IMAP settings columns if they don't exist
DO $$
BEGIN
    -- IMAP enabled flag
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='imap_enabled') THEN
        ALTER TABLE email_settings ADD COLUMN imap_enabled BOOLEAN DEFAULT FALSE;
    END IF;

    -- IMAP host
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='imap_host') THEN
        ALTER TABLE email_settings ADD COLUMN imap_host VARCHAR(255);
    END IF;

    -- IMAP port
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='imap_port') THEN
        ALTER TABLE email_settings ADD COLUMN imap_port INTEGER DEFAULT 993;
    END IF;

    -- IMAP username
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='imap_username') THEN
        ALTER TABLE email_settings ADD COLUMN imap_username VARCHAR(255);
    END IF;

    -- IMAP password
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='imap_password') THEN
        ALTER TABLE email_settings ADD COLUMN imap_password VARCHAR(255);
    END IF;

    -- IMAP use SSL
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='imap_use_ssl') THEN
        ALTER TABLE email_settings ADD COLUMN imap_use_ssl BOOLEAN DEFAULT TRUE;
    END IF;

    -- IMAP mailbox
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='imap_mailbox') THEN
        ALTER TABLE email_settings ADD COLUMN imap_mailbox VARCHAR(255) DEFAULT 'INBOX';
    END IF;

    -- Auto reply enabled
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='auto_reply_enabled') THEN
        ALTER TABLE email_settings ADD COLUMN auto_reply_enabled BOOLEAN DEFAULT FALSE;
    END IF;

    -- Reply signature
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='reply_signature') THEN
        ALTER TABLE email_settings ADD COLUMN reply_signature TEXT;
    END IF;

    -- Check interval
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='check_interval_seconds') THEN
        ALTER TABLE email_settings ADD COLUMN check_interval_seconds INTEGER DEFAULT 300;
    END IF;

    -- Last checked timestamp
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='email_settings' AND column_name='last_checked') THEN
        ALTER TABLE email_settings ADD COLUMN last_checked TIMESTAMP;
    END IF;
END $$;

-- Add comment
COMMENT ON COLUMN email_settings.imap_enabled IS 'Enable IMAP email receiving';
COMMENT ON COLUMN email_settings.auto_reply_enabled IS 'Enable AI-powered automatic replies to received emails';
COMMENT ON COLUMN email_settings.check_interval_seconds IS 'How often to check for new emails (in seconds)';
