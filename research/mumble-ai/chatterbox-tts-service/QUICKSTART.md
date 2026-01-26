# Chatterbox TTS Quick Start Guide

This guide will help you get the Chatterbox TTS service up and running in your Mumble-AI stack.

## Prerequisites

1. **NVIDIA GPU** with CUDA support (optional but recommended)
2. **NVIDIA Container Toolkit** installed (for GPU support)
3. **Docker and Docker Compose** installed
4. At least **4GB of free disk space** (for models)
5. At least **4GB of RAM** (8GB+ recommended with GPU)

## Quick Start

### 1. Verify NVIDIA Container Toolkit (for GPU support)

Test if your GPU is accessible in Docker:

```bash
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

If this works, you're good to go! If not, you'll need to install the NVIDIA Container Toolkit:

**Ubuntu/Debian:**
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Build and Start the Service

From the Mumble-AI root directory:

```bash
# Build the service
docker-compose build chatterbox-tts

# Start the service (and dependencies)
docker-compose up -d chatterbox-tts
```

**First run will take 5-10 minutes** as it downloads the XTTS-v2 model (~2GB).

### 3. Monitor the Startup

Watch the logs to see the model loading:

```bash
docker-compose logs -f chatterbox-tts
```

Look for:
- `Loading TTS model: tts_models/multilingual/multi-dataset/xtts_v2`
- `Using CUDA device: [GPU name]` or `Using CPU device`
- `TTS model loaded successfully`

### 4. Test the Service

Check health:
```bash
curl http://localhost:5005/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "chatterbox-tts",
  "device": "cuda",
  "cuda_available": true,
  "model_loaded": true,
  "gpu_name": "NVIDIA GeForce RTX 3080"
}
```

### 5. Test Voice Cloning

You'll need a reference audio file (WAV format, 3-10 seconds, single speaker).

```bash
# Example using curl (replace with your reference audio path)
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! This is a test of voice cloning with Chatterbox TTS.",
    "speaker_wav": "/path/to/reference/audio.wav",
    "language": "en",
    "speed": 1.0
  }' \
  --output test_output.wav
```

## Configuration Options

### Environment Variables

Edit `docker-compose.yml` to customize:

```yaml
environment:
  - PORT=5005                                        # Service port
  - DEVICE=auto                                      # auto/cuda/cpu
  - TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
  - MODEL_DIR=/app/models                            # Model storage
```

### Device Options

- `DEVICE=auto` - Automatically use GPU if available, fall back to CPU (recommended)
- `DEVICE=cuda` - Force GPU usage (will fail if GPU not available)
- `DEVICE=cpu` - Force CPU usage (slower but works on any system)

### Memory Considerations

GPU memory requirements:
- **Minimum**: 4GB VRAM
- **Recommended**: 6GB+ VRAM

If you get out of memory errors:
1. Reduce other GPU-using services
2. Use `DEVICE=cpu` for CPU-only operation
3. Add memory limits in docker-compose.yml

## Integration with Mumble-AI

The service is already configured in `docker-compose.yml` with:
- URL: `http://chatterbox-tts:5005` (internal)
- Port: `5005` (external)
- Environment variable: `CHATTERBOX_URL` in bot services

## Troubleshooting

### Problem: GPU Not Detected

**Solution:**
1. Verify NVIDIA drivers: `nvidia-smi`
2. Check Docker GPU access: `docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi`
3. Restart Docker: `sudo systemctl restart docker`
4. Use CPU fallback: Set `DEVICE=cpu` in docker-compose.yml

### Problem: Model Download Fails

**Solution:**
1. Check internet connection
2. Check disk space: `df -h`
3. Try manual download:
```bash
docker-compose exec chatterbox-tts python3 -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

### Problem: Service Crashes or OOM

**Solution:**
1. Check logs: `docker-compose logs chatterbox-tts`
2. Reduce memory usage: Set `DEVICE=cpu`
3. Add memory limit in docker-compose.yml:
```yaml
deploy:
  resources:
    limits:
      memory: 8G
```

### Problem: Slow Performance

**CPU Mode (~10-30 seconds per sentence):**
- Normal for CPU mode
- Consider upgrading to GPU

**GPU Mode (should be ~2-5 seconds):**
1. Verify GPU is being used: Check `/health` endpoint
2. Check GPU utilization: `nvidia-smi -l 1`
3. Ensure no other heavy GPU processes

## API Usage Examples

### Python Example

```python
import requests

# Generate speech with voice cloning
response = requests.post('http://localhost:5005/api/tts', json={
    'text': 'Hello from Chatterbox TTS!',
    'speaker_wav': '/path/to/reference.wav',
    'language': 'en',
    'speed': 1.0
})

# Save to file
with open('output.wav', 'wb') as f:
    f.write(response.content)
```

### cURL Example

```bash
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Your text here",
    "speaker_wav": "/path/to/reference.wav",
    "language": "en"
  }' \
  --output output.wav
```

### Check Available Models

```bash
curl http://localhost:5005/api/models
```

### Get Service Information

```bash
curl http://localhost:5005/api/info
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

## Optional: Database Integration

To store voice presets in the database:

```bash
# Apply migration
docker-compose exec postgres psql -U mumbleai -d mumble_ai -f /docker-entrypoint-initdb.d/add_chatterbox_voices.sql

# Or from host
docker-compose exec -T postgres psql -U mumbleai -d mumble_ai < sql/add_chatterbox_voices.sql
```

## Performance Tips

1. **Reference Audio Quality**: Use high-quality, noise-free audio
2. **Reference Length**: 3-10 seconds is optimal
3. **Single Speaker**: Reference should contain only one speaker
4. **GPU Memory**: Close other GPU applications if low on VRAM
5. **Batch Processing**: For multiple requests, keep the service warm

## Next Steps

1. Test with different reference voices
2. Integrate with your Mumble bot
3. Store favorite voices in the database
4. Configure voice presets in the web control panel
5. Add voice cloning to your TTS options

## Support

For issues or questions:
1. Check logs: `docker-compose logs chatterbox-tts`
2. Review the main README: [README.md](./README.md)
3. Check service health: `curl http://localhost:5005/health`

## Resources

- Coqui TTS Documentation: https://docs.coqui.ai/
- XTTS-v2 Model: https://huggingface.co/coqui/XTTS-v2
- Project Repository: https://github.com/devnen/Chatterbox-TTS-Server

