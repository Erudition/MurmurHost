# Chatterbox TTS - Quick Reference

## ✅ Status: FULLY OPERATIONAL

### Access Points
- **Web Interface:** http://localhost:5003
- **Chatterbox API:** http://localhost:5005
- **Database:** PostgreSQL `mumble_ai` table `chatterbox_voices`

### Quick Commands

```bash
# Check status
docker-compose ps chatterbox-tts tts-web-interface

# View logs
docker logs chatterbox-tts --tail 50
docker logs tts-web-interface --tail 50

# Restart services
docker-compose restart chatterbox-tts tts-web-interface

# Check health
curl http://localhost:5005/health  # Chatterbox
curl http://localhost:5003/health  # Web interface
```

### Clone a Voice (API)

```bash
# Test clone
curl -X POST http://localhost:5003/api/chatterbox/clone \
  -F "audio=@your_audio.wav" \
  -F "text=Hello, this is a test" \
  -F "language=en" \
  --output test.wav

# Save to library
curl -X POST http://localhost:5003/api/chatterbox/save \
  -F "audio=@your_audio.wav" \
  -F "name=My Voice" \
  -F "language=en"

# Get all voices
curl http://localhost:5003/api/chatterbox/voices

# Generate TTS
curl -X POST http://localhost:5003/api/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Your text","voice":"1","engine":"chatterbox"}' \
  --output output.wav
```

### Features
- ✅ Voice cloning (3-10 sec audio)
- ✅ 16 languages supported
- ✅ GPU acceleration (GTX 1080)
- ✅ Persistent voice library
- ✅ Web interface
- ✅ REST API

### Performance
- **GPU:** 2-5 sec/clone
- **CPU:** 10-30 sec/clone
- **Model:** XTTS-v2 loaded
- **VRAM:** ~1.9GB allocated

### Documentation
- Setup: `docs/CHATTERBOX_TTS_SETUP.md`
- Integration: `docs/CHATTERBOX_WEB_INTEGRATION.md`
- Summary: `docs/CHATTERBOX_FINAL_SUMMARY.md`
- Service README: `chatterbox-tts-service/README.md`

### What You Can Do NOW

1. **Web UI:** Go to http://localhost:5003
   - Select "Chatterbox TTS" engine
   - Upload audio sample
   - Clone and save voices

2. **API:** Use curl/python to clone voices programmatically

3. **Save Multiple Voices:** Build your voice library

4. **Generate TTS:** Use cloned voices for speech synthesis

### Services Running
- ✅ chatterbox-tts (Port 5005) - HEALTHY
- ✅ tts-web-interface (Port 5003) - HEALTHY
- ✅ Database connected
- ✅ GPU active (NVIDIA GTX 1080)
- ✅ Model loaded (XTTS-v2)

**Everything is ready to use!** 🎉

