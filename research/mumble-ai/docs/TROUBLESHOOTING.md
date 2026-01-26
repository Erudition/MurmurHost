# Troubleshooting Guide

Common issues and solutions for Mumble AI Bot including Flutter app troubleshooting.

## Flutter App Issues

### App Won't Connect to Server

**Symptom:** "Connection failed" or "Server unreachable" error

**Solutions:**
1. **Check Server URL:**
   - Verify the server URL is correct (e.g., `http://192.168.1.100:5002`)
   - Ensure you're using the correct IP address and port
   - Test the URL in a web browser first

2. **Network Connectivity:**
   ```bash
   # Test server connectivity from mobile device
   ping your-server-ip
   
   # Test port accessibility
   telnet your-server-ip 5002
   ```

3. **Firewall Configuration:**
   - Ensure port 5002 is open on the server
   - Check if firewall is blocking connections
   - Verify CORS settings allow mobile app access

4. **Server Status:**
   - Check if Mumble AI server is running
   - Verify web control panel is accessible at `http://server:5002`
   - Check server logs for connection errors

### User Selection Issues

**Symptom:** Can't select or create users

**Solutions:**
1. **Check User Data:**
   - Verify users exist in the database
   - Check if user data is properly initialized
   - Ensure user permissions are correct

2. **Database Connection:**
   - Verify database is accessible from server
   - Check database connection logs
   - Ensure user tables exist and are populated

3. **API Endpoints:**
   - Test user-related API endpoints
   - Check if `/api/users` endpoint is working
   - Verify API responses are valid

### Logging System Issues

**Symptom:** Logs not appearing in web control panel

**Solutions:**
1. **Check Log Sync:**
   - Verify logs are being sent to server
   - Check network connectivity for log transmission
   - Ensure auto-sync is enabled in app

2. **Server-Side Logging:**
   - Check if `/api/logs` endpoint is working
   - Verify `flutter_logs` table exists in database
   - Check server logs for log processing errors

3. **Log Viewing:**
   - Access logs at `http://server:5002/logs`
   - Check if log viewer page loads correctly
   - Verify log filtering and display functionality

### Audio Playback Issues

**Symptom:** Voice previews not playing

**Solutions:**
1. **Audio Permissions:**
   - Grant microphone and audio permissions to the app
   - Check Android audio settings
   - Ensure device volume is not muted

2. **Audio Format:**
   - Verify TTS services are running
   - Check if audio files are being generated
   - Test audio playback in web control panel

3. **Network Issues:**
   - Check if audio files are being downloaded
   - Verify TTS API endpoints are accessible
   - Test audio generation from server

### Performance Issues

**Symptom:** App is slow or unresponsive

**Solutions:**
1. **Memory Management:**
   - Close other apps to free memory
   - Restart the app to clear memory cache
   - Check device available storage

2. **Network Optimization:**
   - Use stable Wi-Fi connection
   - Avoid mobile data for large operations
   - Check network speed and latency

3. **App Optimization:**
   - Update to latest app version
   - Clear app cache and data
   - Restart device if necessary

### Data Synchronization Issues

**Symptom:** Data not updating or syncing properly

**Solutions:**
1. **Manual Refresh:**
   - Use pull-to-refresh on data screens
   - Manually refresh dashboard and other screens
   - Check if auto-refresh is enabled

2. **Network Connectivity:**
   - Ensure stable network connection
   - Check if server is accessible
   - Verify API endpoints are responding

3. **Data Consistency:**
   - Check if data exists on server
   - Verify user permissions for data access
   - Ensure data is not corrupted

### How to View Flutter App Logs

**Accessing Logs:**
1. **Web Interface:**
   - Open browser and navigate to `http://your-server:5002/logs`
   - Use filters to find specific logs
   - Enable auto-refresh for real-time monitoring

2. **Log Filtering:**
   - Filter by log level (DEBUG, INFO, WARNING, ERROR)
   - Filter by screen/component name
   - Set log limit for performance

3. **Log Analysis:**
   - Look for ERROR level logs first
   - Check WARNING logs for potential issues
   - Review INFO logs for app behavior

