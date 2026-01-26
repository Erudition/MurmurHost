# Docker Stack Updates - October 21, 2025

## Overview

This document details the comprehensive updates made to the Docker Compose stack, including new services, enhanced configurations, and improved service management.

## New Services

### 1. Whisper Web Interface (Port 5008)

**Purpose**: Modern web interface for audio/video transcription with AI summarization

```yaml
whisper-web-interface:
  build:
    context: ./whisper-web-interface
    dockerfile: Dockerfile
  container_name: whisper-web-interface
  depends_on:
    postgres:
      condition: service_healthy
    faster-whisper:
      condition: service_started
  ports:
    - "5008:5008"
  environment:
    - DB_HOST=postgres
    - DB_PORT=5432
    - DB_NAME=${POSTGRES_DB:-mumble_ai}
    - DB_USER=${POSTGRES_USER:-mumbleai}
    - DB_PASSWORD=${POSTGRES_PASSWORD:-mumbleai123}
    - WHISPER_URL=http://faster-whisper:5000
    - OLLAMA_URL=${OLLAMA_URL:-http://host.docker.internal:11434}
    - OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.2:latest}
  volumes:
    - /tmp:/tmp
  restart: unless-stopped
  networks:
    - mumble-ai-network
  extra_hosts:
    - "host.docker.internal:host-gateway"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5008/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
```

**Features**:
- React-based frontend with modern UI
- Multi-format audio/video support
- AI-powered summarization
- Database integration for history
- Health checks and monitoring

### 2. Redis Cache (Port 6379)

**Purpose**: Fast in-memory storage for session data and caching

```yaml
redis:
  image: redis:7-alpine
  container_name: mumble-ai-redis
  ports:
    - "6379:6379"
  volumes:
    - redis-data:/data
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
  networks:
    - mumble-ai-network
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 30s
    timeout: 3s
    retries: 3
  restart: unless-stopped
```

**Features**:
- Persistent data storage
- Memory optimization (512MB limit)
- LRU eviction policy
- Health checks
- Network isolation

### 3. ChromaDB Vector Store (Port 8000)

**Purpose**: Vector database for semantic search and embeddings

```yaml
chromadb:
  image: chromadb/chroma:0.5.0
  container_name: mumble-ai-chromadb
  ports:
    - "8000:8000"
  volumes:
    - chromadb-data:/chroma/chroma
  environment:
    - IS_PERSISTENT=TRUE
    - ANONYMIZED_TELEMETRY=FALSE
  networks:
    - mumble-ai-network
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
    interval: 30s
    timeout: 10s
    retries: 3
  restart: unless-stopped
```

**Features**:
- Persistent vector storage
- Semantic search capabilities
- Embedding management
- Health monitoring
- Telemetry disabled

## Enhanced Service Configurations

### 1. Mumble Bot Service

**Enhanced Dependencies**:
```yaml
mumble-bot:
  depends_on:
    postgres:
      condition: service_healthy
    mumble-server:
      condition: service_started
    faster-whisper:
      condition: service_started
    piper-tts:
      condition: service_started
    redis:
      condition: service_healthy
    chromadb:
      condition: service_healthy
```

**New Environment Variables**:
```yaml
environment:
  # Memory system configuration
  - CHROMADB_URL=http://chromadb:8000
  - REDIS_URL=redis://redis:6379
  - PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
  
  # Circuit breaker configuration
  - WHISPER_CIRCUIT_THRESHOLD=${WHISPER_CIRCUIT_THRESHOLD:-5}
  - WHISPER_CIRCUIT_TIMEOUT=${WHISPER_CIRCUIT_TIMEOUT:-60.0}
  - PIPER_CIRCUIT_THRESHOLD=${PIPER_CIRCUIT_THRESHOLD:-5}
  - PIPER_CIRCUIT_TIMEOUT=${PIPER_CIRCUIT_TIMEOUT:-60.0}
  - OLLAMA_CIRCUIT_THRESHOLD=${OLLAMA_CIRCUIT_THRESHOLD:-5}
  - OLLAMA_CIRCUIT_TIMEOUT=${OLLAMA_CIRCUIT_TIMEOUT:-60.0}
  - DB_CIRCUIT_THRESHOLD=${DB_CIRCUIT_THRESHOLD:-3}
  - DB_CIRCUIT_TIMEOUT=${DB_CIRCUIT_TIMEOUT:-30.0}
  
  # Health check configuration
  - HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-30.0}
  - HEALTH_PORT=8080
```

