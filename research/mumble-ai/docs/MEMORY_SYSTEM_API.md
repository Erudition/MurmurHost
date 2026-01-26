# Memory System API Documentation

## 🚀 **Overview**

The Memory System API provides comprehensive endpoints for managing the advanced memory capabilities of the Mumble-AI bot. This includes entity tracking, memory search, consolidation management, and system monitoring.

## 🔗 **Base URLs**

- **Web Control Panel**: `http://localhost:5002`
- **Memory Dashboard**: `http://localhost:5002/memory`
- **API Endpoints**: `http://localhost:5002/api/memory`

## 📋 **Authentication**

All API endpoints require no authentication for local development. In production, consider implementing proper authentication mechanisms.

## 🧠 **Memory System Endpoints**

### **1. System Status**

#### **GET /api/memory/status**
Get comprehensive status of all memory system components.

**Response:**
```json
{
  "success": true,
  "data": {
    "redis": {
      "status": "healthy",
      "info": {
        "memory_usage": "45.2MB",
        "connected_clients": 3,
        "keys_count": 1247
      }
    },
    "chromadb": {
      "status": "healthy",
      "info": {
        "collections_count": 4,
        "total_documents": 15420,
        "last_heartbeat": "2025-01-15T10:30:00Z"
      }
    },
    "postgresql": {
      "status": "healthy",
      "info": {
        "connection_pool": "active",
        "tables_count": 8,
        "last_query_time": "2025-01-15T10:29:45Z"
      }
    },
    "entities": {
      "count": 342,
      "recent": [
        {
          "text": "John Smith",
          "type": "PERSON",
          "context": "user's colleague"
        },
        {
          "text": "New York",
          "type": "PLACE",
          "context": "city they visited"
        }
      ]
    },
    "consolidation": {
      "last_run": "2025-01-15T03:00:00Z",
      "stats": {
        "messages_consolidated": 150,
        "summaries_created": 8,
        "tokens_saved": 4500
      }
    }
  }
}
```

### **2. Entity Management**

#### **GET /api/memory/entities**
Retrieve paginated list of entity mentions.

**Query Parameters:**
- `page` (int, optional): Page number (default: 1)
- `per_page` (int, optional): Items per page (default: 20)
- `user_name` (string, optional): Filter by user
- `entity_type` (string, optional): Filter by entity type
- `search` (string, optional): Search in entity text

**Response:**
```json
{
  "success": true,
  "data": {
    "entities": [
      {
        "id": 123,
        "entity_text": "John Smith",
        "entity_type": "PERSON",
        "user_name": "alice",
        "canonical_id": "uuid-123-456",
        "confidence": 0.95,
        "context_info": "user's colleague from Microsoft",
        "created_at": "2025-01-15T10:30:00Z",
        "updated_at": "2025-01-15T10:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 342,
      "pages": 18
    }
  }
}
```

#### **POST /api/memory/entities**
Create a new entity mention.

**Request Body:**
```json
{
  "entity_text": "Sarah Johnson",
  "entity_type": "PERSON",
  "user_name": "alice",
  "context_info": "user's sister",
  "confidence": 0.9
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 124,
    "entity_text": "Sarah Johnson",
    "entity_type": "PERSON",
    "user_name": "alice",
    "canonical_id": "uuid-789-012",
    "confidence": 0.9,
    "context_info": "user's sister",
    "created_at": "2025-01-15T10:35:00Z"
  }
}
```

#### **PUT /api/memory/entities/{id}**
Update an existing entity mention.

**Request Body:**
```json
{
  "entity_text": "Sarah Johnson-Smith",
  "context_info": "user's sister, married name",
  "confidence": 0.95
}
```

#### **DELETE /api/memory/entities/{id}**
Delete an entity mention.

**Response:**
```json
{
  "success": true,
  "message": "Entity deleted successfully"
}
```

### **3. Memory Search**