**Common Log Patterns:**
- **Connection Issues:** Look for network timeout errors
- **API Failures:** Check for HTTP error responses
- **User Issues:** Look for authentication or permission errors
- **Performance:** Check for slow response times

### Beta Testing Issues

**Symptom:** App crashes or behaves unexpectedly

**Solutions:**
1. **Report Issues:**
   - Use GitHub/Gitea issues to report bugs
   - Include device information and Android version
   - Provide steps to reproduce the issue

2. **Gather Information:**
   - Check app logs for error details
   - Note what you were doing when the issue occurred
   - Include screenshots or screen recordings if helpful

3. **Temporary Workarounds:**
   - Try restarting the app
   - Clear app data and reconfigure
   - Use web control panel as alternative

## Service Issues

### Services Won't Start

**Symptom:** `docker-compose up -d` fails

**Solutions:**
```bash
# Check if ports are already in use
netstat -an | find "64738"  # Mumble
netstat -an | find "5002"   # Web Control Panel
netstat -an | find "8081"   # Mumble Web
netstat -an | find "5060"   # SIP Bridge

# Stop conflicting services
docker-compose down

# Remove old containers
docker-compose rm -f

# Rebuild and start
docker-compose up -d --build
```

### Container Keeps Restarting

**Symptom:** Container status shows "Restarting"

**Diagnosis:**
```bash
# Check logs
docker-compose logs [service-name]

# Common issues:
# - Database not ready
# - Missing environment variables
# - Port conflicts
```

**Solutions:**
```bash
# Wait for database
docker-compose up -d postgres
sleep 10
docker-compose up -d

# Check environment file
cat .env
```

## Bot Connection Issues

### Bot Can't Connect to Mumble

**Symptom:** Bot logs show connection errors

**Solutions:**
```bash
# Check Mumble server is running
docker-compose logs mumble-server

# Verify network
docker network inspect mumble-ai_mumble-ai-network

# Restart bot
docker-compose restart mumble-bot
```

### Bot Can't Connect to Ollama

**Symptom:** "Could not connect to Ollama" errors

**Solutions:**
```bash
# Check Ollama is running
curl http://localhost:11434/api/generate -d '{"model":"llama3.2","prompt":"test"}'

# Verify model is pulled
ollama list

# Pull model if missing
ollama pull llama3.2

# Check bot can reach host
docker exec mumble-bot ping host.docker.internal
```

## Audio Issues

### No Speech Recognition

**Symptom:** Bot doesn't respond to voice

**Solutions:**
```bash
# Check Whisper service
docker-compose logs faster-whisper
curl http://localhost:5000/health

# Test Whisper directly
curl -F "audio=@test.wav" http://localhost:5000/transcribe

# Restart Whisper
docker-compose restart faster-whisper
```

### Chipmunk Voice / Distorted Audio

**Symptom:** TTS sounds too fast or high-pitched

**Solution:**
This should be fixed with audio resampling. If it persists:

```bash
# Check FFmpeg is installed in bot container
docker exec mumble-bot ffmpeg -version

# Rebuild bot container
docker-compose build mumble-bot
docker-compose up -d mumble-bot
```

### No TTS Output

**Symptom:** Bot responds but no voice

**Solutions:**
```bash
# Check Piper service
docker-compose logs piper-tts
curl http://localhost:5001/health

# Verify voices are downloaded
docker exec piper-tts ls /app/models/*.onnx | wc -l

# Restart Piper
docker-compose restart piper-tts
```

## Web Control Panel Issues

### Can't Access Control Panel

**Symptom:** localhost:5002 not accessible

**Solutions:**
```bash
# Check service is running
docker-compose ps web-control-panel

# Check logs
docker-compose logs web-control-panel

# Verify port mapping
docker port web-control-panel

# Test from inside container
docker exec web-control-panel curl localhost:5002
```

### Changes Not Taking Effect

**Symptom:** Config changes don't work