**Health Check**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### 2. Web Control Panel Service

**Enhanced Dependencies**:
```yaml
web-control-panel:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    chromadb:
      condition: service_healthy
```

**New Environment Variables**:
```yaml
environment:
  - REDIS_URL=redis://redis:6379
  - CHROMADB_URL=http://chromadb:8000
```

### 3. SIP-Mumble Bridge Service

**Enhanced Dependencies**:
```yaml
sip-mumble-bridge:
  depends_on:
    mumble-server:
      condition: service_started
    redis:
      condition: service_healthy
    chromadb:
      condition: service_healthy
```

**New Environment Variables**:
```yaml
environment:
  - CHROMADB_URL=http://chromadb:8000
  - REDIS_URL=redis://redis:6379
  - PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
```

## Service Dependencies

### 1. Dependency Graph

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL   │    │     Redis        │    │    ChromaDB     │
│   (Database)   │    │    (Cache)       │    │  (Vector Store) │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Mumble Bot     │    │ Web Control     │    │ SIP Bridge      │
│  (AI Assistant) │    │ Panel            │    │ (Phone Bridge) │
└─────────┬───────┘    └─────────────────┘    └─────────────────┘
          │
          ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Faster Whisper  │    │   Piper TTS     │    │   Ollama        │
│   (Speech-to-   │    │ (Text-to-Speech)│    │  (AI Models)    │
│    Text)        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2. Startup Order

**Phase 1 - Infrastructure**:
1. PostgreSQL (database)
2. Redis (cache)
3. ChromaDB (vector store)

**Phase 2 - Core Services**:
4. Mumble Server
5. Faster Whisper
6. Piper TTS
7. Silero TTS
8. Chatterbox TTS

**Phase 3 - Application Services**:
9. Mumble Bot
10. SIP Bridge
11. Web Control Panel
12. Email Summary Service
13. Whisper Web Interface

**Phase 4 - Web Services**:
14. Landing Page
15. TTS Web Interface
16. Mumble Web
17. Mumble Web Nginx

## Health Checks

### 1. Service Health Checks

**PostgreSQL**:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U mumbleai -d mumble_ai"]
  interval: 10s
  timeout: 5s
  retries: 5
```

**Redis**:
```yaml
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 30s
  timeout: 3s
  retries: 3
```

**ChromaDB**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**Mumble Bot**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

**Whisper Web Interface**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5008/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

### 2. Health Check Monitoring

**Service Status Endpoints**:
- Mumble Bot: `http://localhost:8082/health`
- Whisper Web Interface: `http://localhost:5008/health`
- Web Control Panel: `http://localhost:5002/health`
- Email Summary Service: `http://localhost:5006/health`

**Health Check Script**:
```bash
#!/bin/bash
# Health check script for all services

services=(
  "postgres:5432"
  "redis:6379"
  "chromadb:8000"
  "faster-whisper:5000"
  "piper-tts:5001"
  "web-control-panel:5002"
  "whisper-web-interface:5008"
)

for service in "${services[@]}"; do
  name=$(echo $service | cut -d: -f1)
  port=$(echo $service | cut -d: -f2)
  
  if curl -f "http://localhost:$port/health" >/dev/null 2>&1; then
    echo "✅ $name: Healthy"
  else
    echo "❌ $name: Unhealthy"
  fi
done
```

## Volume Management

### 1. New Volumes

```yaml
volumes:
  # Existing volumes
  mumble-data:
  postgres-data:
  piper-voices:
  silero-models:
  chatterbox-models:
  cloned-voices:
  
  # New volumes
  redis-data:
  chromadb-data:
```

