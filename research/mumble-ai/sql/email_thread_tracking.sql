-- Email Thread Tracking Migration
-- Adds thread-aware conversation tracking and action result logging

-- 1. Create email_threads table for tracking conversation threads by subject
CREATE TABLE IF NOT EXISTS email_threads (
    id SERIAL PRIMARY KEY,
    subject TEXT NOT NULL,
    normalized_subject TEXT NOT NULL,  -- Subject with Re:/Fwd: removed
    user_email VARCHAR(255) NOT NULL,
    mapped_user VARCHAR(255),  -- User name from mapping
    first_message_id VARCHAR(500),  -- Message-ID of first email
    last_message_id VARCHAR(500),  -- Message-ID of last email
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(normalized_subject, user_email)
);

-- Create indexes for email_threads
CREATE INDEX IF NOT EXISTS idx_email_threads_user ON email_threads(user_email);
CREATE INDEX IF NOT EXISTS idx_email_threads_normalized ON email_threads(normalized_subject);
CREATE INDEX IF NOT EXISTS idx_email_threads_updated ON email_threads(updated_at DESC);

-- 2. Create email_thread_messages table for conversation history per thread
CREATE TABLE IF NOT EXISTS email_thread_messages (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES email_threads(id) ON DELETE CASCADE,
    email_log_id INTEGER REFERENCES email_logs(id) ON DELETE SET NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    message_content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for email_thread_messages
CREATE INDEX IF NOT EXISTS idx_thread_messages_thread ON email_thread_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_thread_messages_timestamp ON email_thread_messages(timestamp DESC);

-- 3. Create email_actions table for tracking memory/calendar actions
CREATE TABLE IF NOT EXISTS email_actions (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER REFERENCES email_threads(id) ON DELETE CASCADE,
    email_log_id INTEGER REFERENCES email_logs(id) ON DELETE SET NULL,
    action_type VARCHAR(20) NOT NULL CHECK (action_type IN ('memory', 'schedule')),
    action VARCHAR(20) NOT NULL CHECK (action IN ('add', 'update', 'delete', 'nothing')),
    intent TEXT,  -- What the AI intended to do
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'skipped')),
    details JSONB,  -- Action details (memory content, event details, etc.)
    error_message TEXT,  -- If failed, why?
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for email_actions
CREATE INDEX IF NOT EXISTS idx_email_actions_thread ON email_actions(thread_id);
CREATE INDEX IF NOT EXISTS idx_email_actions_status ON email_actions(status);
CREATE INDEX IF NOT EXISTS idx_email_actions_type ON email_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_email_actions_executed ON email_actions(executed_at DESC);

-- 4. Add thread_id column to email_logs if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='email_logs' AND column_name='thread_id'
    ) THEN
        ALTER TABLE email_logs ADD COLUMN thread_id INTEGER REFERENCES email_threads(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_email_logs_thread ON email_logs(thread_id);
    END IF;
END $$;

-- 5. Add attachments columns to email_logs if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='email_logs' AND column_name='attachments_count'
    ) THEN
        ALTER TABLE email_logs ADD COLUMN attachments_count INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='email_logs' AND column_name='attachments_metadata'
    ) THEN
        ALTER TABLE email_logs ADD COLUMN attachments_metadata JSONB;
    END IF;
END $$;

-- 6. Create update trigger for email_threads updated_at
CREATE OR REPLACE FUNCTION update_email_threads_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_email_threads_updated_at ON email_threads;
CREATE TRIGGER trigger_update_email_threads_updated_at
    BEFORE UPDATE ON email_threads
    FOR EACH ROW
    EXECUTE FUNCTION update_email_threads_updated_at();

-- Add comments for documentation
COMMENT ON TABLE email_threads IS 'Tracks email conversation threads by subject line';
COMMENT ON TABLE email_thread_messages IS 'Stores conversation history per email thread (separate from Mumble conversations)';
COMMENT ON TABLE email_actions IS 'Logs memory and calendar actions performed during email processing with success/failure tracking';
COMMENT ON COLUMN email_threads.normalized_subject IS 'Subject with Re:, Fwd:, etc. removed for thread matching';
COMMENT ON COLUMN email_actions.status IS 'success = action completed, failed = action attempted but failed, skipped = action not needed';