**Solutions:**
```bash
# Verify database update
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT * FROM bot_config;"

# Restart bot to pick up changes
docker-compose restart mumble-bot

# Clear browser cache
Ctrl+Shift+R (hard refresh)
```

### AI Enhance Not Working

**Symptom:** Persona enhancement fails

**Solutions:**
```bash
# Check Ollama is accessible
curl http://localhost:11434/api/tags

# Verify model is loaded
ollama list

# Check control panel logs
docker-compose logs web-control-panel | grep enhance
```

## Database Issues

### Database Connection Refused

**Symptom:** "could not connect to database" errors

**Solutions:**
```bash
# Check PostgreSQL is healthy
docker-compose ps postgres

# Wait for database to be ready
docker-compose logs postgres | grep "ready"

# Restart database
docker-compose restart postgres

# Verify credentials
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT 1;"
```

### Conversation History Not Saving

**Symptom:** No history in control panel

**Solutions:**
```bash
# Check table exists
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "\d conversation_history"

# Check for errors
docker-compose logs mumble-bot | grep "Error saving message"

# Verify bot can connect
docker-compose logs mumble-bot | grep "Database connection pool"
```

## Performance Issues

### Slow Response Times

**Symptom:** Long delays between input and response

**Diagnosis:**
```bash
# Check each service response time
time curl http://localhost:5000/health
time curl http://localhost:5001/health
time curl http://localhost:11434/api/tags
```

**Solutions:**
```bash
# Use smaller Whisper model
WHISPER_MODEL=tiny  # in .env

# Use faster Ollama model
OLLAMA_MODEL=llama3.2:1b

# Check system resources
docker stats

# Limit container memory
# Add to docker-compose.yml:
mem_limit: 2g
```

### High Memory Usage

**Symptom:** System running out of RAM

**Solutions:**
```bash
# Check memory usage
docker stats

# Use smaller models
WHISPER_MODEL=tiny
OLLAMA_MODEL=llama3.2:1b

# Reduce history limit in bot.py
limit=5  # instead of 10

# Restart services
docker-compose restart
```

## Network Issues

### DNS Resolution Failed

**Symptom:** Services can't find each other

**Solutions:**
```bash
# Check Docker network
docker network ls
docker network inspect mumble-ai_mumble-ai-network

# Recreate network
docker-compose down
docker-compose up -d

# Use IP addresses instead of hostnames
docker inspect postgres | grep IPAddress
```

## Data Issues

### Lost All Configuration

**Symptom:** Settings reset after restart

**Solutions:**
```bash
# Check volumes exist
docker volume ls | grep mumble-ai

# Don't use -v flag when stopping
docker-compose down  # Good
# docker-compose down -v  # Bad - deletes volumes

# Restore from backup
cat backup.sql | docker exec -i mumble-ai-postgres psql -U mumbleai mumble_ai
```

### Voices Missing After Update

**Symptom:** Only 1 voice available

**Solutions:**
```bash
# Trigger voice download
docker exec web-control-panel python /app/download_voices.py

# Check volume
docker volume inspect mumble-ai_piper-voices

# Restart affected services
docker-compose restart piper-tts web-control-panel
```

## New Service Issues

### Chatterbox TTS Issues

#### Voice Cloning Not Working

**Symptom:** Chatterbox TTS fails to clone voices or generate speech

**Solutions:**
```bash
# Check Chatterbox TTS logs
docker-compose logs -f chatterbox-tts

# Verify GPU availability
docker exec chatterbox-tts nvidia-smi

# Check model download
docker exec chatterbox-tts ls -la /app/models/

# Test API directly
curl -X POST http://localhost:5005/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world", "speaker_wav":"/path/to/audio.wav"}'
```

#### Slow Voice Generation

**Symptom:** Chatterbox TTS takes too long to generate speech

**Solutions:**
```bash
# Check if using GPU
docker logs chatterbox-tts | grep "device"

# Switch to CPU if GPU issues
# Edit .env file
DEVICE=cpu

# Restart service
docker-compose restart chatterbox-tts
```

#### Voice Quality Issues

**Symptom:** Cloned voices sound distorted or unclear

