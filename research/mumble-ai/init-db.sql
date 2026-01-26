-- Create conversation sessions table for tracking conversation state
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

-- Create conversation history table with semantic memory support
CREATE TABLE IF NOT EXISTS conversation_history (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    user_session INTEGER NOT NULL,
    session_id VARCHAR(255),
    message_type VARCHAR(10) NOT NULL CHECK (message_type IN ('voice', 'text')),
    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    embedding FLOAT8[],
    importance_score FLOAT DEFAULT 0.5,
    summary TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE SET NULL
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_conversation_timestamp ON conversation_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_user ON conversation_history(user_name);
CREATE INDEX IF NOT EXISTS idx_conversation_session ON conversation_history(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_role ON conversation_history(role);
CREATE INDEX IF NOT EXISTS idx_session_user ON conversation_sessions(user_name);
CREATE INDEX IF NOT EXISTS idx_session_activity ON conversation_sessions(last_activity DESC);

-- Create a view for recent conversations
CREATE OR REPLACE VIEW recent_conversations AS
SELECT
    id,
    user_name,
    message_type,
    role,
    message,
    timestamp
FROM conversation_history
ORDER BY timestamp DESC
LIMIT 100;

-- Create bot configuration table
CREATE TABLE IF NOT EXISTS bot_config (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default configuration values
INSERT INTO bot_config (key, value) VALUES
    ('ollama_url', 'http://host.docker.internal:11434'),
    ('ollama_model', 'llama3.2:latest'),
    ('memory_extraction_model', 'qwen2.5:3b'),
    ('piper_voice', 'en_US-lessac-medium'),
    ('bot_persona', ''),
    ('whisper_language', 'auto'),
    ('tts_engine', 'piper'),
    ('silero_voice', 'en_0'),
    ('embedding_model', 'nomic-embed-text:latest'),
    ('short_term_memory_limit', '10'),
    ('long_term_memory_limit', '10'),
    ('semantic_similarity_threshold', '0.7'),
    ('session_timeout_minutes', '30'),
    ('session_reactivation_minutes', '10'),
    ('use_chain_of_thought', 'false'),
    ('use_semantic_memory_ranking', 'true'),
    ('use_response_validation', 'false'),
    ('enable_parallel_processing', 'true')
ON CONFLICT (key) DO NOTHING;

-- Function to calculate cosine similarity between two embedding vectors
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
    event_date DATE,  -- For schedule category memories
    event_time TIME,  -- For schedule category memories
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE SET NULL
);

-- Add event_date and event_time columns if they don't exist (for existing databases)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='persistent_memories' AND column_name='event_date') THEN
        ALTER TABLE persistent_memories ADD COLUMN event_date DATE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='persistent_memories' AND column_name='event_time') THEN
        ALTER TABLE persistent_memories ADD COLUMN event_time TIME;
    END IF;
END $$;

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

-- Create email settings table for daily summary emails and email receiving
CREATE TABLE IF NOT EXISTS email_settings (
    id SERIAL PRIMARY KEY,
    -- SMTP settings (for sending emails)
    smtp_host VARCHAR(255) NOT NULL DEFAULT 'localhost',
    smtp_port INTEGER NOT NULL DEFAULT 25,
    smtp_username VARCHAR(255),
    smtp_password VARCHAR(255),
    smtp_use_tls BOOLEAN DEFAULT FALSE,
    smtp_use_ssl BOOLEAN DEFAULT FALSE,
    from_email VARCHAR(255) NOT NULL DEFAULT 'mumble-ai@localhost',
    recipient_email VARCHAR(255),
    -- Daily summary settings
    daily_summary_enabled BOOLEAN DEFAULT FALSE,
    summary_time TIME DEFAULT '22:00:00',  -- 10pm
    timezone VARCHAR(50) DEFAULT 'America/New_York',  -- EST
    last_sent TIMESTAMP,
    -- IMAP settings (for receiving emails)
    imap_enabled BOOLEAN DEFAULT FALSE,
    imap_host VARCHAR(255),
    imap_port INTEGER DEFAULT 993,
    imap_username VARCHAR(255),
    imap_password VARCHAR(255),
    imap_use_ssl BOOLEAN DEFAULT TRUE,
    imap_mailbox VARCHAR(255) DEFAULT 'INBOX',
    -- AI reply settings
    auto_reply_enabled BOOLEAN DEFAULT FALSE,
    reply_signature TEXT,
    check_interval_seconds INTEGER DEFAULT 300,  -- Check every 5 minutes
    last_checked TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default email settings
INSERT INTO email_settings (id, smtp_host, smtp_port, from_email, daily_summary_enabled)
VALUES (1, 'localhost', 25, 'mumble-ai@localhost', FALSE)
ON CONFLICT (id) DO NOTHING;

-- Create index for email settings
CREATE INDEX IF NOT EXISTS idx_email_last_sent ON email_settings(last_sent DESC);

-- Create email user mappings table
CREATE TABLE IF NOT EXISTS email_user_mappings (
    id SERIAL PRIMARY KEY,
    email_address VARCHAR(255) NOT NULL UNIQUE,
    user_name VARCHAR(255) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for email mappings
CREATE INDEX IF NOT EXISTS idx_email_mappings_email ON email_user_mappings(email_address);
CREATE INDEX IF NOT EXISTS idx_email_mappings_user ON email_user_mappings(user_name);

-- Create email logs table
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

-- Create indexes for email logs
CREATE INDEX IF NOT EXISTS idx_email_logs_direction ON email_logs(direction);
CREATE INDEX IF NOT EXISTS idx_email_logs_timestamp ON email_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_email_logs_from ON email_logs(from_email);
CREATE INDEX IF NOT EXISTS idx_email_logs_to ON email_logs(to_email);
CREATE INDEX IF NOT EXISTS idx_email_logs_type ON email_logs(email_type);
CREATE INDEX IF NOT EXISTS idx_email_logs_status ON email_logs(status);

-- Create schedule_events table for calendar functionality
CREATE TABLE IF NOT EXISTS schedule_events (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME,
    description TEXT,
    importance INTEGER DEFAULT 5 CHECK (importance >= 1 AND importance <= 10),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for schedule_events
CREATE INDEX IF NOT EXISTS idx_schedule_user ON schedule_events(user_name);
CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule_events(event_date);
CREATE INDEX IF NOT EXISTS idx_schedule_active ON schedule_events(active);
CREATE INDEX IF NOT EXISTS idx_schedule_importance ON schedule_events(importance DESC);

-- Add full-text search indexes for event title search
CREATE INDEX IF NOT EXISTS idx_schedule_title_gin ON schedule_events USING GIN(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_schedule_title_trgm ON schedule_events USING GIN(title gin_trgm_ops);

-- Create update trigger for schedule_events updated_at
CREATE OR REPLACE FUNCTION update_schedule_events_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_schedule_events_updated_at
    BEFORE UPDATE ON schedule_events
    FOR EACH ROW
    EXECUTE FUNCTION update_schedule_events_updated_at();

-- Create chatterbox_voices table for voice cloning presets
CREATE TABLE IF NOT EXISTS chatterbox_voices (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    reference_audio_path TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    tags TEXT[],
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for chatterbox_voices
CREATE INDEX IF NOT EXISTS idx_chatterbox_voices_name ON chatterbox_voices(name);
CREATE INDEX IF NOT EXISTS idx_chatterbox_voices_language ON chatterbox_voices(language);
CREATE INDEX IF NOT EXISTS idx_chatterbox_voices_active ON chatterbox_voices(is_active);
CREATE INDEX IF NOT EXISTS idx_chatterbox_voices_tags ON chatterbox_voices USING GIN(tags);

-- Create update trigger for chatterbox_voices updated_at
CREATE OR REPLACE FUNCTION update_chatterbox_voices_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_chatterbox_voices_updated_at
    BEFORE UPDATE ON chatterbox_voices
    FOR EACH ROW
    EXECUTE FUNCTION update_chatterbox_voices_updated_at();

COMMENT ON TABLE conversation_history IS 'Stores all conversation history between users and the AI bot';
COMMENT ON COLUMN conversation_history.message_type IS 'Type of message: voice or text';
COMMENT ON COLUMN conversation_history.role IS 'Role: user or assistant';
COMMENT ON TABLE bot_config IS 'Stores bot configuration settings';
COMMENT ON TABLE persistent_memories IS 'Stores important extracted memories like schedules, facts, preferences, and tasks';
COMMENT ON TABLE schedule_events IS 'Stores calendar events and scheduled tasks for AI scheduling system';
COMMENT ON COLUMN schedule_events.event_time IS 'Optional time for event (NULL for all-day events)';
COMMENT ON TABLE email_settings IS 'Stores email configuration for daily summary emails';
COMMENT ON TABLE email_user_mappings IS 'Maps email addresses to user names for personalized bot responses';
COMMENT ON TABLE email_logs IS 'Logs all email activity including received and sent emails';
COMMENT ON TABLE chatterbox_voices IS 'Stores voice cloning presets for Chatterbox TTS service';
COMMENT ON COLUMN chatterbox_voices.reference_audio_path IS 'Path to reference audio file for voice cloning';
COMMENT ON COLUMN chatterbox_voices.metadata IS 'Additional metadata in JSON format (e.g., speaker info, recording details)';

-- Additional composite indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_memories_user_active_importance 
  ON persistent_memories(user_name, active, importance DESC);

CREATE INDEX IF NOT EXISTS idx_conversation_user_session_timestamp 
  ON conversation_history(user_name, session_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_schedule_user_date 
  ON schedule_events(user_name, event_date, active);

CREATE INDEX IF NOT EXISTS idx_email_logs_direction_timestamp 
  ON email_logs(direction, timestamp DESC);

-- Add embedding column to persistent_memories if it doesn't exist for semantic search
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='persistent_memories' AND column_name='embedding') THEN
        ALTER TABLE persistent_memories ADD COLUMN embedding FLOAT8[];
    END IF;
END $$;

-- Create GIN index for array similarity searches
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON persistent_memories USING GIN(embedding) WHERE embedding IS NOT NULL;

-- Track entity mentions
CREATE TABLE IF NOT EXISTS entity_mentions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    entity_text VARCHAR(500) NOT NULL,
    canonical_id VARCHAR(255),
    entity_type VARCHAR(50) CHECK (entity_type IN ('PERSON', 'PLACE', 'ORGANIZATION', 'DATE', 'TIME', 'EVENT', 'OTHER')),
    message_id INTEGER REFERENCES conversation_history(id) ON DELETE CASCADE,
    confidence FLOAT DEFAULT 1.0,
    context_info TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_user ON entity_mentions(user_name);
CREATE INDEX IF NOT EXISTS idx_entity_canonical ON entity_mentions(canonical_id);
CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_mentions(entity_type);

-- Track consolidation runs
CREATE TABLE IF NOT EXISTS memory_consolidation_log (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    messages_consolidated INTEGER NOT NULL,
    summaries_created INTEGER NOT NULL,
    tokens_saved_estimate INTEGER,
    cutoff_date DATE,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_consolidation_user ON memory_consolidation_log(user_name);
CREATE INDEX IF NOT EXISTS idx_consolidation_date ON memory_consolidation_log(run_at DESC);

-- Add columns to conversation_history for consolidation tracking
ALTER TABLE conversation_history
ADD COLUMN IF NOT EXISTS consolidated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS consolidated_summary_id VARCHAR(255);

-- Create index for consolidation tracking
CREATE INDEX IF NOT EXISTS idx_conversation_consolidated ON conversation_history(consolidated_at) WHERE consolidated_at IS NULL;

-- Add config entries for new memory system
INSERT INTO bot_config (key, value) VALUES
    ('chromadb_url', 'http://chromadb:8000'),
    ('redis_url', 'redis://redis:6379'),
    ('enable_entity_tracking', 'true'),
    ('enable_memory_consolidation', 'true'),
    ('memory_consolidation_days', '7'),
    ('hybrid_search_semantic_weight', '0.7'),
    ('consolidation_schedule_hour', '3')
ON CONFLICT (key) DO NOTHING;

-- Create transcriptions table for Whisper web interface
CREATE TABLE IF NOT EXISTS transcriptions (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    original_format VARCHAR(50) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    duration_seconds FLOAT,
    transcription_text TEXT NOT NULL,
    language VARCHAR(10),
    language_probability FLOAT,
    summary_text TEXT,
    summary_model VARCHAR(100),
    processing_time_seconds FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_identifier VARCHAR(255)
);

-- Create indexes for transcriptions table
CREATE INDEX IF NOT EXISTS idx_transcriptions_created_at ON transcriptions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transcriptions_language ON transcriptions(language);
CREATE INDEX IF NOT EXISTS idx_transcriptions_filename ON transcriptions(filename);
CREATE INDEX IF NOT EXISTS idx_transcriptions_user ON transcriptions(user_identifier);

-- Add comments for transcriptions table
COMMENT ON TABLE transcriptions IS 'Stores audio/video file transcriptions from Whisper web interface';
COMMENT ON COLUMN transcriptions.original_format IS 'Original file format (mp3, mp4, wav, etc.)';
COMMENT ON COLUMN transcriptions.file_size_bytes IS 'File size in bytes';
COMMENT ON COLUMN transcriptions.duration_seconds IS 'Audio duration in seconds';
COMMENT ON COLUMN transcriptions.language IS 'Detected language code (e.g., en, es, fr)';
COMMENT ON COLUMN transcriptions.language_probability IS 'Confidence score for language detection';
COMMENT ON COLUMN transcriptions.summary_text IS 'AI-generated summary of the transcription';
COMMENT ON COLUMN transcriptions.summary_model IS 'Ollama model used for summarization';
COMMENT ON COLUMN transcriptions.processing_time_seconds IS 'Total processing time in seconds';
COMMENT ON COLUMN transcriptions.user_identifier IS 'Optional user identifier for future authentication';

-- Add columns for segments and formatted transcription
ALTER TABLE transcriptions ADD COLUMN IF NOT EXISTS transcription_segments JSONB;
ALTER TABLE transcriptions ADD COLUMN IF NOT EXISTS transcription_formatted TEXT;
ALTER TABLE transcriptions ADD COLUMN IF NOT EXISTS speaker_mappings JSONB;
ALTER TABLE transcriptions ADD COLUMN IF NOT EXISTS title VARCHAR(500);

-- Add indexes for JSONB queries
CREATE INDEX IF NOT EXISTS idx_transcriptions_segments ON transcriptions USING GIN (transcription_segments);
CREATE INDEX IF NOT EXISTS idx_transcriptions_speaker_mappings ON transcriptions USING GIN (speaker_mappings);

-- Add comments
COMMENT ON COLUMN transcriptions.transcription_segments IS 'Structured JSON with segments, timestamps, and speaker labels';
COMMENT ON COLUMN transcriptions.transcription_formatted IS 'Formatted text with inline timestamps and speaker labels';
COMMENT ON COLUMN transcriptions.speaker_mappings IS 'User-defined speaker name mappings (e.g., {"Speaker 1": "John", "Speaker 2": "Mary"})';

-- Create speaker_profiles table for persistent speaker recognition
CREATE TABLE IF NOT EXISTS speaker_profiles (
    id SERIAL PRIMARY KEY,
    speaker_name VARCHAR(255) NOT NULL UNIQUE,
    voice_embedding FLOAT8[] NOT NULL,
    sample_count INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_duration_seconds FLOAT DEFAULT 0,
    description TEXT,
    tags TEXT[],
    confidence_score FLOAT DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for speaker_profiles
CREATE INDEX IF NOT EXISTS idx_speaker_name ON speaker_profiles(speaker_name);
CREATE INDEX IF NOT EXISTS idx_speaker_active ON speaker_profiles(is_active);
CREATE INDEX IF NOT EXISTS idx_speaker_last_seen ON speaker_profiles(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_speaker_tags ON speaker_profiles USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_speaker_embedding ON speaker_profiles USING GIN(voice_embedding);

-- Create speaker_transcription_mapping table to track speaker appearances
CREATE TABLE IF NOT EXISTS speaker_transcription_mapping (
    id SERIAL PRIMARY KEY,
    transcription_id INTEGER NOT NULL REFERENCES transcriptions(id) ON DELETE CASCADE,
    speaker_profile_id INTEGER REFERENCES speaker_profiles(id) ON DELETE SET NULL,
    detected_speaker_label VARCHAR(100) NOT NULL,
    segment_count INTEGER DEFAULT 0,
    total_duration_seconds FLOAT DEFAULT 0,
    average_embedding FLOAT8[],
    similarity_score FLOAT,
    is_confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for speaker_transcription_mapping
CREATE INDEX IF NOT EXISTS idx_speaker_mapping_transcription ON speaker_transcription_mapping(transcription_id);
CREATE INDEX IF NOT EXISTS idx_speaker_mapping_profile ON speaker_transcription_mapping(speaker_profile_id);
CREATE INDEX IF NOT EXISTS idx_speaker_mapping_label ON speaker_transcription_mapping(detected_speaker_label);
CREATE INDEX IF NOT EXISTS idx_speaker_mapping_confirmed ON speaker_transcription_mapping(is_confirmed);

-- Create update trigger for speaker_profiles updated_at
CREATE OR REPLACE FUNCTION update_speaker_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_speaker_profiles_updated_at
    BEFORE UPDATE ON speaker_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_speaker_profiles_updated_at();

-- Add comments for speaker tables
COMMENT ON TABLE speaker_profiles IS 'Stores known speaker voice profiles with embeddings for cross-transcription speaker recognition';
COMMENT ON COLUMN speaker_profiles.voice_embedding IS 'Average voice embedding vector from Resemblyzer for speaker identification';
COMMENT ON COLUMN speaker_profiles.sample_count IS 'Number of audio segments used to build this profile';
COMMENT ON COLUMN speaker_profiles.total_duration_seconds IS 'Total audio duration used for this speaker profile';
COMMENT ON COLUMN speaker_profiles.confidence_score IS 'Confidence score for this speaker profile (0-1)';
COMMENT ON TABLE speaker_transcription_mapping IS 'Links detected speakers in transcriptions to known speaker profiles';
COMMENT ON COLUMN speaker_transcription_mapping.similarity_score IS 'Cosine similarity score between detected speaker and matched profile';
COMMENT ON COLUMN speaker_transcription_mapping.is_confirmed IS 'Whether the speaker match has been confirmed by user';

-- Function to calculate average embedding (useful for speaker profiles)
CREATE OR REPLACE FUNCTION average_embedding(embeddings FLOAT8[][])
RETURNS FLOAT8[] AS $$
DECLARE
    result FLOAT8[];
    sum_arr FLOAT8[];
    emb FLOAT8[];
    i INTEGER;
    count INTEGER := 0;
BEGIN
    IF embeddings IS NULL OR array_length(embeddings, 1) IS NULL THEN
        RETURN NULL;
    END IF;

    -- Initialize sum array with zeros
    sum_arr := ARRAY_FILL(0.0::FLOAT8, ARRAY[array_length(embeddings[1], 1)]);

    -- Sum all embeddings
    FOREACH emb SLICE 1 IN ARRAY embeddings LOOP
        count := count + 1;
        FOR i IN 1..array_length(emb, 1) LOOP
            sum_arr[i] := sum_arr[i] + emb[i];
        END LOOP;
    END LOOP;

    -- Average
    IF count > 0 THEN
        FOR i IN 1..array_length(sum_arr, 1) LOOP
            sum_arr[i] := sum_arr[i] / count;
        END LOOP;
    END IF;

    RETURN sum_arr;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create ai_generated_content table for storing AI-generated content from transcriptions
CREATE TABLE IF NOT EXISTS ai_generated_content (
    id SERIAL PRIMARY KEY,
    transcription_id INTEGER NOT NULL REFERENCES transcriptions(id) ON DELETE CASCADE,
    generation_type VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    model VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(transcription_id, generation_type)
);

-- Create indexes for ai_generated_content
CREATE INDEX IF NOT EXISTS idx_ai_content_transcription ON ai_generated_content(transcription_id);
CREATE INDEX IF NOT EXISTS idx_ai_content_type ON ai_generated_content(generation_type);
CREATE INDEX IF NOT EXISTS idx_ai_content_created ON ai_generated_content(created_at DESC);

-- Add comments for ai_generated_content table
COMMENT ON TABLE ai_generated_content IS 'Stores AI-generated content (summaries, outlines, action items, etc.) for transcriptions';
COMMENT ON COLUMN ai_generated_content.generation_type IS 'Type of AI-generated content (e.g., brief_summary, action_items, sop)';
COMMENT ON COLUMN ai_generated_content.content IS 'The AI-generated content text (typically markdown format)';
COMMENT ON COLUMN ai_generated_content.model IS 'Ollama model used for generation';

-- Create update trigger for ai_generated_content updated_at
CREATE OR REPLACE FUNCTION update_ai_generated_content_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_ai_generated_content_updated_at
    BEFORE UPDATE ON ai_generated_content
    FOR EACH ROW
    EXECUTE FUNCTION update_ai_generated_content_updated_at();