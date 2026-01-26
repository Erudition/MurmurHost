# Persistent Memories System

## Overview

The Mumble AI bot now includes an intelligent **Persistent Memories** system that automatically extracts and stores important information from conversations. The bot can remember schedules, facts, preferences, tasks, and more - and you can view and manage all memories through the web control panel.

## How It Works

### Automatic Memory Extraction

After **every conversation exchange**, the bot analyzes the dialogue and automatically extracts important information using AI:

1. **User says something** → Bot responds
2. **Bot analyzes the exchange** using Ollama
3. **Extracts important information** into categories:
   - 📅 **Schedule**: Appointments, meetings, events with dates/times
   - 💡 **Fact**: Personal information, preferences, relationships
   - ✓ **Task**: Things to do, reminders, action items
   - ❤️ **Preference**: Likes, dislikes, habits
   - ⏰ **Reminder**: Time-based reminders
   - 📌 **Other**: Anything else important

4. **Saves to database** with importance score (1-10)
5. **Bot uses memories** in future conversations

### Memory Usage

When you talk to the bot, it includes your saved memories in its context:

```
User: "What do I have scheduled for Monday?"
Bot retrieves: [SCHEDULE] Funeral at church on Monday at 9am
Bot responds: "You have a funeral at the church on Monday at 9am."
```

The bot will **accurately recall** information from memories instead of making things up!

## Web Control Panel

Access the memories interface at: **http://localhost:5002**

### Viewing Memories

The **🧠 Persistent Memories** section shows all saved memories with:

- **User filter**: See memories for specific users
- **Category filter**: Filter by schedule, fact, task, etc.
- **Color-coded importance**:
  - Gray (1-3): Low importance
  - Blue (4-6): Medium importance
  - Orange (7-8): High importance
  - Red (9-10): Critical importance
- **Timestamps**: When the memory was extracted
- **Delete button**: Remove incorrect or outdated memories

### Adding Manual Memories

Click **"+ Add Memory"** to manually create a memory:

1. Enter **User Name**
2. Select **Category** (schedule, fact, task, etc.)
3. Enter **Memory Content** (e.g., "Funeral at church Monday 9am")
4. Set **Importance** (1-10)
5. Click **Save Memory**

### Managing Memories

- **Filter by user**: Select a user to see only their memories
- **Filter by category**: Show only schedules, facts, tasks, etc.
- **Delete memories**: Click the delete button to remove
- **Refresh**: Update the list with latest memories

## Database Schema

### persistent_memories Table

```sql
CREATE TABLE persistent_memories (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,  -- schedule, fact, task, preference, reminder, other
    content TEXT NOT NULL,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(255),
    importance INTEGER DEFAULT 5 CHECK (importance >= 1 AND importance <= 10),
    tags TEXT[],
    active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_date DATE,         -- For schedule category: exact date of event (YYYY-MM-DD)
    event_time TIME          -- For schedule category: exact time of event (HH:MM)
);
```

### Event Date and Time for Schedule Memories

**NEW FEATURE**: Schedule category memories now include exact date and time information!

When the AI extracts a schedule memory, it:
1. **Calculates the exact date** from relative terms ("tomorrow", "next Monday", etc.)
2. **Stores date in YYYY-MM-DD format** in `event_date` field
3. **Stores time in HH:MM format** in `event_time` field (24-hour)
4. **Includes date/time in content** for human readability

**Examples**:
- User says: "I have a dentist appointment tomorrow at 3pm"
- Bot extracts:
  - `content`: "Dentist appointment on 2025-10-09 at 15:00"
  - `event_date`: "2025-10-09"
  - `event_time`: "15:00"
  - `category`: "schedule"
  - `importance`: 7-8

When displayed in prompts, schedule memories show the full formatted date:
```
[SCHEDULE] Dentist appointment on 2025-10-09 at 15:00 (Date: Wednesday, October 09, 2025, Time: 15:00)
```

### Memory Categories

| Category | Icon | Use Case | Example |
|----------|------|----------|---------|
| schedule | 📅 | Events, appointments, meetings | "Dentist appointment on 2025-10-09 at 15:00" |
| fact | 💡 | Personal info, relationships | "Lives in New York, has 2 cats" |
| task | ✓ | To-dos, action items | "Buy groceries, finish report" |
| preference | ❤️ | Likes, dislikes, habits | "Prefers tea over coffee" |
| reminder | ⏰ | Time-based reminders | "Call mom on her birthday" |
| other | 📌 | Miscellaneous | "Password hint: first pet name" |

## API Endpoints

### GET /api/memories
Get all memories (with optional filters)

**Query Parameters:**
- `user` - Filter by user name
- `category` - Filter by category

**Response:**
```json
[
  {
    "id": 1,
    "user_name": "Charles",
    "category": "schedule",
    "content": "Funeral at church on Monday at 9am",
    "extracted_at": "2025-10-04T21:50:33",
    "importance": 8,
    "tags": [],
    "active": true
  }
]
```

### POST /api/memories
Create a new memory manually

**Request Body:**
```json
{
  "user_name": "Charles",
  "category": "schedule",
  "content": "Doctor appointment Wednesday 2pm",
  "importance": 7,
  "tags": ["health", "appointment"]
}
```

