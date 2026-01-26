# Whisper Web Interface

A modern, feature-rich web interface for transcribing audio and video files using the Whisper AI model, with advanced speaker recognition, persistent speaker profiles, AI-powered summarization, and intelligent title generation.

## Overview

The Whisper Web Interface is a comprehensive service in the Mumble-AI stack that provides a user-friendly web application for transcribing audio and video files. It features cutting-edge speaker diarization with persistent voice recognition, automatic title generation, and a beautiful React-based interface with dedicated transcription detail pages.

## Features

### Core Transcription Features
- **Multi-Format Support**: Audio (.mp3, .wav, .ogg, .flac, .aac, .m4a) and video (.mp4, .webm, .avi, .mov, .mkv) files up to 100MB
- **Real-time Transcription**: Uses the existing faster-whisper service for accurate speech-to-text conversion
- **Language Detection**: Automatic language detection with confidence scores
- **Database Storage**: PostgreSQL integration with full transcription history

### Advanced Speaker Recognition System

#### Aggressive Multi-Speaker Detection
The system uses an enhanced speaker detection algorithm optimized to identify multiple speakers:

- **Resemblyzer Voice Embeddings**: Extracts 256-dimensional voice fingerprints from each audio segment
- **Agglomerative Clustering**: Uses hierarchical clustering with Ward linkage for optimal speaker grouping
- **Pairwise Distance Analysis**: Calculates cosine distances between all voice embeddings to detect diversity
- **PCA Variance Analysis**: Analyzes principal components to estimate number of speakers
- **Silhouette Score Validation**: Tests 2-8 speaker configurations to find optimal clustering
- **Audio Normalization**: Ensures consistent volume levels for accurate voice comparison
- **Very Aggressive Thresholds**: Optimized to favor detecting multiple speakers over single-speaker scenarios

**Technical Details:**
- Variance ratio thresholds: 0.92/0.98/0.94 for 2/3/multi-speaker detection
- Minimum segment length: 0.15 seconds
- Minimum speaker turn: 2 segments
- Post-processing to merge very short speaker turns
- No external API dependencies - completely local processing

#### Persistent Speaker Profiles

**Cross-Session Speaker Recognition** - The system remembers speakers across all transcriptions:

- **Voice Profile Database**: Stores speaker voice embeddings in PostgreSQL
- **Automatic Matching**: Compares detected speakers against all known profiles using cosine similarity
- **75% Similarity Threshold**: Requires 75% match confidence for automatic recognition
- **Weighted Profile Updates**: Updates speaker profiles with new samples using weighted averaging
- **Speaker Metadata**: Track first seen, last seen, total speaking duration, sample count, and importance
- **Confidence Scoring**: Each match includes a confidence score for transparency
- **Multi-Sample Learning**: Profiles improve over time as more samples are collected

**Database Schema:**
```sql
-- Speaker profiles with voice embeddings
CREATE TABLE speaker_profiles (
    id SERIAL PRIMARY KEY,
    speaker_name VARCHAR(255) NOT NULL UNIQUE,
    voice_embedding FLOAT8[] NOT NULL,  -- 256-dim Resemblyzer embedding
    sample_count INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_duration_seconds FLOAT DEFAULT 0,
    description TEXT,
    tags TEXT[],
    confidence_score FLOAT DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Links transcriptions to speaker profiles
CREATE TABLE speaker_transcription_mapping (
    id SERIAL PRIMARY KEY,
    transcription_id INTEGER NOT NULL REFERENCES transcriptions(id),
    speaker_profile_id INTEGER REFERENCES speaker_profiles(id),
    detected_speaker_label VARCHAR(100) NOT NULL,
    segment_count INTEGER DEFAULT 0,
    total_duration_seconds FLOAT DEFAULT 0,
    average_embedding FLOAT8[],
    similarity_score FLOAT,
    is_confirmed BOOLEAN DEFAULT FALSE
);
```

#### Speaker Management UI

**SpeakerManager Component** provides intuitive speaker profile management:

