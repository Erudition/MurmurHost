# Whisper Transcription Web Interface

A modern web interface for transcribing audio and video files using the Whisper AI model, with optional Ollama-powered summarization.

## Features

- **File Upload**: Support for audio (.mp3, .wav, .ogg, .flac, .aac, .m4a) and video (.mp4, .webm, .avi, .mov, .mkv) files up to 100MB
- **Real-time Transcription**: Uses the existing faster-whisper service for accurate speech-to-text conversion
- **AI Summarization**: Optional summarization using Ollama (requires local Ollama installation)
- **Modern UI**: React-based single-page application with Tailwind CSS
- **Database Storage**: PostgreSQL integration for storing transcriptions and summaries
- **Search & Filter**: Search through transcription history
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

- **Backend**: Flask API with PostgreSQL connection pooling
- **Frontend**: React 18 with Vite build system
- **Audio Processing**: pydub + ffmpeg for format conversion
- **Database**: PostgreSQL with proper indexing for performance
- **Containerization**: Multi-stage Docker build

## API Endpoints

- `POST /api/upload` - Upload and validate file
- `POST /api/transcribe` - Transcribe uploaded file
- `POST /api/summarize` - Generate AI summary
- `GET /api/transcriptions` - List transcriptions with pagination
- `GET /api/transcriptions/<id>` - Get single transcription
- `DELETE /api/transcriptions/<id>` - Delete transcription
- `GET /health` - Health check

## Environment Variables

- `DB_HOST` - PostgreSQL host (default: postgres)
- `DB_PORT` - PostgreSQL port (default: 5432)
- `DB_NAME` - Database name (default: mumble_ai)
- `DB_USER` - Database user (default: mumbleai)
- `DB_PASSWORD` - Database password (default: mumbleai123)
- `WHISPER_URL` - Whisper service URL (default: http://faster-whisper:5000)
- `OLLAMA_URL` - Ollama service URL (default: http://host.docker.internal:11434)
- `OLLAMA_MODEL` - Ollama model for summarization (default: llama3.2:latest)

## Usage

1. Access the interface at `http://localhost:5008`
2. Upload an audio or video file using drag-and-drop or file browser
3. Click "Start Transcription" to process the file
4. View the transcription results and optionally generate a summary
5. Browse transcription history in the "Transcription History" tab

## Development

### Backend Development

```bash
cd whisper-web-interface
pip install -r requirements.txt
python app.py
```

### Frontend Development

```bash
cd whisper-web-interface/client
npm install
npm run dev
```

### Docker Build

```bash
docker-compose build whisper-web-interface
docker-compose up whisper-web-interface
```

## Dependencies

- Python 3.11+
- Node.js 18+
- PostgreSQL
- ffmpeg (for audio/video processing)
- Ollama (for AI summarization)

## File Format Support

### Audio Formats
- MP3 (.mp3)
- WAV (.wav)
- OGG (.ogg)
- FLAC (.flac)
- AAC (.aac)
- M4A (.m4a)

### Video Formats
- MP4 (.mp4)
- WebM (.webm)
- AVI (.avi)
- MOV (.mov)
- MKV (.mkv)

All formats are automatically converted to 16kHz mono WAV for optimal Whisper processing.
