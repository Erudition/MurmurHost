# Schedule Event Email Reminders

## Overview

The Mumble AI system now supports automated email reminders for scheduled calendar events. Reminders can be sent 15 minutes, 30 minutes, or 1 hour before events, with AI-generated personalized messages using your configured Ollama LLM and bot persona.

## Features

- ✅ **Flexible Reminder Timing**: Choose 15, 30, or 60 minutes before event
- ✅ **AI-Generated Messages**: Personalized, friendly reminder messages from your AI persona
- ✅ **Beautiful Email Design**: Professional HTML emails with event details
- ✅ **Per-Event Configuration**: Enable reminders for specific events only
- ✅ **Custom Recipients**: Send to default email or specify per-event recipients
- ✅ **Automatic Tracking**: Prevents duplicate reminders from being sent

## Setup Instructions

### 1. Apply Database Migration

**IMPORTANT**: This migration is safe and will NOT delete any existing data. It only adds new columns to the `schedule_events` table.

```bash
# Connect to your PostgreSQL database and run the migration
docker exec -i postgres psql -U mumbleai -d mumble_ai < sql/add_schedule_event_reminders.sql
```

Or manually via psql:

```bash
docker exec -it postgres psql -U mumbleai -d mumble_ai
```

Then paste the contents of `sql/add_schedule_event_reminders.sql`.

### 2. Restart Services

After applying the migration, restart the relevant services:

```bash
docker-compose restart web-control-panel email-summary-service
```

### 3. Configure Email Settings

Ensure your email settings are configured in the Web Control Panel:

1. Navigate to **http://localhost:5002** (Web Control Panel)
2. Go to **Email Settings**
3. Configure:
   - SMTP settings (host, port, credentials)
   - Default recipient email address
   - Enable "Daily Summary" (the email system must be enabled for reminders to work)

## Using Email Reminders

### Creating an Event with Reminder

1. Navigate to **http://localhost:5002/schedule** (Schedule Manager)
2. Click **"+ Add Event"**
3. Fill in event details:
   - User Name
   - Event Title
   - Date and Time
   - Description (optional)
   - Importance (1-10)
4. **Enable Email Reminder**:
   - Check the "📧 Enable Email Reminder" checkbox
   - Select reminder timing: 15, 30, or 60 minutes before
   - Optionally specify a custom email address (or leave blank for default)
5. Click **Save**

### Editing Existing Events

1. Click on any event in the calendar
2. In the edit modal, you can:
   - Enable/disable email reminders
   - Change reminder timing
   - Update recipient email

### How Reminders Work

The `email-summary-service` container checks for upcoming events every minute:

1. **Event Detection**: Finds events with reminders enabled that haven't been sent yet
2. **Timing Check**: Determines if current time is within 5 minutes of the reminder time
3. **Message Generation**: Uses Ollama to generate a personalized, friendly reminder message based on:
   - Your configured bot persona
   - Event details (title, date, time, description, importance)
   - Time until event
4. **Email Sending**: Sends a beautiful HTML email with:
   - AI-generated personalized message
   - Event details card
   - Priority badge
   - Link back to schedule manager
5. **Tracking**: Marks reminder as sent to prevent duplicates

## Email Reminder Examples

### High Priority Event
```
Subject: ⏰ Reminder: Important Client Meeting

[AI-generated message]:
Hey! Just a quick heads up - your important client meeting is coming up in 30 minutes. 
Make sure you have all your materials ready. You've got this! 🎯

Event Details:
📅 Friday, October 10, 2025
🕐 2:00 PM
👤 John
🔴 High Priority
```

### Regular Event
```
Subject: ⏰ Reminder: Dentist Appointment

[AI-generated message]:
Friendly reminder that you have a dentist appointment in 1 hour. 
Don't forget to bring your insurance card!

Event Details:
📅 Monday, October 13, 2025
🕐 3:30 PM
👤 Sarah
🔵 Normal
```

## Database Schema

The following columns were added to `schedule_events`:

