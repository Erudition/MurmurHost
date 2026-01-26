# Architecture Update - October 21, 2025

## Overview

This document describes the updated system architecture for the Mumble-AI stack, including the new whisper-web-interface service, enhanced smart memory system, and improved service communication patterns.

## System Architecture

### 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Access Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │Mumble Client │  │ Web Clients  │  │  SIP Phones  │  │ Email Clients   │ │
│  │(Desktop/Mobile│  │(Port 8081)   │  │(Port 5060)  │  │(IMAP/SMTP)     │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘ │
└─────────┼──────────────────┼──────────────────┼───────────────────┼─────────┘
          │                  │                  │                   │
┌─────────▼──────────────────▼──────────────────▼───────────────────▼─────────┐
│                        Application Layer                                      │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  Mumble Server   │  │ SIP Bridge   │  │ Email System │  │ Mumble Web  │  │
│  │   (Port 48000)   │  │(Port 5060)   │  │(Port 5006)   │  │  Client     │  │
│  └─────────┬────────┘  └──────┬───────┘  └──────┬───────┘  │(Port 8081)  │  │
│            │                  │                  │          └─────────────┘  │
│       ┌────▼──────┐           │                  │                          │
│       │  AI Bot   │           │                  │                          │
│       │(Smart Mem)│           │                  │                          │
│       └─┬───┬───┬─┘           │                  │                          │
└─────────┼───┼───┼─────────────┼──────────────────┼──────────────────────────┘
          │   │   │             │                  │
┌─────────▼───▼───▼─────────────▼──────────────────▼──────────────────────────┐
│                            Service Layer                                    │
│  ┌──────────┐  ┌────────┐  ┌─────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ Faster   │  │ Piper  │  │ Ollama  │  │  PostgreSQL  │  │ Mumble Web  │  │
│  │ Whisper  │  │  TTS   │  │(External│  │              │  │   Simple    │  │
│  │(Port5000)│  │(5001)  │  │ :11434) │  │  (Internal)  │  │(Build Only) │  │
│  └──────────┘  └────────┘  └─────────┘  └──────────────┘  └─────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Silero   │  │Chatterbox│  │ TTS Web  │  │ Web Control │  │ Email       │  │
│  │  TTS     │  │   TTS    │  │Interface │  │   Panel     │  │ Summary     │  │
│  │(Port5004)│  │(Port5005)│  │(Port5003)│  │  (Port5002) │  │(Port 5006)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  └─────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Whisper  │  │ Landing  │  │ Mumble   │  │ Mumble Web  │  │ Mumble Web  │  │
│  │   Web    │  │   Page   │  │   Web    │  │   Nginx     │  │   Simple    │  │
│  │Interface │  │(Port5007)│  │(Port8081)│  │  (Internal) │  │(Build Only) │  │
│  │(Port5008)│  └──────────┘  └──────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────────────────┐
│                        Smart Memory Layer (ENHANCED!)                      │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │  Redis   │  │  ChromaDB    │  │  PostgreSQL  │  │   Memory Manager    │  │
│  │  Cache   │  │ Vector Store │  │   Database   │  │   (Orchestrator)    │  │
│  │(Port6379)│  │ (Port 8000)  │  │  (Port5432)  │  │                     │  │
│  └──────────┘  └──────────────┘  └──────────────┘  └─────────────────────┘  │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │ Entity   │  │  Memory      │  │ Conversation │  │   Hybrid Search     │  │
│  │ Tracker  │  │Consolidator  │  │   Context    │  │   (Semantic+Keyword)│  │
│  └──────────┘  └──────────────┘  └──────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Service Communication Patterns

#### 2.1 Direct Service Communication

**Mumble Bot ↔ AI Services**:
```
Mumble Bot → Faster Whisper (STT)
Mumble Bot → Piper TTS (TTS)
Mumble Bot → Ollama (AI Processing)
Mumble Bot → PostgreSQL (Data Storage)
```

**Whisper Web Interface ↔ Services**:
```
Whisper Web Interface → Faster Whisper (Transcription)
Whisper Web Interface → Ollama (Summarization)
Whisper Web Interface → PostgreSQL (History Storage)
```

**SIP Bridge ↔ Services**:
```
SIP Bridge → Faster Whisper (STT)
SIP Bridge → Piper TTS (TTS)
SIP Bridge → Ollama (AI Processing)
SIP Bridge → PostgreSQL (Data Storage)
```

#### 2.2 Memory System Communication

**Memory Manager ↔ Storage Services**:
```
Memory Manager → PostgreSQL (Structured Data)
Memory Manager → ChromaDB (Vector Storage)
Memory Manager → Redis (Caching)
Memory Manager → Ollama (AI Processing)
```

**Service ↔ Memory Manager**:
```
Mumble Bot → Memory Manager → Storage Services
SIP Bridge → Memory Manager → Storage Services
Web Control Panel → Memory Manager → Storage Services
```

### 3. Data Flow Architecture

#### 3.1 Voice Processing Flow

```
User Voice → Mumble Server → Mumble Bot → Faster Whisper → Ollama → Piper TTS → Mumble Server → User
     │              │              │              │              │              │              │
     │              │              │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼              ▼              ▼
  Audio Data    Audio Data    Text Data    AI Response    Audio Data    Audio Data    Audio Data
```

#### 3.2 Memory System Flow

```
Conversation → Memory Manager → Entity Extraction → ChromaDB (Vectors)
     │              │              │                    │
     │              │              │                    │
     ▼              ▼              ▼                    ▼
User Input → PostgreSQL → Redis Cache → Semantic Search → AI Response
```

#### 3.3 Whisper Web Interface Flow

```
File Upload → Whisper Web Interface → Faster Whisper → Transcription
     │              │                      │              │
     │              │                      │              │
     ▼              ▼                      ▼              ▼
Audio/Video → File Processing → Text Output → AI Summary → Database Storage
```

### 4. Smart Memory System Architecture

#### 4.1 Memory Layers

**Layer 1 - Redis Cache (Fast Access)**:
- Session data (30 min TTL)
- Entity cache (1 hour TTL)
- Hot memories (1 hour TTL)
- User context (30 min TTL)

**Layer 2 - ChromaDB (Vector Storage)**:
- Conversation embeddings
- Entity embeddings
- Consolidated memory embeddings
- Semantic search vectors

**Layer 3 - PostgreSQL (Persistent Storage)**:
- Conversation history
- Entity mentions
- Session tracking
- Configuration data

#### 4.2 Memory Processing Pipeline

```
Input → Entity Extraction → Embedding Generation → Vector Storage
  │              │                    │                    │
  │              │                    │                    │
  ▼              ▼                    ▼                    ▼
Text → Named Entities → Embeddings → ChromaDB → Semantic Search
```

#### 4.3 Hybrid Search Architecture

**Semantic Search (70% weight)**:
```
Query → Embedding → ChromaDB → Vector Similarity → Results
```

**Keyword Search (30% weight)**:
```
Query → PostgreSQL → Full-Text Search → Results
```

**Fusion Algorithm**:
```
Semantic Results + Keyword Results → RRF Fusion → Final Results
```

### 5. Service Dependencies

#### 5.1 Infrastructure Dependencies

**Database Services**:
- PostgreSQL (Primary Database)
- Redis (Caching Layer)
- ChromaDB (Vector Storage)

**AI Services**:
- Ollama (External AI Models)
- Faster Whisper (Speech-to-Text)
- Piper TTS (Text-to-Speech)
- Silero TTS (Alternative TTS)
- Chatterbox TTS (Voice Cloning)

#### 5.2 Application Dependencies

**Core Services**:
- Mumble Server (VoIP Server)
- Mumble Bot (AI Assistant)
- SIP Bridge (Phone Integration)
- Web Control Panel (Management)

**Web Services**:
- Whisper Web Interface (Transcription)
- TTS Web Interface (Voice Generation)
- Landing Page (Project Home)
- Mumble Web (Web Client)

### 6. Network Architecture

#### 6.1 Docker Network Configuration

**Network Topology**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Docker Network (mumble-ai-network)               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │   Services   │  │   Services   │  │   Services   │  │    Services     │  │
│  │   (Internal) │  │   (Internal) │  │   (Internal) │  │   (Internal)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Service Communication**:
- Internal: Container-to-container communication
- External: Port mapping for user access
- Security: Network isolation and firewall rules

#### 6.2 Port Configuration

**External Ports**:
- 48000: Mumble Server (UDP/TCP)
- 5000: Faster Whisper (HTTP)
- 5001: Piper TTS (HTTP)
- 5002: Web Control Panel (HTTP)
- 5003: TTS Web Interface (HTTP)
- 5004: Silero TTS (HTTP)
- 5005: Chatterbox TTS (HTTP)
- 5006: Email Summary Service (HTTP)
- 5007: Landing Page (HTTP)
- 5008: Whisper Web Interface (HTTP)
- 5060: SIP Bridge (UDP)
- 6379: Redis (TCP)
- 8000: ChromaDB (HTTP)
- 8081: Mumble Web (HTTPS)

### 7. Scalability Considerations

#### 7.1 Horizontal Scaling

**Stateless Services**:
- Web Control Panel
- Whisper Web Interface
- TTS Web Interface
- Email Summary Service

**Stateful Services**:
- Mumble Bot (Session State)
- SIP Bridge (Call State)
- PostgreSQL (Database State)
- Redis (Cache State)
- ChromaDB (Vector State)

#### 7.2 Performance Optimization

**Caching Strategy**:
- Redis for session data
- ChromaDB for vector search
- PostgreSQL for persistent storage
- Multi-tier caching approach

**Database Optimization**:
- Connection pooling
- Query optimization
- Index optimization
- Partitioning strategies

### 8. Security Architecture

#### 8.1 Network Security

**Internal Communication**:
- Docker network isolation
- Service-to-service authentication
- Encrypted communication where applicable

**External Access**:
- HTTPS for web services
- SSL/TLS certificates
- Firewall configuration
- Port security

#### 8.2 Data Security

**Data Encryption**:
- Database encryption at rest
- Network encryption in transit
- Volume encryption for sensitive data

**Access Control**:
- Service authentication
- User authorization
- API security
- Audit logging

### 9. Monitoring and Observability

#### 9.1 Health Monitoring

**Service Health Checks**:
- HTTP health endpoints
- Database connectivity
- Service dependencies
- Resource utilization

**Metrics Collection**:
- Service performance
- Error rates
- Response times
- Resource usage

#### 9.2 Logging Architecture

**Centralized Logging**:
- Service logs
- Application logs
- System logs
- Audit logs

**Log Processing**:
- Log aggregation
- Log analysis
- Error tracking
- Performance monitoring

### 10. Deployment Architecture

#### 10.1 Container Orchestration

**Docker Compose**:
- Service definition
- Dependency management
- Volume management
- Network configuration

**Service Management**:
- Startup ordering
- Health checks
- Restart policies
- Resource limits

#### 10.2 Configuration Management

**Environment Variables**:
- Service configuration
- Database settings
- AI model settings
- Security settings

**Configuration Files**:
- Docker Compose configuration
- Service configuration
- Database schema
- Network configuration

### 11. Data Architecture

#### 11.1 Data Storage Strategy

**PostgreSQL (Structured Data)**:
- Conversation history
- User sessions
- Entity mentions
- Configuration data

**ChromaDB (Vector Data)**:
- Conversation embeddings
- Entity embeddings
- Memory embeddings
- Search vectors

**Redis (Cache Data)**:
- Session data
- Entity cache
- Hot memories
- User context

#### 11.2 Data Processing Pipeline

**Data Ingestion**:
- Real-time conversation data
- Batch processing for consolidation
- Entity extraction and tracking
- Memory consolidation

**Data Retrieval**:
- Hybrid search (semantic + keyword)
- Caching for performance
- Vector similarity search
- Full-text search

### 12. AI Integration Architecture

#### 12.1 AI Service Integration

**Ollama Integration**:
- Local LLM processing
- Model management
- Response generation
- Entity extraction

**Speech Processing**:
- Faster Whisper for STT
- Multiple TTS engines
- Audio format conversion
- Quality optimization

#### 12.2 AI Processing Pipeline

**Conversation Processing**:
- Input preprocessing
- AI model inference
- Response generation
- Output postprocessing

**Memory Processing**:
- Entity extraction
- Embedding generation
- Memory consolidation
- Context retrieval

### 13. Future Architecture Considerations

#### 13.1 Scalability Enhancements

**Microservices Architecture**:
- Service decomposition
- API gateway
- Service mesh
- Load balancing

**Cloud Integration**:
- Cloud storage
- Cloud AI services
- Hybrid deployment
- Multi-region support

#### 13.2 Advanced Features

**Real-time Processing**:
- WebSocket communication
- Real-time updates
- Live transcription
- Streaming audio

**Advanced AI**:
- Multi-modal AI
- Advanced reasoning
- Custom models
- Fine-tuning capabilities

## Conclusion

The updated architecture provides a comprehensive, scalable, and maintainable foundation for the Mumble-AI system. The enhancements include:

- **New Services**: Whisper Web Interface for transcription
- **Enhanced Memory System**: Multi-layer memory architecture
- **Improved Communication**: Better service integration
- **Scalability**: Horizontal and vertical scaling capabilities
- **Security**: Comprehensive security measures
- **Monitoring**: Full observability and health monitoring
- **Performance**: Optimized data flow and processing

This architecture ensures reliable, scalable, and maintainable operation of the entire Mumble-AI ecosystem.



