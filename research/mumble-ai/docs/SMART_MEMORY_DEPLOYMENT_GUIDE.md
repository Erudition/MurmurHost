# Smart Memory System - Deployment Guide

## 🚀 **Overview**

This guide provides comprehensive instructions for deploying the Smart Memory System, a revolutionary enhancement to the Mumble-AI bot that provides advanced memory management, entity tracking, and intelligent conversation context.

## 📋 **Prerequisites**

### **System Requirements**

#### **Minimum Requirements**
- **CPU**: 4 cores, 2.4GHz
- **RAM**: 8GB (16GB recommended)
- **Storage**: 50GB available space
- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows with WSL2

#### **Recommended Requirements**
- **CPU**: 8 cores, 3.0GHz+
- **RAM**: 16GB+ (32GB for production)
- **Storage**: 100GB+ SSD
- **GPU**: NVIDIA GPU with CUDA support (optional but recommended)

### **Software Dependencies**

#### **Required Software**
- **Docker**: 20.10+ with Docker Compose 2.0+
- **Git**: 2.30+
- **Python**: 3.9+ (for migration scripts)
- **Ollama**: Latest version running locally

#### **Optional Software**
- **NVIDIA Container Toolkit**: For GPU acceleration
- **Redis CLI**: For debugging
- **PostgreSQL Client**: For database management

## 🔧 **Installation Steps**

### **Step 1: Clone Repository**

```bash
# Clone the repository
git clone https://your-gitea-instance.com/username/Mumble-AI.git
cd Mumble-AI

# Checkout the latest version
git checkout master
```

### **Step 2: Environment Configuration**

```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env
```

#### **Required Environment Variables**

```bash
# Database Configuration
POSTGRES_DB=mumble_ai
POSTGRES_USER=mumbleai
POSTGRES_PASSWORD=your_secure_password_here
DB_HOST=postgres
DB_PORT=5432
DB_NAME=mumble_ai
DB_USER=mumbleai
DB_PASSWORD=your_secure_password_here

# Memory System Configuration
CHROMADB_URL=http://chromadb:8000
REDIS_URL=redis://redis:6379
ENABLE_ENTITY_TRACKING=true
ENABLE_MEMORY_CONSOLIDATION=true
MEMORY_CONSOLIDATION_DAYS=7
HYBRID_SEARCH_SEMANTIC_WEIGHT=0.7
CONSOLIDATION_SCHEDULE_HOUR=3

# AI Configuration
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:3b
WHISPER_MODEL=base
WHISPER_LANGUAGE=en

# TTS Configuration
TTS_ENGINE=piper
PIPER_VOICE=lessac
SILERO_VOICE=0
CHATTERBOX_VOICE=default

# Mumble Configuration
MUMBLE_PASSWORD=your_mumble_password_here
BOT_USERNAME=AI Assistant

# Email Configuration (Optional)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_IMAP_SERVER=imap.gmail.com
EMAIL_IMAP_PORT=993
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# Performance Tuning
REDIS_MAX_MEMORY=512mb
REDIS_MAX_MEMORY_POLICY=allkeys-lru
CHROMADB_BATCH_SIZE=50
POSTGRES_CONNECTION_POOL_SIZE=10

# Debugging
MEMORY_DEBUG_LOGGING=false
ENTITY_EXTRACTION_VERBOSE=false
CONSOLIDATION_VERBOSE=false

# Protobuf Compatibility
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
```

### **Step 3: Ollama Setup**

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull required models
ollama pull llama3.2:3b
ollama pull nomic-embed-text:latest
ollama pull moondream:latest

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### **Step 4: Database Migration**

```bash
# Start only the database services first
docker-compose up -d postgres redis chromadb

# Wait for services to be ready
sleep 30

# Run database migration
python sql/migrate_to_chromadb.py

# Verify migration
python sql/verify_migration.py
```

### **Step 5: Start All Services**

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

### **Step 6: Verify Installation**

