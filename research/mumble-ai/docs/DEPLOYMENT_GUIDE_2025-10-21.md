# Deployment Guide - October 21, 2025

## Overview

This comprehensive deployment guide covers the installation, configuration, and management of the enhanced Mumble-AI stack with the new whisper-web-interface service and smart memory system.

## Prerequisites

### 1. System Requirements

**Minimum Requirements**:
- **CPU**: 4 cores (8 cores recommended)
- **RAM**: 8GB (16GB recommended)
- **Storage**: 50GB free space (100GB recommended)
- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows 10/11
- **Network**: Stable internet connection

**Recommended Requirements**:
- **CPU**: 8+ cores
- **RAM**: 32GB+
- **Storage**: 200GB+ SSD
- **GPU**: NVIDIA GPU with CUDA support (optional)
- **OS**: Ubuntu 22.04 LTS

### 2. Software Dependencies

**Required Software**:
- Docker 20.10+
- Docker Compose 2.0+
- Git 2.0+
- Ollama (local installation)

**Optional Software**:
- NVIDIA Docker Runtime (for GPU acceleration)
- Portainer (for Docker management)
- Nginx (for reverse proxy)

### 3. Network Requirements

**Port Requirements**:
- **48000**: Mumble Server (UDP/TCP)
- **5000**: Faster Whisper (HTTP)
- **5001**: Piper TTS (HTTP)
- **5002**: Web Control Panel (HTTP)
- **5003**: TTS Web Interface (HTTP)
- **5004**: Silero TTS (HTTP)
- **5005**: Chatterbox TTS (HTTP)
- **5006**: Email Summary Service (HTTP)
- **5007**: Landing Page (HTTP)
- **5008**: Whisper Web Interface (HTTP)
- **5060**: SIP Bridge (UDP)
- **6379**: Redis (TCP)
- **8000**: ChromaDB (HTTP)
- **8081**: Mumble Web (HTTPS)

**Firewall Configuration**:
```bash
# Allow required ports
sudo ufw allow 48000/udp
sudo ufw allow 48000/tcp
sudo ufw allow 5000:5008/tcp
sudo ufw allow 5060/udp
sudo ufw allow 6379/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 8081/tcp
sudo ufw allow 10000:10010/udp
```

## Installation

### 1. Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-username/Mumble-AI.git
cd Mumble-AI

# Checkout the latest version
git checkout main
```

### 2. Install Ollama

**Linux/macOS**:
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull required models
ollama pull llama3.2:latest
ollama pull nomic-embed-text:latest
```

**Windows**:
```powershell
# Download and install Ollama from https://ollama.ai/download
# Start Ollama service
ollama serve

# Pull required models
ollama pull llama3.2:latest
ollama pull nomic-embed-text:latest
```

### 3. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Essential Configuration**:
```env
# Database Configuration
POSTGRES_USER=mumbleai
POSTGRES_PASSWORD=mumbleai123
POSTGRES_DB=mumble_ai

# Mumble Configuration
MUMBLE_PASSWORD=changeme
BOT_USERNAME=AI-Bot
BOT_PASSWORD=

# AI Configuration
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:latest
WHISPER_MODEL=base

# TTS Configuration
TTS_ENGINE=piper
PIPER_VOICE=en_US-lessac-medium

# Memory System Configuration
SHORT_TERM_MEMORY_LIMIT=10
LONG_TERM_MEMORY_LIMIT=10
SEMANTIC_SIMILARITY_THRESHOLD=0.7

# Circuit Breaker Configuration
WHISPER_CIRCUIT_THRESHOLD=5
WHISPER_CIRCUIT_TIMEOUT=60.0
PIPER_CIRCUIT_THRESHOLD=5
PIPER_CIRCUIT_TIMEOUT=60.0
OLLAMA_CIRCUIT_THRESHOLD=5
OLLAMA_CIRCUIT_TIMEOUT=60.0
DB_CIRCUIT_THRESHOLD=3
DB_CIRCUIT_TIMEOUT=30.0

# Health Check Configuration
HEALTH_CHECK_INTERVAL=30.0
```

### 4. Install Docker and Docker Compose

**Ubuntu/Debian**:
```bash
# Update package index
sudo apt update

# Install Docker
sudo apt install docker.io docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in
exit
```

**CentOS/RHEL**:
```bash
# Install Docker
sudo yum install docker docker-compose-plugin

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER
```

**macOS**:
```bash
# Install Docker Desktop from https://www.docker.com/products/docker-desktop
# Or use Homebrew
brew install --cask docker
```

**Windows**:
```powershell
# Install Docker Desktop from https://www.docker.com/products/docker-desktop
# Or use Chocolatey
choco install docker-desktop
```