#### **GET /api/memory/search**
Perform hybrid search across conversations and entities.

**Query Parameters:**
- `q` (string, required): Search query
- `limit` (int, optional): Maximum results (default: 20)
- `user_name` (string, optional): Filter by user
- `search_type` (string, optional): "conversations", "entities", or "all" (default: "all")

**Response:**
```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "id": 456,
        "user_name": "alice",
        "message": "I'm meeting John Smith tomorrow at the coffee shop",
        "message_type": "text",
        "role": "user",
        "created_at": "2025-01-15T09:15:00Z",
        "relevance_score": 0.92
      }
    ],
    "entities": [
      {
        "id": 123,
        "entity_text": "John Smith",
        "entity_type": "PERSON",
        "user_name": "alice",
        "context_info": "user's colleague",
        "created_at": "2025-01-15T08:30:00Z",
        "relevance_score": 0.88
      }
    ],
    "total_results": 15,
    "search_time_ms": 45
  }
}
```

### **4. Memory Consolidation**

#### **GET /api/memory/consolidation**
Get consolidation history and statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_runs": 12,
      "total_messages_consolidated": 1250,
      "total_summaries_created": 65,
      "total_tokens_saved": 18750
    },
    "history": [
      {
        "id": 1,
        "user_name": "alice",
        "run_at": "2025-01-15T03:00:00Z",
        "messages_consolidated": 150,
        "summaries_created": 8,
        "tokens_saved_estimate": 4500
      }
    ]
  }
}
```

#### **POST /api/memory/consolidation/run**
Manually trigger memory consolidation for a user.

**Request Body:**
```json
{
  "user_name": "alice",
  "cutoff_days": 7
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "messages_consolidated": 150,
    "summaries_created": 8,
    "tokens_saved_estimate": 4500,
    "run_time_seconds": 45.2
  }
}
```

### **5. Conversation Context**

#### **GET /api/memory/context/{user_name}**
Get conversation context for a specific user.

**Query Parameters:**
- `session_id` (string, optional): Specific session ID
- `include_entities` (boolean, optional): Include entities (default: true)
- `include_consolidated` (boolean, optional): Include consolidated memories (default: true)
- `limit` (int, optional): Maximum context items (default: 10)

**Response:**
```json
{
  "success": true,
  "data": {
    "user_name": "alice",
    "session_id": "session-123-456",
    "context": {
      "memories": [
        {
          "id": 456,
          "content": "I'm meeting John Smith tomorrow at the coffee shop",
          "metadata": {
            "role": "user",
            "timestamp": "2025-01-15T09:15:00Z",
            "importance_score": 0.8
          }
        }
      ],
      "entities": [
        {
          "text": "John Smith",
          "entity_type": "PERSON",
          "context": "user's colleague",
          "confidence": 0.95
        }
      ],
      "session": [
        {
          "role": "user",
          "content": "What's my schedule for tomorrow?",
          "timestamp": "2025-01-15T10:30:00Z"
        }
      ],
      "consolidated": []
    }
  }
}
```

### **6. Memory Statistics**

#### **GET /api/memory/stats**
Get comprehensive memory system statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "total_conversations": 15420,
    "total_entities": 342,
    "total_users": 15,
    "memory_usage": {
      "redis_mb": 45.2,
      "postgresql_mb": 234.7,
      "chromadb_mb": 156.3
    },
    "search_performance": {
      "avg_search_time_ms": 45,
      "total_searches": 1250,
      "cache_hit_rate": 0.78
    },
    "consolidation_stats": {
      "last_run": "2025-01-15T03:00:00Z",
      "total_consolidated": 1250,
      "tokens_saved": 18750,
      "efficiency_ratio": 0.32
    }
  }
}
```

## 🔍 **Search Capabilities**

### **Hybrid Search**
The memory system uses a hybrid search approach that combines:

