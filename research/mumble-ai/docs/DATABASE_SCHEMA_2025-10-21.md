# Database Schema Updates - October 21, 2025

## Overview

This document details the comprehensive database schema updates made to support the enhanced smart memory system, new services, and improved functionality across the Mumble-AI stack.

## New Tables

### 1. conversation_sessions

**Purpose**: Track conversation sessions and user activity

```sql
CREATE TABLE conversation_sessions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    state VARCHAR(20) DEFAULT 'active' CHECK (state IN ('active', 'idle', 'closed')),
    message_count INTEGER DEFAULT 0,
    UNIQUE(user_name, session_id)
);
```

**Fields**:
- `id`: Primary key
- `user_name`: User identifier
- `session_id`: Unique session identifier
- `started_at`: Session start timestamp
- `last_activity`: Last activity timestamp
- `state`: Session state (active, idle, closed)
- `message_count`: Number of messages in session

**Indexes**:
```sql
CREATE INDEX idx_session_user ON conversation_sessions(user_name);
CREATE INDEX idx_session_activity ON conversation_sessions(last_activity DESC);
```

### 2. entity_mentions

**Purpose**: Track named entities mentioned in conversations

```sql
CREATE TABLE entity_mentions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    entity_text VARCHAR(255) NOT NULL,
    canonical_id VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    context_info TEXT,
    message_id INTEGER REFERENCES conversation_history(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Fields**:
- `id`: Primary key
- `user_name`: User identifier
- `entity_text`: Original entity text
- `canonical_id`: Canonical entity identifier
- `entity_type`: Entity type (PERSON, PLACE, ORGANIZATION, etc.)
- `confidence`: Entity confidence score
- `context_info`: Additional context information
- `message_id`: Reference to conversation message
- `created_at`: Creation timestamp

**Indexes**:
```sql
CREATE INDEX idx_entity_canonical ON entity_mentions(canonical_id);
CREATE INDEX idx_entity_user ON entity_mentions(user_name);
CREATE INDEX idx_entity_type ON entity_mentions(entity_type);
```

## Enhanced Tables

### 1. conversation_history

**New Columns Added**:

```sql
-- Embedding support for semantic search
ALTER TABLE conversation_history ADD COLUMN embedding FLOAT8[];

-- Importance scoring for memory prioritization
ALTER TABLE conversation_history ADD COLUMN importance_score FLOAT DEFAULT 0.5;

-- AI-generated summaries
ALTER TABLE conversation_history ADD COLUMN summary TEXT;

-- Memory consolidation tracking
ALTER TABLE conversation_history ADD COLUMN consolidated_at TIMESTAMP;
ALTER TABLE conversation_history ADD COLUMN consolidated_summary_id VARCHAR(255);

-- Session tracking
ALTER TABLE conversation_history ADD COLUMN session_id VARCHAR(255);
ALTER TABLE conversation_history ADD FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE SET NULL;
```

**Updated Schema**:
```sql
CREATE TABLE conversation_history (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    user_session INTEGER NOT NULL,
    session_id VARCHAR(255),
    message_type VARCHAR(10) NOT NULL CHECK (message_type IN ('voice', 'text')),
    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    embedding FLOAT8[],
    importance_score FLOAT DEFAULT 0.5,
    summary TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    consolidated_at TIMESTAMP,
    consolidated_summary_id VARCHAR(255),
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE SET NULL
);
```

### 2. bot_config

**Enhanced Configuration Support**:

```sql
-- New configuration options
INSERT INTO bot_config (key, value) VALUES
    ('embedding_model', 'nomic-embed-text:latest'),
    ('short_term_memory_limit', '10'),
    ('long_term_memory_limit', '10'),
    ('semantic_similarity_threshold', '0.7'),
    ('session_timeout_minutes', '30'),
    ('session_reactivation_minutes', '10'),
    ('use_chain_of_thought', 'false'),
    ('use_semantic_memory_ranking', 'true'),
    ('use_response_validation', 'false'),
    ('enable_parallel_processing', 'true'),
    ('whisper_circuit_threshold', '5'),
    ('whisper_circuit_timeout', '60.0'),
    ('piper_circuit_threshold', '5'),
    ('piper_circuit_timeout', '60.0'),
    ('ollama_circuit_threshold', '5'),
    ('ollama_circuit_timeout', '60.0'),
    ('db_circuit_threshold', '3'),
    ('db_circuit_timeout', '30.0'),
    ('health_check_interval', '30.0');
