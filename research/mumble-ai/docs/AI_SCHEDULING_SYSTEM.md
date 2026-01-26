# AI Scheduling System Documentation

## Overview

The Mumble AI system now includes a comprehensive **AI-powered scheduling system** that allows both the Mumble bot and SIP bridge to automatically manage calendar events through natural conversation. Users can add, modify, delete, and query their schedule simply by talking to the AI assistant.

## Key Features

### 🤖 Automatic Schedule Management
- **Natural Language Processing**: The AI automatically detects scheduling intents in conversations
- **Event Extraction**: Automatically extracts event details (title, date, time, description, importance) from user messages
- **Smart Date Parsing**: Understands relative dates like "tomorrow", "next Monday", "in 3 days"
- **Context-Aware**: Schedule events are included in the AI's context for answering questions

### 📅 Full CRUD Operations
- **Create**: Add new events via conversation
- **Read**: Query upcoming schedule and specific events
- **Update**: Modify existing events (requires event ID)
- **Delete**: Cancel/remove events by title match

### 🌐 Multi-Access Integration
- **Mumble Bot**: Voice and text conversations automatically manage schedules
- **SIP Bridge**: Phone callers can manage their schedule through voice
- **Web Interface**: Full calendar UI at http://localhost:5002/schedule

## Architecture

### Database Schema

The scheduling system uses the `schedule_events` table in PostgreSQL:

```sql
CREATE TABLE schedule_events (
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
```

### AI Components

#### 1. Schedule Functions (bot.py & bridge.py)

**`get_schedule_events(user_name, start_date, end_date, limit)`**
- Retrieves schedule events for a user within a date range
- Used to provide context in AI prompts
- Returns list of events ordered by date/time

**`add_schedule_event(user_name, title, event_date, event_time, description, importance)`**
- Adds a new schedule event to the database
- Returns the new event ID
- All events are active by default

**`update_schedule_event(event_id, title, event_date, event_time, description, importance)`**
- Updates an existing event (soft update)
- Only updates provided fields
- Returns success/failure boolean

**`delete_schedule_event(event_id)`**
- Soft deletes an event (sets active=FALSE)
- Returns success/failure boolean

**`extract_and_manage_schedule(user_message, assistant_response, user_name)`**
- AI-powered extraction of scheduling intent
- Parses user message for schedule operations
- Automatically performs ADD, UPDATE, or DELETE actions
- Runs asynchronously in background thread

#### 2. Prompt Integration

Schedule events are automatically included in the AI's context:

```python
# Get schedule events for the user (next 30 days)
schedule_events = self.get_schedule_events(
    user_name=user_name,
    start_date=current_datetime.strftime('%Y-%m-%d'),
    end_date=(current_datetime + timedelta(days=30)).strftime('%Y-%m-%d'),
    limit=20
)

# Add to prompt with color-coded importance
if schedule_events:
    full_prompt += "📅 YOUR UPCOMING SCHEDULE (next 30 days):\n"
    for event in schedule_events:
        importance_emoji = "🔴" if event['importance'] >= 9 else "🟠" if event['importance'] >= 7 else "🔵"
        full_prompt += f"{importance_emoji} {event['title']} - {event_date_str} at {event_time_str}\n"
```

### Schedule Extraction Logic

The AI uses Ollama to analyze conversations and extract scheduling intent:

1. **Conversation Analysis**: After each user-assistant exchange, a background thread analyzes the conversation
2. **Intent Detection**: Determines if the user wants to ADD, UPDATE, DELETE, or just query their schedule
3. **Entity Extraction**: Extracts event title, date, time, description, and importance
4. **Date Calculation**: Converts relative dates ("tomorrow", "next week") to absolute YYYY-MM-DD format
5. **Action Execution**: Performs the appropriate database operation

#### Example Extraction Prompt:

```
You are a scheduling assistant analyzing a conversation to manage calendar events.

CURRENT DATE: Friday, October 08, 2025

Conversation:
User: I have a dentist appointment tomorrow at 3pm
Assistant: I've noted your dentist appointment for tomorrow at 3pm.

Analyze this conversation and determine if the user wants to:
1. ADD a new event
2. UPDATE an existing event
3. DELETE/CANCEL an event
4. NOTHING - just asking about schedule

Respond ONLY with JSON:
{"action": "ADD", "title": "Dentist appointment", "date": "2025-10-09", "time": "15:00", "description": null, "importance": 7, "event_id": null}
```

## Usage Examples

### Adding Events

**Voice/Text Conversation:**
```
User: "I have a doctor appointment tomorrow at 2pm"
AI: "I've scheduled your doctor appointment for tomorrow at 2pm."
[Event automatically added to database]
```

**With Details:**
```
User: "Schedule a team meeting on Monday at 10am, it's very important"
AI: "I've scheduled the team meeting for Monday at 10am with high priority."
[Creates event with importance=9]
```

**All-Day Events:**
```
User: "I'm on vacation next Friday"
AI: "I've noted your vacation on next Friday."
[Creates all-day event with no specific time]
```

### Querying Schedule

```
User: "What's on my schedule tomorrow?"
AI: "Tomorrow you have: Dentist appointment at 3pm, Team meeting at 5pm."
[AI reads from schedule context in prompt]
```

```
User: "Do I have anything important this week?"
AI: "You have these important events: Client presentation on Wednesday at 2pm (high priority), Board meeting on Friday at 9am (critical)."
```

### Deleting Events

```
User: "Cancel my dentist appointment"
AI: "I've cancelled your dentist appointment."
[Finds and deletes matching event]
```

### Web Interface

The schedule manager provides a full-featured calendar UI:

**Access**: http://localhost:5002/schedule

