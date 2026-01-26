# Chatterbox TTS Integration Guide

**Status:** Work in Progress  
**Last Updated:** October 10, 2025  
**Version:** 1.0.0

## Overview

Chatterbox TTS is a voice cloning service that has been integrated into the Mumble-AI stack. It provides high-quality voice cloning capabilities using Coqui's XTTS-v2 model with CUDA GPU acceleration and CPU fallback support.

## Important Notice

⚠️ **WORK IN PROGRESS**: The Chatterbox TTS voice cloning feature is currently under active development. While the core service is functional, full integration with the web interface and bot is still being finalized.

## Features

### Voice Cloning Capabilities
- **Reference Audio**: Clone any voice using 3-10 seconds of clean reference audio
- **Multi-language Support**: 16 languages including English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Czech, Arabic, Chinese, Japanese, Hungarian, and Korean
- **High Quality**: State-of-the-art XTTS-v2 neural TTS synthesis
- **GPU Acceleration**: CUDA support for fast generation (2-5 seconds per sentence)
- **CPU Fallback**: Automatic fallback to CPU if GPU unavailable (10-30 seconds per sentence)

### Current Status
- ✅ Core TTS service implemented and running
- ✅ Docker integration complete
- ✅ Database schema created for voice presets
- ✅ Basic API endpoints functional
- ✅ Web interface partially integrated
- 🚧 Voice library management UI (in development)
- 🚧 Bot integration (planned)
- 🚧 SIP bridge integration (planned)

## Architecture

### Service Components

```
┌─────────────────────────────────────────────────┐
│          Chatterbox TTS Service (5005)         │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │        Flask API Server                  │  │
│  └────────────────┬─────────────────────────┘  │
│                   │                             │
│  ┌────────────────▼─────────────────────────┐  │
│  │     Coqui TTS Engine (XTTS-v2)          │  │
│  │     - GPU/CPU Detection                  │  │
│  │     - Model Loading                      │  │
│  │     - Voice Synthesis                    │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
           │                    │
           │                    │
    ┌──────▼─────┐      ┌──────▼──────┐
    │ PostgreSQL │      │   Volumes   │
    │  Database  │      │   Storage   │
    │            │      │             │
    │ - Voices   │      │ - Models    │
    │ - Metadata │      │ - Audio     │
    └────────────┘      └─────────────┘
```

### Database Schema

The `chatterbox_voices` table stores voice cloning presets:

```sql
CREATE TABLE chatterbox_voices (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    reference_audio_path TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    tags TEXT[],
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}'::jsonb
);
```

## API Reference

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "chatterbox-tts",
  "device": "cuda",
  "cuda_available": true,
  "model_loaded": true,
  "cuda_version": "12.2",
  "gpu_name": "NVIDIA GeForce RTX 3080"
}
```

### Text-to-Speech
```http
POST /api/tts
Content-Type: application/json
```

**Request Body:**
```json
{
  "text": "Hello, this is a test of voice cloning!",
  "speaker_wav": "/path/to/reference/audio.wav",
  "language": "en",
  "speed": 1.0
}
```

**Response:** WAV audio file

**Parameters:**
- `text` (required): Text to synthesize (string)
- `speaker_wav` (required): Path to reference audio file or base64 encoded audio
- `language` (optional): Language code (default: "en")
- `speed` (optional): Speech speed multiplier (default: 1.0)

### List Models
```http
GET /api/models
```

**Response:**
```json
{
  "models": ["tts_models/multilingual/multi-dataset/xtts_v2", ...],
  "current_model": "tts_models/multilingual/multi-dataset/xtts_v2"
}
```

### List Saved Voices
```http
GET /api/voices
```

**Response:**
```json
{
  "voices": [
    {
      "id": 1,
      "name": "John Doe",
      "description": "Professional male voice",
      "reference_audio": "/app/cloned_voices/abc123.wav",
      "language": "en"
    }
  ]
}
```

### Service Info
```http
GET /api/info
```

**Response:**
```json
{
  "service": "Chatterbox TTS Service",
  "version": "1.0.0",
  "device": "cuda",
  "cuda_available": true,
  "model_loaded": true,
  "supported_languages": ["en", "es", "fr", "de", ...],
  "features": [
    "Voice cloning",
    "Multi-language support",
    "Adjustable speed",
    "High-quality synthesis"
  ]
}
```

## Integration Guide

### TTS Web Interface Integration

The TTS web interface (`http://localhost:5003`) has been updated to support Chatterbox:

1. **Engine Selection**: Users can select Chatterbox from the engine dropdown
2. **Voice Upload**: (Work in progress) Users can upload reference audio files
3. **Voice Library**: (Work in progress) Browse and select from saved cloned voices
4. **Preview**: Test voice cloning before generating full audio

### Current Implementation Status

**Working:**
- ✅ Backend API endpoints
- ✅ Basic voice cloning functionality
- ✅ Database integration for voice storage
- ✅ Audio format conversion (MP3/WAV support)

**In Progress:**
- 🚧 Voice upload UI in web interface
- 🚧 Voice library management
- 🚧 Voice preview functionality
- 🚧 Integration with bot and SIP bridge

### Future Integration Points

**Mumble Bot Integration (Planned):**
- Allow bot to use cloned voices for responses
- Per-user voice preferences
- Dynamic voice selection based on context

**SIP Bridge Integration (Planned):**
- Clone caller voices for personalized responses
- Store voice profiles per phone number
- Voice matching and recognition

**Web Control Panel (Planned):**
- Voice library management UI
- Upload and manage reference audio
- Test and compare voices
- Voice tagging and categorization

## Usage Examples

### Python Client