**Solutions:**
```bash
# Check reference audio quality
# Ensure reference audio is:
# - At least 10 seconds long
# - Clear speech without background noise
# - Mono audio format
# - 22050Hz sample rate

# Test with different reference audio
# Use high-quality recording equipment
```

### Email Summary Service Issues

#### Emails Not Being Processed

**Symptom:** Email service not checking or processing emails

**Solutions:**
```bash
# Check email service logs
docker-compose logs -f email-summary-service

# Verify email settings in web control panel
# Go to http://localhost:5002 and check email configuration

# Test email connectivity
docker exec email-summary-service python -c "
import imaplib
import smtplib
# Test IMAP connection
# Test SMTP connection
"

# Check if email is enabled
docker exec email-summary-service python -c "
from app import get_db_connection
conn = get_db_connection()
cur = conn.cursor()
cur.execute('SELECT enabled FROM email_settings LIMIT 1')
print(cur.fetchone())
"
```

#### Daily Summaries Not Sending

**Symptom:** Daily email summaries are not being sent

**Solutions:**
```bash
# Check email service logs
docker-compose logs -f email-summary-service | grep "summary"

# Verify summary time setting
# Check web control panel for daily summary time

# Test manual summary generation
curl -X POST http://localhost:5006/process_emails

# Check email logs in database
docker exec email-summary-service python -c "
from app import get_db_connection
conn = get_db_connection()
cur = conn.cursor()
cur.execute('SELECT * FROM email_logs ORDER BY created_at DESC LIMIT 5')
print(cur.fetchall())
"
```

#### Attachment Processing Issues

**Symptom:** Email attachments are not being processed or analyzed

**Solutions:**
```bash
# Check vision model availability
curl http://localhost:11434/api/tags | grep moondream

# Verify vision model configuration
# Check web control panel for vision model settings

# Test vision model directly
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"moondream","prompt":"Describe this image","images":["base64_image_data"]}'

# Check attachment processing logs
docker-compose logs -f email-summary-service | grep "attachment"
```

### TTS Voice Generator Issues

#### Voice Generator Not Loading

**Symptom:** TTS Voice Generator web interface not accessible

**Solutions:**
```bash
# Check TTS Voice Generator logs
docker-compose logs -f tts-web-interface

# Verify port 5003 is available
netstat -an | grep 5003

# Check service dependencies
docker-compose ps | grep -E "(piper-tts|silero-tts|chatterbox-tts)"

# Restart service
docker-compose restart tts-web-interface
```

#### Voice Cloning Upload Fails

**Symptom:** Cannot upload audio files for voice cloning

**Solutions:**
```bash
# Check file size limits
# Ensure audio file is under 10MB

# Verify audio format
# Supported formats: WAV, MP3, M4A, FLAC

# Check Chatterbox TTS service
docker-compose logs -f chatterbox-tts

# Test with different audio file
# Use high-quality, clear speech recording
```

### SIP Bridge Issues

#### SIP Call Not Answered

**Symptom:** Phone calls to SIP bridge are not answered

**Solutions:**
```bash
# Check SIP bridge logs
docker logs sip-mumble-bridge

# Verify SIP port is listening
netstat -an | grep 5060

# Check firewall rules
sudo ufw status | grep 5060

# Test SIP registration
docker logs sip-mumble-bridge | grep "SIP account created"
```

#### No Audio on SIP Call

**Symptom:** SIP call connects but no audio

**Solutions:**
```bash
# Check RTP ports are open
netstat -an | grep 10000

# Verify Mumble server connection
docker logs sip-mumble-bridge | grep "Connected to Mumble"

# Check audio conversion logs
docker logs sip-mumble-bridge | grep "Audio bridge"
```

#### SIP Bridge Can't Connect to Mumble

**Symptom:** SIP bridge fails to connect to Mumble server

**Solutions:**
```bash
# Check Mumble server is running
docker ps | grep mumble-server

# Test network connectivity
docker exec sip-mumble-bridge ping mumble-server

# Check Mumble server logs
docker logs mumble-server
```

### Web Client Issues

#### Web Client Not Loading