```

## New Indexes

### Performance Indexes

```sql
-- Conversation history indexes
CREATE INDEX idx_conversation_timestamp ON conversation_history(timestamp DESC);
CREATE INDEX idx_conversation_user ON conversation_history(user_name);
CREATE INDEX idx_conversation_session ON conversation_history(session_id);
CREATE INDEX idx_conversation_role ON conversation_history(role);
CREATE INDEX idx_conversation_importance ON conversation_history(importance_score DESC);

-- Session indexes
CREATE INDEX idx_session_user ON conversation_sessions(user_name);
CREATE INDEX idx_session_activity ON conversation_sessions(last_activity DESC);

-- Entity indexes
CREATE INDEX idx_entity_canonical ON entity_mentions(canonical_id);
CREATE INDEX idx_entity_user ON entity_mentions(user_name);
CREATE INDEX idx_entity_type ON entity_mentions(entity_type);
CREATE INDEX idx_entity_confidence ON entity_mentions(confidence DESC);
```

### Vector Search Indexes

```sql
-- Vector similarity search index (if using pgvector extension)
CREATE INDEX idx_conversation_embedding ON conversation_history 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## New Functions

### 1. Cosine Similarity Function

```sql
CREATE OR REPLACE FUNCTION cosine_similarity(vec1 FLOAT8[], vec2 FLOAT8[])
RETURNS FLOAT8 AS $$
DECLARE
    dot_product FLOAT8 := 0;
    magnitude1 FLOAT8 := 0;
    magnitude2 FLOAT8 := 0;
    i INTEGER;
BEGIN
    -- Handle null or empty arrays
    IF vec1 IS NULL OR vec2 IS NULL OR array_length(vec1, 1) IS NULL OR array_length(vec2, 1) IS NULL THEN
        RETURN 0;
    END IF;

    -- Calculate dot product and magnitudes
    FOR i IN 1..array_length(vec1, 1) LOOP
        dot_product := dot_product + (vec1[i] * vec2[i]);
        magnitude1 := magnitude1 + (vec1[i] * vec1[i]);
        magnitude2 := magnitude2 + (vec2[i] * vec2[i]);
    END LOOP;

    -- Calculate cosine similarity
    IF magnitude1 = 0 OR magnitude2 = 0 THEN
        RETURN 0;
    END IF;

    RETURN dot_product / (SQRT(magnitude1) * SQRT(magnitude2));
END;
$$ LANGUAGE plpgsql;
```

### 2. Memory Consolidation Function

```sql
CREATE OR REPLACE FUNCTION consolidate_old_memories(
    p_user_name VARCHAR(255),
    p_cutoff_days INTEGER DEFAULT 7
)
RETURNS TABLE(
    messages_consolidated INTEGER,
    summaries_created INTEGER
) AS $$
DECLARE
    v_cutoff_date TIMESTAMP;
    v_message_count INTEGER;
    v_summary_count INTEGER;
BEGIN
    v_cutoff_date := NOW() - INTERVAL '1 day' * p_cutoff_days;
    
    -- Count messages to be consolidated
    SELECT COUNT(*) INTO v_message_count
    FROM conversation_history
    WHERE user_name = p_user_name 
      AND timestamp < v_cutoff_date 
      AND consolidated_at IS NULL;
    
    -- For now, return counts (actual consolidation handled by application)
    messages_consolidated := v_message_count;
    summaries_created := 0;
    
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;
```

## Views

### 1. Recent Conversations View

```sql
CREATE OR REPLACE VIEW recent_conversations AS
SELECT
    id,
    user_name,
    message_type,
    role,
    message,
    timestamp,
    importance_score
FROM conversation_history
ORDER BY timestamp DESC
LIMIT 100;
```

### 2. Active Sessions View

```sql
CREATE OR REPLACE VIEW active_sessions AS
SELECT
    s.id,
    s.user_name,
    s.session_id,
    s.started_at,
    s.last_activity,
    s.message_count,
    s.state,
    COUNT(h.id) as actual_message_count
FROM conversation_sessions s
LEFT JOIN conversation_history h ON s.session_id = h.session_id
WHERE s.state = 'active'
GROUP BY s.id, s.user_name, s.session_id, s.started_at, s.last_activity, s.message_count, s.state
ORDER BY s.last_activity DESC;
```

### 3. Entity Summary View

```sql
CREATE OR REPLACE VIEW entity_summary AS
SELECT
    user_name,
    entity_type,
    COUNT(*) as mention_count,
    AVG(confidence) as avg_confidence,
    MAX(created_at) as last_mentioned
FROM entity_mentions
GROUP BY user_name, entity_type
ORDER BY mention_count DESC;
```

## Migration Script

### Complete Migration Script