1. **Semantic Search** (ChromaDB)
   - Vector similarity search
   - Contextual understanding
   - Weight: 70% (configurable)

2. **Keyword Search** (PostgreSQL)
   - Exact and fuzzy matching
   - Fast text search
   - Weight: 30% (configurable)

### **Search Types**

#### **Conversation Search**
- Searches through all conversation history
- Includes user and assistant messages
- Supports voice and text message types
- Relevance scoring based on content similarity

#### **Entity Search**
- Searches through entity mentions
- Filters by entity type and user
- Context-aware search
- Canonical entity resolution

#### **Combined Search**
- Searches both conversations and entities
- Unified relevance scoring
- Cross-reference capabilities
- Comprehensive result set

## 📊 **Performance Monitoring**

### **Health Checks**

#### **Redis Health**
- Connection status
- Memory usage
- Key count
- Response time

#### **ChromaDB Health**
- Collection status
- Document count
- Heartbeat response
- Vector operations

#### **PostgreSQL Health**
- Connection pool status
- Query performance
- Table statistics
- Index usage

### **Metrics Collection**

#### **Search Performance**
- Average search time
- Cache hit rate
- Query complexity
- Result relevance

#### **Memory Usage**
- Redis memory consumption
- PostgreSQL storage
- ChromaDB vector storage
- Cache efficiency

#### **Consolidation Metrics**
- Consolidation frequency
- Token savings
- Processing time
- Error rates

## 🛠️ **Configuration**

### **Environment Variables**

```bash
# Memory System Configuration
CHROMADB_URL=http://chromadb:8000
REDIS_URL=redis://redis:6379
ENABLE_ENTITY_TRACKING=true
ENABLE_MEMORY_CONSOLIDATION=true
MEMORY_CONSOLIDATION_DAYS=7
HYBRID_SEARCH_SEMANTIC_WEIGHT=0.7
CONSOLIDATION_SCHEDULE_HOUR=3

# Performance Tuning
REDIS_MAX_MEMORY=512mb
REDIS_MAX_MEMORY_POLICY=allkeys-lru
CHROMADB_BATCH_SIZE=50
POSTGRES_CONNECTION_POOL_SIZE=10

# Debugging
MEMORY_DEBUG_LOGGING=false
ENTITY_EXTRACTION_VERBOSE=false
CONSOLIDATION_VERBOSE=false
```

### **Service Configuration**

#### **Redis Configuration**
```yaml
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
  ports:
    - "6379:6379"
  volumes:
    - redis-data:/data
```

#### **ChromaDB Configuration**
```yaml
chromadb:
  image: chromadb/chroma:0.4.22
  ports:
    - "8000:8000"
  environment:
    - IS_PERSISTENT=TRUE
    - ANONYMIZED_TELEMETRY=FALSE
  volumes:
    - chromadb-data:/chroma/chroma
```

## 🚨 **Error Handling**

### **Common Error Responses**

#### **Service Unavailable**
```json
{
  "success": false,
  "error": "Service temporarily unavailable",
  "code": "SERVICE_UNAVAILABLE",
  "details": "Redis connection failed"
}
```

#### **Invalid Request**
```json
{
  "success": false,
  "error": "Invalid request parameters",
  "code": "INVALID_REQUEST",
  "details": "Missing required parameter: user_name"
}
```

#### **Entity Not Found**
```json
{
  "success": false,
  "error": "Entity not found",
  "code": "ENTITY_NOT_FOUND",
  "details": "Entity with ID 123 does not exist"
}
```

### **Error Codes**

- `SERVICE_UNAVAILABLE`: Memory service is down
- `INVALID_REQUEST`: Malformed request
- `ENTITY_NOT_FOUND`: Entity doesn't exist
- `SEARCH_FAILED`: Search operation failed
- `CONSOLIDATION_FAILED`: Consolidation operation failed
- `DATABASE_ERROR`: Database operation failed
- `REDIS_ERROR`: Redis operation failed
- `CHROMADB_ERROR`: ChromaDB operation failed

