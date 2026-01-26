# API Reference - October 21, 2025

## Overview

This comprehensive API reference documents all endpoints, request/response formats, and integration patterns for the enhanced Mumble-AI stack, including the new whisper-web-interface service and smart memory system.

## Whisper Web Interface API (Port 5008)

### 1. Health Check

**Endpoint**: `GET /health`

**Description**: Check service health status

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-21T10:30:00Z",
  "version": "1.0.0"
}
```

### 2. File Upload

**Endpoint**: `POST /api/upload`

**Description**: Upload audio or video file for transcription

**Request**:
```bash
curl -X POST http://localhost:5008/api/upload \
  -F "file=@audio.wav" \
  -F "filename=audio.wav"
```

**Response**:
```json
{
  "success": true,
  "file_id": "123e4567-e89b-12d3-a456-426614174000",
  "filename": "audio.wav",
  "file_size": 1024000,
  "file_type": "audio",
  "duration": 30.5,
  "message": "File uploaded successfully"
}
```

### 3. Transcribe File

**Endpoint**: `POST /api/transcribe`

**Description**: Transcribe uploaded file using Faster Whisper

**Request**:
```json
{
  "file_id": "123e4567-e89b-12d3-a456-426614174000",
  "language": "auto"
}
```

**Response**:
```json
{
  "success": true,
  "transcription_id": "456e7890-e89b-12d3-a456-426614174001",
  "text": "Hello, this is a test transcription.",
  "language": "en",
  "language_probability": 0.95,
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello, this is a test transcription."
    }
  ],
  "duration": 2.5,
  "processing_time": 1.2
}
```

### 4. Generate Summary

**Endpoint**: `POST /api/summarize`

**Description**: Generate AI summary of transcription

**Request**:
```json
{
  "transcription_id": "456e7890-e89b-12d3-a456-426614174001"
}
```

**Response**:
```json
{
  "success": true,
  "summary_id": "789e0123-e89b-12d3-a456-426614174002",
  "summary": "This is a test audio file containing a simple greeting message.",
  "processing_time": 3.5,
  "model": "llama3.2:latest"
}
```

### 5. Get Transcriptions

**Endpoint**: `GET /api/transcriptions`

**Description**: List transcriptions with pagination

**Query Parameters**:
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10)
- `search`: Search query
- `file_type`: Filter by file type (audio/video)
- `language`: Filter by language

**Request**:
```bash
curl "http://localhost:5008/api/transcriptions?page=1&limit=10&search=test"
```

**Response**:
```json
{
  "success": true,
  "transcriptions": [
    {
      "id": "456e7890-e89b-12d3-a456-426614174001",
      "filename": "audio.wav",
      "file_type": "audio",
      "duration": 30.5,
      "language": "en",
      "text": "Hello, this is a test transcription.",
      "summary": "This is a test audio file containing a simple greeting message.",
      "created_at": "2025-10-21T10:30:00Z",
      "updated_at": "2025-10-21T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 1,
    "pages": 1
  }
}
```

### 6. Get Single Transcription

**Endpoint**: `GET /api/transcriptions/{id}`

**Description**: Get single transcription by ID

**Request**:
```bash
curl "http://localhost:5008/api/transcriptions/456e7890-e89b-12d3-a456-426614174001"
```

**Response**:
```json
{
  "success": true,
  "transcription": {
    "id": "456e7890-e89b-12d3-a456-426614174001",
    "filename": "audio.wav",
    "file_type": "audio",
    "duration": 30.5,
    "language": "en",
    "text": "Hello, this is a test transcription.",
    "summary": "This is a test audio file containing a simple greeting message.",
    "segments": [
      {
        "start": 0.0,
        "end": 2.5,
        "text": "Hello, this is a test transcription."
      }
    ],
    "created_at": "2025-10-21T10:30:00Z",
    "updated_at": "2025-10-21T10:30:00Z"
  }
}
```

### 7. Delete Transcription

**Endpoint**: `DELETE /api/transcriptions/{id}`

**Description**: Delete transcription and associated data

**Request**:
```bash
curl -X DELETE "http://localhost:5008/api/transcriptions/456e7890-e89b-12d3-a456-426614174001"
```

**Response**:
```json
{
  "success": true,
  "message": "Transcription deleted successfully"
}
```

## Memory System API

### 1. Memory Manager Health

**Endpoint**: `GET /memory/health`

**Description**: Check memory system health

**Response**:
```json
{
  "status": "healthy",
  "components": {
    "postgres": "connected",
    "redis": "connected",
    "chromadb": "connected",
    "ollama": "connected"
  },
  "timestamp": "2025-10-21T10:30:00Z"
}
```

### 2. Store Message

**Endpoint**: `POST /memory/messages`

**Description**: Store conversation message in memory system

**Request**:
```json
{
  "user": "john_doe",
  "message": "Hello, how are you?",
  "role": "user",
  "session_id": "session_123",
  "importance_score": 0.7
}
```

**Response**:
```json
{
  "success": true,
  "message_id": "123e4567-e89b-12d3-a456-426614174000",
  "embedding": [0.1, 0.2, 0.3, ...],
  "timestamp": "2025-10-21T10:30:00Z"
}
```

### 3. Search Memories

**Endpoint**: `POST /memory/search`

**Description**: Search memories using hybrid search

**Request**:
```json
{
  "query": "What did we discuss about the project?",
  "user": "john_doe",
  "limit": 10,
  "include_entities": true,
  "include_consolidated": true
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "content": "We discussed the project timeline and deliverables.",
      "metadata": {
        "role": "assistant",
        "timestamp": "2025-10-21T10:30:00Z",
        "importance_score": 0.8
      },
      "similarity_score": 0.95
    }
  ],
  "entities": [
    {
      "text": "project",
      "type": "OTHER",
      "confidence": 0.9
    }
  ],
  "total_results": 1
}
```

### 4. Get Conversation Context

**Endpoint**: `POST /memory/context`

**Description**: Get conversation context for user

**Request**:
```json
{
  "user": "john_doe",
  "query": "What's my schedule for tomorrow?",
  "session_id": "session_123",
  "include_entities": true,
  "include_consolidated": true,
  "short_term_limit": 10,
  "long_term_limit": 10
}
```

**Response**:
```json
{
  "success": true,
  "context": {
    "entities": [
      {
        "text": "tomorrow",
        "type": "DATE",
        "confidence": 0.9
      }
    ],
    "memories": [
      {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "content": "You have a meeting at 2pm tomorrow.",
        "metadata": {
          "role": "assistant",
          "timestamp": "2025-10-21T10:30:00Z",
          "importance_score": 0.9
        }
      }
    ],
    "session": [
      {
        "role": "user",
        "content": "What's my schedule for tomorrow?",
        "timestamp": "2025-10-21T10:30:00Z"
      }
    ],
    "consolidated": []
  }
}
```

### 5. Extract Entities

**Endpoint**: `POST /memory/entities`

**Description**: Extract entities from conversation

**Request**:
```json
{
  "user_message": "I'm meeting with John Smith at the office tomorrow.",
  "assistant_message": "I'll add that to your calendar.",
  "user": "john_doe"
}
```

**Response**:
```json
{
  "success": true,
  "entities": [
    {
      "text": "John Smith",
      "type": "PERSON",
      "confidence": 0.95,
      "context": "person you're meeting with"
    },
    {
      "text": "office",
      "type": "PLACE",
      "confidence": 0.9,
      "context": "meeting location"
    },
    {
      "text": "tomorrow",
      "type": "DATE",
      "confidence": 0.98,
      "context": "meeting time"
    }
  ]
}
```

## Enhanced Service APIs

### 1. Faster Whisper Service (Port 5000)

**Enhanced Transcribe Endpoint**:
```bash
curl -X POST http://localhost:5000/transcribe \
  -F "audio=@audio.wav" \
  -F "language=en"
