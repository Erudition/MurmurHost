-- Migration script to add persistent memories table
-- Run this to add the memories system to your existing database

-- Create persistent memories table for important notes and information
CREATE TABLE IF NOT EXISTS persistent_memories (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('schedule', 'fact', 'preference', 'task', 'reminder', 'other')),
    content TEXT NOT NULL,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(255),
    importance INTEGER DEFAULT 5 CHECK (importance >= 1 AND importance <= 10),
    tags TEXT[],
    active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE SET NULL
);

-- Create indexes for memories
CREATE INDEX IF NOT EXISTS idx_memories_user ON persistent_memories(user_name);
CREATE INDEX IF NOT EXISTS idx_memories_category ON persistent_memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_active ON persistent_memories(active);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON persistent_memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_tags ON persistent_memories USING GIN(tags);

-- Create a view for active memories
CREATE OR REPLACE VIEW active_memories AS
SELECT
    id,
    user_name,
    category,
    content,
    extracted_at,
    importance,
    tags
FROM persistent_memories
WHERE active = TRUE
ORDER BY importance DESC, extracted_at DESC;

COMMENT ON TABLE persistent_memories IS 'Stores important extracted memories like schedules, facts, preferences, and tasks';

-- Print success message
DO $$
BEGIN
    RAISE NOTICE 'Persistent memories table created successfully!';
    RAISE NOTICE 'You can now store important information that the bot will remember.';
END $$;
