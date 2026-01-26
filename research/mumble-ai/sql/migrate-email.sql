-- Migration script to add email summary functionality
-- Run this on existing installations to add email settings table

-- Create email settings table for daily summary emails
CREATE TABLE IF NOT EXISTS email_settings (
    id SERIAL PRIMARY KEY,
    smtp_host VARCHAR(255) NOT NULL DEFAULT 'localhost',
    smtp_port INTEGER NOT NULL DEFAULT 25,
    smtp_username VARCHAR(255),
    smtp_password VARCHAR(255),
    smtp_use_tls BOOLEAN DEFAULT FALSE,
    smtp_use_ssl BOOLEAN DEFAULT FALSE,
    from_email VARCHAR(255) NOT NULL DEFAULT 'mumble-ai@localhost',
    recipient_email VARCHAR(255),
    daily_summary_enabled BOOLEAN DEFAULT FALSE,
    summary_time TIME DEFAULT '22:00:00',  -- 10pm
    timezone VARCHAR(50) DEFAULT 'America/New_York',  -- EST
    last_sent TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default email settings (only if table was just created)
INSERT INTO email_settings (id, smtp_host, smtp_port, from_email, daily_summary_enabled)
VALUES (1, 'localhost', 25, 'mumble-ai@localhost', FALSE)
ON CONFLICT (id) DO NOTHING;

-- Create index for email settings
CREATE INDEX IF NOT EXISTS idx_email_last_sent ON email_settings(last_sent DESC);

-- Add comment
COMMENT ON TABLE email_settings IS 'Stores email configuration for daily summary emails';

-- Display current settings
SELECT * FROM email_settings;
