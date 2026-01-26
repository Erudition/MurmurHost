-- Add topic state tracking to conversation_history table
-- This migration adds fields to track conversation topics and their resolution state

-- Add new columns to conversation_history table
ALTER TABLE conversation_history 
ADD COLUMN IF NOT EXISTS topic_state VARCHAR(20) DEFAULT 'active',
ADD COLUMN IF NOT EXISTS topic_summary TEXT;

-- Create index for efficient topic state queries
CREATE INDEX IF NOT EXISTS idx_conversation_history_topic_state 
ON conversation_history(topic_state, user_name, session_id);

-- Create index for topic summary searches
CREATE INDEX IF NOT EXISTS idx_conversation_history_topic_summary 
ON conversation_history(topic_summary) 
WHERE topic_summary IS NOT NULL;

-- Update existing records to have 'active' state (default)
UPDATE conversation_history 
SET topic_state = 'active' 
WHERE topic_state IS NULL;

-- Add check constraint for valid topic states
ALTER TABLE conversation_history 
ADD CONSTRAINT chk_topic_state 
CHECK (topic_state IN ('active', 'resolved', 'switched'));
