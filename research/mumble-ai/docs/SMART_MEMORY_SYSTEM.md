# Smart Memory System Documentation

## Overview

The Mumble-AI Smart Memory System is a comprehensive memory management solution that enhances the AI bot's ability to understand, remember, and maintain context across conversations. The system uses a multi-layered architecture combining Redis for fast caching, PostgreSQL with pgvector for structured data, and ChromaDB for semantic vector storage.

## Architecture

### Memory Layers

1. **Short-term Memory (Redis)**
   - Fast in-memory storage for current session data
   - Conversation context and recent interactions
   - Entity mentions and temporary data
   - TTL-based expiration for automatic cleanup

2. **Long-term Memory (ChromaDB)**
   - Semantic vector storage for conversation history
   - Embedding-based similarity search
   - Contextual memory retrieval
   - Persistent storage across sessions

3. **Persistent Memory (PostgreSQL)**
   - Structured data storage
   - Entity tracking and relationships
   - Conversation history and metadata
   - Memory consolidation logs

### Core Components

#### MemoryManager
The central orchestrator that coordinates all memory operations:
- **Entity Tracking**: Extracts and tracks people, places, organizations, dates, events
- **Hybrid Search**: Combines semantic and keyword search for better context retrieval
- **Memory Consolidation**: Automatically summarizes old conversations to reduce token usage
- **Session Management**: Handles conversation state and context

#### EntityTracker
Advanced entity recognition and relationship mapping:
- **Named Entity Recognition**: Identifies and categorizes entities in conversations
- **Entity Resolution**: Links mentions to canonical entities
- **Relationship Mapping**: Builds entity relationship graphs
- **Context Tracking**: Maintains entity context across conversation turns

#### MemoryConsolidator
Intelligent memory optimization:
- **Automatic Summarization**: Reduces token usage by summarizing old conversations
- **Background Processing**: Runs consolidation jobs without blocking main operations
- **Configurable Thresholds**: Customizable consolidation parameters
- **Performance Monitoring**: Tracks consolidation effectiveness

#### ConversationContext
Multi-turn conversation understanding:
- **Coreference Resolution**: Resolves pronouns and references
- **Topic Tracking**: Maintains conversation topic continuity
- **Context Preservation**: Keeps relevant context across turns
- **State Management**: Tracks conversation state per user

## Database Schema

### New Tables Added