```

**Response**:
```json
{
  "text": "Hello, this is a test transcription.",
  "language": "en",
  "language_probability": 0.95,
  "processing_time": 1.2
}
```

### 2. Piper TTS Service (Port 5001)

**Enhanced TTS Endpoint**:
```bash
curl -X POST http://localhost:5001/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "voice": "en_US-lessac-medium",
    "speed": 1.0,
    "pitch": 1.0
  }'
```

**Response**:
```json
{
  "success": true,
  "audio_url": "http://localhost:5001/audio/123e4567-e89b-12d3-a456-426614174000.wav",
  "duration": 2.5,
  "voice": "en_US-lessac-medium"
}
```

### 3. Silero TTS Service (Port 5004)

**Enhanced TTS Endpoint**:
```bash
curl -X POST http://localhost:5004/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "voice": "en_0",
    "speed": 1.0
  }'
```

**Response**:
```json
{
  "success": true,
  "audio_url": "http://localhost:5004/audio/123e4567-e89b-12d3-a456-426614174000.wav",
  "duration": 2.5,
  "voice": "en_0"
}
```

### 4. Chatterbox TTS Service (Port 5005)

**Enhanced TTS Endpoint**:
```bash
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "voice": "default",
    "speed": 1.0
  }'
```

**Response**:
```json
{
  "success": true,
  "audio_url": "http://localhost:5005/audio/123e4567-e89b-12d3-a456-426614174000.wav",
  "duration": 2.5,
  "voice": "default"
}
```

### 5. Email Summary Service (Port 5006)

**Enhanced Email Endpoint**:
```bash
curl -X POST http://localhost:5006/api/send-summary \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "user@example.com",
    "subject": "Daily Summary",
    "content": "Your daily conversation summary"
  }'
