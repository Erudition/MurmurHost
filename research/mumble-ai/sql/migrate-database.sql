-- Migration script to upgrade database for semantic memory system
-- This safely adds new columns and tables without losing existing data

-- Create conversation sessions table if it doesn't exist
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    state VARCHAR(20) DEFAULT 'active' CHECK (state IN ('active', 'idle', 'closed')),
    message_count INTEGER DEFAULT 0,
    UNIQUE(user_name, session_id)
);

-- Add new columns to conversation_history if they don't exist
DO $$
BEGIN
    -- Add session_id column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='conversation_history' AND column_name='session_id') THEN
        ALTER TABLE conversation_history ADD COLUMN session_id VARCHAR(255);
    END IF;

    -- Add embedding column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='conversation_history' AND column_name='embedding') THEN
        ALTER TABLE conversation_history ADD COLUMN embedding FLOAT8[];
    END IF;

    -- Add importance_score column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='conversation_history' AND column_name='importance_score') THEN
        ALTER TABLE conversation_history ADD COLUMN importance_score FLOAT DEFAULT 0.5;
    END IF;

    -- Add summary column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='conversation_history' AND column_name='summary') THEN
        ALTER TABLE conversation_history ADD COLUMN summary TEXT;
    END IF;
END $$;

-- Add foreign key constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'conversation_history_session_id_fkey'
    ) THEN
        ALTER TABLE conversation_history
        ADD CONSTRAINT conversation_history_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE SET NULL;
    END IF;
END $$;

-- Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_conversation_session ON conversation_history(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_role ON conversation_history(role);
CREATE INDEX IF NOT EXISTS idx_session_user ON conversation_sessions(user_name);
CREATE INDEX IF NOT EXISTS idx_session_activity ON conversation_sessions(last_activity DESC);

-- Add new configuration values
INSERT INTO bot_config (key, value) VALUES
    ('embedding_model', 'nomic-embed-text:latest'),
    ('short_term_memory_limit', '3'),
    ('long_term_memory_limit', '3'),
    ('semantic_similarity_threshold', '0.7'),
    ('session_timeout_minutes', '30'),
    ('session_reactivation_minutes', '10')
ON CONFLICT (key) DO NOTHING;

-- Create or replace cosine similarity function
CREATE OR REPLACE FUNCTION cosine_similarity(vec1 FLOAT8[], vec2 FLOAT8[])
RETURNS FLOAT8 AS $$
DECLARE
    dot_product FLOAT8 := 0;
    magnitude1 FLOAT8 := 0;
    magnitude2 FLOAT8 := 0;
    i INTEGER;
BEGIN
    -- Handle null or empty arrays
    IF vec1 IS NULL OR vec2 IS NULL OR array_length(vec1, 1) IS NULL OR array_length(vec2, 1) IS NULL THEN
        RETURN 0;
    END IF;

    -- Calculate dot product and magnitudes
    FOR i IN 1..array_length(vec1, 1) LOOP
        dot_product := dot_product + (vec1[i] * vec2[i]);
        magnitude1 := magnitude1 + (vec1[i] * vec1[i]);
        magnitude2 := magnitude2 + (vec2[i] * vec2[i]);
    END LOOP;

    -- Avoid division by zero
    IF magnitude1 = 0 OR magnitude2 = 0 THEN
        RETURN 0;
    END IF;

    RETURN dot_product / (sqrt(magnitude1) * sqrt(magnitude2));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Print success message
DO $$
BEGIN
    RAISE NOTICE 'Database migration completed successfully!';
    RAISE NOTICE 'Existing conversation history has been preserved.';
    RAISE NOTICE 'New embeddings will be generated automatically for new messages.';
END $$;
