# Flutter API Documentation

## Overview

This document describes the REST API endpoints available for the Flutter Android app to interact with the Mumble-AI system. The API provides full CRUD operations for memories, schedules, conversations, and AI chat functionality.

## Base URL

```
http://localhost:5002/api
```

## Authentication

Currently, no authentication is required. All endpoints are open.

## Response Format

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": "Additional context"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

## Error Codes

- `MISSING_PARAMETER` - Required parameter missing
- `INVALID_FORMAT` - Invalid data format
- `NOT_FOUND` - Resource not found
- `DATABASE_ERROR` - Database operation failed
- `OLLAMA_ERROR` - AI service error
- `CONFIG_ERROR` - Configuration error
- `CONTEXT_ERROR` - Context building error
- `INTERNAL_ERROR` - Unexpected server error
- `HEALTH_CHECK_FAILED` - Health check failed

## Endpoints

### 1. AI Chat

#### POST /api/chat

Send a message to the AI and receive a response with full context (memories, schedules, conversation history).

**Request:**
```json
{
  "user_name": "John",
  "message": "What do I have scheduled for tomorrow?",
  "session_id": "optional-uuid",
  "include_memories": true,
  "include_schedule": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "response": "You have a doctor's appointment at 2:00 PM tomorrow.",
    "session_id": "generated-or-provided-uuid",
    "context_used": {
      "memories_count": 5,
      "schedule_events_count": 3
    }
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

### 2. Memories

#### GET /api/memories

Get persistent memories for a user with filtering and pagination.

**Query Parameters:**
- `user_name` (required) - User name
- `category` (optional) - Filter by category
- `importance` (optional) - Minimum importance level (1-10)
- `limit` (optional) - Number of results (default: 50)
- `offset` (optional) - Pagination offset (default: 0)

**Example:**
```
GET /api/memories?user_name=John&category=schedule&limit=10
```

**Response:**
```json
{
  "success": true,
  "data": {
    "memories": [
      {
        "id": 1,
        "user_name": "John",
        "category": "schedule",
        "content": "Doctor appointment tomorrow at 2 PM",
        "extracted_at": "2025-10-15T20:00:00",
        "importance": 8,
        "tags": ["medical", "appointment"],
        "active": true,
        "event_date": "2025-10-16",
        "event_time": "14:00:00"
      }
    ],
    "pagination": {
      "total": 15,
      "limit": 10,
      "offset": 0,
      "has_more": true
    }
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

#### POST /api/memories

Create a new memory.

**Request:**
```json
{
  "user_name": "John",
  "category": "fact",
  "content": "John prefers coffee over tea",
  "importance": 6,
  "tags": ["preference", "beverage"],
  "event_date": "2025-10-16",
  "event_time": "09:00:00"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 16,
    "status": "created"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

#### PUT /api/memories/{id}

Update an existing memory.

**Request:**
```json
{
  "content": "Updated memory content",
  "importance": 7,
  "tags": ["updated", "tag"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "updated"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

#### DELETE /api/memories/{id}

Delete (deactivate) a memory.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "deleted"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

#### GET /api/memories/categories

Get available memory categories.

**Response:**
```json
{
  "success": true,
  "data": {
    "categories": ["schedule", "fact", "preference", "task", "reminder", "other"]
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

### 3. Schedule Events

#### GET /api/schedule

Get schedule events for a user with filtering and pagination.

**Query Parameters:**
- `user_name` (required) - User name
- `start_date` (optional) - Start date filter (YYYY-MM-DD)
- `end_date` (optional) - End date filter (YYYY-MM-DD)
- `upcoming` (optional) - Next N days
- `limit` (optional) - Number of results (default: 50)
- `offset` (optional) - Pagination offset (default: 0)

**Example:**
```
GET /api/schedule?user_name=John&upcoming=7&limit=10
```

**Response:**
```json
{
  "success": true,
  "data": {
    "events": [
      {
        "id": 1,
        "user_name": "John",
        "title": "Doctor Appointment",
        "event_date": "2025-10-16",
        "event_time": "14:00:00",
        "description": "Annual checkup",
        "importance": 8,
        "created_at": "2025-10-15T20:00:00",
        "reminder_enabled": true,
        "reminder_minutes": 60,
        "recipient_email": "john@example.com",
        "reminder_sent": false
      }
    ],
    "pagination": {
      "total": 5,
      "limit": 10,
      "offset": 0,
      "has_more": false
    }
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

#### POST /api/schedule

Create a new schedule event.

**Request:**
```json
{
  "user_name": "John",
  "title": "Team Meeting",
  "event_date": "2025-10-17",
  "event_time": "10:00:00",
  "description": "Weekly team standup",
  "importance": 7,
  "reminder_enabled": true,
  "reminder_minutes": 30,
  "recipient_email": "john@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 6,
    "status": "created"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

#### PUT /api/schedule/{id}

Update an existing schedule event.

**Request:**
```json
{
  "title": "Updated Meeting Title",
  "event_time": "11:00:00",
  "description": "Updated description"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "updated"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

#### DELETE /api/schedule/{id}

Delete (deactivate) a schedule event.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "deleted"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

### 4. Conversations

#### GET /api/conversations

Get conversation history for a user with filtering and pagination.

**Query Parameters:**
- `user_name` (required) - User name
- `session_id` (optional) - Filter by session ID
- `limit` (optional) - Number of results (default: 100)
- `offset` (optional) - Pagination offset (default: 0)

**Example:**
```
GET /api/conversations?user_name=John&session_id=uuid&limit=20
```

**Response:**
```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "id": 1,
        "user_name": "John",
        "message_type": "text",
        "role": "user",
        "message": "What do I have scheduled for tomorrow?",
        "timestamp": "2025-10-15T23:14:58.062968"
      },
      {
        "id": 2,
        "user_name": "John",
        "message_type": "text",
        "role": "assistant",
        "message": "You have a doctor's appointment at 2:00 PM tomorrow.",
        "timestamp": "2025-10-15T23:14:58.062968"
      }
    ],
    "pagination": {
      "total": 50,
      "limit": 20,
      "offset": 0,
      "has_more": true
    }
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

#### GET /api/conversations/sessions

Get conversation sessions for a user.

**Query Parameters:**
- `user_name` (required) - User name

**Response:**
```json
{
  "success": true,
  "data": {
    "sessions": [
      {
        "session_id": "uuid-123",
        "user_name": "John",
        "started_at": "2025-10-15T20:00:00",
        "last_activity": "2025-10-15T23:14:58",
        "message_count": 42
      }
    ]
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

### 5. User Profile

#### GET /api/users/{user_name}/profile

Get user profile with statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "user_name": "John",
    "memory_count": 15,
    "schedule_count": 8,
    "conversation_count": 120,
    "last_active": "2025-10-15T23:14:58.062968"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

### 6. Configuration

#### GET /api/config/mobile

Get mobile-specific configuration.

**Response:**
```json
{
  "success": true,
  "data": {
    "ollama_model": "llama3.2:latest",
    "bot_persona": "You are a helpful AI assistant...",
    "features_enabled": {
      "memories": true,
      "schedules": true,
      "voice": false
    }
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

### 7. Health Check

#### GET /api/health/mobile

Check the health of mobile API services.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": "connected",
    "ollama": "healthy",
    "timestamp": "2025-10-15T23:14:58.062968"
  },
  "timestamp": "2025-10-15T23:14:58.062968"
}
```

## Usage Examples

### Flutter HTTP Client Example

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class MumbleAIApi {
  static const String baseUrl = 'http://localhost:5002/api';
  
  // Send chat message
  static Future<Map<String, dynamic>> sendChat({
    required String userName,
    required String message,
    String? sessionId,
    bool includeMemories = true,
    bool includeSchedule = true,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/chat'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'user_name': userName,
        'message': message,
        'session_id': sessionId,
        'include_memories': includeMemories,
        'include_schedule': includeSchedule,
      }),
    );
    
    return json.decode(response.body);
  }
  
  // Get memories
  static Future<Map<String, dynamic>> getMemories({
    required String userName,
    String? category,
    int? importance,
    int limit = 50,
    int offset = 0,
  }) async {
    final queryParams = {
      'user_name': userName,
      if (category != null) 'category': category,
      if (importance != null) 'importance': importance.toString(),
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    
    final uri = Uri.parse('$baseUrl/memories').replace(
      queryParameters: queryParams,
    );
    
    final response = await http.get(uri);
    return json.decode(response.body);
  }
  
  // Get schedule events
  static Future<Map<String, dynamic>> getSchedule({
    required String userName,
    String? startDate,
    String? endDate,
    int? upcoming,
    int limit = 50,
    int offset = 0,
  }) async {
    final queryParams = {
      'user_name': userName,
      if (startDate != null) 'start_date': startDate,
      if (endDate != null) 'end_date': endDate,
      if (upcoming != null) 'upcoming': upcoming.toString(),
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    
    final uri = Uri.parse('$baseUrl/schedule').replace(
      queryParameters: queryParams,
    );
    
    final response = await http.get(uri);
    return json.decode(response.body);
  }
}
```

## Rate Limiting

Currently, no rate limiting is implemented. This may be added in future versions.

## Notes

- All timestamps are in ISO 8601 format
- Date formats should be YYYY-MM-DD
- Time formats should be HH:MM:SS
- The API uses soft deletes (setting `active = false`) for memories and schedule events
- Session IDs are UUIDs and can be generated client-side or server-side
- The AI chat endpoint includes full context by default (memories, schedules, conversation history)
- All endpoints return consistent JSON responses with success/error indicators