```bash
# Check service health
curl http://localhost:5002/api/memory/status

# Test memory search
curl "http://localhost:5002/api/memory/search?q=test&limit=5"

# Check entity tracking
curl "http://localhost:5002/api/memory/entities?limit=5"
```

## 🔍 **Service Configuration**

### **Redis Configuration**

#### **Basic Configuration**
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
  restart: unless-stopped
  networks:
    - mumble-ai-network
```

#### **Production Configuration**
```yaml
redis:
  image: redis:7-alpine
  container_name: mumble-ai-redis
  ports:
    - "6379:6379"
  volumes:
    - redis-data:/data
  command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru --save 900 1 --save 300 10 --save 60 10000
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 30s
    timeout: 3s
    retries: 3
  restart: unless-stopped
  networks:
    - mumble-ai-network
```

### **ChromaDB Configuration**

#### **Basic Configuration**
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
  restart: unless-stopped
  networks:
    - mumble-ai-network
```

#### **Production Configuration**
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
    - CHROMA_SERVER_HOST=0.0.0.0
    - CHROMA_SERVER_HTTP_PORT=8000
  healthcheck:
    test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8000/api/v1/heartbeat"]
    interval: 30s
    timeout: 10s
    retries: 3
  restart: unless-stopped
  networks:
    - mumble-ai-network
```

### **PostgreSQL Configuration**

#### **Enhanced Schema**
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create entity mentions table
CREATE TABLE IF NOT EXISTS entity_mentions (
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

-- Create memory consolidation log table
CREATE TABLE IF NOT EXISTS memory_consolidation_log (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    messages_consolidated INTEGER NOT NULL,
    summaries_created INTEGER NOT NULL,
    tokens_saved_estimate INTEGER,
    cutoff_date DATE,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add consolidation columns to conversation_history
ALTER TABLE conversation_history
ADD COLUMN IF NOT EXISTS consolidated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS consolidated_summary_id VARCHAR(255);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_entity_mentions_user ON entity_mentions(user_name);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_type ON entity_mentions(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_canonical ON entity_mentions(canonical_id);
CREATE INDEX IF NOT EXISTS idx_consolidation_log_user ON memory_consolidation_log(user_name);
CREATE INDEX IF NOT EXISTS idx_consolidation_log_date ON memory_consolidation_log(run_at);
```

## 🚀 **Production Deployment**

### **Docker Compose Production**

```yaml
version: '3.8'

services:
  # ... existing services ...

  redis:
    image: redis:7-alpine
    container_name: mumble-ai-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 3s
      retries: 3
    restart: unless-stopped
    networks:
      - mumble-ai-network
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

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
    restart: unless-stopped
    networks:
      - mumble-ai-network
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

volumes:
  redis-data:
    driver: local
  chromadb-data:
    driver: local
```

### **Environment-Specific Configuration**

#### **Development Environment**
```bash
# .env.development
ENVIRONMENT=development
DEBUG=true
MEMORY_DEBUG_LOGGING=true
ENTITY_EXTRACTION_VERBOSE=true
CONSOLIDATION_VERBOSE=true
REDIS_MAX_MEMORY=256mb
CHROMADB_BATCH_SIZE=25
```

#### **Staging Environment**
```bash
# .env.staging
ENVIRONMENT=staging
DEBUG=false
MEMORY_DEBUG_LOGGING=false
ENTITY_EXTRACTION_VERBOSE=false
CONSOLIDATION_VERBOSE=false
REDIS_MAX_MEMORY=1gb
CHROMADB_BATCH_SIZE=50
```

#### **Production Environment**
```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
MEMORY_DEBUG_LOGGING=false
ENTITY_EXTRACTION_VERBOSE=false
CONSOLIDATION_VERBOSE=false
REDIS_MAX_MEMORY=2gb
CHROMADB_BATCH_SIZE=100
POSTGRES_CONNECTION_POOL_SIZE=20
```

## 📊 **Monitoring and Maintenance**

### **Health Monitoring**

