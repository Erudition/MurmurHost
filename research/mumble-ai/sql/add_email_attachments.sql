-- Migration: Add email attachment support
-- Date: 2025-10-10
-- Description: Add columns to track email attachments and add vision model configuration

-- Add attachment tracking columns to email_logs table
ALTER TABLE email_logs 
ADD COLUMN IF NOT EXISTS attachments_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS attachments_metadata JSONB;

-- Add index for attachment queries
CREATE INDEX IF NOT EXISTS idx_email_logs_attachments ON email_logs(attachments_count) WHERE attachments_count > 0;

-- Add vision model configuration to bot_config
INSERT INTO bot_config (key, value) VALUES 
    ('ollama_vision_model', 'moondream:latest')
ON CONFLICT (key) DO NOTHING;

-- Add comment
COMMENT ON COLUMN email_logs.attachments_count IS 'Number of attachments in the email';
COMMENT ON COLUMN email_logs.attachments_metadata IS 'JSON array of attachment details (filename, size, type, analysis summary)';



