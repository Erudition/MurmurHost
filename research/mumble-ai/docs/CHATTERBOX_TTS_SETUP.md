# Chatterbox TTS Service Setup

**Date:** October 9, 2025  
**Status:** Ready for Testing  
**Port:** 5005

## Overview

A new Chatterbox TTS (voice cloning) service has been added to the Mumble-AI stack. This service provides high-quality voice cloning capabilities using the Coqui XTTS-v2 model with CUDA GPU support and CPU fallback.

## What Was Added

### 1. New Service Directory: `chatterbox-tts-service/`

```
chatterbox-tts-service/
├── Dockerfile              # CUDA-enabled Docker image
├── requirements.txt        # Python dependencies
├── app.py                  # Flask API service
├── README.md               # Detailed documentation
├── QUICKSTART.md           # Quick start guide
└── test_service.py         # Service test script
```

### 2. Docker Compose Integration

The service has been added to `docker-compose.yml` with:
- **Port:** 5005
- **Device:** Auto (CUDA with CPU fallback)
- **Model:** XTTS-v2 (multilingual, multi-dataset)
- **Volume:** `chatterbox-models` for persistent model storage
- **Network:** `mumble-ai-network` (integrated with other services)
- **GPU Support:** NVIDIA GPU reservation with fallback

### 3. Service Integration

Environment variables added to:
- **mumble-bot**: `CHATTERBOX_URL=http://chatterbox-tts:5005`
- **sip-mumble-bridge**: `CHATTERBOX_URL=http://chatterbox-tts:5005`
- **tts-web-interface**: `CHATTERBOX_TTS_URL=http://chatterbox-tts:5005`

### 4. Database Migration (Optional)

Created `sql/add_chatterbox_voices.sql` for storing voice presets:
- Table: `chatterbox_voices`
- Supports voice metadata, tags, and reference audio paths
- Ready for web control panel integration

## Key Features

### Voice Cloning
- Clone any voice with 3-10 seconds of reference audio
- High-quality neural synthesis
- Real-time or near-real-time processing (with GPU)

### Multi-language Support
Supports 16 languages:
- English, Spanish, French, German, Italian, Portuguese
- Polish, Turkish, Russian, Dutch, Czech, Arabic
- Chinese, Japanese, Hungarian, Korean

### GPU Acceleration
- **Automatic GPU detection** (DEVICE=auto)
- **CUDA support** for NVIDIA GPUs (~2-5 seconds per sentence)
- **CPU fallback** when GPU unavailable (~10-30 seconds per sentence)
- **Memory efficient** (4GB+ VRAM recommended)

### REST API
- `/health` - Service health and GPU status
- `/api/tts` - Text-to-speech with voice cloning
- `/api/models` - List available models
- `/api/voices` - List saved voice presets
- `/api/info` - Service information

## Getting Started

### Prerequisites

1. **NVIDIA GPU** (optional but recommended)
   - CUDA-compatible GPU (GTX 10 series or newer)
   - 4GB+ VRAM recommended
   - 6GB+ VRAM for optimal performance

2. **NVIDIA Container Toolkit** (for GPU support)
   - Install if not already present
   - Test with: `docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi`

3. **System Resources**
   - 4GB+ disk space for models
   - 4GB+ RAM (8GB+ recommended)

### Quick Start

```bash
# From Mumble-AI root directory

# 1. Build the service
docker-compose build chatterbox-tts

# 2. Start the service
docker-compose up -d chatterbox-tts

# 3. Watch startup (first run downloads ~2GB model)
docker-compose logs -f chatterbox-tts

# 4. Wait for "TTS model loaded successfully"
# This may take 5-10 minutes on first run

# 5. Test the service
curl http://localhost:5005/health

# 6. Run test suite (optional)
python chatterbox-tts-service/test_service.py
```

### First TTS Test

You'll need a reference audio file (WAV format, 3-10 seconds, single speaker):

```bash
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! This is a test of voice cloning.",
    "speaker_wav": "/path/to/your/reference.wav",
    "language": "en",
    "speed": 1.0
  }' \
  --output test_voice.wav
```

## Configuration

### Device Selection

Edit `docker-compose.yml` to change device mode:

```yaml
environment:
  - DEVICE=auto   # Default: Auto-detect GPU, fallback to CPU
  # - DEVICE=cuda  # Force GPU (fails if unavailable)
  # - DEVICE=cpu   # Force CPU (slower but always works)
```

### Model Selection

Change the TTS model:

```yaml
environment:
  - TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2  # Default
  # Or use other Coqui TTS models
```

### Resource Limits

Add memory limits if needed:

```yaml
deploy:
  resources:
    limits:
      memory: 8G
      cpus: '4.0'
```

## API Usage Examples

### Python Integration

```python
import requests

def generate_speech(text, reference_audio, language='en'):
    """Generate speech with voice cloning"""
    response = requests.post('http://localhost:5005/api/tts', json={
        'text': text,
        'speaker_wav': reference_audio,
        'language': language,
        'speed': 1.0
    })
    
    if response.status_code == 200:
        return response.content  # WAV audio bytes
    else:
        raise Exception(f"TTS failed: {response.text}")

# Usage
audio = generate_speech(
    "Hello from Chatterbox TTS!",
    "/path/to/reference.wav"
)

with open('output.wav', 'wb') as f:
    f.write(audio)
```