- **Match Indicators**: Green badges show which speakers were automatically recognized
- **Confidence Display**: Shows similarity percentage for each match
- **Easy Naming**: Input fields to name unknown speakers directly in the UI
- **One-Click Profile Creation**: Save new speaker profiles with a single button click
- **Known Speakers List**: View all stored speaker profiles at the bottom
- **Cross-Reference**: See which transcriptions each speaker appears in

### AI-Generated Titles

**Automatic Intelligent Title Generation** - Every transcription gets a descriptive title:

- **Ollama Integration**: Uses local LLM to analyze transcription content
- **Smart Sampling**: Analyzes first 2000 characters for quick title generation
- **Concise Titles**: Generates 8-word maximum descriptive titles
- **Context-Aware**: Understands content type (meeting, interview, lecture, etc.)
- **Graceful Fallback**: Uses filename if title generation fails
- **30-Second Timeout**: Fast response to avoid blocking transcription workflow

**Example Generated Titles:**
- "Team Meeting: Q4 Budget Planning Discussion"
- "Customer Support Call: Billing Issue Resolution"
- "Podcast Interview: AI Technology and Ethics"
- "Lecture: Introduction to Machine Learning Concepts"

### Modern React UI Architecture

**Single-Page Application with React Router:**

#### Navigation Structure
- **Home Page** (`/`): Upload interface with drag-and-drop support
- **History Page** (`/history`): Card-based grid of all transcriptions with pagination
- **Transcription Detail** (`/transcription/:id`): Individual transcription pages with full features

#### Beautiful Card-Based History Page
- **3-Column Responsive Grid**: Adapts to desktop, tablet, and mobile screens
- **Hover Effects**: Cards elevate on hover with smooth transitions
- **Rich Metadata Display**: Format badge, duration, language, speaker count
- **Text Preview**: First 3 lines of transcription in each card
- **Summary Indicator**: Blue badge when AI summary is available
- **Delete on Hover**: Delete button appears when hovering over cards
- **Full-Text Search**: Search across titles, filenames, and transcription content
- **Smart Pagination**: 10 items per page with intelligent page number display

#### Individual Transcription Pages
Each transcription has its own dedicated page with:
- **Full Metadata Header**: Title, filename, duration, language, file size, speakers
- **View Mode Toggle**: Switch between Formatted and Timeline views
- **Speaker Management Section**: Profile matching and naming interface
- **Speaker Editor**: Rename speakers and merge duplicate detections
- **AI Summary Panel**: Generate and view summaries with model selection
- **Back Navigation**: Easy return to history page
- **Delete Confirmation**: Safe deletion with confirmation dialog

#### Enhanced Components
- **TimelineView**: Interactive segment-by-segment timeline with speaker color coding
- **SummaryPanel**: AI-powered summary generation with Ollama model selection
- **SpeakerEditor**: Bulk speaker renaming and merging
- **LoadingSpinner**: Beautiful loading states with contextual messages
- **UploadZone**: Drag-and-drop file upload with progress tracking

### AI Summarization
- **Ollama Integration**: Local LLM-powered intelligent summaries
- **Model Selection**: Choose from available Ollama models
- **Configurable Length**: Adjust summary detail level
- **Re-generate**: Generate new summaries with different models or settings
- **Markdown Support**: Formatted summaries with proper structure

### Search and Filtering
- **Full-Text Search**: Search across titles, filenames, and transcription content
- **Real-time Results**: Instant search results as you type
- **Pagination Reset**: Automatically returns to page 1 on new search
- **Clear Search**: One-click search reset button
- **Result Counter**: Shows total results and current page range

## Architecture

### Technology Stack

**Backend:**
- **Flask**: Python web framework with RESTful API design
- **PostgreSQL**: Relational database with JSONB support for embeddings
- **Resemblyzer**: Neural voice embedding library (256-dim vectors)
- **scikit-learn**: Machine learning for clustering algorithms
- **pydub + FFmpeg**: Audio format conversion and processing
- **librosa 0.9.2**: Audio analysis (specific version for Resemblyzer compatibility)
- **NumPy**: Numerical operations for embeddings and distances
- **psycopg2**: PostgreSQL connection with pooling

**Frontend:**
- **React 18**: Modern UI library with hooks
- **React Router v6**: Client-side routing for SPA navigation
- **Vite**: Fast build system and dev server
- **Tailwind CSS**: Utility-first CSS framework
- **Lucide React**: Beautiful icon library
- **Axios**: HTTP client for API requests