```sql
-- Migration script for database schema updates
-- Run this script to update existing databases

-- 1. Create conversation_sessions table
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    state VARCHAR(20) DEFAULT 'active' CHECK (state IN ('active', 'idle', 'closed')),
    message_count INTEGER DEFAULT 0,
    UNIQUE(user_name, session_id)
);

-- 2. Create entity_mentions table
CREATE TABLE IF NOT EXISTS entity_mentions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    entity_text VARCHAR(255) NOT NULL,
    canonical_id VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    context_info TEXT,
    message_id INTEGER REFERENCES conversation_history(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Add new columns to conversation_history
ALTER TABLE conversation_history 
ADD COLUMN IF NOT EXISTS embedding FLOAT8[],
ADD COLUMN IF NOT EXISTS importance_score FLOAT DEFAULT 0.5,
ADD COLUMN IF NOT EXISTS summary TEXT,
ADD COLUMN IF NOT EXISTS consolidated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS consolidated_summary_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS session_id VARCHAR(255);

-- 4. Add foreign key constraint
ALTER TABLE conversation_history 
ADD CONSTRAINT fk_conversation_session 
FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE SET NULL;

-- 5. Create indexes
CREATE INDEX IF NOT EXISTS idx_conversation_timestamp ON conversation_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_user ON conversation_history(user_name);
CREATE INDEX IF NOT EXISTS idx_conversation_session ON conversation_history(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_role ON conversation_history(role);
CREATE INDEX IF NOT EXISTS idx_conversation_importance ON conversation_history(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_session_user ON conversation_sessions(user_name);
CREATE INDEX IF NOT EXISTS idx_session_activity ON conversation_sessions(last_activity DESC);
CREATE INDEX IF NOT EXISTS idx_entity_canonical ON entity_mentions(canonical_id);
CREATE INDEX IF NOT EXISTS idx_entity_user ON entity_mentions(user_name);
CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_mentions(entity_type);

-- 6. Add new configuration options
INSERT INTO bot_config (key, value) VALUES
    ('embedding_model', 'nomic-embed-text:latest'),
    ('short_term_memory_limit', '10'),
    ('long_term_memory_limit', '10'),
    ('semantic_similarity_threshold', '0.7'),
    ('session_timeout_minutes', '30'),
    ('session_reactivation_minutes', '10'),
    ('use_chain_of_thought', 'false'),
    ('use_semantic_memory_ranking', 'true'),
    ('use_response_validation', 'false'),
    ('enable_parallel_processing', 'true'),
    ('whisper_circuit_threshold', '5'),
    ('whisper_circuit_timeout', '60.0'),
    ('piper_circuit_threshold', '5'),
    ('piper_circuit_timeout', '60.0'),
    ('ollama_circuit_threshold', '5'),
    ('ollama_circuit_timeout', '60.0'),
    ('db_circuit_threshold', '3'),
    ('db_circuit_timeout', '30.0'),
    ('health_check_interval', '30.0')
ON CONFLICT (key) DO NOTHING;

-- 7. Create functions
CREATE OR REPLACE FUNCTION cosine_similarity(vec1 FLOAT8[], vec2 FLOAT8[])
RETURNS FLOAT8 AS $$
DECLARE
    dot_product FLOAT8 := 0;
    magnitude1 FLOAT8 := 0;
    magnitude2 FLOAT8 := 0;
    i INTEGER;
BEGIN
    IF vec1 IS NULL OR vec2 IS NULL OR array_length(vec1, 1) IS NULL OR array_length(vec2, 1) IS NULL THEN
        RETURN 0;
    END IF;

    FOR i IN 1..array_length(vec1, 1) LOOP
        dot_product := dot_product + (vec1[i] * vec2[i]);
        magnitude1 := magnitude1 + (vec1[i] * vec1[i]);
        magnitude2 := magnitude2 + (vec2[i] * vec2[i]);
    END LOOP;

    IF magnitude1 = 0 OR magnitude2 = 0 THEN
        RETURN 0;
    END IF;

    RETURN dot_product / (SQRT(magnitude1) * SQRT(magnitude2));
END;
$$ LANGUAGE plpgsql;

-- 8. Create views
CREATE OR REPLACE VIEW recent_conversations AS
SELECT
    id,
    user_name,
    message_type,
    role,
    message,
    timestamp,
    importance_score
FROM conversation_history
ORDER BY timestamp DESC
LIMIT 100;

CREATE OR REPLACE VIEW active_sessions AS
SELECT
    s.id,
    s.user_name,
    s.session_id,
    s.started_at,
    s.last_activity,
    s.message_count,
    s.state,
    COUNT(h.id) as actual_message_count
FROM conversation_sessions s
LEFT JOIN conversation_history h ON s.session_id = h.session_id
WHERE s.state = 'active'
GROUP BY s.id, s.user_name, s.session_id, s.started_at, s.last_activity, s.message_count, s.state
ORDER BY s.last_activity DESC;

CREATE OR REPLACE VIEW entity_summary AS
SELECT
    user_name,
    entity_type,
    COUNT(*) as mention_count,
    AVG(confidence) as avg_confidence,
    MAX(created_at) as last_mentioned
FROM entity_mentions
GROUP BY user_name, entity_type
ORDER BY mention_count DESC;
```