| Column | Type | Description |
|--------|------|-------------|
| `reminder_enabled` | BOOLEAN | Whether reminder is enabled (default: FALSE) |
| `reminder_minutes` | INTEGER | Minutes before event (15, 30, or 60) |
| `reminder_sent` | BOOLEAN | Whether reminder was sent (default: FALSE) |
| `reminder_sent_at` | TIMESTAMP | When reminder was sent |
| `recipient_email` | VARCHAR(255) | Custom recipient email (optional) |

## Configuration Options

### Reminder Timing Options

- **15 minutes**: For last-minute preparation
- **30 minutes**: Standard reminder time
- **60 minutes (1 hour)**: Default, gives plenty of prep time

### Email Recipients

- **Default**: Uses the recipient email from Email Settings
- **Custom**: Specify a different email address for specific events

## Troubleshooting

### Reminders Not Sending

1. **Check Email Settings**:
   - Ensure "Daily Summary Enabled" is ON (reminders use the same email system)
   - Verify SMTP settings are correct
   - Test with "Send Test Email" button

2. **Check Event Configuration**:
   - Reminder checkbox must be enabled
   - Event must be in the future
   - Reminder hasn't already been sent (`reminder_sent` = FALSE)

3. **Check Service Logs**:
   ```bash
   docker-compose logs -f email-summary-service
   ```

4. **Verify Database Migration**:
   ```bash
   docker exec -it postgres psql -U mumbleai -d mumble_ai -c "\d schedule_events"
   ```
   
   Should show the reminder columns.

### Testing Reminders

To test the reminder system:

1. Create an event 1-2 hours in the future
2. Enable reminder with 60-minute timing
3. Wait for the reminder time window (±5 minutes)
4. Check email and service logs

Or for immediate testing:

1. Create an event 20 minutes in the future
2. Enable reminder with 15-minute timing
3. Check logs in ~5 minutes

## Email Logs

All reminder emails are logged in the `email_logs` table:

```sql
SELECT * FROM email_logs 
WHERE email_type = 'other' 
AND subject LIKE '%Reminder:%' 
ORDER BY timestamp DESC;
```

## API Reference

### Schedule Event Fields

When creating/updating events via API:

```json
{
  "user_name": "John",
  "title": "Doctor Appointment",
  "event_date": "2025-10-15",
  "event_time": "14:30",
  "description": "Annual checkup",
  "importance": 7,
  "reminder_enabled": true,
  "reminder_minutes": 60,
  "recipient_email": "john@example.com"
}
```

## Advanced Features

### AI Persona Integration

Reminder messages use your configured AI persona from the bot configuration. To customize:

1. Go to Web Control Panel → Settings
2. Update "Bot Persona" field
3. Reminders will use this persona for message generation

### Custom Reminder Messages

The system uses Ollama to generate contextual messages based on:
- Event type (inferred from title)
- Importance level
- Time until event
- Event description

Example prompts:
- High importance + soon: More urgent, encouraging tone
- Normal importance: Friendly, casual reminder
- All-day events: Morning reminder with calm tone

## Security & Privacy

- ✅ Email credentials stored in database (use environment variables for production)
- ✅ Reminders only sent to configured recipients
- ✅ No sensitive event data exposed in logs
- ✅ SMTP supports TLS/SSL encryption

## Future Enhancements

Potential improvements (not yet implemented):

- SMS reminders via Twilio
- Push notifications
- Recurring event reminders
- Snooze functionality
- Multi-event digest emails
- Reminder templates

## Support

For issues or questions:
1. Check service logs: `docker-compose logs -f email-summary-service`
2. Verify database migration applied
3. Test email settings with test email button
4. Check Email Logs in Web Control Panel

## Summary

The email reminder system provides automated, AI-powered notifications for your scheduled events. It integrates seamlessly with the existing Mumble AI infrastructure, using your configured bot persona and email settings to deliver personalized, timely reminders that help you stay on top of your schedule.