#### **Service Health Checks**
```bash
#!/bin/bash
# health_check.sh

echo "Checking Mumble-AI Smart Memory System Health..."

# Check Redis
echo "Redis Status:"
docker exec mumble-ai-redis redis-cli ping

# Check ChromaDB
echo "ChromaDB Status:"
curl -s http://localhost:8000/api/v1/heartbeat

# Check PostgreSQL
echo "PostgreSQL Status:"
docker exec mumble-ai-postgres psql -U mumbleai -d mumble_ai -c "SELECT 1;"

# Check Memory System API
echo "Memory System API Status:"
curl -s http://localhost:5002/api/memory/status | jq '.success'

echo "Health check complete!"
```

#### **Performance Monitoring**
```bash
#!/bin/bash
# performance_monitor.sh

echo "Mumble-AI Smart Memory System Performance:"

# Redis Memory Usage
echo "Redis Memory:"
docker exec mumble-ai-redis redis-cli info memory | grep used_memory_human

# PostgreSQL Size
echo "PostgreSQL Size:"
docker exec mumble-ai-postgres psql -U mumbleai -d mumble_ai -c "SELECT pg_size_pretty(pg_database_size('mumble_ai'));"

# ChromaDB Collections
echo "ChromaDB Collections:"
curl -s http://localhost:8000/api/v1/collections | jq '.data | length'

# Memory System Stats
echo "Memory System Stats:"
curl -s http://localhost:5002/api/memory/stats | jq '.data'
```

### **Backup and Recovery**

#### **Database Backup**
```bash
#!/bin/bash
# backup_databases.sh

BACKUP_DIR="/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating database backup in $BACKUP_DIR..."

# Backup PostgreSQL
docker exec mumble-ai-postgres pg_dump -U mumbleai mumble_ai > "$BACKUP_DIR/postgres_backup.sql"

# Backup Redis
docker exec mumble-ai-redis redis-cli --rdb "$BACKUP_DIR/redis_backup.rdb"

# Backup ChromaDB
docker cp mumble-ai-chromadb:/chroma/chroma "$BACKUP_DIR/chromadb_backup"

echo "Backup complete: $BACKUP_DIR"
```

#### **Database Restore**
```bash
#!/bin/bash
# restore_databases.sh

BACKUP_DIR="$1"

if [ -z "$BACKUP_DIR" ]; then
    echo "Usage: $0 <backup_directory>"
    exit 1
fi

echo "Restoring from backup: $BACKUP_DIR"

# Restore PostgreSQL
docker exec -i mumble-ai-postgres psql -U mumbleai mumble_ai < "$BACKUP_DIR/postgres_backup.sql"

# Restore Redis
docker cp "$BACKUP_DIR/redis_backup.rdb" mumble-ai-redis:/data/dump.rdb
docker restart mumble-ai-redis

# Restore ChromaDB
docker cp "$BACKUP_DIR/chromadb_backup" mumble-ai-chromadb:/chroma/

echo "Restore complete!"
```

## 🔧 **Troubleshooting**

### **Common Issues**

#### **ChromaDB Connection Issues**
```bash
# Check ChromaDB logs
docker-compose logs chromadb

# Test ChromaDB connection
curl -v http://localhost:8000/api/v1/heartbeat

# Restart ChromaDB
docker-compose restart chromadb
```

#### **Redis Memory Issues**
```bash
# Check Redis memory usage
docker exec mumble-ai-redis redis-cli info memory

# Clear Redis cache
docker exec mumble-ai-redis redis-cli flushall

# Restart Redis
docker-compose restart redis
```

#### **PostgreSQL Connection Issues**
```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Test PostgreSQL connection
docker exec mumble-ai-postgres psql -U mumbleai -d mumble_ai -c "SELECT 1;"

# Restart PostgreSQL
docker-compose restart postgres
```