### 5. Verify Installation

```bash
# Check Docker installation
docker --version
docker-compose --version

# Check Ollama installation
ollama --version

# Test Ollama connectivity
curl http://localhost:11434/api/generate -d '{"model":"llama3.2:latest","prompt":"Hello"}'
```

## Deployment

### 1. Start Infrastructure Services

```bash
# Start database and cache services
docker-compose up -d postgres redis chromadb

# Wait for services to be healthy
docker-compose ps
```

**Verify Infrastructure**:
```bash
# Check PostgreSQL
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT version();"

# Check Redis
docker-compose exec redis redis-cli ping

# Check ChromaDB
curl -f http://localhost:8000/api/v1/heartbeat
```

### 2. Start Core Services

```bash
# Start Mumble server and AI services
docker-compose up -d mumble-server faster-whisper piper-tts silero-tts chatterbox-tts

# Wait for services to be ready
docker-compose ps
```

**Verify Core Services**:
```bash
# Check Mumble server
docker-compose logs mumble-server

# Check Faster Whisper
curl -f http://localhost:5000/health

# Check Piper TTS
curl -f http://localhost:5001/health

# Check Silero TTS
curl -f http://localhost:5004/health

# Check Chatterbox TTS
curl -f http://localhost:5005/health
```

### 3. Start Application Services

```bash
# Start main application services
docker-compose up -d mumble-bot sip-mumble-bridge web-control-panel email-summary-service

# Wait for services to be ready
docker-compose ps
```

**Verify Application Services**:
```bash
# Check Mumble Bot
curl -f http://localhost:8082/health

# Check Web Control Panel
curl -f http://localhost:5002/health

# Check Email Summary Service
curl -f http://localhost:5006/health
```

### 4. Start Web Services

```bash
# Start web interfaces
docker-compose up -d whisper-web-interface tts-web-interface landing-page mumble-web mumble-web-nginx

# Wait for services to be ready
docker-compose ps
```

**Verify Web Services**:
```bash
# Check Whisper Web Interface
curl -f http://localhost:5008/health

# Check TTS Web Interface
curl -f http://localhost:5003/health

# Check Landing Page
curl -f http://localhost:5007/health

# Check Mumble Web
curl -k https://localhost:8081
```

### 5. Complete Stack Deployment

```bash
# Start all services
docker-compose up -d

# Check all services
docker-compose ps

# View logs
docker-compose logs -f
```

## Configuration

### 1. Database Configuration

**PostgreSQL Setup**:
```bash
# Connect to database
docker-compose exec postgres psql -U mumbleai -d mumble_ai

# Check tables
\dt

# Check configuration
SELECT * FROM bot_config;
```

**Database Schema**:
```bash
# Run schema updates
docker-compose exec postgres psql -U mumbleai -d mumble_ai -f /docker-entrypoint-initdb.d/init-db.sql
```

### 2. Memory System Configuration

**Redis Configuration**:
```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check Redis info
INFO

# Check memory usage
INFO memory
```

**ChromaDB Configuration**:
```bash
# Check ChromaDB status
curl -f http://localhost:8000/api/v1/heartbeat

# Check collections
curl -f http://localhost:8000/api/v1/collections
```

### 3. Service Configuration

**Web Control Panel**:
1. Navigate to `http://localhost:5002`
2. Configure AI models and TTS voices
3. Set up email integration
4. Configure memory system settings

**Whisper Web Interface**:
1. Navigate to `http://localhost:5008`
2. Test file upload and transcription
3. Configure AI summarization
4. Test database integration

### 4. Network Configuration

**Docker Network**:
```bash
# Check network configuration
docker network ls
docker network inspect mumble-ai-network

# Check service connectivity
docker-compose exec mumble-bot ping postgres
docker-compose exec mumble-bot ping redis
docker-compose exec mumble-bot ping chromadb
```

## Health Checks

### 1. Service Health Verification

**Automated Health Check Script**:
```bash
#!/bin/bash
# health-check.sh

services=(
  "postgres:5432"
  "redis:6379"
  "chromadb:8000"
  "faster-whisper:5000"
  "piper-tts:5001"
  "silero-tts:5004"
  "chatterbox-tts:5005"
  "web-control-panel:5002"
  "whisper-web-interface:5008"
  "email-summary-service:5006"
  "landing-page:5007"
  "mumble-web:8081"
)

echo "Checking service health..."
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

**Manual Health Checks**:
```bash
# Check service status
docker-compose ps

# Check service logs
docker-compose logs -f mumble-bot
docker-compose logs -f whisper-web-interface

# Check resource usage
docker stats
```

### 2. Database Health

**PostgreSQL Health**:
```bash
# Check database connectivity
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT 1;"