```

**Response**:
```json
{
  "success": true,
  "message_id": "123e4567-e89b-12d3-a456-426614174000",
  "sent_at": "2025-10-21T10:30:00Z"
}
```

## Web Control Panel API (Port 5002)

### 1. Dashboard Data

**Endpoint**: `GET /api/dashboard`

**Description**: Get dashboard statistics

**Response**:
```json
{
  "success": true,
  "data": {
    "total_messages": 1250,
    "unique_users": 15,
    "voice_messages": 800,
    "text_messages": 450,
    "upcoming_events": [
      {
        "id": 1,
        "title": "Team Meeting",
        "date": "2025-10-22",
        "time": "14:00:00",
        "importance": 8
      }
    ],
    "memory_stats": {
      "total_memories": 150,
      "entities_tracked": 45,
      "consolidated_memories": 25
    }
  }
}
```

### 2. Memory System Status

**Endpoint**: `GET /api/memory/status`

**Description**: Get memory system status

**Response**:
```json
{
  "success": true,
  "status": {
    "postgres": {
      "status": "connected",
      "response_time": 5.2
    },
    "redis": {
      "status": "connected",
      "memory_usage": "45%",
      "keys": 1250
    },
    "chromadb": {
      "status": "connected",
      "collections": 4,
      "vectors": 5000
    }
  }
}
```

### 3. Configuration Management

**Endpoint**: `GET /api/config`

**Description**: Get system configuration

**Response**:
```json
{
  "success": true,
  "config": {
    "ollama_url": "http://host.docker.internal:11434",
    "ollama_model": "llama3.2:latest",
    "whisper_model": "base",
    "tts_engine": "piper",
    "piper_voice": "en_US-lessac-medium",
    "memory_limits": {
      "short_term": 10,
      "long_term": 10
    },
    "circuit_breakers": {
      "whisper_threshold": 5,
      "piper_threshold": 5,
      "ollama_threshold": 5
    }
  }
}
```

**Endpoint**: `POST /api/config`

**Description**: Update system configuration

**Request**:
```json
{
  "ollama_model": "llama3.2:latest",
  "tts_engine": "piper",
  "piper_voice": "en_US-lessac-medium",
  "memory_limits": {
    "short_term": 15,
    "long_term": 15
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": "Configuration updated successfully"
}
```

## Error Handling

### 1. Standard Error Response

**Format**:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": "Additional error details",
    "timestamp": "2025-10-21T10:30:00Z"
  }
}
```

### 2. Common Error Codes

**HTTP Status Codes**:
- `200`: Success
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `500`: Internal Server Error
- `503`: Service Unavailable

**Error Codes**:
- `INVALID_FILE`: Invalid file format or size
- `TRANSCRIPTION_FAILED`: Transcription processing failed
- `AI_SERVICE_UNAVAILABLE`: AI service not available
- `DATABASE_ERROR`: Database operation failed
- `MEMORY_SYSTEM_ERROR`: Memory system error
- `CIRCUIT_BREAKER_OPEN`: Circuit breaker is open
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded

### 3. Error Examples

**File Upload Error**:
```json
{
  "success": false,
  "error": {
    "code": "INVALID_FILE",
    "message": "File size exceeds maximum limit of 100MB",
    "details": "Uploaded file size: 150MB, Maximum allowed: 100MB",
    "timestamp": "2025-10-21T10:30:00Z"
  }
}
```

**Transcription Error**:
```json
{
  "success": false,
  "error": {
    "code": "TRANSCRIPTION_FAILED",
    "message": "Transcription processing failed",
    "details": "Whisper service returned error: Model not loaded",
    "timestamp": "2025-10-21T10:30:00Z"
  }
}
```

**Memory System Error**:
```json
{
  "success": false,
  "error": {
    "code": "MEMORY_SYSTEM_ERROR",
    "message": "Memory system operation failed",
    "details": "ChromaDB connection timeout",
    "timestamp": "2025-10-21T10:30:00Z"
  }
}
```

## Authentication

### 1. API Key Authentication

**Header**:
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5008/api/transcriptions
```

### 2. Session Authentication

**Cookie**:
```bash
curl -H "Cookie: session=your-session-id" http://localhost:5008/api/transcriptions
```

### 3. JWT Authentication

**Header**:
```bash
curl -H "Authorization: Bearer your-jwt-token" http://localhost:5008/api/transcriptions
```

## Rate Limiting

### 1. Rate Limit Headers

**Response Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

### 2. Rate Limit Exceeded

**Response**:
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": "Too many requests. Try again in 60 seconds.",
    "timestamp": "2025-10-21T10:30:00Z"
  }
}
```

## WebSocket API

### 1. Real-time Transcription

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:5008/ws/transcribe');

ws.onopen = function() {
  console.log('Connected to transcription service');
};

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Transcription update:', data);
};
```

**Message Format**:
```json
{
  "type": "transcription_update",
  "data": {
    "text": "Partial transcription text",
    "confidence": 0.85,
    "is_final": false
  }
}
```

### 2. Real-time Memory Updates

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:5002/ws/memory');

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Memory update:', data);
};
```

