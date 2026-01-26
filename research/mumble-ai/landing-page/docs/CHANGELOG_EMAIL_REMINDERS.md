# Changelog: Email Reminders for Scheduled Events

**Date**: October 10, 2025  
**Version**: 1.3.0  
**Feature**: Email Reminders for Calendar Events

## Overview

Implemented automated email reminder system for scheduled calendar events with AI-generated personalized messages.

## What's New

### Email Reminder System
- **Per-Event Reminders**: Enable email reminders for individual calendar events
- **Flexible Timing**: Choose from 15, 30, or 60 minutes before event
- **AI-Generated Messages**: Personalized, friendly reminders using your configured bot persona and Ollama LLM
- **Beautiful HTML Emails**: Professional email design with event details, priority badges, and branding
- **Custom Recipients**: Send to default email or specify custom email per event
- **Automatic Tracking**: Prevents duplicate reminders from being sent
- **NY Timezone**: All reminder calculations use America/New_York timezone

### Database Changes
Added 5 new columns to `schedule_events` table:
- `reminder_enabled` (BOOLEAN) - Toggle reminders on/off
- `reminder_minutes` (INTEGER) - Timing: 15, 30, or 60 minutes
- `reminder_sent` (BOOLEAN) - Tracks if reminder was sent
- `reminder_sent_at` (TIMESTAMP) - When reminder was sent
- `recipient_email` (VARCHAR) - Optional custom recipient

**Migration**: `sql/add_schedule_event_reminders.sql`
- ✅ Safe, non-destructive migration
- ✅ Adds columns only, preserves all existing data
- ✅ Includes optimized index for reminder queries

### UI Updates

#### Schedule Manager (`web-control-panel/templates/schedule.html`)
- Added "📧 Enable Email Reminder" checkbox in event form
- Dropdown selector for reminder timing (15/30/60 minutes)
- Optional email address field for custom recipients
- Reminder fields auto-populate when editing existing events
- Visual feedback for reminder-enabled events

### Backend Updates

#### Web Control Panel (`web-control-panel/app.py`)
- Updated `/api/schedule` GET endpoint to return reminder fields
- Updated `/api/schedule` POST endpoint to accept reminder data on creation
- Updated `/api/schedule/<id>` PUT endpoint to accept reminder updates
- Updated `/api/schedule/upcoming` endpoint to include reminder status

#### Email Summary Service (`email-summary-service/app.py`)
- **New Method**: `get_events_needing_reminders()` - Finds events within reminder window
- **New Method**: `mark_reminder_sent()` - Tracks sent reminders
- **New Method**: `generate_reminder_message()` - AI-powered message generation
- **New Method**: `send_event_reminder()` - Sends formatted reminder emails
- **New Method**: `check_and_send_reminders()` - Main reminder checking logic
- **Enhanced**: Service loop now checks for reminders every 60 seconds
- **Fixed**: Timezone handling using `zoneinfo.ZoneInfo` (America/New_York)

### Email Template Features
- Gradient header with alarm clock emoji
- AI-generated personalized message section
- Event card with date, time, user, and priority
- Color-coded importance badges (red/orange/blue)
- Event description display (if provided)
- Responsive design for mobile devices
- Link back to schedule manager
- Plain text fallback version

### AI Integration
Reminder messages use Ollama to generate contextual, friendly messages based on:
- Event title and description
- Time until event
- Importance level (1-10)
- Your configured bot persona
- Event type (inferred from title)

**Example Prompt Structure**:
```
Generate a friendly, brief reminder message for an upcoming calendar event.
EVENT DETAILS:
- Title: Doctor Appointment
- Date: Friday, October 11, 2025
- Time: 2:00 PM
- Minutes until event: 60
- Importance: 7/10

Generate a short, friendly reminder message (2-3 sentences max).
```

### Timing & Logic

#### Reminder Window
- Checks every 60 seconds for events needing reminders
- Sends reminders within ±5 minute window of scheduled time
- Example: 60-minute reminder sent between 55-65 minutes before event

#### All-Day Events
- Default reminder time: 9:00 AM on event date
- Calculated in America/New_York timezone

#### Duplicate Prevention
- `reminder_sent` flag prevents duplicate sends
- Once sent, reminder marked permanently as sent
- Logged in `email_logs` table with type 'other'

## Files Modified

### New Files
1. `sql/add_schedule_event_reminders.sql` - Database migration
2. `docs/SCHEDULE_EMAIL_REMINDERS.md` - Complete feature documentation
3. `docs/CHANGELOG_EMAIL_REMINDERS.md` - This changelog

### Modified Files
1. `web-control-panel/templates/schedule.html` - UI for reminder settings
2. `web-control-panel/app.py` - API endpoints for reminder data
3. `email-summary-service/app.py` - Reminder checking and sending logic
4. `README.md` - Updated feature list

## Setup Instructions

### 1. Apply Migration
```bash
# PowerShell (Windows)
Get-Content sql/add_schedule_event_reminders.sql | docker exec -i mumble-ai-postgres psql -U mumbleai -d mumble_ai

# Bash (Linux/Mac)
docker exec -i mumble-ai-postgres psql -U mumbleai -d mumble_ai < sql/add_schedule_event_reminders.sql
```

### 2. Rebuild Containers
```bash
docker-compose build --no-cache web-control-panel email-summary-service
```

