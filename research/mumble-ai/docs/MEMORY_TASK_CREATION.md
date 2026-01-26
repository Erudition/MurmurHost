# Memory and Task Creation System

## Overview

The Mumble AI bot implements an intelligent memory and task creation system that automatically extracts, categorizes, and stores important information from conversations. The system uses AI-powered analysis to identify schedules, facts, preferences, tasks, and other critical information, then makes this information available for future conversations.

## Memory Extraction Process

### Automatic Memory Extraction

After every conversation exchange, the bot automatically analyzes the dialogue and extracts important information:

1. **User says something** → Bot responds
2. **Bot analyzes the exchange** using Ollama AI
3. **Extracts important information** into structured categories
4. **Assigns importance scores** (1-10) based on content analysis
5. **Saves to database** with metadata (user, session, timestamp)
6. **Makes memories available** for future conversations

### Extraction Algorithm

The memory extraction uses a specialized AI prompt to analyze conversations:

```python
extraction_prompt = f"""Analyze this conversation exchange and extract ANY important information that should be remembered.

User said: "{user_message}"
Assistant responded: "{assistant_response}"

Extract information in these categories:
- schedule: appointments, meetings, events with dates/times
- fact: personal information, preferences, relationships, important details
- task: things to do, reminders, action items
- preference: likes, dislikes, habits
- other: anything else important

Return ONLY a JSON array of memories (can be empty if nothing important).
Each memory should have:
{{"category": "schedule|fact|task|preference|other", "content": "brief description", "importance": 1-10}}

If there's nothing important to remember, return: []

JSON:"""
```

### Extraction Configuration

The extraction process uses specific settings for consistency:

```python
response = requests.post(
    f"{ollama_url}/api/generate",
    json={
        'model': ollama_model,
        'prompt': extraction_prompt,
        'stream': False,
        'options': {'temperature': 0.3}  # Lower temp for more consistent extraction
    },
    timeout=30
)
```

## Memory Categories

### 1. **📅 Schedule**
- **Purpose**: Time-based events and appointments
- **Examples**: "Doctor appointment Wednesday 2pm", "Meeting with John on Friday"
- **Usage**: Calendar queries and scheduling reminders
- **Importance**: Typically 7-9 for confirmed appointments

### 2. **💡 Fact**
- **Purpose**: Personal information and important details
- **Examples**: "Lives in New York City", "Works as a software engineer"
- **Usage**: Personal context and relationship building
- **Importance**: Typically 5-8 for significant facts

### 3. **✓ Task**
- **Purpose**: Action items and things to do
- **Examples**: "Call the dentist", "Buy groceries", "Finish the report"
- **Usage**: Task management and reminders
- **Importance**: Typically 6-8 for actionable items

### 4. **❤️ Preference**
- **Purpose**: Likes, dislikes, and habits
- **Examples**: "Prefers tea over coffee", "Likes Italian food", "Hates mushrooms"
- **Usage**: Personalization and recommendation
- **Importance**: Typically 4-7 for preferences

### 5. **⏰ Reminder**
- **Purpose**: Time-based reminders and notifications
- **Examples**: "Take medication at 8am", "Call mom on Sunday"
- **Usage**: Automated reminders and notifications
- **Importance**: Typically 6-9 for important reminders

### 6. **📌 Other**
- **Purpose**: Miscellaneous important information
- **Examples**: "Allergic to peanuts", "Has a dog named Max"
- **Usage**: General context and safety information
- **Importance**: Varies based on content

## Importance Scoring System

### Scoring Criteria

The bot assigns importance scores (1-10) based on:

- **Urgency**: Time-sensitive information gets higher scores
- **Personal significance**: Important personal details score higher
- **Actionability**: Tasks and reminders get higher scores
- **Frequency**: Information mentioned multiple times scores higher
- **Context**: Information in important conversations scores higher

### Score Ranges

- **1-3 (Gray)**: Low importance - general preferences, minor facts
- **4-6 (Blue)**: Medium importance - regular tasks, common preferences
- **7-8 (Orange)**: High importance - important appointments, critical tasks
- **9-10 (Red)**: Critical importance - urgent tasks, safety information

