# AI Scheduling Quick Reference Guide

## Overview

The AI assistant can automatically manage your calendar through natural conversation. Just talk about your plans, and the AI handles the rest.

## Usage Examples

### ✅ Adding Events

| What to Say | What Happens |
|------------|--------------|
| "I have a dentist appointment tomorrow at 3pm" | Event added for tomorrow at 15:00 |
| "Schedule a team meeting Monday at 10am" | Event added for next Monday at 10:00 |
| "Remind me about the conference next Friday" | All-day event added for next Friday |
| "I'm on vacation from the 15th to the 20th" | Event added for date range |

### 📋 Querying Schedule

| What to Say | What Happens |
|------------|--------------|
| "What's on my schedule tomorrow?" | AI lists tomorrow's events |
| "Do I have anything this week?" | AI lists this week's events |
| "Am I free on Friday?" | AI checks Friday's schedule |
| "What time is my meeting on Monday?" | AI finds Monday meeting time |

### ✏️ Modifying Events

| What to Say | What Happens |
|------------|--------------|
| "Move my dentist appointment to 4pm" | Updates event time (if unique title match) |
| "Change the meeting to Tuesday" | Updates event date |

### ❌ Deleting Events

| What to Say | What Happens |
|------------|--------------|
| "Cancel my dentist appointment" | Deletes matching event |
| "Remove the meeting on Monday" | Deletes Monday meeting |

## Web Interface

**URL**: http://localhost:5002/schedule

**Features**:
- 📅 Monthly, weekly, daily calendar views
- ➕ Click any date to add event
- ✏️ Click any event to edit
- 🗑️ Delete button when editing
- 🔍 Filter by user
- 🔄 Refresh calendar

**Color Coding**:
- 🔴 **Red** = Critical (importance 9-10)
- 🟠 **Orange** = High (importance 7-8)
- 🔵 **Blue** = Medium (importance 4-6)
- ⚪ **Gray** = Low (importance 1-3)

## API Quick Reference

### Get Events
```bash
curl http://localhost:5002/api/schedule?user=USERNAME
```

### Add Event
```bash
curl -X POST http://localhost:5002/api/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "John",
    "title": "Team Meeting",
    "event_date": "2025-10-15",
    "event_time": "14:00",
    "importance": 7
  }'
```

### Update Event
```bash
curl -X PUT http://localhost:5002/api/schedule/1 \
  -H "Content-Type: application/json" \
  -d '{"event_time": "15:00"}'
```

### Delete Event
```bash
curl -X DELETE http://localhost:5002/api/schedule/1
```

## Database Commands

### View Schedule
```bash
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "
  SELECT id, title, event_date, event_time, importance
  FROM schedule_events
  WHERE user_name='USERNAME' AND active=TRUE
  ORDER BY event_date, event_time;
"
```

### Add Event Manually
```bash
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "
  INSERT INTO schedule_events (user_name, title, event_date, event_time, importance)
  VALUES ('John', 'Doctor Appointment', '2025-10-15', '14:00', 8);
"
```

### Delete Event
```bash
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "
  UPDATE schedule_events
  SET active=FALSE
  WHERE id=1;
"
```

## How It Works

### 1. Automatic Detection
When you mention events, appointments, or plans in conversation, the AI automatically:
- Detects scheduling intent
- Extracts event details (title, date, time)
- Calculates absolute dates from relative terms ("tomorrow", "next Monday")
- Saves to database

### 2. Context Integration
Your upcoming schedule (next 30 days) is automatically included when you ask questions:
```
User: "What's on my schedule?"
AI: [Reads from database] "You have dentist at 3pm tomorrow, team meeting Monday at 10am..."
```

### 3. Smart Date Parsing
The AI understands:
- ✅ "tomorrow" → calculates tomorrow's date
- ✅ "next Monday" → finds next occurrence of Monday
- ✅ "in 3 days" → adds 3 days to current date
- ✅ "October 15th" → converts to YYYY-MM-DD format
- ✅ "3pm" → converts to 15:00 24-hour format

## Access Methods

### 1. Mumble Voice/Text
- Connect to Mumble server (localhost:64738)
- Talk to the AI bot
- Mention events in natural conversation
- Ask about your schedule

### 2. SIP Phone
- Call SIP bridge (localhost:5060)
- Talk to the AI through phone
- Schedule management works the same

### 3. Web Calendar
- Open http://localhost:5002/schedule
- Visual calendar interface
- Drag-and-drop scheduling
- Full event management

## Tips & Best Practices

### ✨ Best Practices
- Be specific with dates: "tomorrow at 3pm" vs "tomorrow"
- Include importance: "very important meeting" sets higher priority
- Use clear titles: "dentist appointment" vs "appointment"
- Confirm: "What's on my schedule?" to verify events were added

### ⚠️ Limitations
- Update requires event ID (web interface needed for easy updates)
- Delete finds first matching title (be specific)
- Time range limited to next 30 days in AI context
- No recurring events (yet)

## Troubleshooting

### Event Not Added?
```bash
# Check extraction logs
docker-compose logs -f mumble-bot | grep "schedule"

# Verify in database
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "
  SELECT * FROM schedule_events
  WHERE user_name='USERNAME'
  ORDER BY created_at DESC LIMIT 5;
"
```

### AI Doesn't Know About Events?
- Events older than 30 days won't show in context
- Check if events are active: `WHERE active=TRUE`
- Verify user name matches exactly

### Web Calendar Issues?
```bash
# Check service
docker-compose ps web-control-panel

# Test API
curl http://localhost:5002/api/schedule/users

# View logs
docker-compose logs web-control-panel
```

## Configuration Files

**Mumble Bot**: `mumble-bot/bot.py`
- Schedule functions: Lines 1176-1471
- Prompt integration: Lines 1630-1654

**SIP Bridge**: `sip-mumble-bridge/bridge.py`
- Schedule functions: Lines 907-1203
- Prompt integration: Lines 1372-1396

**Web Panel**: `web-control-panel/app.py`
- API endpoints: Lines 942-1094
- Frontend: `templates/schedule.html`

## Support

For detailed documentation, see:
- Full Guide: `docs/AI_SCHEDULING_SYSTEM.md`
- Architecture: `docs/ARCHITECTURE.md`
- API Reference: `docs/API.md`