**Features:**
- Monthly, weekly, and daily calendar views
- Click date to add event
- Click event to edit
- User filtering
- Color-coded by importance (Red=Critical, Orange=High, Blue=Medium, Gray=Low)
- Drag-and-drop date changes
- Responsive design

## API Endpoints

### Get Schedule Events
```bash
GET /api/schedule?user=USERNAME
```

**Response:**
```json
[
  {
    "id": 1,
    "user_name": "John",
    "title": "Team Meeting",
    "event_date": "2025-10-09",
    "event_time": "14:00:00",
    "description": "Discuss Q4 goals",
    "importance": 7,
    "created_at": "2025-10-08T10:30:00"
  }
]
```

### Add Schedule Event
```bash
POST /api/schedule
Content-Type: application/json

{
  "user_name": "John",
  "title": "Doctor Appointment",
  "event_date": "2025-10-10",
  "event_time": "15:00",
  "description": "Annual checkup",
  "importance": 8
}
```

### Update Schedule Event
```bash
PUT /api/schedule/1
Content-Type: application/json

{
  "title": "Doctor Appointment (Rescheduled)",
  "event_time": "16:00"
}
```

### Delete Schedule Event
```bash
DELETE /api/schedule/1
```

### Get Users with Events
```bash
GET /api/schedule/users
```

## Configuration

### AI System Instructions

Both the Mumble bot and SIP bridge include scheduling instructions in their prompts:

```
SCHEDULING CAPABILITIES:
- You can access the user's calendar/schedule automatically
- When users mention events, appointments, or plans, they are AUTOMATICALLY saved to their schedule
- You can answer questions about upcoming events using the schedule shown below
- Users can ask "What's on my schedule?", "Do I have anything tomorrow?", etc.
```

### Schedule Context Window

- **Time Range**: Next 30 days from current date
- **Event Limit**: Up to 20 events per user
- **Sorting**: Events ordered by date, then time
- **Importance Display**: Color-coded in prompt (🔴 Critical, 🟠 High, 🔵 Medium)

### Background Processing

Schedule extraction runs asynchronously to avoid blocking conversations:

```python
# Extract and manage schedule in background (non-blocking)
threading.Thread(
    target=self.extract_and_manage_schedule,
    args=(transcript, response_text, user_name),
    daemon=True
).start()
```

## Integration Points

### Mumble Bot Integration

**File**: `mumble-bot/bot.py`

- Schedule functions: Lines 1176-1471
- Prompt integration: Lines 1630-1654
- Extraction calls: Lines 565-570, 639-644

### SIP Bridge Integration

**File**: `sip-mumble-bridge/bridge.py`

- Schedule functions: Lines 907-1203
- Prompt integration: Lines 1372-1396
- Extraction calls: Lines 1912-1917

### Web Control Panel

**Files**:
- Backend: `web-control-panel/app.py` (Lines 942-1094)
- Frontend: `web-control-panel/templates/schedule.html`
- Navigation: `web-control-panel/templates/index.html` (Line 243)

## Troubleshooting

### Event Not Added

**Symptom**: User mentions appointment but event doesn't appear in schedule

**Debugging:**
```bash
# Check extraction logs
docker-compose logs -f mumble-bot | grep "schedule"

# Verify database
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT * FROM schedule_events WHERE user_name='USERNAME' ORDER BY created_at DESC LIMIT 5;"
```

**Common Causes:**
- JSON parsing error in extraction (check Ollama response)
- Date calculation error (check current date context)
- Database connection issue

### Schedule Not Showing in Conversation

**Symptom**: AI doesn't know about user's schedule

**Check:**
```bash
# Verify events exist
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT COUNT(*) FROM schedule_events WHERE user_name='USERNAME' AND active=TRUE;"

# Check date range (30 days from now)
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT event_date FROM schedule_events WHERE user_name='USERNAME' AND event_date >= CURRENT_DATE AND event_date <= CURRENT_DATE + INTERVAL '30 days';"
```

### Web Calendar Not Loading

**Symptom**: Calendar page shows errors

**Check:**
```bash
# Verify web control panel is running
docker-compose ps web-control-panel

# Check API endpoint
curl http://localhost:5002/api/schedule/users

# View logs
docker-compose logs web-control-panel
```

## Performance Considerations

### Database Indexes

Recommended indexes for optimal performance:

```sql
CREATE INDEX idx_schedule_user_date ON schedule_events(user_name, event_date) WHERE active = TRUE;
CREATE INDEX idx_schedule_active ON schedule_events(active);
```

### Memory Usage

- Schedule extraction uses Ollama (additional LLM call per conversation)
- Runs in background thread (non-blocking)
- Each extraction ~1-2 seconds with llama3.2

### Context Window Impact

- Each event adds ~1-2 lines to prompt
- Limit of 20 events keeps prompt manageable
- 30-day window balances relevance vs. context size

## Future Enhancements

Potential improvements:

1. **Recurring Events**: Support for daily/weekly/monthly repeating events
2. **Reminders**: Proactive reminders before events
3. **Event Categories**: Tags/categories for better organization
4. **Conflict Detection**: Alert user if events overlap
5. **Calendar Sync**: Integration with Google Calendar, Outlook, etc.
6. **Smart Suggestions**: AI suggests optimal meeting times
7. **Location Support**: Add event location/venue
8. **Attendees**: Multi-user event support

## Security Notes

- Events are user-scoped (one user cannot see another's schedule)
- No authentication in default setup (local network only)
- For production: Add authentication to web interface
- Soft deletes preserve audit trail

## Summary

The AI scheduling system provides seamless calendar management through natural conversation, with full integration across Mumble voice, SIP phone calls, and web interface. The system automatically extracts scheduling intent from conversations and maintains a synchronized calendar for each user, enhancing the AI assistant's capabilities as a personal productivity tool.
