-- Migration script to add email user mappings table
-- This table maps email addresses to user names for personalized AI responses

-- Create email_user_mappings table
CREATE TABLE IF NOT EXISTS email_user_mappings (
    id SERIAL PRIMARY KEY,
    email_address VARCHAR(255) NOT NULL UNIQUE,
    user_name VARCHAR(255) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster email lookups
CREATE INDEX IF NOT EXISTS idx_email_mappings_email ON email_user_mappings(email_address);
CREATE INDEX IF NOT EXISTS idx_email_mappings_user ON email_user_mappings(user_name);

-- Add comment
COMMENT ON TABLE email_user_mappings IS 'Maps email addresses to user names for personalized bot responses';
COMMENT ON COLUMN email_user_mappings.email_address IS 'Email address of the sender';
COMMENT ON COLUMN email_user_mappings.user_name IS 'Associated user name in the system (for memories/schedule lookup)';
COMMENT ON COLUMN email_user_mappings.notes IS 'Optional notes about this mapping';