## Data Types and Constraints

### 1. Entity Types

**Supported Entity Types**:
- `PERSON`: People, names, individuals
- `PLACE`: Locations, cities, countries, addresses
- `ORGANIZATION`: Companies, institutions, groups
- `DATE`: Dates, times, schedules
- `TIME`: Time references, durations
- `EVENT`: Events, meetings, occasions
- `OTHER`: Miscellaneous entities

### 2. Session States

**Session State Values**:
- `active`: Currently active session
- `idle`: Session with no recent activity
- `closed`: Session that has been closed

### 3. Message Types

**Message Type Values**:
- `voice`: Voice/audio messages
- `text`: Text messages

### 4. Roles

**Role Values**:
- `user`: User messages
- `assistant`: AI assistant messages

## Performance Considerations

### 1. Indexing Strategy

**Primary Indexes**:
- Timestamp-based indexes for time-series queries
- User-based indexes for user-specific queries
- Session-based indexes for session management
- Entity-based indexes for entity tracking

**Composite Indexes**:
- User + timestamp for user activity queries
- Session + timestamp for session activity
- Entity + user for entity tracking

### 2. Query Optimization

**Common Query Patterns**:
- Recent conversations by user
- Session activity tracking
- Entity mention history
- Memory consolidation queries
- Semantic search queries

**Optimization Techniques**:
- Proper indexing for common queries
- Query plan analysis and optimization
- Connection pooling for performance
- Caching strategies for frequently accessed data

### 3. Storage Considerations

**Embedding Storage**:
- Vector embeddings stored as FLOAT8 arrays
- Consider pgvector extension for better vector operations
- Optimize embedding dimensions for performance

**Text Storage**:
- TEXT fields for large content
- Proper encoding for international text
- Compression for large text fields

## Backup and Recovery

### 1. Backup Strategy

**Full Backup**:
```bash
pg_dump -h localhost -U mumbleai -d mumble_ai > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Incremental Backup**:
```bash
pg_dump -h localhost -U mumbleai -d mumble_ai --schema-only > schema_backup.sql
```

### 2. Recovery Procedures

**Schema Recovery**:
```bash
psql -h localhost -U mumbleai -d mumble_ai < schema_backup.sql
```

**Data Recovery**:
```bash
psql -h localhost -U mumbleai -d mumble_ai < backup_file.sql
```

### 3. Migration Testing

**Test Environment**:
- Create test database with same schema
- Run migration scripts on test data
- Validate data integrity and performance
- Test rollback procedures

## Monitoring and Maintenance

### 1. Performance Monitoring

**Key Metrics**:
- Query performance and execution times
- Index usage and effectiveness
- Connection pool utilization
- Storage usage and growth

**Monitoring Queries**:
```sql
-- Slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;

-- Index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes 
ORDER BY idx_scan DESC;
```

### 2. Maintenance Tasks

**Regular Maintenance**:
- Analyze tables for query optimization
- Update statistics for better query plans
- Clean up old consolidated data
- Monitor and optimize index usage

**Automated Maintenance**:
```sql
-- Analyze tables
ANALYZE conversation_history;
ANALYZE conversation_sessions;
ANALYZE entity_mentions;

-- Update statistics
UPDATE pg_stat_user_tables SET n_tup_ins = 0, n_tup_upd = 0, n_tup_del = 0;
```

## Security Considerations

### 1. Access Control

**User Permissions**:
- Application user with limited permissions
- Read-only access for monitoring
- Backup user with appropriate permissions

### 2. Data Protection

**Sensitive Data**:
- Encrypt sensitive configuration data
- Secure storage of user information
- Proper handling of conversation data

### 3. Audit Logging

**Audit Trail**:
- Track schema changes
- Monitor data access patterns
- Log administrative actions

## Conclusion

The database schema updates provide a solid foundation for the enhanced smart memory system and new services. The changes include:

- **New Tables**: Session tracking and entity management
- **Enhanced Tables**: Embedding support and metadata
- **Performance Indexes**: Optimized query performance
- **New Functions**: Vector similarity and memory consolidation
- **Views**: Simplified data access patterns
- **Migration Support**: Smooth upgrade procedures

These updates maintain backward compatibility while providing significant improvements in functionality and performance.