```python
import requests

def clone_voice(text, reference_audio_path, language='en'):
    """Generate speech using voice cloning"""
    
    url = 'http://localhost:5005/api/tts'
    
    payload = {
        'text': text,
        'speaker_wav': reference_audio_path,
        'language': language,
        'speed': 1.0
    }
    
    response = requests.post(url, json=payload, timeout=300)
    
    if response.status_code == 200:
        return response.content  # WAV audio data
    else:
        raise Exception(f"TTS failed: {response.text}")

# Example usage
audio_data = clone_voice(
    "Hello! This is a test of voice cloning.",
    "/path/to/reference.wav",
    "en"
)

with open('cloned_output.wav', 'wb') as f:
    f.write(audio_data)
```

### cURL Example

```bash
# Test voice cloning
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a test of voice cloning technology.",
    "speaker_wav": "/app/cloned_voices/reference.wav",
    "language": "en",
    "speed": 1.0
  }' \
  --output cloned_voice.wav
```

## Configuration

### Environment Variables

Configure in `docker-compose.yml`:

```yaml
chatterbox-tts:
  environment:
    - PORT=5005
    - DEVICE=auto              # auto, cuda, or cpu
    - TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
    - MODEL_DIR=/app/models
    - DB_HOST=postgres
    - DB_PORT=5432
    - DB_NAME=mumble_ai
    - DB_USER=mumbleai
    - DB_PASSWORD=mumbleai123
```

### Device Modes

- **`auto`** (default): Automatically detect GPU, fallback to CPU
- **`cuda`**: Force GPU usage (fails if unavailable)
- **`cpu`**: Force CPU usage (slower but always works)

### Volume Management

Volumes used by Chatterbox TTS:

- `chatterbox-models`: Persistent model storage (~2GB)
- `cloned-voices`: Reference audio files and voice library

## Performance Considerations

### GPU vs CPU Performance

| Device | Typical Generation Time | VRAM Required | Use Case |
|--------|------------------------|---------------|----------|
| GPU (CUDA) | 2-5 seconds | 4GB+ | Production, real-time |
| CPU | 10-30 seconds | N/A | Development, backup |

### Optimization Tips

1. **Reference Audio Quality**:
   - Use 48kHz, 16-bit WAV files when possible
   - Ensure audio is noise-free
   - 3-10 seconds duration is optimal
   - Single speaker only

2. **GPU Memory**:
   - Close other GPU applications
   - Monitor VRAM usage with `nvidia-smi`
   - Consider CPU mode if VRAM limited

3. **Model Caching**:
   - Model stays loaded in memory
   - Warm restarts are faster
   - First request after startup takes longer

## Troubleshooting

### Common Issues

**GPU Not Detected**
```bash
# Check GPU availability
nvidia-smi

# Test Docker GPU access
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi

# Check Chatterbox health
curl http://localhost:5005/health | jq
```

**Out of Memory**
```yaml
# Solution: Force CPU mode
environment:
  - DEVICE=cpu
```

**Slow Generation**
- Verify GPU is being used via `/health` endpoint
- Check for thermal throttling
- Monitor GPU usage with `nvidia-smi`
- Ensure no competing GPU processes

**Model Download Fails**
```bash
# Check internet connection
ping huggingface.co

# Check disk space
df -h

# Manual model download
docker-compose exec chatterbox-tts python3 -c \
  "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

## Development Roadmap

### Phase 1: Core Service (Complete ✅)
- [x] Service implementation
- [x] Docker integration
- [x] Database schema
- [x] Basic API endpoints

### Phase 2: Web Integration (In Progress 🚧)
- [ ] Voice upload UI
- [ ] Voice library management
- [ ] Voice preview functionality
- [ ] Voice comparison tools

### Phase 3: Bot Integration (Planned 📋)
- [ ] Bot voice selection
- [ ] Per-user voice preferences
- [ ] Dynamic voice switching
- [ ] Voice caching

### Phase 4: Advanced Features (Planned 📋)
- [ ] Voice mixing/blending
- [ ] Emotion control
- [ ] Voice aging effects
- [ ] Multi-speaker support

## Security Considerations

1. **File Upload Security**:
   - Validate file types (WAV only currently supported)
   - Size limits enforced (configurable)
   - Sanitize file names
   - Isolated storage directory

2. **Database Security**:
   - Parameterized queries prevent SQL injection
   - User permissions properly configured
   - Sensitive data not logged

3. **API Security**:
   - Currently internal-only (Docker network)
   - Consider authentication for external access
   - Rate limiting recommended for production

## Resources

### Documentation
- [Chatterbox Service README](../chatterbox-tts-service/README.md)
- [Chatterbox Quick Start](../chatterbox-tts-service/QUICKSTART.md)
- [Chatterbox Setup Guide](CHATTERBOX_TTS_SETUP.md)
- [Voice Cloning Usage Guide](HOW_TO_USE_VOICE_CLONING.md)

### External Resources
- [Coqui TTS Documentation](https://docs.coqui.ai/)
- [XTTS-v2 Model Card](https://huggingface.co/coqui/XTTS-v2)
- [Chatterbox TTS Server](https://github.com/devnen/Chatterbox-TTS-Server)

### Support
- Check service logs: `docker-compose logs -f chatterbox-tts`
- Health check: `curl http://localhost:5005/health`
- Test script: `python chatterbox-tts-service/test_service.py`

## License

Chatterbox TTS uses Coqui TTS, which is licensed under MPL 2.0. Please review the license terms before commercial use.

---

**Note**: This is a living document and will be updated as the Chatterbox TTS integration progresses. For the latest status, check the git commit history and service logs.