#### **Memory System API Issues**
```bash
# Check memory system logs
docker-compose logs mumble-bot | grep -i memory

# Test memory system API
curl -v http://localhost:5002/api/memory/status

# Restart memory system
docker-compose restart mumble-bot
```

### **Debug Commands**

```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f mumble-bot
docker-compose logs -f redis
docker-compose logs -f chromadb
docker-compose logs -f postgres

# Check service status
docker-compose ps

# Check resource usage
docker stats

# Check network connectivity
docker network ls
docker network inspect mumble-ai_mumble-ai-network
```

## 📈 **Performance Optimization**

### **Redis Optimization**

#### **Memory Configuration**
```bash
# Optimize Redis memory usage
redis-cli config set maxmemory 2gb
redis-cli config set maxmemory-policy allkeys-lru
redis-cli config set save "900 1 300 10 60 10000"
```

#### **Connection Pooling**
```python
# In memory_manager.py
redis_pool = redis.ConnectionPool(
    host='redis',
    port=6379,
    max_connections=20,
    retry_on_timeout=True
)
```

### **ChromaDB Optimization**

#### **Batch Processing**
```python
# Optimize batch size for your use case
CHROMADB_BATCH_SIZE = 100  # Increase for better throughput
CHROMADB_EMBEDDING_BATCH_SIZE = 50  # Optimize for your GPU memory
```

#### **Collection Management**
```python
# Regular collection maintenance
def optimize_collections():
    # Remove old collections
    # Optimize indexes
    # Clean up orphaned data
    pass
```

### **PostgreSQL Optimization**

#### **Index Optimization**
```sql
-- Create additional indexes for performance
CREATE INDEX CONCURRENTLY idx_conversation_history_embedding 
ON conversation_history USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX CONCURRENTLY idx_entity_mentions_text 
ON entity_mentions USING gin (to_tsvector('english', entity_text));
```

#### **Connection Pooling**
```python
# Optimize connection pool
db_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=5,
    maxconn=20,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
```

## 🔒 **Security Considerations**

### **Network Security**

#### **Firewall Configuration**
```bash
# Allow only necessary ports
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw allow 5002  # Web Control Panel
ufw allow 5000  # Whisper API
ufw allow 5001  # Piper TTS
ufw allow 5004  # Silero TTS
ufw allow 5005  # Chatterbox TTS
ufw allow 5006  # Email Service
ufw allow 5007  # Landing Page
ufw allow 8081  # Mumble Web
ufw allow 48000 # Mumble Server
ufw allow 5060  # SIP Bridge
ufw deny 6379   # Redis (internal only)
ufw deny 8000   # ChromaDB (internal only)
ufw deny 5432   # PostgreSQL (internal only)
```

#### **Docker Network Security**
```yaml
# Use internal networks for sensitive services
networks:
  mumble-ai-network:
    driver: bridge
    internal: false
  mumble-ai-internal:
    driver: bridge
    internal: true
```

### **Data Security**

#### **Encryption at Rest**
```bash
# Encrypt database volumes
docker volume create --driver local \
  --opt type=none \
  --opt device=/encrypted/postgres \
  --opt o=bind \
  postgres-encrypted
```

#### **Environment Variable Security**
```bash
# Use secrets management
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)" >> .env
echo "MUMBLE_PASSWORD=$(openssl rand -base64 32)" >> .env
```

## 📚 **Additional Resources**

### **Documentation**
- **Smart Memory System Guide**: `docs/SMART_MEMORY_SYSTEM.md`
- **API Documentation**: `docs/MEMORY_SYSTEM_API.md`
- **Quick Reference**: `docs/SMART_MEMORY_QUICK_REFERENCE.md`
- **Architecture Overview**: `docs/ARCHITECTURE.md`
- **Troubleshooting Guide**: `docs/TROUBLESHOOTING.md`

### **Support**
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Comprehensive guides and references
- **Community**: Join discussions and get help
- **Professional Support**: Available for enterprise deployments

---

**Built with ❤️ using Docker, Redis, ChromaDB, PostgreSQL, and AI**