**Message Format**:
```json
{
  "type": "memory_update",
  "data": {
    "user": "john_doe",
    "action": "entity_extracted",
    "entity": {
      "text": "John Smith",
      "type": "PERSON",
      "confidence": 0.95
    }
  }
}
```

## SDK Examples

### 1. Python SDK

```python
import requests

class MumbleAIClient:
    def __init__(self, base_url="http://localhost:5008"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def upload_file(self, file_path):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(f"{self.base_url}/api/upload", files=files)
        return response.json()
    
    def transcribe_file(self, file_id, language="auto"):
        data = {"file_id": file_id, "language": language}
        response = self.session.post(f"{self.base_url}/api/transcribe", json=data)
        return response.json()
    
    def get_transcriptions(self, page=1, limit=10):
        params = {"page": page, "limit": limit}
        response = self.session.get(f"{self.base_url}/api/transcriptions", params=params)
        return response.json()

# Usage
client = MumbleAIClient()
result = client.upload_file("audio.wav")
print(result)
```

### 2. JavaScript SDK

```javascript
class MumbleAIClient {
  constructor(baseUrl = 'http://localhost:5008') {
    this.baseUrl = baseUrl;
  }
  
  async uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${this.baseUrl}/api/upload`, {
      method: 'POST',
      body: formData
    });
    
    return await response.json();
  }
  
  async transcribeFile(fileId, language = 'auto') {
    const response = await fetch(`${this.baseUrl}/api/transcribe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        file_id: fileId,
        language: language
      })
    });
    
    return await response.json();
  }
  
  async getTranscriptions(page = 1, limit = 10) {
    const response = await fetch(`${this.baseUrl}/api/transcriptions?page=${page}&limit=${limit}`);
    return await response.json();
  }
}

// Usage
const client = new MumbleAIClient();
const result = await client.uploadFile(fileInput.files[0]);
console.log(result);
```

## Testing

### 1. API Testing

**Health Check Test**:
```bash
curl -f http://localhost:5008/health
```

**File Upload Test**:
```bash
curl -X POST http://localhost:5008/api/upload \
  -F "file=@test.wav" \
  -F "filename=test.wav"
```

**Transcription Test**:
```bash
curl -X POST http://localhost:5008/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{"file_id":"123e4567-e89b-12d3-a456-426614174000","language":"auto"}'
```

### 2. Load Testing

**Apache Bench Test**:
```bash
ab -n 100 -c 10 http://localhost:5008/health
```

**Artillery Test**:
```yaml
config:
  target: 'http://localhost:5008'
  phases:
    - duration: 60
      arrivalRate: 10
scenarios:
  - name: "Health Check"
    weight: 100
    flow:
      - get:
          url: "/health"
```

## Conclusion

This API reference provides comprehensive documentation for all endpoints and integration patterns in the enhanced Mumble-AI stack. The APIs provide:

- **Whisper Web Interface**: Complete transcription and summarization API
- **Memory System**: Advanced memory management and search capabilities
- **Enhanced Services**: Improved service APIs with better error handling
- **Web Control Panel**: Management and monitoring APIs
- **Error Handling**: Comprehensive error codes and responses
- **Authentication**: Multiple authentication methods
- **Rate Limiting**: Built-in rate limiting and protection
- **WebSocket Support**: Real-time communication capabilities
- **SDK Examples**: Ready-to-use client libraries
- **Testing**: Comprehensive testing procedures

These APIs ensure reliable, scalable, and maintainable integration with the Mumble-AI system.