**Infrastructure:**
- **Multi-stage Docker Build**: Optimized container images
- **nginx**: Static file serving in production
- **Health Checks**: Comprehensive service monitoring
- **Connection Pooling**: Efficient database connections

### Service Integration

The Whisper Web Interface integrates with multiple Mumble-AI services:

- **Faster Whisper Service** (`http://faster-whisper:5000`): Core transcription engine
- **Ollama** (`http://host.docker.internal:11434`): AI summarization and title generation
- **PostgreSQL** (`postgres:5432`): Data persistence and speaker profile storage
- **Shared Network**: `mumble-ai-network` for service discovery

### Speaker Detection Algorithm Flow

1. **Audio Preprocessing**:
   - Normalize audio volume
   - Convert to mono 16kHz WAV
   - Split into 0.15-second segments

2. **Voice Embedding Extraction**:
   - Process each segment through Resemblyzer
   - Generate 256-dimensional voice fingerprint
   - Store embeddings for clustering

3. **Initial Speaker Estimation**:
   - Perform PCA on all embeddings
   - Calculate variance ratios
   - Analyze pairwise cosine distances
   - Estimate likely number of speakers (2-8 range)

4. **Optimal Clustering**:
   - Test Agglomerative Clustering for 2-8 speakers
   - Calculate silhouette score for each configuration
   - Select configuration with highest score
   - Apply Ward linkage for hierarchical grouping

5. **Post-Processing**:
   - Merge very short speaker turns (< 2 segments)
   - Assign "Speaker 1", "Speaker 2" labels
   - Calculate average embedding per speaker

6. **Profile Matching**:
   - Compare each speaker's average embedding to all stored profiles
   - Calculate cosine similarity scores
   - Match speakers with > 75% similarity
   - Return match confidence scores

7. **Database Storage**:
   - Save detected speakers with embeddings
   - Create transcription-to-profile mappings
   - Update profile statistics (last seen, duration, sample count)

## API Endpoints

### Core Transcription Endpoints

#### Upload File
```bash
POST /api/upload
Content-Type: multipart/form-data

curl -X POST http://localhost:5008/api/upload \
  -F "file=@audio.wav" \
  -F "filename=audio.wav"

Response:
{
  "temp_path": "/tmp/abc123.wav",
  "filename": "audio.wav",
  "original_format": "wav",
  "file_size_bytes": 1048576,
  "duration_seconds": 125.3
}
```

#### Transcribe File
```bash
POST /api/transcribe
Content-Type: application/json

{
  "temp_path": "/tmp/abc123.wav",
  "filename": "audio.wav",
  "language": "auto"
}

Response:
{
  "transcription_id": 42,
  "title": "Team Meeting Q4 Budget Planning",
  "transcription_text": "Full transcription text...",
  "transcription_segments": [...],
  "transcription_formatted": "Formatted with speakers...",
  "language": "en",
  "language_probability": 0.98,
  "processing_time_seconds": 12.5,
  "speaker_matches": [
    {
      "detected_label": "Speaker 1",
      "profile_id": 5,
      "speaker_name": "John Smith",
      "confidence": 0.87
    },
    {
      "detected_label": "Speaker 2",
      "profile_id": null,
      "speaker_name": null,
      "confidence": null
    }
  ]
}
```

#### List Transcriptions
```bash
GET /api/transcriptions?page=1&per_page=10&search=meeting

Response:
{
  "transcriptions": [...],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 45,
    "pages": 5
  }
}
```

#### Get Single Transcription
```bash
GET /api/transcriptions/<id>

Response:
{
  "id": 42,
  "title": "Team Meeting Q4 Budget Planning",
  "filename": "meeting_recording.mp3",
  "original_format": "mp3",
  "file_size_bytes": 5242880,
  "duration_seconds": 1825.3,
  "transcription_text": "...",
  "transcription_segments": [...],
  "transcription_formatted": "...",
  "summary_text": "...",
  "summary_model": "llama3.2",
  "language": "en",
  "language_probability": 0.98,
  "processing_time_seconds": 45.2,
  "created_at": "2025-10-21T14:30:00Z",
  "speaker_matches": [...]
}
```