### Scoring Examples

```json
[
  {
    "category": "schedule",
    "content": "Doctor appointment Wednesday 2pm",
    "importance": 8
  },
  {
    "category": "preference",
    "content": "Prefers tea over coffee",
    "importance": 5
  },
  {
    "category": "task",
    "content": "Call the dentist tomorrow",
    "importance": 7
  },
  {
    "category": "fact",
    "content": "Allergic to peanuts",
    "importance": 9
  }
]
```

## Memory Storage

### Database Schema

Memories are stored in the `persistent_memories` table:

```sql
CREATE TABLE persistent_memories (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(255),
    importance INTEGER DEFAULT 5,
    tags TEXT[],
    active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Storage Process

1. **Parse JSON response** from extraction
2. **Validate memory structure** (category, content, importance)
3. **Save to database** with user and session metadata
4. **Log extraction results** for monitoring
5. **Make available** for future conversations

```python
def save_persistent_memory(self, user_name: str, category: str, content: str, 
                          session_id: str = None, importance: int = 5, 
                          tags: List[str] = None):
    conn = self.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO persistent_memories
        (user_name, category, content, session_id, importance, tags)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (user_name, category, content, session_id, importance, tags or [])
    )
    conn.commit()
```

## Memory Retrieval

### Retrieval Process

When generating responses, the bot retrieves relevant memories:

1. **Query database** for user's memories
2. **Sort by importance** and recency
3. **Limit results** to prevent prompt overflow (default: 10)
4. **Include in prompt** as "IMPORTANT SAVED INFORMATION"
5. **Use for factual responses** to user questions

### Retrieval Query

```python
def get_persistent_memories(self, user_name: str, limit: int = 10):
    conn = self.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT category, content, importance, extracted_at
        FROM persistent_memories
        WHERE user_name = %s AND active = TRUE
        ORDER BY importance DESC, extracted_at DESC
        LIMIT %s
        """,
        (user_name, limit)
    )
    return cursor.fetchall()
```

### Memory Usage in Prompts

Retrieved memories are integrated into the bot's prompt:

```
IMPORTANT SAVED INFORMATION (use this to answer questions accurately):
[SCHEDULE] Funeral at church on Monday at 9am
[FACT] Lives in New York City
[PREFERENCE] Prefers tea over coffee
[TASK] Call the dentist tomorrow
[REMINDER] Take medication at 8am

Use this information to answer questions. If asked about schedules, tasks, or facts, refer to the saved information above.
```

## Task Management

### Task Creation

Tasks are automatically created when the bot identifies actionable items:

- **Explicit tasks**: "I need to call the dentist"
- **Implicit tasks**: "I should finish that report"
- **Reminders**: "Don't forget to pick up groceries"
- **Deadlines**: "The project is due Friday"

### Task Categories

Tasks are categorized based on content analysis:

- **Urgent**: High-priority, time-sensitive tasks
- **Important**: Significant but not urgent tasks
- **Routine**: Regular, recurring tasks
- **Personal**: Personal life tasks
- **Work**: Professional tasks

### Task Integration

Tasks are integrated into the bot's memory system:

1. **Extracted as tasks** during conversation analysis
2. **Stored with importance scores** based on urgency
3. **Retrieved for task queries** and reminders
4. **Used for proactive assistance** and follow-up

## Memory Management

### Web Control Panel

The web control panel (http://localhost:5002) provides memory management:

- **View all memories** with filtering by user and category
- **Color-coded importance** visualization
- **Delete outdated memories** with one click
- **Manual memory creation** for important information
- **Memory statistics** and usage analytics

### Memory Lifecycle

1. **Creation**: Automatic extraction from conversations
2. **Storage**: Database storage with metadata
3. **Retrieval**: Context-aware retrieval for responses
4. **Usage**: Integration into bot responses
5. **Maintenance**: Manual cleanup and updates
6. **Deletion**: Removal of outdated or incorrect memories

### Memory Validation

The system includes validation for extracted memories:

- **Category validation**: Ensures valid category values
- **Content validation**: Checks for meaningful content
- **Importance validation**: Validates importance scores (1-10)
- **JSON parsing**: Robust parsing of extraction responses

## Advanced Features

### Memory Tagging

Memories can be tagged for better organization:

```python
tags = ["health", "appointment", "urgent"]
self.save_persistent_memory(
    user_name=user_name,
    category="schedule",
    content="Doctor appointment Wednesday 2pm",
    importance=8,
    tags=tags
)
```

### Memory Relationships

The system can identify relationships between memories:

- **Related tasks**: Tasks that depend on each other
- **Schedule conflicts**: Overlapping appointments
- **Preference patterns**: Consistent preferences across categories
- **Context connections**: Memories that provide context for each other

### Memory Analytics

The system provides analytics on memory usage:

- **Memory creation rates**: How often memories are extracted
- **Category distribution**: Most common memory types
- **Importance patterns**: Distribution of importance scores
- **Usage statistics**: How often memories are retrieved

## Configuration

### Extraction Settings

Memory extraction can be configured:

- **Temperature**: Lower values (0.3) for more consistent extraction
- **Timeout**: Maximum time for extraction requests
- **Categories**: Configurable memory categories
- **Importance thresholds**: Minimum importance for storage

### Retrieval Settings

Memory retrieval can be tuned:

- **Memory limit**: Maximum memories to include in prompts
- **Importance filtering**: Minimum importance for retrieval
- **Recency weighting**: Balance between importance and recency
- **Category filtering**: Include/exclude specific categories

## Error Handling

### Extraction Failures

If memory extraction fails:

1. **Log the error** for debugging
2. **Continue conversation** without memory extraction
3. **Retry extraction** on next conversation
4. **Monitor extraction rates** for system health

### Storage Failures

If memory storage fails:

1. **Log the error** with details
2. **Rollback database transaction**
3. **Continue conversation** without memory storage
4. **Alert administrators** for persistent failures

## Performance Optimization

### Background Processing

Memory extraction runs in background threads:

```python
# Extract and save memories in background (non-blocking)
threading.Thread(
    target=self.extract_and_save_memory,
    args=(user_message, bot_response, user_name, session_id),
    daemon=True
).start()
```

### Database Optimization

- **Indexes**: Optimized queries for user, category, and importance
- **Batch operations**: Efficient memory storage
- **Connection pooling**: Database connection reuse
- **Query optimization**: Efficient memory retrieval

### Caching Strategies

- **Memory cache**: Cache frequently accessed memories
- **Session tracking**: In-memory session management
- **Embedding cache**: Reduce API calls for repeated text

## Monitoring and Analytics

### Extraction Monitoring

The system monitors memory extraction:

- **Success rates**: Percentage of successful extractions
- **Extraction latency**: Time required for extraction
- **Error rates**: Frequency of extraction failures
- **Memory quality**: Importance and relevance of extracted memories

### Usage Analytics

Memory usage is tracked for optimization:

- **Retrieval frequency**: How often memories are retrieved
- **Category usage**: Most commonly used memory categories
- **Importance effectiveness**: Correlation between importance and usage
- **User patterns**: Individual user memory patterns

## Best Practices

### Memory Quality

1. **Regular cleanup**: Remove outdated or incorrect memories
2. **Importance accuracy**: Use appropriate importance scores
3. **Category consistency**: Ensure proper memory categorization
4. **Content relevance**: Store only meaningful information

### Performance Optimization

1. **Memory limits**: Balance context richness with prompt size
2. **Extraction efficiency**: Optimize extraction prompts and settings
3. **Storage optimization**: Efficient database operations
4. **Retrieval optimization**: Smart memory selection

### User Experience

1. **Memory accuracy**: Ensure memories are factually correct
2. **Privacy respect**: Handle sensitive information appropriately
3. **User control**: Allow users to manage their memories
4. **Transparency**: Make memory usage clear to users

This comprehensive memory and task creation system enables the Mumble AI bot to provide intelligent, personalized assistance while maintaining accuracy and respecting user privacy through careful memory management and task organization.
