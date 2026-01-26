# Bot Memory System Architecture

## Overview

The Mumble AI bot implements a sophisticated multi-layered memory system that enables intelligent conversation management, automatic memory extraction, and contextual awareness. The system combines short-term session memory, long-term semantic memory, and persistent memory storage to create a comprehensive AI assistant experience.

## Memory Architecture

### 1. Three-Layer Memory System

The bot uses a hierarchical memory architecture with three distinct layers:

#### **Layer 1: Short-Term Memory (Current Session)**
- **Purpose**: Maintains conversation flow within the current session
- **Duration**: Active conversation session (typically 30 minutes of inactivity)
- **Storage**: In-memory session tracking + database conversation history
- **Content**: Last 3 exchanges by default (configurable)
- **Usage**: Immediate conversation context and flow

#### **Layer 2: Long-Term Memory (Semantic Context)**
- **Purpose**: Retrieves relevant past conversations using semantic similarity
- **Duration**: Persistent across all sessions
- **Storage**: Database with vector embeddings
- **Content**: Similar past conversations (>70% similarity threshold)
- **Usage**: Background context for understanding user patterns and preferences

#### **Layer 3: Persistent Memory (Important Information)**
- **Purpose**: Stores critical information that should be remembered long-term
- **Duration**: Permanent until manually deleted
- **Storage**: Database with structured categories
- **Content**: Schedules, facts, tasks, preferences, reminders
- **Usage**: Factual recall and personal information management

## Memory Categories

### Persistent Memory Categories

The bot automatically categorizes extracted information into six types:

1. **📅 Schedule**: Appointments, meetings, events with dates/times
2. **💡 Fact**: Personal information, preferences, relationships, important details
3. **✓ Task**: Things to do, reminders, action items
4. **❤️ Preference**: Likes, dislikes, habits
5. **⏰ Reminder**: Time-based reminders
6. **📌 Other**: Anything else important

### Importance Scoring

Each memory is assigned an importance score (1-10):
- **1-3 (Gray)**: Low importance
- **4-6 (Blue)**: Medium importance  
- **7-8 (Orange)**: High importance
- **9-10 (Red)**: Critical importance

## How Memory Works

### 1. Memory Extraction Process

After every conversation exchange, the bot automatically:

1. **Analyzes the dialogue** using Ollama AI
2. **Extracts important information** into structured categories
3. **Assigns importance scores** based on content analysis
4. **Saves to database** with metadata (user, session, timestamp)
5. **Makes memories available** for future conversations

```python
# Memory extraction happens in background thread
threading.Thread(
    target=self.extract_and_save_memory,
    args=(user_message, bot_response, user_name, session_id),
    daemon=True
).start()
```

### 2. Memory Retrieval Process

When generating responses, the bot:

1. **Retrieves persistent memories** (top 10 most important for user)
2. **Gets semantic context** (similar past conversations)
3. **Loads current session** (last 3 exchanges)
4. **Builds comprehensive prompt** with all context layers
5. **Generates response** using full context

### 3. Session Management

The bot maintains conversation sessions with:

- **Automatic session creation** for new users
- **Session timeout** (30 minutes of inactivity)
- **Activity tracking** with last_activity timestamps
- **Session state management** (active, idle, closed)
- **Message counting** per session

## Database Schema

### Core Tables

#### `conversation_sessions`
```sql
CREATE TABLE conversation_sessions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    state VARCHAR(20) DEFAULT 'active',
    message_count INTEGER DEFAULT 0
);
```

#### `conversation_history`
```sql
CREATE TABLE conversation_history (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    user_session INTEGER NOT NULL,
    session_id VARCHAR(255),
    message_type VARCHAR(10) NOT NULL,
    role VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    embedding FLOAT8[],
    importance_score FLOAT DEFAULT 0.5,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `persistent_memories`
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
    active BOOLEAN DEFAULT TRUE
);
```

## Prompt Engineering

### Prompt Structure

The bot's prompt is carefully structured to provide optimal context:

```
CRITICAL RULES: [Anti-hallucination and brevity rules]

Your personality: [Bot persona if configured]

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

### Anti-Hallucination Measures

The bot includes strict rules to prevent hallucination:

1. **TRUTH**: Never make up information
2. **NO HALLUCINATION**: Don't invent schedules, events, or details
3. **STAY GROUNDED**: Only discuss actually mentioned topics
4. **RESPOND TO CURRENT MESSAGE**: Focus on current input, not past topics
5. **NO REPETITION**: Don't repeat previous responses
6. **NO SUMMARIES**: Don't summarize conversations

## Memory Extraction Algorithm

### Extraction Prompt

The bot uses a specialized prompt to extract memories:

```
Analyze this conversation exchange and extract ANY important information that should be remembered.

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
{"category": "schedule|fact|task|preference|other", "content": "brief description", "importance": 1-10}
```

### Extraction Process

1. **Send extraction prompt** to Ollama with low temperature (0.3)
2. **Parse JSON response** using regex to extract JSON array
3. **Validate memory structure** (category, content, importance)
4. **Save to database** with user and session metadata
5. **Log extraction results** for monitoring

## Semantic Memory System

### Embedding Generation

The bot uses Ollama's `nomic-embed-text` model to generate embeddings:

```python
def generate_embedding(self, text: str) -> Optional[List[float]]:
    response = requests.post(
        f"{ollama_url}/api/embeddings",
        json={'model': 'nomic-embed-text:latest', 'prompt': text}
    )
    return response.json().get('embedding', [])