### DELETE /api/memories/{id}
Delete (deactivate) a memory

### PUT /api/memories/{id}
Update a memory

**Request Body:**
```json
{
  "content": "Updated content",
  "importance": 9
}
```

### GET /api/users
Get list of users who have memories

## How the Bot Uses Memories

The bot's prompt now includes three types of context:

1. **IMPORTANT SAVED INFORMATION** (Persistent Memories)
   - Top 10 most important memories for the user
   - Sorted by importance, then recency
   - Used to answer factual questions

2. **BACKGROUND CONTEXT** (Semantic Memory)
   - Similar past conversations
   - Helps understand context
   - NOT brought up unless relevant

3. **Current Conversation** (Short-term Memory)
   - Last 3 exchanges in current session
   - Immediate conversation flow

### Example Prompt Structure

```
CRITICAL RULES: Be brief, truthful, no hallucination...

Your personality: [Bot persona]

IMPORTANT SAVED INFORMATION:
[SCHEDULE] Funeral at church on Monday at 9am
[FACT] Lives in New York City
[PREFERENCE] Prefers tea over coffee

BACKGROUND CONTEXT (understanding only):
[Past similar conversations...]

Current conversation:
User: Good morning!
You: Good morning! How are you?

User: What do I have Monday?
You:
```

The bot will respond: "You have a funeral at the church on Monday at 9am" ✅

## Configuration

Memory extraction can be tuned in the bot code:

### Memory Extraction Settings

```python
# mumble-bot/bot.py - extract_and_save_memory()

# Temperature for extraction (lower = more consistent)
'temperature': 0.3

# Categories extracted
categories = ['schedule', 'fact', 'task', 'preference', 'other']
```

### Memory Display Limits

```python
# mumble-bot/bot.py - get_persistent_memories()

# Number of memories included in bot context
persistent_memories = self.get_persistent_memories(user_name, limit=10)
```

## Troubleshooting

### Memories Not Being Extracted

1. **Check Ollama is running**: `curl http://localhost:11434/api/tags`
2. **Check bot logs**: `docker-compose logs -f mumble-bot | grep "Extracted memory"`
3. **Verify database**: `docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT * FROM persistent_memories;"`

### Memories Not Appearing in Web Panel

1. **Check web panel logs**: `docker-compose logs -f web-control-panel`
2. **Verify API**: `curl http://localhost:5002/api/memories`
3. **Check browser console**: F12 → Console tab

### Bot Not Using Memories

1. **Verify memories exist**: Check web control panel
2. **Check prompt building**: Look for "IMPORTANT SAVED INFORMATION" in logs
3. **Verify user names match**: Case-sensitive matching

## Performance Notes

- **Memory extraction runs in background** - doesn't slow down responses
- **Embeddings are NOT generated** for memories (unlike conversation history)
- **Database queries are optimized** with indexes on user_name, category, importance
- **Memories are cached** in prompt context (no repeated DB queries per message)

## Future Enhancements

The system is designed to support:

- **Memory tagging** - Already in schema, can be used for advanced filtering
- **Memory search** - Full-text search across memories
- **Memory expiration** - Auto-archive old memories
- **Memory importance auto-adjustment** - Learn which memories are used most
- **Memory merging** - Combine duplicate/similar memories
- **Export/Import** - Backup and restore memories

## Examples

### Example 1: Schedule Management

```
User: "I have a dentist appointment next Tuesday at 3pm"
Bot: "Got it, I'll remember that!"
→ Extracts: [SCHEDULE] Dentist appointment Tuesday 3pm (importance: 7)

Later...
User: "What do I have Tuesday?"
Bot: "You have a dentist appointment at 3pm"
```

### Example 2: Personal Preferences

```
User: "I really hate mushrooms in my food"
Bot: "Noted! I'll remember you don't like mushrooms"
→ Extracts: [PREFERENCE] Dislikes mushrooms (importance: 5)

Later...
User: "What should I order for dinner?"
Bot: "How about pizza? Just make sure to skip the mushrooms since you don't like them!"
```

### Example 3: Tasks and Reminders

```
User: "Remind me to call mom this weekend"
Bot: "I'll remember to remind you!"
→ Extracts: [TASK] Call mom this weekend (importance: 6)

User: "What do I need to do this weekend?"
Bot: "You need to call your mom this weekend"
```

## Migration Guide

If you have an existing Mumble AI installation, run the migration:

```bash
# Apply the memories table migration
docker exec -i mumble-ai-postgres psql -U mumbleai mumble_ai < migrate-memories.sql

# Rebuild and restart services
docker-compose build mumble-bot web-control-panel
docker-compose restart mumble-bot web-control-panel
```

## Summary

The Persistent Memories system gives your Mumble AI bot a **real memory** that persists across sessions. It:

✅ **Automatically extracts** important information from conversations
✅ **Stores memories** in a structured database
✅ **Uses memories** to give accurate, contextual responses
✅ **Visual management** through the web control panel
✅ **Never forgets** schedules, facts, preferences, and tasks

Your bot will now remember what you tell it and use that information intelligently in future conversations!