# Check database size
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT pg_size_pretty(pg_database_size('mumble_ai'));"

# Check active connections
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT * FROM pg_stat_activity;"
```

**Redis Health**:
```bash
# Check Redis connectivity
docker-compose exec redis redis-cli ping

# Check Redis memory
docker-compose exec redis redis-cli info memory

# Check Redis keys
docker-compose exec redis redis-cli keys "*"
```

**ChromaDB Health**:
```bash
# Check ChromaDB status
curl -f http://localhost:8000/api/v1/heartbeat

# Check collections
curl -f http://localhost:8000/api/v1/collections

# Check collection count
curl -f http://localhost:8000/api/v1/collections | jq '.data | length'
```

### 3. AI Service Health

**Ollama Health**:
```bash
# Check Ollama status
curl -f http://localhost:11434/api/tags

# Test Ollama generation
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:latest","prompt":"Hello","stream":false}'
```

**Whisper Health**:
```bash
# Test Whisper service
curl -X POST http://localhost:5000/transcribe \
  -F "audio=@test.wav" \
  -F "language=auto"
```

**TTS Health**:
```bash
# Test Piper TTS
curl -X POST http://localhost:5001/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice":"en_US-lessac-medium"}'

# Test Silero TTS
curl -X POST http://localhost:5004/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice":"en_0"}'

# Test Chatterbox TTS
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice":"default"}'
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

# Recreate failed services
docker-compose up -d --force-recreate <service-name>
```

**Database Connection Issues**:
```bash
# Check PostgreSQL logs
docker-compose logs -f postgres

# Check database connectivity
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT 1;"

# Check database configuration
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SHOW ALL;"
```

**Memory System Issues**:
```bash
# Check Redis logs
docker-compose logs -f redis

# Check ChromaDB logs
docker-compose logs -f chromadb

# Check memory system connectivity
docker-compose exec mumble-bot curl -f http://redis:6379
docker-compose exec mumble-bot curl -f http://chromadb:8000/api/v1/heartbeat
```

**AI Service Issues**:
```bash
# Check Ollama status
curl -f http://localhost:11434/api/tags

# Check Ollama logs
ollama logs

# Test Ollama connectivity
docker-compose exec mumble-bot curl -f http://host.docker.internal:11434/api/tags
```

### 2. Performance Issues

**Resource Monitoring**:
```bash
# Check resource usage
docker stats

# Check specific service resources
docker stats mumble-bot whisper-web-interface

# Check system resources
htop
```

**Database Performance**:
```bash
# Check database performance
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT * FROM pg_stat_activity;"

# Check slow queries
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

**Memory System Performance**:
```bash
# Check Redis performance
docker-compose exec redis redis-cli info stats

# Check ChromaDB performance
curl -f http://localhost:8000/api/v1/heartbeat
```

### 3. Network Issues

**Network Connectivity**:
```bash
# Check network configuration
docker network ls
docker network inspect mumble-ai-network

# Check service connectivity
docker-compose exec mumble-bot ping postgres
docker-compose exec mumble-bot ping redis
docker-compose exec mumble-bot ping chromadb
```

**Port Conflicts**:
```bash
# Check port usage
netstat -tulpn | grep -E "(48000|5000|5001|5002|5003|5004|5005|5006|5007|5008|5060|6379|8000|8081)"

# Check Docker port mapping
docker-compose ps
```

### 4. Log Analysis

**Service Logs**:
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f mumble-bot
docker-compose logs -f whisper-web-interface

# View logs with timestamps
docker-compose logs -f --timestamps mumble-bot
```

**Error Analysis**:
```bash
# Filter error logs
docker-compose logs -f mumble-bot | grep -i error
docker-compose logs -f whisper-web-interface | grep -i error

# Check service health
curl -f http://localhost:5008/health
curl -f http://localhost:5002/health
```

## Backup and Recovery

### 1. Database Backup

**PostgreSQL Backup**:
```bash
# Create backup
docker-compose exec postgres pg_dump -U mumbleai -d mumble_ai > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker-compose exec postgres psql -U mumbleai -d mumble_ai < backup_file.sql
```

**Redis Backup**:
```bash
# Create Redis backup
docker-compose exec redis redis-cli BGSAVE

# Copy Redis data
docker cp mumble-ai-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

**ChromaDB Backup**:
```bash
# Create ChromaDB backup
docker-compose exec chromadb tar czf /backup/chromadb_backup_$(date +%Y%m%d_%H%M%S).tar.gz /chroma/chroma
```

### 2. Volume Backup

