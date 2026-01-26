# Chatterbox TTS Service - Complete Guide

**Service:** Chatterbox TTS (Voice Cloning)  
**Port:** 5005  
**Version:** 1.0.0  
**Status:** Production Ready

## Overview

The Chatterbox TTS service provides state-of-the-art voice cloning capabilities using Coqui TTS with the XTTS-v2 model. This service enables users to clone any voice with just 3-10 seconds of reference audio, supporting 16+ languages with GPU acceleration and CPU fallback.

## Features

### 🎤 Voice Cloning
- **High-Quality Synthesis**: State-of-the-art XTTS-v2 neural voice cloning
- **Multi-Language Support**: 16+ languages including English, Spanish, French, German, Italian, Portuguese, and more
- **GPU Acceleration**: Automatic CUDA detection with CPU fallback
- **Fast Synthesis**: 2-5 seconds on GPU, 10-30 seconds on CPU
- **Reference Audio**: Clone any voice with 3-10 seconds of clear audio

### 🔧 Technical Features
- **REST API**: Simple HTTP API for easy integration
- **Docker Support**: Containerized deployment with Docker Compose
- **Health Monitoring**: Built-in health checks and status endpoints
- **Error Handling**: Robust error handling with detailed logging
- **Model Management**: Automatic model downloading and caching

## Installation & Setup

### Prerequisites

1. **Docker & Docker Compose**: Required for containerized deployment
2. **NVIDIA GPU (Optional)**: For GPU acceleration (CUDA 11.8+)
3. **Storage**: ~2GB for model files
4. **Memory**: 4GB+ RAM recommended

### Environment Configuration

Add to your `.env` file:

```env
# Chatterbox TTS Configuration
CHATTERBOX_TTS_PORT=5005
CHATTERBOX_TTS_DEVICE=auto  # auto, cuda, or cpu
CHATTERBOX_TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
CHATTERBOX_TTS_MODEL_DIR=/app/models
CHATTERBOX_TTS_COQUI_TOS_AGREED=1  # Required for model download
```

### Docker Compose Integration

Add to your `docker-compose.yml`:

```yaml
chatterbox-tts:
  build: ./chatterbox-tts-service
  ports:
    - "5005:5005"
  environment:
    - PORT=5005
    - DEVICE=${CHATTERBOX_TTS_DEVICE:-auto}
    - TTS_MODEL=${CHATTERBOX_TTS_MODEL:-tts_models/multilingual/multi-dataset/xtts_v2}
    - MODEL_DIR=${CHATTERBOX_TTS_MODEL_DIR:-/app/models}
    - COQUI_TOS_AGREED=1
  volumes:
    - ./models/chatterbox:/app/models
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5005/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### GPU Support (Optional)

For GPU acceleration, ensure you have:

1. **NVIDIA Drivers**: Latest drivers installed
2. **NVIDIA Container Toolkit**: For Docker GPU support
3. **CUDA**: Version 11.8 or higher

Test GPU support:
```bash
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

## API Reference

### Base URL
```
http://localhost:5005
```

### Health Check

**Endpoint:** `GET /health`

**Description:** Check service health and device information

**Response:**
```json
{
  "status": "healthy",
  "device": "cuda",
  "model_loaded": true,
  "model_name": "tts_models/multilingual/multi-dataset/xtts_v2",
  "gpu_available": true,
  "gpu_name": "NVIDIA GeForce RTX 3080",
  "memory_usage": {
    "total": 10240,
    "used": 2048,
    "free": 8192
  }
}
```

### Text-to-Speech (Voice Cloning)

**Endpoint:** `POST /api/tts`

**Description:** Generate speech from text using voice cloning

**Request Body:**
```json
{
  "text": "Hello, this is a test of voice cloning!",
  "speaker_wav": "/path/to/reference/audio.wav",
  "language": "en",
  "speed": 1.0
}
```

**Parameters:**
- `text` (required): Text to synthesize (max 5000 characters)
- `speaker_wav` (required): Path to reference audio file (3-10 seconds recommended)
- `language` (optional): Language code (default: "en")
- `speed` (optional): Speech speed multiplier (default: 1.0, range: 0.5-2.0)

**Response:** WAV audio file (binary)

**Example Usage:**
```bash
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, world!",
    "speaker_wav": "/path/to/reference.wav",
    "language": "en"
  }' \
  --output output.wav
```

### List Available Models

**Endpoint:** `GET /api/models`

**Description:** Get list of available TTS models

**Response:**
```json
{
  "models": [
    {
      "name": "tts_models/multilingual/multi-dataset/xtts_v2",
      "description": "XTTS-v2 multilingual voice cloning model",
      "languages": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"],
      "size": "1.9GB",
      "loaded": true
    }
  ]
}
```

### List Voice Presets

**Endpoint:** `GET /api/voices`

**Description:** Get list of saved voice presets (requires database configuration)