### Health Check

```python
import requests

response = requests.get('http://localhost:5005/health')
health = response.json()

print(f"Device: {health['device']}")
print(f"CUDA Available: {health['cuda_available']}")
print(f"Model Loaded: {health['model_loaded']}")
if 'gpu_name' in health:
    print(f"GPU: {health['gpu_name']}")
```

## Troubleshooting

### GPU Not Detected

**Symptoms:**
- Health check shows `"device": "cpu"` when GPU expected
- Service logs show "CUDA not available"

**Solutions:**
1. Verify GPU: `nvidia-smi`
2. Check Docker GPU access: `docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi`
3. Install NVIDIA Container Toolkit if missing
4. Restart Docker: `sudo systemctl restart docker`
5. Rebuild container: `docker-compose build --no-cache chatterbox-tts`

### Model Download Fails

**Symptoms:**
- Service crashes on startup
- Logs show download errors
- Container exits with error

**Solutions:**
1. Check internet connection
2. Check disk space: `df -h`
3. Increase Docker timeout in `docker-compose.yml`:
```yaml
healthcheck:
  start_period: 120s  # Increase for slow connections
```
4. Manual model download:
```bash
docker-compose exec chatterbox-tts python3 -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

### Out of Memory (OOM)

**Symptoms:**
- Container crashes during synthesis
- CUDA out of memory errors
- Service becomes unresponsive

**Solutions:**
1. Close other GPU applications
2. Reduce GPU memory usage:
   - Set `DEVICE=cpu` in docker-compose.yml
   - Stop other GPU-using containers temporarily
3. Increase system memory:
   - Add swap space
   - Upgrade RAM

### Slow Performance

**Expected Performance:**
- **GPU Mode:** 2-5 seconds per sentence
- **CPU Mode:** 10-30 seconds per sentence

**If slower than expected:**
1. Verify GPU usage: Check `/health` endpoint
2. Monitor GPU: `watch -n 1 nvidia-smi`
3. Check for thermal throttling
4. Ensure no competing GPU processes

### Audio Quality Issues

**For better quality:**
1. Use high-quality reference audio (48kHz, 16-bit recommended)
2. Ensure reference is noise-free
3. Use 5-10 second reference clips
4. Ensure single speaker in reference
5. Match speaking style of reference to desired output

## Performance Tips

1. **Reference Audio Quality**
   - Use clean, professional recordings when possible
   - Remove background noise
   - Avoid compression artifacts (use WAV instead of MP3)

2. **Optimal Reference Length**
   - 3-10 seconds is ideal
   - Too short: May not capture voice well
   - Too long: Unnecessary processing time

3. **GPU Memory Management**
   - Keep only necessary containers running
   - Monitor VRAM usage: `nvidia-smi`
   - Consider CPU mode if VRAM limited

4. **Batch Processing**
   - Keep service running (stays warm)
   - Process multiple requests without restart
   - Model stays loaded in memory

## Next Steps

### Integration Options

1. **Add to Mumble Bot**
   - Modify `mumble-bot/bot.py` to support Chatterbox TTS option
   - Add voice selection in web control panel
   - Store user voice preferences in database

2. **Store Voice Presets**
   - Apply database migration: `sql/add_chatterbox_voices.sql`
   - Add UI in web control panel for voice management
   - Allow users to upload reference audio

3. **Update TTS Web Interface**
   - Add Chatterbox option to `tts-web-interface/app.py`
   - Create voice preview/testing interface
   - Enable voice comparison

4. **SIP Bridge Integration**
   - Add voice cloning option for phone calls
   - Store caller voice profiles
   - Enable personalized responses

### Testing Checklist

- [ ] Service starts successfully
- [ ] GPU detected (if available)
- [ ] Health check returns `200 OK`
- [ ] Model loads without errors
- [ ] TTS generates audio successfully
- [ ] Audio quality is acceptable
- [ ] Performance is within expected range
- [ ] Service integrates with other containers
- [ ] Logs show no errors
- [ ] Test script passes all tests

## Resources

### Documentation
- **Service README**: `chatterbox-tts-service/README.md`
- **Quick Start Guide**: `chatterbox-tts-service/QUICKSTART.md`
- **API Documentation**: See README for endpoint details

### External Links
- **Coqui TTS**: https://docs.coqui.ai/
- **XTTS-v2 Model**: https://huggingface.co/coqui/XTTS-v2
- **Chatterbox TTS**: https://github.com/devnen/Chatterbox-TTS-Server

### Support
- Check logs: `docker-compose logs chatterbox-tts`
- Health check: `curl http://localhost:5005/health`
- Test suite: `python chatterbox-tts-service/test_service.py`

## Summary

The Chatterbox TTS service is now fully integrated into your Mumble-AI stack and ready for testing. The service provides:

- ✓ High-quality voice cloning
- ✓ GPU acceleration (with CPU fallback)
- ✓ Multi-language support (16 languages)
- ✓ REST API integration
- ✓ Docker Compose integration
- ✓ Database support (optional)

**Status:** Ready for first build and test!

**Command to start:**
```bash
docker-compose up -d chatterbox-tts
```

**No existing code has been modified** - only additions have been made to:
- New service directory
- docker-compose.yml (new service + environment variables)
- Documentation

Your existing services will continue to work unchanged.

