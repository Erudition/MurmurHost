-- Fix email_actions constraint to allow 'error' action
-- This fixes the constraint violation when schedule/memory extraction fails

-- Drop the old constraint
ALTER TABLE email_actions DROP CONSTRAINT IF EXISTS email_actions_action_check;

-- Add new constraint that includes 'error'
ALTER TABLE email_actions ADD CONSTRAINT email_actions_action_check
    CHECK (action IN ('add', 'update', 'delete', 'nothing', 'error'));

-- Add comment explaining the error action
COMMENT ON COLUMN email_actions.action IS 'add = created new entry, update = modified existing, delete = removed entry, nothing = no action needed, error = extraction/processing failed';