**Symptom:** localhost:8081 shows error or doesn't load

**Solutions:**
```bash
# Check web client container
docker ps | grep mumble-web

# Check logs
docker logs mumble-web

# Verify port mapping
docker port mumble-web

# Test connectivity
curl http://localhost:8081
```

#### Web Client Can't Connect to Mumble

**Symptom:** Web client loads but can't connect to Mumble server

**Solutions:**
```bash
# Check Mumble server is running
docker ps | grep mumble-server

# Test network connectivity
docker exec mumble-web ping mumble-server

# Check Mumble server logs
docker logs mumble-server

# Verify Mumble server configuration
docker exec mumble-server cat /etc/mumble-server.ini
```

#### Web Client Audio Issues

**Symptom:** No audio in web client

**Solutions:**
```bash
# Check browser console for errors
# Open Developer Tools (F12) and check Console tab

# Verify microphone permissions
# Check browser microphone settings

# Test with different browser
# Try Chrome/Chromium for best compatibility

# Check WebRTC support
# Visit https://webrtc.github.io/samples/src/content/devices/input-output/
```

### Mumble Web Simple Build Issues

#### Build Fails

**Symptom:** `npm run build` fails

**Solutions:**
```bash
# Check Node.js version
node --version  # Should be >= 22.0.0

# Clean and reinstall
cd mumble-web-simple
rm -rf node_modules package-lock.json
npm ci

# Check for specific errors
npm run build 2>&1 | tee build.log
```

#### Build Succeeds But Client Doesn't Work

**Symptom:** Build completes but web client has issues

**Solutions:**
```bash
# Check if dist folder was created
ls -la mumble-web-simple/dist/

# Verify all files are present
ls -la mumble-web-simple/dist/app/

# Test with development build
npm run build:dev
```

## Common Error Messages

### "relation 'bot_config' does not exist"

**Cause:** Database not initialized

**Solution:**
```bash
# Re-run init script
docker exec -i mumble-ai-postgres psql -U mumbleai mumble_ai < init-db.sql

# Or recreate database
docker-compose down -v
docker-compose up -d
```

### "ECONNREFUSED 127.0.0.1:11434"

**Cause:** Ollama not accessible

**Solution:**
```bash
# Start Ollama
ollama serve

# Check it's running
curl http://localhost:11434/api/tags

# Verify from container
docker exec mumble-bot curl host.docker.internal:11434/api/tags
```

### "ffmpeg: not found"

**Cause:** FFmpeg not installed in bot container

**Solution:**
```bash
# Rebuild bot
docker-compose build mumble-bot
docker-compose up -d mumble-bot

# Verify installation
docker exec mumble-bot ffmpeg -version
```

### "SIP account creation failed"

**Cause:** SIP bridge can't create SIP account

**Solution:**
```bash
# Check port 5060 is available
netstat -an | grep 5060

# Restart SIP bridge
docker-compose restart sip-mumble-bridge

# Check logs for specific error
docker logs sip-mumble-bridge | grep -i error
```

### "WebRTC connection failed"

**Cause:** Web client can't establish WebRTC connection

**Solution:**
```bash
# Check Mumble server is accessible
docker exec mumble-web ping mumble-server

# Verify Mumble server configuration
docker exec mumble-server cat /etc/mumble-server.ini | grep -i webrtc

# Check browser compatibility
# Try Chrome/Chromium browser
```

## Debug Mode

Enable detailed logging:

```bash
# Edit service files, set logging level
logging.basicConfig(level=logging.DEBUG)

# Rebuild and restart
docker-compose build [service]
docker-compose up -d [service]

# Monitor logs
docker-compose logs -f [service]
```

## Complete Reset

If all else fails:

```bash
# FULL RESET - WARNING: Deletes all data
docker-compose down -v
docker system prune -a
rm -rf mumble-data/

# Start fresh
docker-compose up -d --build
```

## Getting Help

1. Check logs: `docker-compose logs`
2. Search issues on Gitea
3. Include in report:
   - Error messages
   - Service logs
   - Docker version
   - System info