**Response:**
```json
{
  "voices": [
    {
      "id": 1,
      "name": "John's Voice",
      "description": "Professional male voice",
      "language": "en",
      "reference_audio_path": "/app/models/voices/john.wav",
      "created_at": "2025-01-15T10:30:00Z",
      "tags": ["professional", "male", "clear"]
    }
  ]
}
```

### Service Information

**Endpoint:** `GET /api/info`

**Description:** Get detailed service information

**Response:**
```json
{
  "service": "Chatterbox TTS",
  "version": "1.0.0",
  "device": "cuda",
  "model": "tts_models/multilingual/multi-dataset/xtts_v2",
  "supported_languages": [
    {
      "code": "en",
      "name": "English"
    },
    {
      "code": "es", 
      "name": "Spanish"
    }
  ],
  "features": [
    "voice_cloning",
    "multilingual",
    "gpu_acceleration",
    "real_time_synthesis"
  ],
  "limits": {
    "max_text_length": 5000,
    "min_reference_audio": 3,
    "max_reference_audio": 10,
    "supported_formats": ["wav", "mp3", "flac", "ogg"]
  }
}
```

## Supported Languages

| Code | Language | Status |
|------|----------|--------|
| `en` | English | ✅ Full Support |
| `es` | Spanish | ✅ Full Support |
| `fr` | French | ✅ Full Support |
| `de` | German | ✅ Full Support |
| `it` | Italian | ✅ Full Support |
| `pt` | Portuguese | ✅ Full Support |
| `pl` | Polish | ✅ Full Support |
| `tr` | Turkish | ✅ Full Support |
| `ru` | Russian | ✅ Full Support |
| `nl` | Dutch | ✅ Full Support |
| `cs` | Czech | ✅ Full Support |
| `ar` | Arabic | ✅ Full Support |
| `zh-cn` | Chinese (Simplified) | ✅ Full Support |
| `ja` | Japanese | ✅ Full Support |
| `hu` | Hungarian | ✅ Full Support |
| `ko` | Korean | ✅ Full Support |

## Voice Cloning Best Practices

### Reference Audio Requirements

1. **Duration**: 3-10 seconds of clear speech
2. **Quality**: High-quality, noise-free audio
3. **Single Speaker**: Only one person speaking
4. **Consistent Style**: Similar speaking style to desired output
5. **Format**: WAV format recommended (MP3, FLAC, OGG also supported)

### Audio Preparation Tips

1. **Remove Background Noise**: Use noise reduction tools
2. **Normalize Volume**: Ensure consistent audio levels
3. **Clear Pronunciation**: Avoid mumbled or unclear speech
4. **Natural Pace**: Use normal speaking speed
5. **Emotion**: Match the emotional tone you want in output

### Text Input Guidelines

1. **Length**: Keep under 5000 characters for best performance
2. **Punctuation**: Use proper punctuation for natural pauses
3. **Language**: Match the language of your reference audio
4. **Style**: Consider the speaking style of the reference voice

## Integration with Mumble-AI

### Bot Integration

The Chatterbox TTS service integrates seamlessly with the Mumble-AI bot:

1. **Automatic Fallback**: Bot automatically uses Chatterbox when configured
2. **Voice Selection**: Choose from saved voice presets
3. **Real-time Synthesis**: Generate speech during conversations
4. **Memory Integration**: Store voice preferences in persistent memory

### Configuration in Web Control Panel

1. **TTS Engine Selection**: Choose "Chatterbox" as TTS engine
2. **Voice Presets**: Upload and manage voice presets
3. **Language Settings**: Configure default language
4. **Performance Tuning**: Adjust speed and quality settings

### API Integration Example

```python
import requests
import json

def generate_speech(text, reference_audio_path, language="en"):
    """Generate speech using Chatterbox TTS"""
    
    url = "http://localhost:5005/api/tts"
    payload = {
        "text": text,
        "speaker_wav": reference_audio_path,
        "language": language,
        "speed": 1.0
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.content  # WAV audio data
    except requests.exceptions.RequestException as e:
        print(f"Error generating speech: {e}")
        return None

# Example usage
audio_data = generate_speech(
    "Hello, this is a test of voice cloning!",
    "/path/to/reference.wav",
    "en"
)

if audio_data:
    with open("output.wav", "wb") as f:
        f.write(audio_data)
```

## Performance Optimization

### GPU Configuration

For optimal GPU performance:

1. **CUDA Version**: Use CUDA 11.8 or higher
2. **Memory**: Ensure sufficient GPU memory (4GB+ recommended)
3. **Driver**: Keep NVIDIA drivers updated
4. **Container**: Use `--gpus all` flag in Docker

### CPU Fallback

When GPU is not available:

1. **Model Size**: Consider using smaller models for faster CPU processing
2. **Batch Processing**: Process multiple requests together
3. **Caching**: Cache frequently used voice presets
4. **Resource Limits**: Set appropriate CPU limits in Docker