### 3. Restart Services
```bash
docker-compose up -d web-control-panel email-summary-service
```

### 4. Verify
```bash
# Check logs for reminder checking
docker-compose logs -f email-summary-service

# Should see:
# "Checking for events needing reminders..."
# "Found X events needing reminders"
```

## Usage

### Creating Event with Reminder
1. Navigate to http://localhost:5002/schedule
2. Click "+ Add Event"
3. Fill in event details (title, date, time, etc.)
4. ✅ Check "📧 Enable Email Reminder"
5. Select timing: 15, 30, or 60 minutes before
6. Optional: Enter custom email address
7. Click "Save"

### Email Reminder Content
Subject: `⏰ Reminder: [Event Title]`

Contains:
- AI-generated personalized message from bot persona
- Event details card (date, time, user, importance)
- Priority badge (color-coded)
- Event description (if provided)
- Link to schedule manager

## Configuration

### Email Settings Required
Email reminders use the existing email system. Ensure:
- SMTP settings configured in Web Control Panel
- "Daily Summary Enabled" is ON (enables email system)
- Default recipient email set (or use per-event custom emails)

### Bot Persona
Reminder messages use the bot persona from Settings:
- More professional persona → formal reminders
- Casual persona → friendly, conversational reminders

## Technical Details

### Database Schema
```sql
ALTER TABLE schedule_events 
ADD COLUMN reminder_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN reminder_minutes INTEGER DEFAULT 60 
    CHECK (reminder_minutes IN (15, 30, 60)),
ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE,
ADD COLUMN reminder_sent_at TIMESTAMP,
ADD COLUMN recipient_email VARCHAR(255);
```

### Optimized Index
```sql
CREATE INDEX idx_schedule_reminder_pending 
ON schedule_events(event_date, event_time, reminder_enabled, reminder_sent) 
WHERE active = TRUE AND reminder_enabled = TRUE AND reminder_sent = FALSE;
```

### API Response Example
```json
{
  "id": 42,
  "user_name": "John",
  "title": "Team Meeting",
  "event_date": "2025-10-15",
  "event_time": "14:30",
  "description": "Quarterly review",
  "importance": 8,
  "reminder_enabled": true,
  "reminder_minutes": 60,
  "reminder_sent": false,
  "recipient_email": null
}
```

## Bug Fixes

### Timezone Handling
- **Issue**: Mixed use of `pytz.localize()` with `zoneinfo.ZoneInfo`
- **Fix**: Standardized on `datetime.replace(tzinfo=ny_tz)`
- **Impact**: Reminders now calculate correctly in NY timezone

## Known Limitations

1. **One Reminder Per Event**: Each event can only have one reminder time
2. **No Recurring Events**: Reminders don't support recurring events yet
3. **No Snooze**: Once sent, reminders cannot be snoozed or resent
4. **Email Only**: No SMS or push notification support yet

## Future Enhancements

Potential improvements:
- Multiple reminders per event (e.g., 1 hour + 15 minutes)
- SMS reminders via Twilio integration
- Push notifications
- Recurring event reminder support
- Snooze/dismiss functionality
- Reminder templates
- Multi-event digest emails
- Calendar sync (Google Calendar, Outlook, etc.)

## Testing

### Manual Testing Checklist
- [x] Create event with 15-minute reminder
- [x] Create event with 30-minute reminder
- [x] Create event with 60-minute reminder
- [x] Edit event to enable reminder
- [x] Edit event to disable reminder
- [x] Custom email address for reminder
- [x] All-day event reminder
- [x] Verify reminder sent at correct time
- [x] Verify no duplicate reminders
- [x] Check beautiful HTML email rendering
- [x] Verify AI message generation
- [x] Check NY timezone calculations

### Performance Testing
- Reminder queries use optimized index
- Minimal database load (checks every 60 seconds)
- Quick response time (<1 second for query)

## Documentation

- **Complete Guide**: `docs/SCHEDULE_EMAIL_REMINDERS.md`
- **Quick Reference**: Main README.md updated
- **Migration Script**: `sql/add_schedule_event_reminders.sql`

## Support & Troubleshooting

### Common Issues

**Reminders Not Sending**
- Ensure "Daily Summary Enabled" is ON in Email Settings
- Verify SMTP settings with "Send Test Email"
- Check event date/time is in the future
- Confirm reminder hasn't already been sent

**Check Logs**
```bash
docker-compose logs -f email-summary-service
```

**Verify Migration**
```bash
docker exec -i mumble-ai-postgres psql -U mumbleai -d mumble_ai -c "\d schedule_events"
```

## Security Considerations

- Email credentials stored in database (use environment variables for production)
- SMTP supports TLS/SSL encryption
- No sensitive event data exposed in logs
- Recipient emails validated before sending

## Compatibility

- **Database**: PostgreSQL 16+
- **Python**: 3.11+
- **Dependencies**: zoneinfo (Python 3.9+ standard library)
- **Browsers**: Modern browsers for web UI (Chrome, Firefox, Safari, Edge)

## Credits

Developed as part of the Mumble AI project to enhance scheduling capabilities with intelligent, AI-powered event reminders.

---

**Version**: 1.3.0  
**Release Date**: October 10, 2025  
**Status**: ✅ Production Ready