#### entity_mentions
Tracks entities mentioned in conversations:
```sql
CREATE TABLE entity_mentions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    entity_text VARCHAR(500) NOT NULL,
    canonical_id VARCHAR(255),
    entity_type VARCHAR(50) CHECK (entity_type IN ('PERSON', 'PLACE', 'ORGANIZATION', 'DATE', 'TIME', 'EVENT', 'OTHER')),
    message_id INTEGER REFERENCES conversation_history(id) ON DELETE CASCADE,
    confidence FLOAT DEFAULT 1.0,
    context_info TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### memory_consolidation_log
Tracks memory consolidation operations:
```sql
CREATE TABLE memory_consolidation_log (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    messages_consolidated INTEGER NOT NULL,
    summaries_created INTEGER NOT NULL,
    tokens_saved_estimate INTEGER,
    cutoff_date DATE,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Enhanced conversation_history
Added consolidation tracking:
```sql
ALTER TABLE conversation_history
ADD COLUMN consolidated_at TIMESTAMP,
ADD COLUMN consolidated_summary_id VARCHAR(255);
```

## Configuration

### Environment Variables

```bash
# ChromaDB Configuration
CHROMADB_URL=http://chromadb:8000

# Redis Configuration
REDIS_URL=redis://redis:6379

# Memory System Features
ENABLE_ENTITY_TRACKING=true
ENABLE_MEMORY_CONSOLIDATION=true
MEMORY_CONSOLIDATION_DAYS=7
HYBRID_SEARCH_SEMANTIC_WEIGHT=0.7
CONSOLIDATION_SCHEDULE_HOUR=3

# Protobuf Compatibility
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
```

### Docker Services

#### Redis Service
```yaml
redis:
  image: redis:7-alpine
  container_name: mumble-ai-redis
  ports:
    - "6379:6379"
  volumes:
    - redis-data:/data
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 30s
    timeout: 3s
    retries: 3
```

#### ChromaDB Service
```yaml
chromadb:
  image: chromadb/chroma:0.4.22
  container_name: mumble-ai-chromadb
  ports:
    - "8000:8000"
  volumes:
    - chromadb-data:/chroma/chroma
  environment:
    - IS_PERSISTENT=TRUE
    - ANONYMIZED_TELEMETRY=FALSE
  healthcheck:
    test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8000/api/v1/heartbeat"]
    interval: 30s
    timeout: 10s
    retries: 3
```

## Usage

### Basic Memory Operations

#### Saving Messages
```python
# The MemoryManager automatically handles message saving
memory_manager.save_message(
    user_name="john_doe",
    message="I love pizza from Tony's Restaurant",
    message_type="text",
    session_id="session_123"
)
```

#### Retrieving Context
```python
# Get relevant context for a conversation
context = memory_manager.get_conversation_context(
    user_name="john_doe",
    current_message="What's my favorite food?",
    max_messages=10
)
```

#### Entity Extraction
```python
# Extract entities from a message
entities = memory_manager.extract_entities(
    message="I'm meeting Sarah at the coffee shop tomorrow",
    user_name="john_doe"
)
# Returns: [{"text": "Sarah", "type": "PERSON"}, {"text": "coffee shop", "type": "PLACE"}, {"text": "tomorrow", "type": "DATE"}]
```

### Advanced Features

#### Hybrid Search
The system combines semantic similarity with keyword matching for better context retrieval:

```python
# Semantic search finds contextually similar conversations
semantic_results = vector_store.semantic_search(query, limit=5)

# Keyword search finds exact matches
keyword_results = keyword_search(query, limit=5)

# RRF fusion combines both approaches
combined_results = hybrid_search(semantic_results, keyword_results)
```

#### Memory Consolidation
Automatic summarization reduces token usage:

```python
# Consolidate old memories for a user
result = memory_consolidator.consolidate_old_memories(
    user="john_doe",
    cutoff_days=7
)
# Returns: {"messages_consolidated": 50, "summaries_created": 3, "tokens_saved_estimate": 1500}
```

## Performance Optimizations

### Redis Caching
- **Session Data**: Fast access to current conversation state
- **Entity Cache**: Cached entity relationships and context
- **Search Results**: Cached search results for common queries
- **TTL Management**: Automatic cleanup of expired data

### Database Indexing
- **Entity Indexes**: Fast entity lookups by user and type
- **Conversation Indexes**: Optimized conversation history queries
- **Consolidation Indexes**: Efficient consolidation job queries

### Memory Management
- **Automatic Cleanup**: Periodic cleanup of old session data
- **Consolidation Scheduling**: Background consolidation jobs
- **Resource Monitoring**: Memory usage tracking and optimization

## Monitoring and Debugging

### Health Checks
- **Redis**: `redis-cli ping` should return `PONG`
- **ChromaDB**: `curl http://localhost:8000/api/v1/heartbeat`
- **PostgreSQL**: Database connection and query tests

### Logging
The system provides comprehensive logging:
- **Memory Operations**: Track memory saves, retrievals, and consolidations
- **Entity Tracking**: Log entity extractions and relationships
- **Performance Metrics**: Monitor search times and consolidation effectiveness
- **Error Handling**: Detailed error logging for debugging

### Metrics
- **Memory Usage**: Track Redis and database memory consumption
- **Search Performance**: Monitor search query response times
- **Consolidation Stats**: Track consolidation effectiveness and token savings
- **Entity Coverage**: Monitor entity extraction accuracy

## Troubleshooting

### Common Issues

#### ChromaDB Connection Issues
- **Symptom**: ChromaDB health check fails
- **Solution**: Check ChromaDB logs, ensure proper NumPy version compatibility
- **Workaround**: System can run with Redis + PostgreSQL only

#### Redis Memory Issues
- **Symptom**: Redis memory usage too high
- **Solution**: Adjust `maxmemory` and `maxmemory-policy` settings
- **Monitoring**: Use `redis-cli info memory` to check usage

#### Entity Extraction Errors
- **Symptom**: Poor entity extraction accuracy
- **Solution**: Check Ollama connection and model availability
- **Fallback**: System continues to work with basic keyword matching

### Debug Commands

```bash
# Check Redis status
docker exec mumble-ai-redis redis-cli ping

# Check ChromaDB status
curl http://localhost:8000/api/v1/heartbeat

# Check database schema
docker exec mumble-ai-postgres psql -U mumbleai -d mumble_ai -c "\dt"

# View memory manager logs
docker-compose logs mumble-bot | grep memory

# Check entity extraction
docker-compose logs mumble-bot | grep entity
```

## Future Enhancements

### Planned Features
- **Multi-modal Memory**: Support for image and audio memory
- **Advanced Analytics**: Conversation pattern analysis
- **Personalization**: User-specific memory preferences
- **Integration APIs**: External system integration

### Performance Improvements
- **Distributed Caching**: Multi-node Redis cluster
- **Vector Optimization**: Advanced vector indexing
- **Query Optimization**: Intelligent query caching
- **Resource Scaling**: Dynamic resource allocation

## Conclusion

The Smart Memory System significantly enhances the Mumble-AI bot's conversational capabilities by providing:
- **Persistent Memory**: Remembers information across sessions
- **Context Awareness**: Maintains conversation context
- **Entity Intelligence**: Tracks and understands entities
- **Performance Optimization**: Efficient memory management
- **Scalability**: Designed for high-volume usage

The system is production-ready and provides a solid foundation for advanced AI conversational features.





