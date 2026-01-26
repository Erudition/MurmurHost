-- Migration script to add email logs table
-- This table tracks all email activity (received and sent)

-- Create email_logs table
CREATE TABLE IF NOT EXISTS email_logs (
    id SERIAL PRIMARY KEY,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('received', 'sent')),
    email_type VARCHAR(20) NOT NULL CHECK (email_type IN ('reply', 'summary', 'test', 'other')),
    from_email VARCHAR(255) NOT NULL,
    to_email VARCHAR(255) NOT NULL,
    subject TEXT,
    body_preview TEXT,  -- First 500 chars of body
    full_body TEXT,  -- Full email body
    status VARCHAR(20) DEFAULT 'success' CHECK (status IN ('success', 'error', 'pending')),
    error_message TEXT,
    mapped_user VARCHAR(255),  -- User name from email mapping (if applicable)
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_email_logs_direction ON email_logs(direction);
CREATE INDEX IF NOT EXISTS idx_email_logs_timestamp ON email_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_email_logs_from ON email_logs(from_email);
CREATE INDEX IF NOT EXISTS idx_email_logs_to ON email_logs(to_email);
CREATE INDEX IF NOT EXISTS idx_email_logs_type ON email_logs(email_type);
CREATE INDEX IF NOT EXISTS idx_email_logs_status ON email_logs(status);

-- Add comment
COMMENT ON TABLE email_logs IS 'Logs all email activity including received and sent emails';
COMMENT ON COLUMN email_logs.direction IS 'Direction: received or sent';
COMMENT ON COLUMN email_logs.email_type IS 'Type: reply, summary, test, other';
COMMENT ON COLUMN email_logs.body_preview IS 'First 500 characters of email body';
COMMENT ON COLUMN email_logs.mapped_user IS 'User name from email mapping (for personalized context)';
