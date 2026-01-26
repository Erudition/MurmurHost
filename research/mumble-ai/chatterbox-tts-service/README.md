# Chatterbox TTS Service

A high-quality voice cloning TTS service using Coqui TTS (XTTS-v2) with CUDA support and CPU fallback.

## Features

- **Voice Cloning**: Clone any voice with just a few seconds of reference audio
- **Multi-language Support**: Supports 15+ languages
- **GPU Acceleration**: Automatic CUDA detection with CPU fallback
- **REST API**: Simple HTTP API for integration
- **High Quality**: State-of-the-art neural TTS synthesis

## Environment Variables

- `PORT`: Service port (default: 5005)
- `DEVICE`: Device to use - `auto`, `cuda`, or `cpu` (default: auto)
- `TTS_MODEL`: TTS model to use (default: tts_models/multilingual/multi-dataset/xtts_v2)
- `MODEL_DIR`: Directory for storing models (default: /app/models)
- `DB_HOST`: Database host (optional, for voice presets)
- `DB_PORT`: Database port (optional)
- `DB_NAME`: Database name (optional)
- `DB_USER`: Database user (optional)
- `DB_PASSWORD`: Database password (optional)

## API Endpoints

### Health Check
```bash
GET /health
```

Returns service health status and device information.

### Text-to-Speech
```bash
POST /api/tts
Content-Type: application/json

{
  "text": "Hello, this is a test of voice cloning!",
  "speaker_wav": "/path/to/reference/audio.wav",
  "language": "en",
  "speed": 1.0
}
```

Generates speech from text using the provided reference audio for voice cloning.

**Parameters:**
- `text` (required): Text to synthesize
- `speaker_wav` (required): Path to reference audio file (3-10 seconds recommended)
- `language` (optional): Language code (default: "en")
- `speed` (optional): Speech speed multiplier (default: 1.0)

**Response:** WAV audio file

### List Models
```bash
GET /api/models
```

Returns list of available TTS models.

### List Voices
```bash
GET /api/voices
```

Returns list of saved voice presets (if database is configured).

### Service Info
```bash
GET /api/info
```

Returns detailed service information including supported languages and features.

## Usage Examples

### Basic TTS Request
```python
import requests

response = requests.post('http://localhost:5005/api/tts', json={
    'text': 'Hello, world!',
    'speaker_wav': '/path/to/reference.wav',
    'language': 'en'
})

with open('output.wav', 'wb') as f:
    f.write(response.content)
```

### Check Service Health
```python
import requests

response = requests.get('http://localhost:5005/health')
print(response.json())
```

## Supported Languages

- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Polish (pl)
- Turkish (tr)
- Russian (ru)
- Dutch (nl)
- Czech (cs)
- Arabic (ar)
- Chinese (zh-cn)
- Japanese (ja)
- Hungarian (hu)
- Korean (ko)

## Voice Cloning Tips

1. **Reference Audio Quality**: Use clear, noise-free audio (3-10 seconds)
2. **Single Speaker**: Reference audio should contain only one speaker
3. **Consistent Style**: For best results, use audio with similar speaking style to desired output
4. **Audio Format**: WAV format recommended, but MP3 and other formats are supported

## Performance

- **GPU (NVIDIA RTX 3080)**: ~2-5 seconds for a typical sentence
- **CPU (Modern 8-core)**: ~10-30 seconds for a typical sentence

## Troubleshooting

### CUDA Not Detected
If GPU is not detected:
1. Ensure NVIDIA drivers are installed
2. Verify NVIDIA Container Toolkit is installed
3. Check Docker GPU support: `docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi`

### Out of Memory
If you get CUDA out of memory errors:
1. Reduce batch size (if applicable)
2. Use a smaller model
3. Fall back to CPU: set `DEVICE=cpu`

### Slow Performance
If synthesis is slow:
1. Verify GPU is being used: check `/health` endpoint
2. Ensure CUDA is properly configured
3. Consider using a smaller/faster model

## Integration with Mumble-AI

This service is designed to integrate seamlessly with the Mumble-AI stack:

1. Add to `docker-compose.yml`
2. Configure environment variables
3. Update bot to use Chatterbox TTS endpoint
4. Store voice presets in shared database

## License

This service uses Coqui TTS, which is licensed under MPL 2.0.