#### Delete Transcription
```bash
DELETE /api/transcriptions/<id>

Response:
{
  "success": true,
  "message": "Transcription deleted successfully"
}
```

### Speaker Management Endpoints

#### List All Speakers
```bash
GET /api/speakers

Response:
{
  "speakers": [
    {
      "id": 5,
      "speaker_name": "John Smith",
      "sample_count": 12,
      "first_seen": "2025-10-15T10:00:00Z",
      "last_seen": "2025-10-21T14:30:00Z",
      "total_duration_seconds": 3650.5,
      "confidence_score": 0.92,
      "is_active": true,
      "description": "Engineering team lead",
      "tags": ["engineering", "meetings"],
      "transcription_count": 8
    }
  ]
}
```

#### Create/Update Speaker Profile
```bash
POST /api/speakers
Content-Type: application/json

{
  "speaker_name": "John Smith",
  "transcription_id": 42,
  "detected_speaker_label": "Speaker 1",
  "description": "Engineering team lead",
  "tags": ["engineering", "meetings"]
}

Response:
{
  "success": true,
  "profile_id": 5,
  "speaker_name": "John Smith",
  "is_new": false,
  "updated_fields": ["voice_embedding", "sample_count", "last_seen"],
  "sample_count": 13
}
```

#### Update Speaker Metadata
```bash
PUT /api/speakers/<id>
Content-Type: application/json

{
  "speaker_name": "John R. Smith",
  "description": "Senior Engineering Manager",
  "tags": ["engineering", "leadership", "meetings"]
}

Response:
{
  "success": true,
  "message": "Speaker profile updated successfully"
}
```

#### Delete Speaker Profile
```bash
DELETE /api/speakers/<id>

Response:
{
  "success": true,
  "message": "Speaker profile deactivated"
}
```

### Summary Endpoints

#### Generate Summary
```bash
POST /api/summarize
Content-Type: application/json

{
  "transcription_id": 42,
  "model": "llama3.2"
}

Response:
{
  "success": true,
  "summary": "This meeting covered Q4 budget planning...",
  "model": "llama3.2"
}
```

### Speaker Editor Endpoints

#### Update Speaker Names
```bash
POST /api/transcriptions/<id>/update-speakers
Content-Type: application/json

{
  "speaker_mappings": {
    "Speaker 1": "John",
    "Speaker 2": "Mary"
  }
}

Response:
{
  "success": true,
  "transcription_formatted": "Updated formatted text..."
}
```

#### Merge Speakers
```bash
POST /api/transcriptions/<id>/merge-speakers
Content-Type: application/json

{
  "source_speakers": ["Speaker 2", "Speaker 3"],
  "target_speaker": "Speaker 1"
}

Response:
{
  "success": true,
  "merged_count": 2,
  "segments_affected": 45
}
```

## Database Schema

### Transcriptions Table
```sql
CREATE TABLE transcriptions (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    title VARCHAR(500),  -- AI-generated title
    original_format VARCHAR(10),
    file_size_bytes BIGINT,
    duration_seconds FLOAT,
    transcription_text TEXT,
    transcription_segments JSONB,  -- Array of {start, end, text, speaker}
    transcription_formatted TEXT,  -- Human-readable with speakers
    summary_text TEXT,
    summary_model VARCHAR(50),
    language VARCHAR(10),
    language_probability FLOAT,
    processing_time_seconds FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transcriptions_created_at ON transcriptions(created_at DESC);
CREATE INDEX idx_transcriptions_language ON transcriptions(language);
CREATE INDEX idx_transcriptions_title ON transcriptions(title);
```

### Speaker Profiles Table
```sql
CREATE TABLE speaker_profiles (
    id SERIAL PRIMARY KEY,
    speaker_name VARCHAR(255) NOT NULL UNIQUE,
    voice_embedding FLOAT8[] NOT NULL,  -- 256-dim Resemblyzer embedding
    sample_count INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_duration_seconds FLOAT DEFAULT 0,
    description TEXT,
    tags TEXT[],
    confidence_score FLOAT DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_speaker_profiles_name ON speaker_profiles(speaker_name);
CREATE INDEX idx_speaker_profiles_active ON speaker_profiles(is_active);
```

