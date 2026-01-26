# Semantic Memory System Upgrade

## Overview

Your Mumble AI bot has been upgraded with an advanced semantic memory system that dramatically improves conversation quality and eliminates repetitive responses.

## What's New

### 1. **Dual Memory Architecture**
- **Short-term memory**: Tracks the current conversation session (last 3 exchanges by default)
- **Long-term memory**: Uses semantic similarity to retrieve relevant context from past conversations

### 2. **Conversation Session Management**
- Automatic session tracking per user
- Sessions automatically close after 30 minutes of inactivity
- Each session maintains its own conversation flow

### 3. **Semantic Context Retrieval**
- Messages are converted to embeddings using Ollama's nomic-embed-text model
- Similar past conversations are automatically retrieved when relevant
- Only messages with >70% similarity are included (configurable)

### 4. **Anti-Repetition System**
- Built-in instructions prevent the bot from repeating itself
- Explicitly told to build on conversations, not summarize them
- Distinguishes between current conversation and past context

### 5. **Smart Prompt Engineering**
- Short-term memory: "Current conversation" (immediate context)
- Long-term memory: "Relevant context from past conversations"
- Clear role labeling to prevent confusion

## Key Improvements

### Before:
```
User: Tell me about dogs
Bot: Dogs are loyal pets...

User: What else?
Bot: As I mentioned, dogs are loyal pets... [repeats itself]
```

### After:
```
User: Tell me about dogs
Bot: Dogs are loyal companions known for their intelligence.

User: What else?
Bot: They also have incredible senses - they can smell 100,000 times better than humans!
```

## Database Changes

### New Tables:
- `conversation_sessions` - Tracks conversation sessions with state management

### Updated Tables:
- `conversation_history` - Added:
  - `session_id` - Links to conversation session
  - `embedding` - Vector embedding for semantic search
  - `importance_score` - For future importance weighting
  - `summary` - For future summarization features

### New Functions:
- `cosine_similarity()` - Calculates similarity between embeddings

### New Configuration:
- `embedding_model` - Model for generating embeddings (default: nomic-embed-text:latest)
- `short_term_memory_limit` - Number of recent exchanges to include (default: 3)
- `long_term_memory_limit` - Number of semantic matches to include (default: 3)
- `semantic_similarity_threshold` - Minimum similarity score (default: 0.7)
- `session_timeout_minutes` - Session idle timeout (default: 30)

## Deployment Instructions

### Step 1: Verify Ollama has the embedding model

```bash
# Check if nomic-embed-text is available
ollama list | grep nomic-embed-text

# If not, pull it
ollama pull nomic-embed-text
```

### Step 2: Backup your database (IMPORTANT!)

```bash
docker exec mumble-ai-postgres pg_dump -U mumbleai mumble_ai > backup-$(date +%Y%m%d).sql
```

### Step 3: Apply the migration

```bash
# Apply the migration script to upgrade your existing database
docker exec -i mumble-ai-postgres psql -U mumbleai mumble_ai < migrate-database.sql
```

### Step 4: Rebuild and restart services

```bash
# Stop services
docker-compose down

# Rebuild the bot with new code
docker-compose build mumble-bot

# Start all services
docker-compose up -d

# Check logs to verify it's working
docker-compose logs -f mumble-bot
```

### Step 5: Verify the upgrade

```bash
# Check that new config values are present
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT * FROM bot_config WHERE key LIKE '%memory%' OR key LIKE '%semantic%' OR key LIKE '%embedding%';"

# Check that new columns exist
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "\d conversation_history"

# Check that sessions table exists
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "\d conversation_sessions"
```

## Configuration Tuning

You can adjust the memory system via the web control panel (http://localhost:5002) or directly in the database:

### Increase context memory:
```sql
UPDATE bot_config SET value = '5' WHERE key = 'short_term_memory_limit';
UPDATE bot_config SET value = '5' WHERE key = 'long_term_memory_limit';
```

### Adjust similarity threshold (lower = more context, higher = more selective):
```sql
UPDATE bot_config SET value = '0.6' WHERE key = 'semantic_similarity_threshold';
```

### Change session timeout:
```sql
UPDATE bot_config SET value = '60' WHERE key = 'session_timeout_minutes';
```

## How It Works

### When a user sends a message:

1. **Session Management**
   - Bot gets or creates a session ID for the user
   - Updates session activity timestamp

2. **Context Retrieval**
   - Generates embedding for the user's message
   - Retrieves last 3 exchanges from current session (short-term)
   - Searches for similar messages from past sessions (long-term)

3. **Prompt Construction**
   - Builds prompt with anti-repetition instructions
   - Adds bot persona
   - Includes relevant long-term context (if any)
   - Includes current conversation (short-term)
   - Adds the new message

4. **Response Generation**
   - Ollama generates response based on complete context
   - Response is natural and builds on conversation

5. **Embedding & Storage**
   - Message and response embeddings are generated
   - Both are saved with session_id for future retrieval

### Session Lifecycle:

- **Active**: User is actively conversing
- **Idle**: No activity for 30+ minutes (automatically closed)
- **Closed**: Archived session (can still be searched semantically)

## Monitoring

### Check active sessions:
```sql
SELECT user_name, session_id, started_at, last_activity, message_count
FROM conversation_sessions
WHERE state = 'active'
ORDER BY last_activity DESC;
```

### View semantic matches for a phrase:
```sql
-- First, get an embedding (you'll need to generate this via Ollama API)
-- Then use it to find similar messages:
SELECT user_name, message, role,
       cosine_similarity(ARRAY[0.1, 0.2, ...], embedding) as similarity
FROM conversation_history
WHERE embedding IS NOT NULL
ORDER BY similarity DESC
LIMIT 5;
```

### Check embedding coverage:
```sql
SELECT
  COUNT(*) as total_messages,
  COUNT(embedding) as messages_with_embeddings,
  ROUND(COUNT(embedding) * 100.0 / COUNT(*), 2) as coverage_percentage
FROM conversation_history;
```

## Troubleshooting

### Bot still repeating itself?
1. Check that embeddings are being generated (logs should show "Saved ... message with session_id")
2. Verify nomic-embed-text model is available in Ollama
3. Try lowering semantic_similarity_threshold to include more context

### Slow responses?
1. Embedding generation adds ~200-500ms per message
2. Consider using a smaller Ollama model for faster generation
3. Check Ollama server has sufficient resources

### Sessions not being created?
1. Check database connection in logs
2. Verify migration was applied successfully
3. Check for errors in docker-compose logs

### Want to reset and start fresh?
```bash
# WARNING: This deletes all conversation history
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "TRUNCATE conversation_sessions CASCADE;"
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "TRUNCATE conversation_history CASCADE;"
```

## Performance Notes

- **Embedding cache**: Embeddings are cached in memory to reduce API calls
- **Background storage**: Messages are saved asynchronously to not block responses
- **Session cleanup**: Runs every 5 minutes automatically
- **Memory usage**: Minimal - embeddings are stored in database, not RAM

## Future Enhancements

The system is designed to support:
- Message importance scoring (already in schema)
- Automatic conversation summarization
- Multi-user context awareness
- Configurable memory pruning strategies

## Support

If you encounter issues:
1. Check logs: `docker-compose logs -f mumble-bot`
2. Verify database schema: `docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "\d conversation_history"`
3. Test Ollama connectivity: `curl http://localhost:11434/api/tags`

---

**Created**: $(date)
**Database Migration**: migrate-database.sql
**Code Changes**: mumble-bot/bot.py, init-db.sql