```

### Similarity Calculation

Uses cosine similarity to find relevant past conversations:

```sql
SELECT *, cosine_similarity(embedding, %s) as similarity
FROM conversation_history 
WHERE user_name = %s 
  AND cosine_similarity(embedding, %s) > %s
ORDER BY similarity DESC
LIMIT %s
```

### Context Retrieval

1. **Generate embedding** for current message
2. **Query database** for similar past conversations
3. **Filter by similarity threshold** (>70% by default)
4. **Limit results** to prevent prompt overflow
5. **Include in background context** section of prompt

## Configuration

### Memory Limits

Configurable through database settings:

- `short_term_memory_limit`: Number of recent exchanges to include (default: 3)
- `long_term_memory_limit`: Number of similar past conversations (default: 3)
- `semantic_similarity_threshold`: Minimum similarity for context retrieval (default: 0.7)
- `session_timeout_minutes`: Session inactivity timeout (default: 30)

### Bot Persona

The bot can be configured with a personality:

```python
persona = self.get_config('bot_persona', '')
if persona and persona.strip():
    full_prompt += f"Your personality/character: {persona.strip()}\n\n"
    full_prompt += "IMPORTANT: Stay in character BUT prioritize truthfulness over role-playing.\n\n"
```

## Web Control Panel

### Memory Management Interface

The web control panel (http://localhost:5002) provides:

- **View all memories** with filtering by user and category
- **Color-coded importance** visualization
- **Delete outdated memories** with one click
- **Manual memory creation** for important information
- **Memory statistics** and usage analytics

### API Endpoints

- `GET /api/memories` - Retrieve memories with filtering
- `POST /api/memories` - Create new memory manually
- `PUT /api/memories/{id}` - Update existing memory
- `DELETE /api/memories/{id}` - Delete/deactivate memory
- `GET /api/users` - List users with memories

## Performance Optimizations

### Caching

- **Embedding cache**: Reduces API calls for repeated text
- **Session tracking**: In-memory session management
- **Connection pooling**: Database connection reuse

### Background Processing

- **Asynchronous memory extraction**: Non-blocking memory processing
- **Circuit breakers**: Fault tolerance for external services
- **Health monitoring**: Automatic service recovery

### Database Optimization

- **Indexes**: Optimized queries for user, session, and similarity
- **Views**: Pre-computed active memories
- **Batch operations**: Efficient memory storage

## Error Handling

### Circuit Breakers

The bot implements circuit breakers for external services:

- **Whisper service**: Speech-to-text processing
- **Piper service**: Text-to-speech synthesis
- **Ollama service**: LLM and embedding generation
- **Database**: Connection and query failures

### Fallback Mechanisms

- **Service degradation**: Graceful handling of service failures
- **Auto-recovery**: Automatic reconnection attempts
- **Health monitoring**: Continuous service status checking

## Monitoring and Analytics

### Health Checks

The bot continuously monitors:

- **Service availability**: Whisper, Piper, Ollama, Database
- **Connection status**: Mumble server connectivity
- **Memory usage**: Database and application metrics
- **Response times**: Service performance tracking

### Logging

Comprehensive logging for:

- **Memory extraction**: Success/failure of memory processing
- **Session management**: User interactions and session lifecycle
- **Error tracking**: Service failures and recovery attempts
- **Performance metrics**: Response times and resource usage

## Best Practices

### Memory Management

1. **Regular cleanup**: Remove outdated or incorrect memories
2. **Importance scoring**: Use appropriate importance levels
3. **Category accuracy**: Ensure proper memory categorization
4. **User privacy**: Respect sensitive information handling

### Performance Tuning

1. **Memory limits**: Balance context richness with prompt size
2. **Similarity thresholds**: Tune for optimal context retrieval
3. **Session timeouts**: Balance user experience with resource usage
4. **Caching strategies**: Optimize for common use cases

### Security Considerations

1. **Data privacy**: Secure storage of personal information
2. **Access control**: User-specific memory isolation
3. **Data retention**: Appropriate cleanup of old data
4. **Audit logging**: Track memory access and modifications

## Troubleshooting

### Common Issues

1. **Memory not being extracted**: Check Ollama service and extraction prompts
2. **Context not retrieved**: Verify embedding generation and similarity thresholds
3. **Session timeouts**: Adjust session timeout configuration
4. **Performance issues**: Monitor database queries and service health

### Debugging Tools

1. **Web control panel**: Visual memory management interface
2. **Database queries**: Direct inspection of memory data
3. **Log analysis**: Detailed logging for troubleshooting
4. **Health endpoints**: Service status monitoring

This comprehensive memory system enables the Mumble AI bot to provide intelligent, context-aware conversations while maintaining accuracy and preventing hallucination through careful prompt engineering and multi-layered memory management.