## 📝 **Usage Examples**

### **JavaScript/Node.js**

```javascript
// Get memory system status
const status = await fetch('/api/memory/status');
const statusData = await status.json();

// Search for conversations
const searchResults = await fetch('/api/memory/search?q=John Smith&limit=10');
const searchData = await searchResults.json();

// Get entity mentions
const entities = await fetch('/api/memory/entities?user_name=alice&entity_type=PERSON');
const entityData = await entities.json();

// Create new entity
const newEntity = await fetch('/api/memory/entities', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    entity_text: 'Sarah Johnson',
    entity_type: 'PERSON',
    user_name: 'alice',
    context_info: 'user\'s sister'
  })
});
```

### **Python**

```python
import requests

# Get memory system status
response = requests.get('http://localhost:5002/api/memory/status')
status = response.json()

# Search for conversations
search_params = {'q': 'John Smith', 'limit': 10}
response = requests.get('http://localhost:5002/api/memory/search', params=search_params)
search_results = response.json()

# Get entity mentions
entity_params = {'user_name': 'alice', 'entity_type': 'PERSON'}
response = requests.get('http://localhost:5002/api/memory/entities', params=entity_params)
entities = response.json()

# Create new entity
new_entity = {
    'entity_text': 'Sarah Johnson',
    'entity_type': 'PERSON',
    'user_name': 'alice',
    'context_info': 'user\'s sister'
}
response = requests.post('http://localhost:5002/api/memory/entities', json=new_entity)
```

### **cURL**

```bash
# Get system status
curl -X GET "http://localhost:5002/api/memory/status"

# Search conversations
curl -X GET "http://localhost:5002/api/memory/search?q=John%20Smith&limit=10"

# Get entities
curl -X GET "http://localhost:5002/api/memory/entities?user_name=alice&entity_type=PERSON"

# Create entity
curl -X POST "http://localhost:5002/api/memory/entities" \
  -H "Content-Type: application/json" \
  -d '{"entity_text":"Sarah Johnson","entity_type":"PERSON","user_name":"alice","context_info":"user'\''s sister"}'
```

## 🔧 **Troubleshooting**

### **Common Issues**

#### **ChromaDB Connection Issues**
- Check if ChromaDB service is running
- Verify CHROMADB_URL environment variable
- Check network connectivity
- Review ChromaDB logs

#### **Redis Connection Issues**
- Check if Redis service is running
- Verify REDIS_URL environment variable
- Check Redis memory limits
- Review Redis logs

#### **Search Performance Issues**
- Check database indexes
- Monitor memory usage
- Review query complexity
- Check cache hit rates

#### **Entity Extraction Issues**
- Verify Ollama is running
- Check model availability
- Review extraction logs
- Test with simple examples

### **Debug Commands**

```bash
# Check Redis status
docker exec mumble-ai-redis redis-cli ping

# Check ChromaDB status
curl http://localhost:8000/api/v1/heartbeat

# Check PostgreSQL status
docker exec mumble-ai-postgres psql -U mumbleai -d mumble_ai -c "SELECT COUNT(*) FROM conversation_history;"

# View memory manager logs
docker-compose logs mumble-bot | grep -i memory

# Check entity extraction
docker-compose logs mumble-bot | grep -i entity
```

## 📚 **Additional Resources**

- **Smart Memory System Guide**: `docs/SMART_MEMORY_SYSTEM.md`
- **Quick Reference**: `docs/SMART_MEMORY_QUICK_REFERENCE.md`
- **Architecture Overview**: `docs/ARCHITECTURE.md`
- **Configuration Guide**: `docs/CONFIGURATION.md`
- **Troubleshooting Guide**: `docs/TROUBLESHOOTING.md`

---

**Built with ❤️ using Flask, Redis, ChromaDB, and PostgreSQL**
