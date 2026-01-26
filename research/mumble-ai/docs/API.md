# API Reference

Complete API documentation for all Mumble AI Bot services.

## Table of Contents

- [Landing Page Service API](#landing-page-service-api) (Port 5007)
- [Web Control Panel API](#web-control-panel-api) (Port 5002)
- [TTS Voice Generator API](#tts-voice-generator-api) (Port 5003)
- [Faster Whisper API](#faster-whisper-api) (Port 5000)
- [Piper TTS API](#piper-tts-api) (Port 5001)
- [Silero TTS API](#silero-tts-api) (Port 5004)
- [Chatterbox TTS API](#chatterbox-tts-api) (Port 5005)
- [Email Summary Service API](#email-summary-service-api) (Port 5006)
- [Advanced Search System](#advanced-search-system)
- [Topic State Tracking](#topic-state-tracking)
- [Flutter App Logging API](#flutter-app-logging-api)
- [SIP Bridge](#sip-bridge) (Port 5060)
- [Mumble Web Client](#mumble-web-client) (Port 8081)

## Landing Page Service API

Base URL: `http://localhost:5007`

The Landing Page Service provides a comprehensive web interface for accessing the Mumble AI system, including service status monitoring, APK downloads, and changelog display.

### Service Status

#### Get Service Status

**Endpoint:** `GET /api/status`

Returns real-time status of all Mumble AI services.

**Response:**
```json
{
  "timestamp": "2025-01-15T10:30:00.000Z",
  "services": [
    {
      "service": "mumble-server",
      "name": "Mumble Server",
      "port": 48000,
      "internalPort": 64738,
      "host": "mumble-server",
      "status": "healthy",
      "responseTime": "15ms",
      "details": { "message": "TCP connection successful" },
      "url": "mumble-server:64738",
      "method": "tcp"
    }
  ],
  "summary": {
    "total": 10,
    "healthy": 8,
    "running": 1,
    "unhealthy": 1
  }
}
```

### Changelog Data

#### Get Changelog Data

**Endpoint:** `GET /api/changelog`

Returns parsed changelog data from all `CHANGELOG_*.md` files.

**Response:**
```json
[
  {
    "component": "Topic State And Search Improvements",
    "date": "January 15, 2025",
    "content": "<h1>Topic State & Search Improvements</h1>...",
    "filename": "CHANGELOG_TOPIC_STATE_AND_SEARCH_IMPROVEMENTS.md"
  }
]
```

### APK Files

#### Get APK Files

**Endpoint:** `GET /api/apk`

Returns information about available APK files.

**Response:**
```json
[
  {
    "filename": "app-release.apk",
    "size": "25.4 MB",
    "sizeBytes": 26624000,
    "modified": "2025-01-15T09:15:00.000Z",
    "path": "/app/apk/app-release.apk"
  }
]
```

#### Generate QR Code

**Endpoint:** `GET /api/qr/:filename`

Generates a QR code for APK download.

**Parameters:**
- `filename` (string): APK filename

**Response:**
```json
{
  "filename": "app-release.apk",
  "downloadUrl": "http://192.168.1.100:5007/download/apk/app-release.apk",
  "qrCode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "deviceIP": "192.168.1.100"
}
```

#### Download APK

**Endpoint:** `GET /download/apk/:filename`

Serves APK files for download.

**Parameters:**
- `filename` (string): APK filename

**Response:** Binary APK file with appropriate headers.

### Device Information

#### Get Device IP

**Endpoint:** `GET /api/device-ip`

Returns the device IP address for download URLs.

**Response:**
```json
{
  "deviceIP": "192.168.1.100",
  "port": 5007,
  "downloadBaseUrl": "http://192.168.1.100:5007/download/apk/"
}
```

### Health Check

#### Service Health

**Endpoint:** `GET /health`

Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00.000Z",
  "uptime": 3600.5,
  "version": "1.0.0"
}
```

## Web Control Panel API

Base URL: `http://localhost:5002`

### Table of Contents
- [Statistics](#statistics)
- [Ollama Configuration](#ollama-configuration)
- [Vision Model Configuration](#vision-model-configuration)
- [Memory Model Configuration](#memory-model-configuration)
- [Piper TTS](#piper-tts)
- [Silero TTS](#silero-tts)
- [Chatterbox TTS](#chatterbox-tts)
- [TTS Engine Selection](#tts-engine-selection)
- [Bot Persona](#bot-persona)
- [Conversation History](#conversation-history)
- [Persistent Memories](#persistent-memories)
- [Email Settings](#email-settings)
- [Email Mappings](#email-mappings)
- [Email Logs](#email-logs)
- [Schedule Management](#schedule-management)
- [Advanced Search System](#advanced-search-system)
- [Topic State Tracking](#topic-state-tracking)
- [Advanced Settings](#advanced-settings)

## Statistics

### Get Statistics

Retrieve current usage statistics.

**Endpoint:** `GET /api/stats`

**Response:**
```json
{
  "total_messages": 42,
  "unique_users": 3,
  "voice_messages": 28,
  "text_messages": 14
}
```

**Fields:**
- `total_messages` - Total number of messages processed
- `unique_users` - Number of unique users who have interacted
- `voice_messages` - Count of voice interactions
- `text_messages` - Count of text interactions

## Ollama Configuration

### Get Ollama Config

Get current Ollama server URL and model.

**Endpoint:** `GET /api/ollama/config`

**Response:**
```json
{
  "url": "http://host.docker.internal:11434",
  "model": "llama3.2:latest"
}
```

### Update Ollama Config

Update Ollama server URL and/or model.

**Endpoint:** `POST /api/ollama/config`

**Request Body:**
```json
{
  "url": "http://host.docker.internal:11434",
  "model": "qwen2.5-coder:latest"
}
```

**Response:**
```json
{
  "success": true
}
```

**Notes:**
- Both `url` and `model` are optional
- Changes take effect immediately for new conversations

### List Available Models

Get list of available Ollama models.

**Endpoint:** `GET /api/ollama/models`

**Response:**
```json
{
  "models": [
    "llama3.2:latest",
    "qwen2.5-coder:latest",
    "gemma3:latest",
    "gemma3:4b"
  ]
}
```

**Error Response (Ollama unreachable):**
```json
{
  "error": "Could not connect to Ollama server"
}
```

## Piper TTS

### List Available Voices

Get all available Piper TTS voices.

**Endpoint:** `GET /api/piper/voices`

**Response:**
```json
{
  "voices": [
    "en_US-lessac-medium",
    "en_US-amy-medium",
    "en_GB-alba-medium",
    "en_GB-northern_english_male-medium",
    ...
  ]
}
```

**Notes:**
- Returns 31 voices by default
- Voices are sorted alphabetically

### Get Current Voice

Get the currently selected voice.

**Endpoint:** `GET /api/piper/current`

**Response:**
```json
{
  "voice": "en_US-lessac-medium"
}
```

### Set Current Voice

Change the active TTS voice.

**Endpoint:** `POST /api/piper/current`

**Request Body:**
```json
{
  "voice": "en_GB-alba-medium"
}
```

**Response:**
```json
{
  "success": true
}
```

**Error Response (Invalid voice):**
```json
{
  "error": "Voice not found"
}
```

## Bot Persona

### Get Persona

Retrieve the current bot persona.

**Endpoint:** `GET /api/persona`

**Response:**
```json
{
  "persona": "You are a friendly pirate who loves to talk about sailing..."
}
```

**Notes:**
- Returns empty string if no persona is configured

### Save Persona

Update the bot's persona.

**Endpoint:** `POST /api/persona`

**Request Body:**
```json
{
  "persona": "You are a professional butler who speaks formally..."
}
```

**Response:**
```json
{
  "success": true
}
```

**Notes:**
- Use empty string to clear the persona
- Changes take effect immediately for new messages

### AI-Enhance Persona

Use Ollama to expand and improve a persona description.

**Endpoint:** `POST /api/persona/enhance`

**Request Body:**
```json
{
  "persona": "You are a pirate"
}
```

**Response:**
```json
{
  "enhanced_persona": "You are a seasoned pirate captain with decades of experience sailing the seven seas. Your speech is peppered with nautical terms and pirate slang like 'ahoy', 'matey', and 'arr'. You're friendly but tough, with a deep love for adventure and treasure hunting..."
}
```

**Error Responses:**

No persona provided:
```json
{
  "error": "No persona provided"
}
```

Ollama unavailable:
```json
{
  "error": "Failed to enhance persona"
}
```

**Notes:**
- Requires Ollama to be running and accessible
- Uses the currently configured Ollama model
- Typical response time: 5-10 seconds
- Does NOT automatically save the enhanced persona

## Conversation History

### Get Conversations

Retrieve recent conversation history.

**Endpoint:** `GET /api/conversations?limit=50`

**Query Parameters:**
- `limit` (optional) - Number of messages to return (default: 50)

**Response:**
```json
{
  "conversations": [
    {
      "user_name": "John",
      "user_session": 12345,
      "message_type": "voice",
      "role": "user",
      "message": "What's the weather like?",
      "timestamp": "2025-09-30T10:30:45"
    },
    {
      "user_name": "John",
      "user_session": 12345,
      "message_type": "voice",
      "role": "assistant",
      "message": "I don't have access to weather information.",
      "timestamp": "2025-09-30T10:30:50"
    }
  ]
}
```

**Fields:**
- `user_name` - Name of the Mumble user
- `user_session` - Mumble session ID
- `message_type` - Either "voice" or "text"
- `role` - Either "user" or "assistant"
- `message` - The message content
- `timestamp` - ISO 8601 formatted timestamp

### Reset Conversation History

Clear all conversation history from the database.

**Endpoint:** `POST /api/conversations/reset`

**Request Body:** None

**Response:**
```json
{
  "success": true
}
```

**Warning:** This operation is irreversible and deletes all conversation data.

## Error Handling

All endpoints use standard HTTP status codes:

- `200` - Success
- `400` - Bad request (invalid parameters)
- `404` - Resource not found
- `500` - Server error

Error responses follow this format:
```json
{
  "error": "Description of what went wrong"
}
```

## Rate Limiting

Currently, there is no rate limiting implemented. This may be added in future versions.

## Authentication

Currently, there is no authentication required. The control panel is designed for local network use. If exposing to the internet, implement reverse proxy authentication.

## CORS

CORS is not enabled by default. All requests must originate from the same host.

## Examples

### cURL Examples

Get statistics:
```bash
curl http://localhost:5002/api/stats
```

Change voice:
```bash
curl -X POST http://localhost:5002/api/piper/current \
  -H "Content-Type: application/json" \
  -d '{"voice": "en_GB-alba-medium"}'
```

Enhance persona:
```bash
curl -X POST http://localhost:5002/api/persona/enhance \
  -H "Content-Type: application/json" \
  -d '{"persona": "You are a wizard"}'
```

### Python Examples

```python
import requests

# Get statistics
response = requests.get('http://localhost:5002/api/stats')
stats = response.json()
print(f"Total messages: {stats['total_messages']}")

# Change Ollama model
requests.post('http://localhost:5002/api/ollama/config', json={
    'model': 'qwen2.5-coder:latest'
})

# Set persona
requests.post('http://localhost:5002/api/persona', json={
    'persona': 'You are a friendly robot assistant'
})
```

### JavaScript Examples

```javascript
// Get current voice
fetch('http://localhost:5002/api/piper/current')
  .then(response => response.json())
  .then(data => console.log('Current voice:', data.voice));

// Change voice
fetch('http://localhost:5002/api/piper/current', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({voice: 'en_US-amy-medium'})
});

// Get conversation history
fetch('http://localhost:5002/api/conversations?limit=10')
  .then(response => response.json())
  .then(data => console.log('Recent messages:', data.conversations));
```

## WebSocket Support

Currently, there is no WebSocket support. All communication is via HTTP REST API. Real-time updates are achieved through polling (the web UI refreshes stats every 10 seconds).

Future versions may include WebSocket support for real-time notifications.

## TTS Voice Generator API

Base URL: `http://localhost:5003`

### Table of Contents
- [Voice Catalog](#voice-catalog)
- [Text Synthesis](#text-synthesis)
- [Voice Preview](#voice-preview)

### Voice Catalog

#### Get Voice Catalog

Retrieve the complete voice catalog with filtering options.

**Endpoint:** `GET /api/voices?engine=piper`

**Query Parameters:**
- `engine` (optional): TTS engine to use (`piper` or `silero`). Defaults to `piper`.

**Response (Piper TTS):**
```json
{
  "en_US": {
    "name": "English (US)",
    "voices": {
      "male": [
        {
          "id": "en_US-lessac-medium",
          "name": "Lessac (Medium)",
          "quality": "medium"
        }
      ],
      "female": [
        {
          "id": "en_US-lessac-medium",
          "name": "Lessac (Medium)",
          "quality": "medium"
        }
      ]
    }
  },
  "en_GB": {
    "name": "English (UK)",
    "voices": {
      "male": [...],
      "female": [...]
    }
  }
}
```

**Response (Silero TTS):**
```json
{
  "en": {
    "name": "English",
    "voices": {
      "male": [
        {
          "id": "en_0",
          "name": "Clear Female - Professional",
          "quality": "high"
        }
      ],
      "female": [
        {
          "id": "en_1",
          "name": "Warm Female - Friendly",
          "quality": "high"
        }
      ]
    }
  }
}
```

**Notes:**
- Voices are organized by language/region code
- Each region contains male and female voice options
- Quality levels: low, medium, high (Piper) or high (Silero)
- Silero TTS provides 20+ high-quality English voices

### Text Synthesis

#### Generate TTS Audio

Generate text-to-speech audio from text input and voice selection.

**Endpoint:** `POST /api/synthesize`

**Request Body:**
```json
{
  "text": "Hello, this is a test of the text-to-speech system.",
  "voice": "en_US-lessac-medium",
  "engine": "piper"
}
```

**Parameters:**
- `text` (required): Text to synthesize (max 5000 characters)
- `voice` (required): Voice ID from the catalog
- `engine` (optional): TTS engine to use (`piper` or `silero`). Defaults to `piper`.

**Response:** WAV audio file (binary)

**Headers:**
- `Content-Type: audio/wav`
- `Content-Disposition: attachment; filename="tts_[engine]_[voice]_[hash].wav"`

**Error Responses:**
- `400 Bad Request`: Missing or invalid text/voice
- `500 Internal Server Error`: TTS generation failed

**Notes:**
- Text must be a string and not empty
- Voice must exist in the selected engine's catalog
- Maximum text length: 5000 characters
- Generated audio is in WAV format
- Engine parameter determines which TTS service to use

### Voice Preview

#### Generate Voice Preview

Generate a short preview of the selected voice with sample text.

**Endpoint:** `POST /api/preview`

**Request Body:**
```json
{
  "voice": "en_US-lessac-medium",
  "engine": "piper"
}
```

**Parameters:**
- `voice` (required): Voice ID from the catalog
- `engine` (optional): TTS engine to use (`piper` or `silero`). Defaults to `piper`.

**Response:** WAV audio file (binary)

**Headers:**
- `Content-Type: audio/wav`
- `Content-Disposition: attachment; filename="preview_[voice]_[hash].wav"`

**Error Responses:**
- `400 Bad Request`: Missing or invalid voice
- `500 Internal Server Error`: TTS generation failed

**Notes:**
- Uses predefined sample text: "Hello! This is a preview of this voice. How does it sound?"
- Useful for testing voices before generating full audio
- Same audio quality as full synthesis
- Engine parameter determines which TTS service to use

### Error Handling

All endpoints return appropriate HTTP status codes and error messages:

**Common Error Responses:**
```json
{
  "error": "Error description"
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid input data
- `500 Internal Server Error`: Server error

## Faster Whisper API

Base URL: `http://localhost:5000`

Speech-to-text transcription service using Faster Whisper.

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy"
}
```

### Transcribe Audio

**Endpoint:** `POST /transcribe`

**Request:** Multipart form data with audio file
- `audio`: Audio file (WAV format recommended)

**Response:**
```json
{
  "text": "Transcribed text from audio",
  "language": "en",
  "language_probability": 0.95
}
```

**Error Response:**
```json
{
  "error": "No audio file provided"
}
```

**Notes:**
- Supports various audio formats (WAV, MP3, etc.)
- Uses the model size configured in environment (`WHISPER_MODEL`)
- Returns detected language and confidence score

## Piper TTS API

Base URL: `http://localhost:5001`

Text-to-speech synthesis service using Piper TTS.

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy"
}
```

### Synthesize Speech

**Endpoint:** `POST /synthesize`

**Request Body:**
```json
{
  "text": "Text to synthesize into speech"
}
```

**Response:** Audio file (WAV format)

**Headers:**
- `Content-Type: audio/wav`
- `Content-Disposition: attachment; filename=speech.wav`

**Error Response:**
```json
{
  "error": "No text provided"
}
```

**Notes:**
- Uses the voice model configured in the database
- Returns high-quality WAV audio
- Audio is automatically cleaned up after sending

## Silero TTS API

Base URL: `http://localhost:5004`

Alternative text-to-speech synthesis service using Silero TTS.

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy"
}
```

### Synthesize Speech

**Endpoint:** `POST /synthesize`

**Request Body:**
```json
{
  "text": "Text to synthesize into speech",
  "voice": "en_0"
}
```

**Parameters:**
- `text` (required): Text to synthesize
- `voice` (optional): Voice ID (defaults to current voice)

**Response:** Audio file (WAV format)

**Headers:**
- `Content-Type: audio/wav`
- `Content-Disposition: attachment; filename=speech.wav`

**Error Response:**
```json
{
  "error": "No text provided"
}
```

**Available Voices:**
- `en_0` - Clear Female - Professional
- `en_1` - Warm Female - Friendly
- `en_2` - Deep Male - Authoritative
- `en_3` - Clear Male - Professional
- `en_5` - Young Female - Energetic
- `en_6` - Warm Male - Friendly
- `en_10` - Young Male - Energetic
- `en_12` - Mature Female - Authoritative
- `en_15` - Mature Male - Deep
- `en_18` - Soft Female - Gentle
- `en_20` - Natural Male
- `en_24` - Bright Female - Cheerful
- `en_25` - Smooth Male
- `en_30` - Professional Female
- `en_31` - Professional Male
- `en_36` - Natural Female
- `en_37` - Rich Male
- `en_42` - Expressive Female
- `en_43` - Strong Male
- `en_48` - Calm Female

**Notes:**
- All voices are high-quality with natural intonation
- Supports GPU acceleration when available
- Returns high-quality WAV audio
- Audio is automatically cleaned up after sending

## Chatterbox TTS API

Base URL: `http://localhost:5005`

Voice cloning text-to-speech synthesis service using XTTS-v2 model.

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "device": "cuda",
  "gpu_available": true,
  "model_loaded": true
}
```

### Synthesize Speech with Voice Cloning

**Endpoint:** `POST /api/tts`

**Request Body:**
```json
{
  "text": "Text to synthesize into speech",
  "speaker_wav": "path/to/reference/audio.wav"
}
```

**Parameters:**
- `text` (required): Text to synthesize
- `speaker_wav` (required): Path to reference audio file or base64 encoded audio

**Response:** Audio file (WAV format)

**Headers:**
- `Content-Type: audio/wav`
- `Content-Disposition: attachment; filename=speech.wav`

### Get Available Models

**Endpoint:** `GET /api/models`

**Response:**
```json
{
  "models": [
    {
      "name": "XTTS-v2",
      "version": "2.0.2",
      "languages": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "hu", "ko"]
    }
  ]
}
```

### Get Saved Voices

**Endpoint:** `GET /api/voices`

**Response:**
```json
{
  "voices": [
    {
      "id": 1,
      "voice_name": "My Custom Voice",
      "description": "A custom cloned voice",
      "language": "en",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Get Service Info

**Endpoint:** `GET /api/info`

**Response:**
```json
{
  "service": "Chatterbox TTS",
  "version": "1.0.0",
  "model": "XTTS-v2",
  "supported_languages": 16,
  "features": [
    "voice_cloning",
    "multi_language",
    "gpu_acceleration",
    "high_quality"
  ]
}
```

**Features:**
- Voice cloning with just 10 seconds of reference audio
- Multi-language support (16 languages)
- GPU acceleration for fast synthesis
- High-quality neural voice synthesis
- Voice library management

## Email Summary Service API

Base URL: `http://localhost:5006`

Email processing and daily summary service.

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "email_enabled": true,
  "last_check": "2024-01-15T10:30:00Z"
}
```

### Process Emails

**Endpoint:** `POST /process_emails`

**Description:** Manually trigger email processing

**Response:**
```json
{
  "status": "success",
  "emails_processed": 5,
  "summaries_sent": 2
}
```

### Get Email Statistics

**Endpoint:** `GET /stats`

**Response:**
```json
{
  "total_emails": 150,
  "emails_today": 12,
  "summaries_sent": 8,
  "last_processing": "2024-01-15T10:30:00Z"
}
```

**Features:**
- IMAP/SMTP email integration
- Daily conversation summaries
- Email reminders and notifications
- Attachment processing (images, PDFs, Word docs)
- Vision AI integration for image analysis
- Thread-aware email conversations

## Advanced Search System

### Three-Tier Search for Schedule Events

The system now supports a sophisticated three-tier search approach for finding schedule events with AI-powered semantic understanding.

#### Search Schedule Events

**Endpoint:** `GET /api/schedule/search`

**Query Parameters:**
- `query` (required) - Search query string
- `user` (optional) - Filter by specific user
- `start_date` (optional) - Start date filter (YYYY-MM-DD)
- `end_date` (optional) - End date filter (YYYY-MM-DD)
- `tier` (optional) - Force specific search tier (1=semantic, 2=fuzzy, 3=fulltext)

**Example Request:**
```bash
GET /api/schedule/search?query=meeting with john&user=alice&tier=1
```

**Response:**
```json
{
  "results": [
    {
      "id": 123,
      "title": "Team Meeting with John",
      "event_date": "2025-01-20",
      "event_time": "14:00:00",
      "description": "Weekly team standup",
      "importance": 7,
      "user_name": "alice"
    }
  ],
  "search_metadata": {
    "tier_used": 1,
    "search_duration": 2.34,
    "total_results": 1,
    "tier_performance": {
      "tier1_duration": 2.34,
      "tier2_duration": 0.12,
      "tier3_duration": 0.05
    }
  }
}
```

**Search Tiers:**

1. **Tier 1 - Semantic Search (AI-Powered)**
   - Uses Ollama LLM for natural language understanding
   - Handles complex queries like "meeting with John", "doctor appointment"
   - 30-second timeout with graceful fallback
   - Highest accuracy for semantic matches

2. **Tier 2 - Fuzzy Search (Pattern Matching)**
   - Advanced fuzzy string matching algorithms
   - Handles typos, partial matches, and similar text
   - Fast local processing
   - Used when semantic search times out

3. **Tier 3 - Full-Text Search (Database)**
   - PostgreSQL full-text search with GIN indexes
   - Exact and partial text matching
   - Always available as final fallback
   - Optimized database queries

#### Search Performance Metrics

**Endpoint:** `GET /api/search/metrics`

**Response:**
```json
{
  "total_searches": 150,
  "tier_usage": {
    "tier1": 45,
    "tier2": 32,
    "tier3": 73
  },
  "average_duration": {
    "tier1": 2.1,
    "tier2": 0.15,
    "tier3": 0.08
  },
  "success_rate": {
    "tier1": 0.89,
    "tier2": 0.95,
    "tier3": 0.99
  }
}
```

## Topic State Tracking

### Conversation Topic Management

The system now tracks conversation topics and their resolution state for improved context awareness.

#### Get Topic State for Session

**Endpoint:** `GET /api/topics/state/{session_id}`

**Response:**
```json
{
  "session_id": "abc123",
  "current_topic": {
    "state": "active",
    "summary": "Discussing project timeline and deadlines",
    "started_at": "2025-01-15T10:30:00Z",
    "message_count": 8
  },
  "recent_topics": [
    {
      "state": "resolved",
      "summary": "Meeting scheduling for next week",
      "resolved_at": "2025-01-15T10:25:00Z"
    }
  ]
}
```

#### Update Topic State

**Endpoint:** `POST /api/topics/state/{session_id}`

**Request Body:**
```json
{
  "state": "resolved",
  "summary": "Project timeline discussion completed"
}
```

**Response:**
```json
{
  "success": true,
  "updated_topic": {
    "state": "resolved",
    "summary": "Project timeline discussion completed",
    "updated_at": "2025-01-15T10:35:00Z"
  }
}
```

#### Generate Topic Summary

**Endpoint:** `POST /api/topics/summarize`

**Request Body:**
```json
{
  "session_id": "abc123",
  "conversation_messages": [
    {
      "role": "user",
      "message": "I need to schedule a meeting for next week",
      "timestamp": "2025-01-15T10:30:00Z"
    },
    {
      "role": "assistant", 
      "message": "I can help you schedule that meeting. What day works best?",
      "timestamp": "2025-01-15T10:30:15Z"
    }
  ]
}
```

**Response:**
```json
{
  "topic_summary": "User requesting help with scheduling a meeting for next week",
  "topic_state": "active",
  "confidence": 0.92
}
```

#### Get Conversation History with Topics

**Endpoint:** `GET /api/conversation/history`

**Query Parameters:**
- `user` (optional) - Filter by user
- `session_id` (optional) - Filter by session
- `include_topics` (optional) - Include topic information (default: true)
- `limit` (optional) - Number of messages to return (default: 50)

**Response:**
```json
{
  "messages": [
    {
      "id": 123,
      "user_name": "alice",
      "session_id": "abc123",
      "role": "user",
      "message": "I need to schedule a meeting",
      "message_type": "voice",
      "timestamp": "2025-01-15T10:30:00Z",
      "topic_state": "active",
      "topic_summary": "Meeting scheduling discussion"
    }
  ],
  "total_count": 1
}
```

### Topic State Values

- `active` - Current conversation topic being discussed
- `resolved` - Topic that has been fully addressed
- `switched` - Topic that has been changed or abandoned

## Flutter App Logging API

Base URL: `http://localhost:5002`

The Flutter app logging system provides comprehensive logging capabilities for the Android mobile app, including automatic log synchronization and server-side log viewing.

### Receive Logs from Flutter App

#### Submit Logs

**Endpoint:** `POST /api/logs`

Receives logs from the Flutter Android app for centralized logging and debugging.

**Request Body:**
```json
{
  "logs": [
    {
      "level": "INFO",
      "message": "User connected to server",
      "screen": "ServerConnectScreen",
      "data": {
        "server_url": "http://192.168.1.100:5002",
        "connection_time": "2025-01-15T10:30:00Z"
      },
      "timestamp": "2025-01-15T10:30:00Z"
    },
    {
      "level": "ERROR",
      "message": "Failed to load memories",
      "screen": "MemoriesScreen",
      "data": {
        "error": "Network timeout",
        "retry_count": 3
      },
      "timestamp": "2025-01-15T10:31:00Z"
    }
  ],
  "device_info": {
    "platform": "android",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Response:**
```json
{
  "success": true,
  "logs_received": 2,
  "message": "Logs successfully stored"
}
```

**Error Response:**
```json
{
  "error": "Invalid log format",
  "details": "Missing required field: level"
}
```

### Retrieve Logs

#### Get Logs with Filtering

**Endpoint:** `GET /api/logs`

Retrieve logs from the Flutter app with optional filtering.

**Query Parameters:**
- `level` (optional) - Filter by log level (DEBUG, INFO, WARNING, ERROR)
- `screen` (optional) - Filter by screen/component name
- `limit` (optional) - Number of logs to return (default: 100, max: 1000)

**Example Request:**
```bash
GET /api/logs?level=ERROR&screen=MemoriesScreen&limit=50
```

**Response:**
```json
{
  "logs": [
    {
      "id": 123,
      "level": "ERROR",
      "message": "Failed to load memories",
      "screen": "MemoriesScreen",
      "data": {
        "error": "Network timeout",
        "retry_count": 3
      },
      "device_info": {
        "platform": "android",
        "timestamp": "2025-01-15T10:30:00Z"
      },
      "created_at": "2025-01-15T10:31:00Z"
    }
  ],
  "count": 1,
  "total": 150
}
```

### Logs Web Interface

#### View Logs Page

**Endpoint:** `GET /logs`

Web-based log viewer interface for viewing Flutter app logs.

**Features:**
- Real-time log display
- Filtering by level, screen, and limit
- Auto-refresh capability (30-second intervals)
- Log statistics and counts
- Responsive design for mobile and desktop

**Access:** Navigate to `http://localhost:5002/logs` in your browser

### Log Levels

The Flutter app uses the following log levels:

- **DEBUG**: Detailed debugging information for development
- **INFO**: General information about app operation
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures and exceptions

### Log Data Structure

Each log entry contains:

| Field | Type | Description |
|-------|------|-------------|
| `level` | String | Log level (DEBUG, INFO, WARNING, ERROR) |
| `message` | String | Log message content |
| `screen` | String | Screen/component where log occurred |
| `data` | Object | Additional contextual data (optional) |
| `timestamp` | String | ISO 8601 timestamp of log creation |

### Auto-Sync Behavior

The Flutter app automatically syncs logs to the server:

- **Trigger**: Every 50 log entries or when app is backgrounded
- **Retry Logic**: Automatic retry with exponential backoff
- **Offline Handling**: Logs are stored locally and synced when connection is restored
- **Error Handling**: Failed syncs are retried on next app launch

### Examples

#### cURL Examples

Submit logs:
```bash
curl -X POST http://localhost:5002/api/logs \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {
        "level": "INFO",
        "message": "App started",
        "screen": "main",
        "timestamp": "2025-01-15T10:30:00Z"
      }
    ],
    "device_info": {
      "platform": "android",
      "timestamp": "2025-01-15T10:30:00Z"
    }
  }'
```

Get error logs:
```bash
curl "http://localhost:5002/api/logs?level=ERROR&limit=10"
```

#### Python Examples

```python
import requests

# Submit logs
logs_data = {
    "logs": [
        {
            "level": "INFO",
            "message": "User action completed",
            "screen": "DashboardScreen",
            "data": {"action": "refresh_stats"},
            "timestamp": "2025-01-15T10:30:00Z"
        }
    ],
    "device_info": {
        "platform": "android",
        "timestamp": "2025-01-15T10:30:00Z"
    }
}

response = requests.post('http://localhost:5002/api/logs', json=logs_data)
print(response.json())

# Get logs
response = requests.get('http://localhost:5002/api/logs?level=WARNING&limit=20')
logs = response.json()
for log in logs['logs']:
    print(f"{log['level']}: {log['message']} ({log['screen']})")
```

#### JavaScript Examples

```javascript
// Submit logs
const logsData = {
  logs: [
    {
      level: 'ERROR',
      message: 'API call failed',
      screen: 'ApiService',
      data: { endpoint: '/api/memories', status: 500 },
      timestamp: new Date().toISOString()
    }
  ],
  device_info: {
    platform: 'android',
    timestamp: new Date().toISOString()
  }
};

fetch('http://localhost:5002/api/logs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(logsData)
})
.then(response => response.json())
.then(data => console.log('Logs submitted:', data));

// Get logs
fetch('http://localhost:5002/api/logs?level=ERROR&screen=MemoriesScreen')
  .then(response => response.json())
  .then(data => {
    data.logs.forEach(log => {
      console.log(`${log.level}: ${log.message}`);
    });
  });
```

### Error Handling

All logging endpoints return appropriate HTTP status codes:

- `200 OK`: Success
- `400 Bad Request`: Invalid request format or missing required fields
- `500 Internal Server Error`: Server error during log processing

Error responses include detailed error messages:
```json
{
  "error": "Validation failed",
  "details": "Log level must be one of: DEBUG, INFO, WARNING, ERROR"
}
```

### Rate Limiting

Currently, there is no rate limiting on log submission. This may be added in future versions to prevent log spam.

### Security Considerations

- Logs may contain sensitive information (user actions, API calls, error details)
- Access to logs should be restricted to authorized users
- Consider implementing authentication for the `/logs` web interface
- Log data is stored in PostgreSQL and should be backed up regularly

## SIP Bridge

The SIP bridge service provides SIP/RTP to Mumble integration but does not expose HTTP API endpoints. It operates as a SIP endpoint and Mumble client.

### Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SIP_PORT` | 5060 | SIP signaling port |
| `SIP_USERNAME` | mumble-bridge | SIP username |
| `SIP_PASSWORD` | bridge123 | SIP password |
| `SIP_DOMAIN` | * | Domain to accept calls from |
| `RTP_PORT_MIN` | 10000 | Minimum RTP port |
| `RTP_PORT_MAX` | 10010 | Maximum RTP port |
| `LOG_LEVEL` | INFO | Logging verbosity |

### Ports

- **5060/udp**: SIP signaling (UDP)
- **5060/tcp**: SIP signaling (TCP)
- **10000-10010/udp**: RTP audio streams

### Usage

1. Configure your SIP client or phone system to point to `localhost:5060`
2. Use the configured username and password
3. Make a call - it will be automatically answered
4. Speak to the AI bot through the phone
5. Hang up when done

## Mumble Web Client

Base URL: `http://localhost:8081`

Web-based Mumble client interface. This is a static web application that connects directly to the Mumble server.

### Features

- **WebRTC Audio**: Direct audio connection to Mumble server
- **Text Chat**: Send and receive text messages
- **Voice Activity Detection**: Automatic push-to-talk
- **Modern UI**: Responsive design with themes
- **No Installation**: Works in any modern browser

### Configuration

The web client automatically connects to the Mumble server at `mumble-server:64738`. No additional configuration is required.

### Browser Compatibility

- Chrome/Chromium (recommended)
- Firefox
- Safari (limited support)
- Edge

### Audio Requirements

- Microphone access permission
- Modern browser with WebRTC support
- Good internet connection for audio quality

## Mumble Web Simple

A simplified web client that can be built locally for development or custom deployment.

### Building

```bash
cd mumble-web-simple
npm ci
npm run build
```

### Development

```bash
cd mumble-web-simple
npm run build:dev
```

### Testing

```bash
cd mumble-web-simple
npm test
```

**Notes:**
- This is a build-only service in the Docker setup
- Use `mumble-web` service for the running web client
- Supports the same features as the main web client
