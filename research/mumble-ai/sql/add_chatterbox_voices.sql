-- Migration: Add Chatterbox TTS Voice Presets Table
-- Description: Add table for storing voice cloning presets for Chatterbox TTS
-- Date: 2025-10-09

-- Create chatterbox_voices table
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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_chatterbox_voices_name ON chatterbox_voices(name);
CREATE INDEX IF NOT EXISTS idx_chatterbox_voices_language ON chatterbox_voices(language);
CREATE INDEX IF NOT EXISTS idx_chatterbox_voices_active ON chatterbox_voices(is_active);
CREATE INDEX IF NOT EXISTS idx_chatterbox_voices_tags ON chatterbox_voices USING GIN(tags);

-- Create update trigger for updated_at
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

-- Add sample voices (optional - comment out if not needed)
-- INSERT INTO chatterbox_voices (name, description, reference_audio_path, language, created_by) VALUES
-- ('Default Male', 'Default male voice preset', '/app/models/samples/male_sample.wav', 'en', 'system'),
-- ('Default Female', 'Default female voice preset', '/app/models/samples/female_sample.wav', 'en', 'system');

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON chatterbox_voices TO mumbleai;
GRANT USAGE, SELECT ON SEQUENCE chatterbox_voices_id_seq TO mumbleai;

-- Add comment
COMMENT ON TABLE chatterbox_voices IS 'Stores voice cloning presets for Chatterbox TTS service';
COMMENT ON COLUMN chatterbox_voices.reference_audio_path IS 'Path to reference audio file for voice cloning';
COMMENT ON COLUMN chatterbox_voices.metadata IS 'Additional metadata in JSON format (e.g., speaker info, recording details)';