### Memory Management

1. **Model Caching**: Models are cached in memory for faster access
2. **Audio Buffering**: Efficient audio data handling
3. **Garbage Collection**: Automatic cleanup of temporary files
4. **Resource Monitoring**: Built-in memory usage tracking

## Troubleshooting

### Common Issues

#### CUDA Not Detected
**Symptoms:** Service starts but uses CPU instead of GPU

**Solutions:**
```bash
# Check NVIDIA drivers
nvidia-smi

# Verify Docker GPU support
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi

# Check container GPU access
docker exec -it chatterbox-tts nvidia-smi
```

#### Out of Memory Errors
**Symptoms:** CUDA out of memory errors during synthesis

**Solutions:**
1. **Reduce Text Length**: Split long text into smaller chunks
2. **Use CPU**: Set `DEVICE=cpu` in environment
3. **Increase GPU Memory**: Use GPU with more memory
4. **Model Optimization**: Use smaller/faster models

#### Slow Performance
**Symptoms:** Synthesis takes longer than expected

**Solutions:**
1. **Check Device**: Verify GPU is being used via `/health` endpoint
2. **Update Drivers**: Ensure latest NVIDIA drivers
3. **Model Size**: Consider using faster models
4. **Resource Limits**: Check Docker resource constraints

#### Audio Quality Issues
**Symptoms:** Poor quality or distorted output

**Solutions:**
1. **Reference Audio**: Use higher quality reference audio
2. **Audio Format**: Use WAV format for reference audio
3. **Text Length**: Keep text under 1000 characters
4. **Language Match**: Ensure text language matches reference audio

### Debugging

#### Enable Debug Logging

```env
LOG_LEVEL=DEBUG
```

#### Check Service Logs

```bash
# View real-time logs
docker-compose logs -f chatterbox-tts

# Check specific errors
docker-compose logs chatterbox-tts | grep ERROR

# Monitor performance
docker-compose logs chatterbox-tts | grep "synthesis"
```

#### Health Check

```bash
# Check service health
curl http://localhost:5005/health

# Test basic functionality
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"test","speaker_wav":"/path/to/test.wav"}' \
  --output test.wav
```

## Security Considerations

### Model Licensing

- **Coqui TTS**: Licensed under MPL 2.0
- **XTTS-v2**: Non-commercial use license
- **Compliance**: Ensure compliance with model licenses

### Data Privacy

1. **Audio Processing**: Reference audio is processed locally
2. **No Data Storage**: Audio data is not permanently stored
3. **Temporary Files**: Clean up temporary files automatically
4. **Network Security**: Use HTTPS in production environments

### Access Control

1. **API Authentication**: Implement authentication for production use
2. **Rate Limiting**: Add rate limiting to prevent abuse
3. **Input Validation**: Validate all input parameters
4. **Error Handling**: Don't expose sensitive information in errors

## Monitoring & Maintenance

### Health Monitoring

```bash
# Automated health checks
curl -f http://localhost:5005/health || echo "Service unhealthy"

# Performance monitoring
curl http://localhost:5005/api/info | jq '.performance'
```

### Log Analysis

```bash
# Monitor synthesis performance
docker-compose logs chatterbox-tts | grep "synthesis completed"

# Check error rates
docker-compose logs chatterbox-tts | grep ERROR | wc -l

# Monitor memory usage
docker stats chatterbox-tts --no-stream
```

### Maintenance Tasks

1. **Model Updates**: Regularly update TTS models
2. **Driver Updates**: Keep NVIDIA drivers current
3. **Log Rotation**: Implement log rotation for long-running services
4. **Resource Monitoring**: Monitor CPU/GPU/memory usage

## Future Enhancements

### Planned Features

1. **Batch Processing**: Process multiple requests simultaneously
2. **Voice Training**: Custom voice model training
3. **Emotion Control**: Control emotional tone in synthesis
4. **Real-time Streaming**: Stream audio as it's generated
5. **Voice Mixing**: Blend multiple voices together

### Performance Improvements

1. **Model Optimization**: Smaller, faster models
2. **Caching**: Advanced result caching
3. **Load Balancing**: Multiple service instances
4. **GPU Optimization**: Better GPU memory management

## Support & Resources

### Documentation

- [Coqui TTS Documentation](https://tts.readthedocs.io/)
- [XTTS-v2 Model Information](https://huggingface.co/coqui/XTTS-v2)
- [Docker GPU Support](https://docs.nvidia.com/datacenter/cloud-native/)

### Community

- [Coqui TTS GitHub](https://github.com/coqui-ai/TTS)
- [Mumble-AI Issues](https://your-gitea-instance/issues)
- [Discord Community](https://discord.gg/your-server)

### Professional Support

For enterprise support and custom implementations, contact the development team.

---

**Last Updated:** January 15, 2025  
**Version:** 1.0.0  
**Status:** Production Ready