### 2. Volume Configuration

**Redis Volume**:
```yaml
redis-data:
  driver: local
  driver_opts:
    type: none
    o: bind
    device: /path/to/redis/data
```

**ChromaDB Volume**:
```yaml
chromadb-data:
  driver: local
  driver_opts:
    type: none
    o: bind
    device: /path/to/chromadb/data
```

### 3. Volume Backup

**Backup Script**:
```bash
#!/bin/bash
# Volume backup script

BACKUP_DIR="/backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL data
docker run --rm -v mumble-ai_postgres-data:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/postgres-data.tar.gz -C /data .

# Backup Redis data
docker run --rm -v mumble-ai_redis-data:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/redis-data.tar.gz -C /data .

# Backup ChromaDB data
docker run --rm -v mumble-ai_chromadb-data:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/chromadb-data.tar.gz -C /data .

echo "Backup completed: $BACKUP_DIR"
```

## Network Configuration

### 1. Docker Network

```yaml
networks:
  mumble-ai-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### 2. Service Communication

**Internal Communication**:
- All services communicate via Docker network
- Service discovery using container names
- No external port exposure for internal services

**External Access**:
- Web services: HTTP/HTTPS ports
- Mumble Server: UDP/TCP port 48000
- SIP Bridge: UDP port 5060
- RTP ports: 10000-10010

### 3. Network Security

**Firewall Rules**:
```bash
# Allow Mumble traffic
ufw allow 48000/udp
ufw allow 48000/tcp

# Allow SIP traffic
ufw allow 5060/udp
ufw allow 5060/tcp

# Allow RTP traffic
ufw allow 10000:10010/udp

# Allow web services
ufw allow 5002/tcp  # Web Control Panel
ufw allow 5008/tcp  # Whisper Web Interface
ufw allow 8081/tcp  # Mumble Web
```

## Environment Variables

### 1. New Environment Variables

**Memory System Configuration**:
```env
# ChromaDB configuration
CHROMADB_URL=http://chromadb:8000

# Redis configuration
REDIS_URL=redis://redis:6379

# Memory limits
SHORT_TERM_MEMORY_LIMIT=10
LONG_TERM_MEMORY_LIMIT=10
SEMANTIC_SIMILARITY_THRESHOLD=0.7

# Session management
SESSION_TIMEOUT_MINUTES=30
SESSION_REACTIVATION_MINUTES=10

# Circuit breaker settings
WHISPER_CIRCUIT_THRESHOLD=5
WHISPER_CIRCUIT_TIMEOUT=60.0
PIPER_CIRCUIT_THRESHOLD=5
PIPER_CIRCUIT_TIMEOUT=60.0
OLLAMA_CIRCUIT_THRESHOLD=5
OLLAMA_CIRCUIT_TIMEOUT=60.0
DB_CIRCUIT_THRESHOLD=3
DB_CIRCUIT_TIMEOUT=30.0

# Health check configuration
HEALTH_CHECK_INTERVAL=30.0
```

### 2. Service-Specific Variables

**Whisper Web Interface**:
```env
# Database configuration
DB_HOST=postgres
DB_PORT=5432
DB_NAME=mumble_ai
DB_USER=mumbleai
DB_PASSWORD=mumbleai123

# Service URLs
WHISPER_URL=http://faster-whisper:5000
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:latest
```

**Redis Configuration**:
```env
# Redis memory settings
REDIS_MAXMEMORY=512mb
REDIS_MAXMEMORY_POLICY=allkeys-lru
REDIS_APPENDONLY=yes
```

**ChromaDB Configuration**:
```env
# ChromaDB settings
IS_PERSISTENT=TRUE
ANONYMIZED_TELEMETRY=FALSE
```

## Service Management

### 1. Service Commands

**Start All Services**:
```bash
docker-compose up -d
```

**Start Specific Services**:
```bash
# Start infrastructure services
docker-compose up -d postgres redis chromadb

# Start core services
docker-compose up -d mumble-server faster-whisper piper-tts