### Speaker-Transcription Mapping Table
```sql
CREATE TABLE speaker_transcription_mapping (
    id SERIAL PRIMARY KEY,
    transcription_id INTEGER NOT NULL REFERENCES transcriptions(id) ON DELETE CASCADE,
    speaker_profile_id INTEGER REFERENCES speaker_profiles(id) ON DELETE SET NULL,
    detected_speaker_label VARCHAR(100) NOT NULL,
    segment_count INTEGER DEFAULT 0,
    total_duration_seconds FLOAT DEFAULT 0,
    average_embedding FLOAT8[],  -- Average embedding for this speaker in this transcription
    similarity_score FLOAT,  -- Similarity to matched profile
    is_confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_mapping_transcription ON speaker_transcription_mapping(transcription_id);
CREATE INDEX idx_mapping_profile ON speaker_transcription_mapping(speaker_profile_id);
```

## Configuration

### Environment Variables

```bash
# Database Configuration
DB_HOST=postgres
DB_PORT=5432
DB_NAME=mumble_ai
DB_USER=mumbleai
DB_PASSWORD=mumbleai123

# Service URLs
WHISPER_URL=http://faster-whisper:5000
OLLAMA_URL=http://host.docker.internal:11434

# Ollama Configuration
OLLAMA_MODEL=llama3.2:latest
OLLAMA_TIMEOUT=30  # Seconds for title generation

# Speaker Recognition
SPEAKER_SIMILARITY_THRESHOLD=0.75  # 75% minimum for profile matching

# File Upload
MAX_FILE_SIZE=104857600  # 100MB in bytes
UPLOAD_FOLDER=/tmp

# Application
FLASK_ENV=production
PORT=5008
```

### Docker Configuration

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

## Usage Guide

### For End Users

#### Basic Transcription Workflow

1. **Access the Interface**: Navigate to `http://localhost:5008`
2. **Upload a File**:
   - Click or drag-and-drop an audio/video file
   - Wait for upload to complete (shows file metadata)
3. **Start Transcription**:
   - Click "Start Transcription"
   - Processing includes:
     - Audio extraction (for video files)
     - Speech-to-text conversion
     - Speaker detection and diarization
     - AI title generation
     - Speaker profile matching
4. **Review Results**:
   - Automatically redirected to transcription detail page
   - View full transcription with speaker labels
   - Check which speakers were automatically recognized (green badges)
5. **Name Unknown Speakers**:
   - Enter names in the Speaker Manager section
   - Click "Save Speaker Names" to create permanent profiles
   - Future transcriptions will auto-recognize these speakers
6. **Generate Summary** (optional):
   - Click "Generate Summary" in the Summary Panel
   - Select an Ollama model
   - Wait for AI-generated summary
7. **Browse History**:
   - Click "History" in navigation
   - Search for specific transcriptions
   - Navigate through pages
   - Click any card to view details

#### Speaker Recognition Workflow

**First Time a Speaker is Detected:**
1. Speaker appears as "Speaker 1" (or 2, 3, etc.)
2. In Speaker Manager, enter their name
3. Click "Save Speaker Names"
4. System creates a voice profile

**Subsequent Transcriptions:**
1. System automatically compares detected voices to all stored profiles
2. If similarity > 75%, speaker is auto-recognized
3. Green "Recognized" badge appears with confidence score
4. Speaker labeled with their known name
5. Profile updated with new voice sample (weighted averaging)

**Managing Profiles:**
- View all known speakers at bottom of Speaker Manager
- See how many transcriptions each speaker appears in
- Update names and descriptions as needed
- Deactivate profiles if no longer needed

### For Developers

#### Local Development Setup

**Backend Development:**
```bash
cd whisper-web-interface

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export WHISPER_URL=http://localhost:5000
export OLLAMA_URL=http://localhost:11434

# Run development server
python app.py
```

**Frontend Development:**
```bash
cd whisper-web-interface/client

# Install dependencies
npm install

# Run development server (with hot reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

#### Docker Development

**Build and Run:**
```bash
# Build service
docker-compose build whisper-web-interface

# Start service
docker-compose up whisper-web-interface