**Volume Backup Script**:
```bash
#!/bin/bash
# volume-backup.sh

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

### 3. Recovery Procedures

**Full System Recovery**:
```bash
# Stop all services
docker-compose down

# Restore volumes
docker volume rm mumble-ai_postgres-data mumble-ai_redis-data mumble-ai_chromadb-data
docker volume create mumble-ai_postgres-data
docker volume create mumble-ai_redis-data
docker volume create mumble-ai_chromadb-data

# Restore data
docker run --rm -v mumble-ai_postgres-data:/data -v /backup:/backup alpine tar xzf /backup/postgres-data.tar.gz -C /data
docker run --rm -v mumble-ai_redis-data:/data -v /backup:/backup alpine tar xzf /backup/redis-data.tar.gz -C /data
docker run --rm -v mumble-ai_chromadb-data:/data -v /backup:/backup alpine tar xzf /backup/chromadb-data.tar.gz -C /data

# Start services
docker-compose up -d
```

## Monitoring and Maintenance

### 1. Service Monitoring

**Health Check Script**:
```bash
#!/bin/bash
# monitor.sh

while true; do
  echo "=== Service Health Check $(date) ==="
  
  # Check Docker services
  docker-compose ps
  
  # Check service health endpoints
  curl -f http://localhost:5008/health >/dev/null 2>&1 && echo "✅ Whisper Web Interface" || echo "❌ Whisper Web Interface"
  curl -f http://localhost:5002/health >/dev/null 2>&1 && echo "✅ Web Control Panel" || echo "❌ Web Control Panel"
  curl -f http://localhost:5006/health >/dev/null 2>&1 && echo "✅ Email Summary Service" || echo "❌ Email Summary Service"
  
  # Check resource usage
  docker stats --no-stream
  
  sleep 60
done
```

**Log Monitoring**:
```bash
# Monitor logs in real-time
docker-compose logs -f --tail=100

# Monitor specific service logs
docker-compose logs -f mumble-bot | grep -E "(ERROR|WARNING|INFO)"
```

### 2. Performance Monitoring

**Resource Monitoring**:
```bash
# Monitor CPU and memory usage
docker stats --no-stream

# Monitor disk usage
df -h
docker system df

# Monitor network usage
docker network ls
docker network inspect mumble-ai-network
```

**Database Monitoring**:
```bash
# Monitor database performance
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT * FROM pg_stat_activity;"

# Monitor database size
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT pg_size_pretty(pg_database_size('mumble_ai'));"
```

### 3. Maintenance Tasks

**Regular Maintenance**:
```bash
# Clean up Docker system
docker system prune -f

# Clean up unused volumes
docker volume prune -f

# Clean up unused networks
docker network prune -f

# Update services
docker-compose pull
docker-compose up -d
```

**Database Maintenance**:
```bash
# Analyze tables for better performance
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "ANALYZE;"

# Vacuum database
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "VACUUM;"
```

## Security Considerations

### 1. Network Security

**Firewall Configuration**:
```bash
# Configure UFW firewall
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 48000/udp
sudo ufw allow 5000:5008/tcp
sudo ufw allow 5060/udp
sudo ufw allow 6379/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 8081/tcp
```

**SSL/TLS Configuration**:
```bash
# Generate SSL certificates for production
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### 2. Data Security

**Database Security**:
```bash
# Change default passwords
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "ALTER USER mumbleai PASSWORD 'new_secure_password';"

# Enable SSL for PostgreSQL
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "ALTER SYSTEM SET ssl = on;"
```

**Volume Security**:
```bash
# Set proper permissions for volumes
sudo chown -R 999:999 /var/lib/docker/volumes/mumble-ai_postgres-data
sudo chmod -R 700 /var/lib/docker/volumes/mumble-ai_postgres-data
```

### 3. Service Security

**Container Security**:
```bash
# Run containers as non-root user
docker-compose exec mumble-bot whoami

# Check container security
docker-compose exec mumble-bot id
```

**API Security**:
```bash
# Test API endpoints
curl -f http://localhost:5008/health
curl -f http://localhost:5002/health

# Check for security headers
curl -I http://localhost:5008/health
```

## Conclusion

This deployment guide provides comprehensive instructions for installing, configuring, and managing the enhanced Mumble-AI stack. The guide covers:

- **Prerequisites**: System requirements and dependencies
- **Installation**: Step-by-step installation procedures
- **Configuration**: Service and system configuration
- **Health Checks**: Service health verification
- **Troubleshooting**: Common issues and solutions
- **Backup and Recovery**: Data protection procedures
- **Monitoring**: Service and performance monitoring
- **Security**: Security considerations and best practices

Following this guide ensures a successful deployment of the Mumble-AI system with all new features and enhancements.