# Start application services
docker-compose up -d mumble-bot web-control-panel whisper-web-interface
```

**Stop Services**:
```bash
# Stop all services
docker-compose down

# Stop specific services
docker-compose stop mumble-bot whisper-web-interface
```

### 2. Service Monitoring

**Service Status**:
```bash
# Check service status
docker-compose ps

# Check service logs
docker-compose logs -f mumble-bot
docker-compose logs -f whisper-web-interface

# Check service health
docker-compose exec mumble-bot curl -f http://localhost:8080/health
```

**Resource Usage**:
```bash
# Check resource usage
docker stats

# Check specific service resources
docker stats mumble-bot whisper-web-interface
```

### 3. Service Scaling

**Horizontal Scaling**:
```yaml
# Scale specific services
services:
  mumble-bot:
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '0.5'
          memory: 1G
        reservations:
          cpus: '0.25'
          memory: 512M
```

## Troubleshooting

### 1. Common Issues

**Service Startup Failures**:
```bash
# Check service logs
docker-compose logs -f <service-name>

# Check service dependencies
docker-compose ps

# Restart failed services
docker-compose restart <service-name>
```

**Network Issues**:
```bash
# Check network connectivity
docker-compose exec mumble-bot ping postgres
docker-compose exec mumble-bot ping redis
docker-compose exec mumble-bot ping chromadb

# Check service URLs
docker-compose exec mumble-bot curl -f http://postgres:5432
docker-compose exec mumble-bot curl -f http://redis:6379
docker-compose exec mumble-bot curl -f http://chromadb:8000
```

**Volume Issues**:
```bash
# Check volume mounts
docker-compose exec mumble-bot ls -la /data

# Check volume permissions
docker-compose exec mumble-bot ls -la /tmp
```

### 2. Performance Issues

**Resource Monitoring**:
```bash
# Monitor CPU and memory usage
docker stats

# Check service health
curl -f http://localhost:5008/health
curl -f http://localhost:5002/health
```

**Database Performance**:
```bash
# Check database connections
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT * FROM pg_stat_activity;"

# Check database size
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT pg_size_pretty(pg_database_size('mumble_ai'));"
```

### 3. Recovery Procedures

**Service Recovery**:
```bash
# Restart failed services
docker-compose restart <service-name>

# Recreate failed services
docker-compose up -d --force-recreate <service-name>

# Full stack restart
docker-compose down && docker-compose up -d
```

**Data Recovery**:
```bash
# Restore from backup
docker-compose down
docker volume rm mumble-ai_postgres-data
docker volume create mumble-ai_postgres-data
docker run --rm -v mumble-ai_postgres-data:/data -v /backup:/backup alpine tar xzf /backup/postgres-data.tar.gz -C /data
docker-compose up -d
```

## Security Considerations

### 1. Network Security

**Internal Communication**:
- All services communicate via Docker network
- No external exposure of internal services
- Service-to-service authentication where applicable

**External Access**:
- HTTPS for web services
- Proper firewall configuration
- SSL/TLS certificates for production

### 2. Data Security

**Volume Security**:
- Proper volume permissions
- Encrypted volumes for sensitive data
- Regular backup procedures

**Database Security**:
- Strong passwords for database users
- Limited database permissions
- Regular security updates

### 3. Service Security

**Container Security**:
- Non-root users in containers
- Minimal base images
- Regular security updates
- Vulnerability scanning

**Service Authentication**:
- API authentication where applicable
- Service-to-service authentication
- Proper error handling and logging

## Conclusion

The Docker stack updates provide a comprehensive, scalable, and maintainable infrastructure for the Mumble-AI system. The enhancements include:

- **New Services**: Whisper Web Interface, Redis, and ChromaDB
- **Enhanced Dependencies**: Proper service dependency management
- **Health Checks**: Comprehensive health monitoring
- **Volume Management**: Persistent data storage
- **Network Security**: Isolated service communication
- **Environment Configuration**: Flexible configuration management
- **Service Management**: Easy service management and monitoring

These updates ensure reliable, scalable, and maintainable operation of the entire Mumble-AI stack.