# View logs
docker-compose logs -f whisper-web-interface

# Restart service
docker-compose restart whisper-web-interface

# Apply code changes (IMPORTANT)
docker-compose stop whisper-web-interface
docker-compose up -d whisper-web-interface  # Recreates container
```

#### Adding New Features

**Backend API Endpoint:**
1. Add route in `app.py`
2. Implement database queries
3. Add error handling
4. Update API documentation

**Frontend Component:**
1. Create component in `client/src/components/`
2. Add to appropriate page
3. Connect to API via `services/api.js`
4. Style with Tailwind CSS

**Database Migration:**
1. Update schema in `init-db.sql`
2. Test locally
3. Rebuild containers
4. Update documentation

## Performance Considerations

### File Processing Times

**Audio Files:**
- Small (< 5 min): 10-30 seconds
- Medium (5-30 min): 30-120 seconds
- Large (30-60 min): 2-5 minutes

**Video Files:**
- Additional 20-30% time for audio extraction
- Depends on video codec and resolution

**Speaker Detection:**
- Adds 10-20% to transcription time
- More speakers = longer processing
- Optimization: Processes in parallel with transcription

**Title Generation:**
- Typically 2-5 seconds
- Depends on Ollama model speed
- 30-second timeout prevents blocking

### Resource Usage

**Memory:**
- Base: ~500MB
- During transcription: +1-2GB
- Large files (> 50MB): +3-4GB

**CPU:**
- Moderate during upload
- High during transcription
- Low during playback/browsing

**Storage:**
- Temporary files cleaned automatically
- Database grows with transcription history
- Voice embeddings: ~256 bytes per speaker per transcription

### Optimization Tips

1. **Use Smaller Audio Formats**: Convert large files to compressed formats before upload
2. **Batch Processing**: Process multiple files during off-hours
3. **Database Indexing**: Ensure proper indexes for search performance
4. **Connection Pooling**: Already configured for PostgreSQL
5. **Caching**: Consider Redis for frequently accessed transcriptions

## Troubleshooting

### Common Issues

#### Speaker Detection Only Finding One Speaker

**Symptoms:** Multiple distinct speakers detected as one

**Solutions:**
1. Check audio quality - ensure clear separation between speakers
2. Verify speakers have distinct voices (not very similar)
3. Check for background noise - clean audio improves detection
4. Ensure speakers don't overlap/interrupt frequently
5. Minimum 0.15s per speaker turn required

**Technical Details:**
- Detection uses variance thresholds: 0.92/0.98/0.94
- Silhouette score must exceed -0.5 for multi-speaker
- Try with clearer audio samples if possible

#### Speaker Profile Not Matching

**Symptoms:** Known speaker not recognized automatically

**Possible Causes:**
1. Different audio quality than training samples
2. Background noise affecting voice embedding
3. Speaker voice changed (illness, different microphone)
4. Similarity below 75% threshold
5. Only one previous sample (needs more samples for accuracy)

**Solutions:**
1. Manually assign speaker name in this transcription
2. Save to add new sample to profile (improves future matching)
3. Collect 3-5 samples for best accuracy
4. Consider lowering threshold if needed (not recommended)

#### Title Generation Fails

**Symptoms:** Title falls back to filename

**Solutions:**
1. Check Ollama is running: `curl http://localhost:11434/api/tags`
2. Verify model is available: `ollama list`
3. Check Ollama logs: `docker logs mumble-bot` (or wherever Ollama runs)
4. Ensure network connectivity to host.docker.internal
5. Try pulling model again: `ollama pull llama3.2`

#### File Upload Fails

**Symptoms:** Upload error or file rejected

**Solutions:**
1. Check file size < 100MB
2. Verify format is supported (see File Format Support)
3. Ensure disk space available in /tmp
4. Check Docker volume mounts
5. Verify file isn't corrupted

#### Transcription Errors

**Symptoms:** Transcription fails or incomplete

**Solutions:**
1. Verify faster-whisper service is running:
   ```bash
   docker-compose ps faster-whisper
   curl http://localhost:5000/health
   ```
2. Check audio quality (should be clear speech)
3. Try different language setting if auto-detection fails
4. Check faster-whisper logs: `docker-compose logs faster-whisper`
5. Verify audio format conversion succeeded

