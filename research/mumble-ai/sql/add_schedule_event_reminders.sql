-- Migration to add email reminder functionality to schedule_events table
-- This allows users to receive email reminders before scheduled events

-- Add reminder columns to schedule_events table
ALTER TABLE schedule_events 
ADD COLUMN IF NOT EXISTS reminder_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS reminder_minutes INTEGER DEFAULT 60 CHECK (reminder_minutes IN (15, 30, 60)),
ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS recipient_email VARCHAR(255);

-- Create index for efficient reminder queries (find events that need reminders)
CREATE INDEX IF NOT EXISTS idx_schedule_reminder_pending 
ON schedule_events(event_date, event_time, reminder_enabled, reminder_sent) 
WHERE active = TRUE AND reminder_enabled = TRUE AND reminder_sent = FALSE;

-- Add comment explaining the columns
COMMENT ON COLUMN schedule_events.reminder_enabled IS 'Whether email reminder is enabled for this event';
COMMENT ON COLUMN schedule_events.reminder_minutes IS 'Minutes before event to send reminder (15, 30, or 60)';
COMMENT ON COLUMN schedule_events.reminder_sent IS 'Whether the reminder email has been sent';
COMMENT ON COLUMN schedule_events.reminder_sent_at IS 'Timestamp when reminder email was sent';
COMMENT ON COLUMN schedule_events.recipient_email IS 'Email address to send reminder to (NULL uses default from email_settings)';

