# Architecture

System design and component interaction documentation.

## Overview

Mumble AI Bot is a microservices-based voice AI system built on Docker. It consists of 15 primary services that work together to provide voice and text interaction through multiple access methods including Mumble VoIP, web clients, SIP phone integration, email communication, transcription services, and mobile app access.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            User Access Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │Mumble Client │  │ Web Clients  │  │ SIP Phones   │  │ Web Browser     │ │
│  │(Desktop/Mobile│  │(Port 8081)   │  │(Port 5060)  │  │(Control Panel)  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │Android App   │  │ Landing Page │  │ Email Client │  │ Whisper Web UI  │ │
│  │(Flutter Beta)│  │(Port 5007)   │  │(IMAP/SMTP)   │  │(Port 5008)      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘ │
└─────────┼──────────────────┼──────────────────┼───────────────────┼─────────┘
          │                  │                  │                   │
┌─────────▼──────────────────▼──────────────────▼───────────────────▼─────────┐
│                        Application Layer                                      │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  Mumble Server   │  │ SIP Bridge   │  │ Web Control  │  │ Mumble Web  │  │
│  │   (Port 48000)   │  │(Port 5060)   │  │   Panel      │  │  Client     │  │
│  └─────────┬────────┘  └──────┬───────┘  │(Port 5002)   │  │(Port 8081)  │  │
│            │                  │          └──────────────┘  └─────────────┘  │
│       ┌────▼──────┐           │          ┌──────────────┐  ┌─────────────┐  │
│       │  AI Bot   │           │          │ Landing Page │  │ TTS Voice   │  │
│       └─┬───┬───┬─┘           │          │(Port 5007)   │  │ Generator   │  │
│         │   │   │             │          ├──────────────┤  │(Port 5003)  │  │
│         │   │   │             │          │ Whisper Web  │  └─────────────┘  │
│         │   │   │             │          │ Interface    │                    │
│         │   │   │             │          │(Port 5008)   │                    │
└─────────┼───┼───┼─────────────┼──────────└──────────────┘──────────────────┘  │
          │   │   │             │
┌─────────▼───▼───▼─────────────▼────────────────────────────────────────────┐
│                            Service Layer                                    │
│  ┌──────────┐  ┌────────┐  ┌─────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ Faster   │  │ Piper  │  │ Ollama  │  │  PostgreSQL  │  │ Mumble Web  │  │
│  │ Whisper  │  │  TTS   │  │(External│  │              │  │   Simple    │  │
│  │(Port5000)│  │(5001)  │  │ :11434) │  │  (Internal)  │  │(Build Only) │  │
│  └──────────┘  └────────┘  └─────────┘  └──────────────┘  └─────────────┘  │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────┐ │
│  │ Silero   │  │ Chatterbox   │  │ Email Summary│  │ TTS Voice   │  │Email│ │
│  │  TTS     │  │     TTS      │  │   Service    │  │ Generator   │  │System│ │
│  │(Port5004)│  │ (Port 5005)  │  │ (Port 5006)  │  │(Port 5003)  │  │     │ │
│  └──────────┘  └──────────────┘  └──────────────┘  └─────────────┘  └─────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Voice Message Flow (Mumble Client)

1. User speaks in Mumble client
2. Mumble Server transmits audio to AI Bot
3. AI Bot buffers audio until 1.5s silence
4. Audio (PCM) sent to Faster Whisper service
5. Whisper returns transcribed text
6. Bot saves user message to PostgreSQL
7. Bot retrieves conversation history from database
8. Bot gets persona configuration from database
9. Bot builds context-aware prompt
10. Prompt sent to Ollama
11. Ollama returns generated response
12. Bot saves assistant response to database
13. Response text sent to Piper TTS
14. Piper returns synthesized audio (WAV)
15. Bot resamples audio to 48kHz
16. Audio sent back through Mumble Server
17. User hears AI response

### Voice Message Flow (Web Client)

1. User speaks in web browser
2. WebRTC audio sent to Mumble Server
3. Mumble Server transmits audio to AI Bot
4. Steps 3-16 same as Mumble client flow
5. Audio sent back through Mumble Server to web client
6. User hears AI response in browser

### Voice Message Flow (SIP Phone)

1. User calls SIP bridge from phone
2. SIP bridge auto-answers call
3. **Welcome message generated using bot persona and Ollama**
4. **Welcome message converted to speech via TTS (Piper or Silero)**
5. **Welcome message played to caller over RTP**
6. SIP bridge connects to Mumble Server as client
7. Phone audio (RTP) converted to Mumble audio format
8. Audio sent to Mumble Server → AI Bot
9. Steps 4-15 same as Mumble client flow
10. Audio sent back through Mumble Server → SIP bridge
11. SIP bridge converts audio back to RTP format
12. User hears AI response on phone

### Text Message Flow

1. User types message in Mumble chat (any client)
2. Message sent to AI Bot via Mumble Server
3. Steps 6-12 same as voice flow
4. Bot sends text response to Mumble Server
5. User receives text message

### Web Control Panel Flow

1. User accesses control panel in browser
2. Frontend requests data via REST API
3. Backend queries PostgreSQL for current config
4. Config displayed in UI
5. User makes changes
6. Frontend POSTs to API
7. Backend updates database
8. Bot picks up changes on next message

### Flutter App Flow

1. User launches Flutter app on Android device
2. App connects to Mumble AI server via HTTP API
3. User selection screen allows multi-user management
4. App requests data from all available endpoints
5. Real-time data synchronization with server
6. Comprehensive logging system captures all actions
7. Logs auto-sync to server every 50 entries
8. Server-side log viewer available at `/logs` endpoint

### Whisper Web Interface Flow

1. User accesses Whisper Web Interface in browser (`http://localhost:5008`)
2. User uploads audio or video file (drag-and-drop or file selector)
3. Frontend sends file to `/api/upload` endpoint
4. Backend validates file (format, size) and saves to temporary location
5. Frontend initiates transcription via `/api/transcribe` endpoint
6. Backend extracts audio from video files (if needed) using pydub/FFmpeg
7. Audio sent to Faster Whisper service for speech-to-text conversion
8. Backend performs advanced speaker diarization:
   - Extracts voice embeddings using Resemblyzer (256-dim vectors)
   - Performs Agglomerative Clustering with Ward linkage
   - Tests 2-8 speaker configurations, selects optimal using silhouette score
   - Matches detected speakers to stored voice profiles (75% similarity threshold)
   - Returns speaker-labeled segments with match confidence scores
9. Backend generates AI title using Ollama (first 2000 chars of transcription)
10. Transcription, segments, speaker matches, and title saved to PostgreSQL
11. Frontend redirects to individual transcription detail page (`/transcription/:id`)
12. User can name unknown speakers via Speaker Manager component
13. Naming speakers creates/updates voice profiles in database
14. Future transcriptions automatically recognize named speakers
15. User can generate AI summary via Summary Panel (using Ollama)
16. User can browse history, search transcriptions, and navigate with pagination

## Services

### 1. Mumble Server

- **Image:** `mumblevoip/mumble-server:latest`
- **Purpose:** VoIP communication hub
- **Ports:** 64738 (TCP/UDP)
- **Dependencies:** None
- **Data:** Persistent volume for server state

### 2. AI Bot

- **Image:** Custom (Python 3.11)
- **Purpose:** Core orchestration and Mumble client
- **Dependencies:** Whisper, Piper, PostgreSQL, Ollama
- **Features:**
  - Audio buffering and silence detection
  - Dual-mode communication (voice/text)
  - Context-aware conversation
  - Database interaction

### 3. Faster Whisper

- **Image:** Custom (Python 3.11)
- **Purpose:** Speech-to-text transcription
- **Port:** 5000
- **Model:** Configurable (tiny/base/small/medium/large)
- **API:** POST /transcribe, GET /health

### 4. Piper TTS

- **Image:** Custom (Python 3.11)
- **Purpose:** Text-to-speech synthesis
- **Port:** 5001
- **Voices:** 31 pre-loaded models
- **API:** POST /synthesize, GET /health

### 5. Silero TTS

- **Image:** Custom (Python 3.11)
- **Purpose:** Alternative text-to-speech synthesis
- **Port:** 5004
- **Voices:** 20+ high-quality English voices
- **API:** POST /synthesize, GET /health
- **Features:** GPU acceleration support, natural intonation

### 6. PostgreSQL

- **Image:** postgres:16-alpine
- **Purpose:** Persistent data storage
- **Port:** 5432 (internal only)
- **Data:**
  - Conversation history
  - Bot configuration
  - User statistics

### 7. Web Control Panel

- **Image:** Custom (Python 3.11 + Flask)
- **Purpose:** Management interface
- **Port:** 5002
- **Features:**
  - Real-time statistics
  - Model/voice selection
  - Persona management
  - History viewing
  - Flutter app log viewer (`/logs`)
  - Multi-user support

### 8. SIP Bridge

- **Image:** Custom (Python 3.11)
- **Purpose:** SIP/RTP to Mumble integration
- **Ports:** 5060 (UDP/TCP), 10000-10010 (UDP)
- **Dependencies:** Mumble Server, Whisper, Piper, Silero, PostgreSQL, Ollama
- **Features:**
  - Auto-answer SIP calls
  - **Personalized welcome messages using bot persona and Ollama**
  - RTP audio conversion
  - Mumble client connection
  - AI pipeline integration

### 9. TTS Voice Generator

- **Image:** Custom (Python 3.11 + Flask)
- **Purpose:** Standalone TTS voice generation and cloning web interface
- **Port:** 5003
- **Dependencies:** Piper TTS, Silero TTS, Chatterbox TTS, PostgreSQL
- **Features:**
  - Triple TTS engine support (Piper, Silero, and Chatterbox)
  - Voice cloning with XTTS-v2
  - Modern responsive web interface
  - Voice preview and filtering
  - Voice library management
  - Audio file download
  - Independent operation

### 10. Mumble Web

- **Image:** `rankenstein/mumble-web:latest`
- **Purpose:** Web-based Mumble client
- **Port:** 8081
- **Features:**
  - WebRTC audio connection
  - Text chat interface
  - Voice activity detection
  - Modern responsive UI

### 11. Chatterbox TTS

- **Image:** Custom (Python 3.11)
- **Purpose:** Voice cloning text-to-speech synthesis
- **Port:** 5005
- **Model:** XTTS-v2
- **API:** POST /api/tts, GET /health, GET /api/voices
- **Features:**
  - Voice cloning with 10 seconds of reference audio
  - Multi-language support (16 languages)
  - GPU acceleration support
  - High-quality neural voice synthesis
  - Voice library management

### 12. Email Summary Service

- **Image:** Custom (Python 3.11)
- **Purpose:** Email processing and daily summaries
- **Port:** 5006
- **Dependencies:** PostgreSQL, Ollama
- **Features:**
  - IMAP/SMTP email integration
  - Daily conversation summaries
  - Email reminders and notifications
  - Attachment processing (images, PDFs, Word docs)
  - Vision AI integration for image analysis
  - Thread-aware email conversations

### 13. Mumble Web Simple

- **Image:** Custom (Node.js build)
- **Purpose:** Simplified web client (build only)
- **Port:** N/A (build service)
- **Features:**
  - Lightweight web client
  - Customizable themes
  - Development-friendly

### 14. Whisper Web Interface

- **Image:** Custom (Python 3.11 + Node.js multi-stage build)
- **Purpose:** Advanced audio/video transcription with persistent speaker recognition
- **Port:** 5008
- **Dependencies:** PostgreSQL, Faster Whisper, Ollama
- **Technology Stack:**
  - **Backend:** Flask, Resemblyzer, scikit-learn, pydub, librosa 0.9.2
  - **Frontend:** React 18, React Router v6, Vite, Tailwind CSS, Axios
- **Features:**
  - **Advanced Speaker Diarization:** Aggressive multi-speaker detection using Resemblyzer voice embeddings
  - **Persistent Speaker Profiles:** Cross-session speaker recognition with 75% similarity threshold
  - **AI-Generated Titles:** Automatic intelligent title generation using Ollama
  - **Modern React UI:** Single-page application with React Router navigation
  - **Card-Based History:** Beautiful 3-column grid with pagination (10 items/page)
  - **Individual Transcription Pages:** Dedicated detail pages for each transcription
  - **Speaker Management UI:** Name speakers, view confidence scores, manage profiles
  - **AI Summarization:** Ollama-powered summaries with model selection
  - **Multi-Format Support:** Audio (.mp3, .wav, .ogg, .flac, .aac, .m4a) and video (.mp4, .webm, .avi, .mov, .mkv)
  - **Full-Text Search:** Search across titles, filenames, and content
  - **Voice Profile Database:** 256-dimensional embeddings stored in PostgreSQL
  - **Weighted Profile Updates:** Profiles improve with each new sample
- **API Endpoints:**
  - `/api/upload` - File upload and validation
  - `/api/transcribe` - Transcription with speaker detection
  - `/api/transcriptions` - List with pagination and search
  - `/api/transcriptions/<id>` - Get single transcription
  - `/api/speakers` - Speaker profile management
  - `/api/summarize` - AI summary generation
  - `/health` - Health check

## Database Schema

### conversation_history

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| user_name | VARCHAR(255) | Mumble username |
| user_session | INTEGER | Session ID |
| message_type | VARCHAR(10) | 'voice' or 'text' |
| role | VARCHAR(20) | 'user' or 'assistant' |
| message | TEXT | Message content |
| timestamp | TIMESTAMP | When message occurred |

### bot_config

| Column | Type | Description |
|--------|------|-------------|
| key | VARCHAR(255) | Config key (PK) |
| value | TEXT | Config value |
| updated_at | TIMESTAMP | Last update |

**Config Keys:**
- `ollama_url` - Ollama server URL
- `ollama_model` - Active model name
- `piper_voice` - Active TTS voice
- `silero_voice` - Active Silero TTS voice
- `chatterbox_voice` - Active Chatterbox TTS voice
- `tts_engine` - Selected TTS engine (piper/silero/chatterbox)
- `bot_persona` - Personality description
- `whisper_language` - Whisper language setting
- `vision_model` - Vision AI model for email attachments
- `memory_model` - Model for memory extraction

### persistent_memories

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| user_name | VARCHAR(255) | User who created the memory |
| memory_text | TEXT | Memory content |
| category | VARCHAR(50) | Memory category |
| importance | INTEGER | Importance level (1-10) |
| event_date | DATE | Optional event date |
| event_time | TIME | Optional event time |
| created_at | TIMESTAMP | When memory was created |
| embedding | VECTOR(1536) | Semantic embedding for search |

### email_settings

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| smtp_server | VARCHAR(255) | SMTP server address |
| smtp_port | INTEGER | SMTP port |
| imap_server | VARCHAR(255) | IMAP server address |
| imap_port | INTEGER | IMAP port |
| username | VARCHAR(255) | Email username |
| password | VARCHAR(255) | Email password (encrypted) |
| enabled | BOOLEAN | Whether email is enabled |
| daily_summary_time | TIME | Time for daily summaries |
| created_at | TIMESTAMP | When settings were created |

### email_logs

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| email_id | VARCHAR(255) | Email message ID |
| direction | VARCHAR(10) | 'incoming' or 'outgoing' |
| from_email | VARCHAR(255) | Sender email |
| to_email | VARCHAR(255) | Recipient email |
| subject | TEXT | Email subject |
| content | TEXT | Email content |
| status | VARCHAR(20) | Processing status |
| error_message | TEXT | Error details if failed |
| created_at | TIMESTAMP | When email was processed |

### chatterbox_voices

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| voice_name | VARCHAR(255) | Voice name |
| description | TEXT | Voice description |
| reference_audio_path | VARCHAR(500) | Path to reference audio |
| language | VARCHAR(10) | Voice language |
| created_at | TIMESTAMP | When voice was created |
| is_deleted | BOOLEAN | Soft delete flag |

### flutter_logs

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| level | VARCHAR(10) | Log level (DEBUG, INFO, WARNING, ERROR) |
| message | TEXT | Log message content |
| screen | VARCHAR(100) | Screen/component where log occurred |
| data | JSONB | Additional log data (optional) |
| device_info | JSONB | Device information (platform, timestamp) |
| created_at | TIMESTAMP | When log was created |

### transcriptions

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| filename | VARCHAR(255) | Original filename |
| title | VARCHAR(500) | AI-generated title |
| original_format | VARCHAR(10) | File format (mp3, wav, etc.) |
| file_size_bytes | BIGINT | File size in bytes |
| duration_seconds | FLOAT | Audio duration |
| transcription_text | TEXT | Full transcription text |
| transcription_segments | JSONB | Array of {start, end, text, speaker} objects |
| transcription_formatted | TEXT | Human-readable text with speakers |
| summary_text | TEXT | AI-generated summary |
| summary_model | VARCHAR(50) | Ollama model used for summary |
| language | VARCHAR(10) | Detected language code |
| language_probability | FLOAT | Language detection confidence |
| processing_time_seconds | FLOAT | Total processing time |
| created_at | TIMESTAMP | When transcription was created |
| updated_at | TIMESTAMP | Last update time |

**Indexes:**
- `idx_transcriptions_created_at` - Optimizes history page ordering
- `idx_transcriptions_language` - Optimizes language filtering
- `idx_transcriptions_title` - Optimizes search performance

### speaker_profiles

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| speaker_name | VARCHAR(255) | Speaker name (unique) |
| voice_embedding | FLOAT8[] | 256-dimensional Resemblyzer voice fingerprint |
| sample_count | INTEGER | Number of voice samples collected |
| first_seen | TIMESTAMP | When speaker was first detected |
| last_seen | TIMESTAMP | When speaker was last detected |
| total_duration_seconds | FLOAT | Total speaking time across all transcriptions |
| description | TEXT | Optional speaker description |
| tags | TEXT[] | Array of tags for categorization |
| confidence_score | FLOAT | Overall profile confidence (1.0 = highest) |
| is_active | BOOLEAN | Whether profile is active (soft delete) |
| created_at | TIMESTAMP | When profile was created |
| updated_at | TIMESTAMP | Last update time |
| metadata | JSONB | Additional metadata |

**Indexes:**
- `idx_speaker_profiles_name` - Optimizes name lookups
- `idx_speaker_profiles_active` - Optimizes active profile queries

### speaker_transcription_mapping

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| transcription_id | INTEGER | Foreign key to transcriptions table |
| speaker_profile_id | INTEGER | Foreign key to speaker_profiles table (nullable) |
| detected_speaker_label | VARCHAR(100) | Original detected label (Speaker 1, Speaker 2, etc.) |
| segment_count | INTEGER | Number of segments by this speaker |
| total_duration_seconds | FLOAT | Total speaking time in this transcription |
| average_embedding | FLOAT8[] | Average voice embedding for this speaker |
| similarity_score | FLOAT | Similarity to matched profile (0.0-1.0) |
| is_confirmed | BOOLEAN | Whether match was confirmed by user |
| created_at | TIMESTAMP | When mapping was created |

**Indexes:**
- `idx_mapping_transcription` - Optimizes transcription queries
- `idx_mapping_profile` - Optimizes profile queries

**Constraints:**
- `transcription_id` references `transcriptions(id)` ON DELETE CASCADE
- `speaker_profile_id` references `speaker_profiles(id)` ON DELETE SET NULL

## Audio Processing

### Input Audio (Mumble → Whisper)
- Format: PCM 48kHz mono 16-bit
- Buffered in memory per user
- Converted to WAV for Whisper
- Transcription happens after silence threshold

### Output Audio (TTS → Mumble)
- **Piper TTS:** 22050Hz mono → resampled to 48000Hz mono 16-bit
- **Silero TTS:** 22050Hz mono → resampled to 48000Hz mono 16-bit  
- **Chatterbox TTS:** 22050Hz mono → resampled to 48000Hz mono 16-bit
- **Format:** 48000Hz mono 16-bit (required by Mumble protocol)
- **Processing:** FFmpeg resampling prevents chipmunk voice effect

## Security Considerations

- **No Authentication:** Default setup is for trusted local networks
- **Database Credentials:** Stored in .env file
- **Ollama Access:** Uses host network for local access
- **Web Panel:** No HTTPS by default

**Production Recommendations:**
- Add reverse proxy with auth
- Use secrets management
- Enable HTTPS
- Implement rate limiting
- Add input validation

## Scaling Considerations

Current architecture is single-instance. For scaling:

1. **Multiple Bots:** Deploy multiple bot instances
2. **Load Balancing:** Use nginx for Whisper/Piper
3. **Database:** Consider connection pooling tuning
4. **Ollama:** Deploy multiple Ollama instances
5. **Storage:** Use external volume for voices

## Network Architecture

```
mumble-ai-network (bridge)
├── mumble-server (64738)
├── faster-whisper (5000)
├── piper-tts (5001)
├── web-control-panel (5002)
├── tts-voice-generator (5003)
├── silero-tts (5004)
├── chatterbox-tts (5005)
├── email-summary-service (5006)
├── sip-mumble-bridge (5060, 10000-10010)
├── whisper-web-interface (5008)
├── mumble-web (8081)
├── postgres (5432 internal)
└── mumble-bot (client only)
```

External:
- Ollama: host.docker.internal:11434
- SIP Phones: localhost:5060
- Web Browsers:
  - Mumble Web Client: localhost:8081
  - Web Control Panel: localhost:5002
  - TTS Voice Generator: localhost:5003
  - Whisper Web Interface: localhost:5008
  - Landing Page: localhost:5007

## Monitoring

**Health Checks:**
- PostgreSQL: pg_isready every 10s
- Whisper: GET /health
- Piper: GET /health

**Logs:**
- Centralized via docker-compose logs
- JSON structured logging
- Log levels: INFO, WARNING, ERROR

## Recovery

**Service Restart Policy:** unless-stopped

**Failure Scenarios:**
1. **Ollama Down:** Bot continues, returns error message
2. **Whisper Down:** Bot waits for service recovery
3. **Piper Down:** Bot waits for service recovery
4. **Database Down:** Services wait for recovery
5. **Mumble Down:** Bot reconnects automatically

## Future Enhancements

- WebSocket support for real-time updates
- Multi-channel support
- Voice activity detection improvements
- Caching layer for frequent queries
- Metrics and observability (Prometheus)
- Container health endpoints