#### Pagination Not Working

**Symptoms:** Page buttons don't navigate properly

**Solutions:**
1. Check browser console for JavaScript errors
2. Verify API response includes pagination object
3. Clear browser cache
4. Ensure database has transcriptions
5. Check network tab for failed API requests

### Health Checks

The service includes comprehensive health monitoring:

```bash
# Overall health
curl http://localhost:5008/health

Response:
{
  "status": "healthy",
  "database": "connected",
  "whisper_service": "available",
  "ollama_service": "available",
  "uptime_seconds": 3650.5
}
```

### Debugging Tips

**Backend Debugging:**
```bash
# View detailed logs
docker-compose logs -f whisper-web-interface

# Check database connections
docker exec -it whisper-web-interface python -c "import psycopg2; print('DB OK')"

# Test Whisper service
curl -X POST http://localhost:5000/transcribe -F "audio=@test.wav"

# Test Ollama
curl http://localhost:11434/api/generate -d '{"model":"llama3.2","prompt":"test"}'
```

**Frontend Debugging:**
```bash
# View browser console for errors
# Check Network tab for failed API requests
# Inspect React components with React DevTools

# Test API directly
curl http://localhost:5008/api/transcriptions
curl http://localhost:5008/api/speakers
```

**Database Debugging:**
```bash
# Connect to PostgreSQL
docker exec -it mumble-ai-postgres psql -U mumbleai mumble_ai

# Check transcriptions
SELECT id, title, filename, created_at FROM transcriptions ORDER BY created_at DESC LIMIT 5;

# Check speaker profiles
SELECT id, speaker_name, sample_count, last_seen FROM speaker_profiles WHERE is_active = true;

# Check speaker mappings
SELECT t.title, sp.speaker_name, stm.similarity_score
FROM speaker_transcription_mapping stm
JOIN transcriptions t ON t.id = stm.transcription_id
JOIN speaker_profiles sp ON sp.id = stm.speaker_profile_id
ORDER BY stm.created_at DESC LIMIT 10;
```

## Security Considerations

### Input Validation
- File type validation (whitelist approach)
- File size limits (100MB max)
- Filename sanitization
- SQL injection prevention (parameterized queries)
- XSS prevention (React escaping)

### File Handling
- Temporary file cleanup after processing
- Unique filenames to prevent collisions
- Restricted upload directory (/tmp)
- No arbitrary file execution

### Database Security
- Connection pooling with timeouts
- Prepared statements for all queries
- No direct user input in SQL
- Proper indexing for DoS prevention

### API Security
- CORS configuration for trusted origins
- Rate limiting recommended for production
- Input validation on all endpoints
- Error messages don't leak sensitive info

### Production Recommendations
1. Add authentication/authorization
2. Implement API rate limiting
3. Use HTTPS/TLS
4. Set up reverse proxy (nginx)
5. Regular security updates
6. Database backups
7. Audit logging
8. Secrets management (not .env)

## Future Enhancements

### Planned Features
- **Real-time Streaming**: Live transcription with speaker detection
- **Batch Processing**: Upload and process multiple files
- **Custom Whisper Models**: Support for fine-tuned models
- **Advanced Audio Analysis**: Emotion detection, sentiment analysis
- **Integration with Mumble Bot**: Transcribe Mumble conversations
- **User Authentication**: Multi-user support with profiles
- **API Rate Limiting**: Production-ready traffic management
- **Advanced Search**: Semantic search using embeddings
- **Export Options**: PDF, DOCX, SRT subtitle formats
- **Speaker Clustering**: Group similar voices across all transcriptions
- **Voice Cloning**: Generate TTS using speaker profiles
- **Multi-language UI**: Internationalization support

### Community Contributions
Contributions welcome! Areas for improvement:
- Additional language support
- UI/UX enhancements
- Performance optimizations
- Additional export formats
- Mobile app development
- Cloud deployment guides

## License

Part of the Mumble-AI project. See main project LICENSE for details.

## Support

For issues, questions, or contributions:
- GitHub Issues: [Mumble-AI Repository]
- Documentation: See `docs/` folder
- CLAUDE.md: Development guidelines for AI assistance
