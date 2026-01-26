# Configuration Guide

Complete configuration reference for Mumble AI Bot including Flutter app configuration.

## Environment Variables

### Database Configuration

```bash
# PostgreSQL credentials
POSTGRES_USER=mumbleai
POSTGRES_PASSWORD=mumbleai123
POSTGRES_DB=mumble_ai
```

### Mumble Server

```bash
# Mumble server superuser password
MUMBLE_PASSWORD=changeme

# Bot username in Mumble
BOT_USERNAME=AI-Bot
BOT_PASSWORD=  # Optional, leave empty for no password
```

### Whisper Configuration

```bash
# Model size: tiny, base, small, medium, large
WHISPER_MODEL=base

# Device: cpu or cuda (requires GPU setup)
DEVICE=cpu
```

### TTS Configuration

```bash
# TTS Engine selection (piper, silero, or chatterbox)
TTS_ENGINE=piper

# Piper TTS voice (if using Piper)
PIPER_VOICE=en_US-lessac-medium

# Silero TTS voice (if using Silero)
SILERO_VOICE=en_0

# Chatterbox TTS voice (if using Chatterbox)
CHATTERBOX_VOICE=default
```

### Ollama Configuration

```bash
# Ollama server URL (host.docker.internal for local)
OLLAMA_URL=http://host.docker.internal:11434

# Default model to use
OLLAMA_MODEL=llama3.2:latest
```

### SIP Bridge Configuration

```bash
# SIP server settings
SIP_PORT=5060
SIP_USERNAME=mumble-bridge
SIP_PASSWORD=bridge123
SIP_DOMAIN=*  # Accept calls from any domain

# RTP port range for audio streams
RTP_PORT_MIN=10000
RTP_PORT_MAX=10010

# Logging level
LOG_LEVEL=INFO

# Welcome message uses bot_persona from database
# Configure via web control panel or directly in database
```

### Web Client Configuration

```bash
# Mumble Web client automatically connects to mumble-server:64738
# No additional environment variables required
```

## Service Configuration

### Web Control Panel

Access: `http://localhost:5002`

#### Changing Ports

Edit `docker-compose.yml`:

```yaml
web-control-panel:
  ports:
    - "8080:5002"  # Change 8080 to your desired port
```

### Chatterbox TTS Configuration

```bash
# Device: cpu or cuda (requires GPU setup)
DEVICE=cpu

# TTS model (currently only XTTS-v2 supported)
TTS_MODEL=XTTS-v2

# Voice cloning settings
VOICE_CLONING_ENABLED=true
REFERENCE_AUDIO_DURATION=10  # seconds
```

### Email Summary Service Configuration

```bash
# Email settings
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_IMAP_SERVER=imap.gmail.com
EMAIL_IMAP_PORT=993
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_ENABLED=true

# Daily summary settings
DAILY_SUMMARY_TIME=09:00
SUMMARY_RECIPIENTS=user1@example.com,user2@example.com

# Vision AI for attachments
VISION_MODEL=moondream
VISION_MODEL_URL=http://host.docker.internal:11434

# Memory extraction
MEMORY_MODEL=mistral
MEMORY_MODEL_URL=http://host.docker.internal:11434
```

### Flutter App Configuration

#### Server Connection

The Flutter app requires configuration to connect to your Mumble AI server:

**Server URL Configuration:**
- **Default**: `http://localhost:5002` (for local development)
- **Remote Server**: `http://your-server-ip:5002` (for remote access)
- **HTTPS**: `https://your-domain.com:5002` (for production with SSL)

**Network Requirements:**
- **Port Access**: Ensure port 5002 is accessible from your mobile device
- **Firewall**: Configure firewall to allow connections on port 5002
- **CORS**: The web control panel must allow cross-origin requests from mobile devices

#### User Management

**Multi-User Support:**
- **User Selection**: Choose from existing users or create new ones
- **User-Specific Data**: Each user has separate memories, schedules, and conversations
- **Persistent Selection**: App remembers the last selected user
- **User Creation**: Create new users directly from the app

**User Data Isolation:**
- **Memories**: Each user's memories are separate and private
- **Schedules**: Calendar events are user-specific
- **Conversations**: Chat history is isolated per user
- **Settings**: User preferences are maintained separately

#### Logging System Configuration

**Automatic Logging:**
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Auto-Sync**: Logs automatically sync to server every 50 entries
- **Local Storage**: Logs stored locally until synced
- **Retry Logic**: Failed syncs are retried automatically

**Log Viewing:**
- **Web Interface**: View logs at `http://your-server:5002/logs`
- **Filtering**: Filter by level, screen, and time range
- **Real-Time**: Auto-refresh for live log monitoring
- **Export**: Download logs for analysis

**Log Configuration:**
```bash
# Log retention (server-side)
LOG_RETENTION_DAYS=30  # Keep logs for 30 days

# Log level filtering
MIN_LOG_LEVEL=INFO  # Only store INFO and above

# Log storage limits
MAX_LOG_ENTRIES=10000  # Maximum logs per user
```

#### Audio Configuration

**Voice Preview:**
- **Audio Playback**: Preview TTS voices before selection
- **Audio Format**: WAV format for high quality
- **Volume Control**: Integration with system volume
- **Audio Permissions**: Requires microphone permission for voice features

**TTS Integration:**
- **Engine Support**: Piper, Silero, and Chatterbox TTS
- **Voice Selection**: Choose from 70+ available voices
- **Audio Quality**: High-quality audio output
- **Offline Support**: Basic functionality without network

#### Performance Configuration

**Memory Management:**
- **Cache Size**: Local cache for frequently accessed data
- **Memory Limits**: Configurable memory usage limits
- **Garbage Collection**: Automatic cleanup of unused resources
- **Background Sync**: Efficient background data synchronization

**Network Optimization:**
- **Connection Pooling**: Reuse HTTP connections
- **Request Batching**: Batch multiple API calls
- **Timeout Settings**: Configurable request timeouts
- **Retry Logic**: Automatic retry for failed requests

#### Security Configuration

**Data Protection:**
- **Local Storage**: Encrypted local storage for sensitive data
- **Network Security**: HTTPS support for secure connections
- **Authentication**: Optional authentication for server access
- **Data Privacy**: User data isolation and protection

**Access Control:**
- **User Permissions**: Role-based access control
- **API Security**: Rate limiting and request validation
- **Log Security**: Secure log storage and access
- **Device Management**: Device registration and management

#### Beta Testing Configuration

**Testing Settings:**
- **Debug Mode**: Enable detailed logging and debugging
- **Performance Monitoring**: Track app performance metrics
- **Crash Reporting**: Automatic crash detection and reporting
- **User Feedback**: Built-in feedback collection system

**Development Configuration:**
```bash
# Flutter app development settings
FLUTTER_DEBUG=true
FLUTTER_VERBOSE_LOGGING=true
FLUTTER_PERFORMANCE_MONITORING=true
FLUTTER_CRASH_REPORTING=true
```

#### Troubleshooting Configuration

**Debug Settings:**
- **Verbose Logging**: Enable detailed debug information
- **Network Debugging**: Log all network requests and responses
- **Performance Profiling**: Track app performance metrics
- **Error Reporting**: Detailed error reporting and stack traces

**Recovery Settings:**
- **Auto-Recovery**: Automatic recovery from common errors
- **Fallback Modes**: Graceful degradation when features fail
- **Data Backup**: Automatic backup of user data
- **Restore Options**: Data restoration capabilities

### Vision AI Configuration

```bash
# Vision model for email attachment analysis
VISION_MODEL=moondream
VISION_MODEL_URL=http://host.docker.internal:11434

# Alternative vision models
# VISION_MODEL=llava
# VISION_MODEL=bakllava
```

### Memory Extraction Configuration

```bash
# Model for extracting memories from conversations
MEMORY_MODEL=mistral
MEMORY_MODEL_URL=http://host.docker.internal:11434

# Memory extraction settings
MEMORY_EXTRACTION_ENABLED=true
MEMORY_IMPORTANCE_THRESHOLD=5
MEMORY_CATEGORIES=Schedule,Fact,Task,Preference,Reminder,Other
```

### SIP Bridge

#### Port Configuration

The SIP bridge uses multiple ports:

```yaml
sip-mumble-bridge:
  ports:
    - "5060:5060/udp"      # SIP signaling (UDP)
    - "5060:5060/tcp"      # SIP signaling (TCP)
    - "10000-10010:10000-10010/udp"  # RTP audio streams
```

#### Security Configuration

For production use, restrict SIP access:

```bash
# In .env file
SIP_DOMAIN=your-pbx-server-ip  # Instead of *
SIP_PASSWORD=strong-password   # Use strong password
```

#### Firewall Rules

```bash
# Allow SIP only from your PBX server
sudo ufw allow from <PBX_IP> to any port 5060 proto udp
sudo ufw allow from <PBX_IP> to any port 5060 proto tcp
sudo ufw allow from <PBX_IP> to any port 10000:10010 proto udp
```

### Mumble Web Client

#### Port Configuration

```yaml
mumble-web:
  ports:
    - "8081:8080"  # External port 8081 maps to internal 8080
```

#### Custom Server Configuration

The web client automatically connects to `mumble-server:64738`. To change this:

1. Edit `docker-compose.yml`:
```yaml
mumble-web:
  environment:
    - MUMBLE_SERVER=your-server:64738
```

2. Or modify the client configuration after build.

### Mumble Web Simple

#### Build Configuration

```bash
cd mumble-web-simple
npm ci
npm run build
```

#### Development Mode

```bash
cd mumble-web-simple
npm run build:dev
```

## Voice Configuration

### Adding More Voices

1. Find voices at https://github.com/rhasspy/piper/releases
2. Edit `web-control-panel/download_voices.py`
3. Add voice to VOICES list:
```python
("voice-name", "https://url-to-voice.onnx")
```
4. Rebuild: `docker-compose build web-control-panel`

### Changing Default Voice

Via web panel or directly in database:
```sql
UPDATE bot_config SET value = 'en_GB-alba-medium' WHERE key = 'piper_voice';
```

## Bot Behavior

### Silence Threshold

Edit `mumble-bot/bot.py`:
```python
self.silence_threshold = 1.5  # seconds
```

### Conversation History Limit

Edit `mumble-bot/bot.py`:
```python
history = self.get_conversation_history(user_name=user_name, limit=10)
```

## Database

### Connection Pool Size

Edit `mumble-bot/bot.py`:
```python
self.db_pool = psycopg2.pool.SimpleConnectionPool(
    1, 10,  # min, max connections
    ...
)
```

### Backup

```bash
docker exec mumble-ai-postgres pg_dump -U mumbleai mumble_ai > backup.sql
```

### Restore

```bash
cat backup.sql | docker exec -i mumble-ai-postgres psql -U mumbleai mumble_ai
```

## Audio Settings

### Whisper Model Trade-offs

| Model | RAM | Speed | Accuracy |
|-------|-----|-------|----------|
| tiny | ~1GB | Fastest | Low |
| base | ~1GB | Fast | Good |
| small | ~2GB | Medium | Better |
| medium | ~5GB | Slow | High |
| large | ~10GB | Slowest | Best |

### GPU Acceleration

Edit `docker-compose.yml` for faster-whisper service:

```yaml
faster-whisper:
  environment:
    - DEVICE=cuda
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

## Advanced Configuration

### Custom System Prompt

Modify `mumble-bot/bot.py` in `build_prompt_with_context`:

```python
# Add system prompt before persona
system_prompt = "You are a helpful AI assistant.\n"
full_prompt = system_prompt
```

### Logging Level

Edit each service's Python file:

```python
logging.basicConfig(level=logging.DEBUG)  # or INFO, WARNING, ERROR
```

### Network Configuration

Custom network settings in `docker-compose.yml`:

```yaml
networks:
  mumble-ai-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.25.0.0/16
```

## Security Hardening

### Add Authentication to Web Panel

Use nginx reverse proxy:

```nginx
location / {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://localhost:5002;
}
```

### Environment Secrets

Use Docker secrets instead of .env:

```yaml
services:
  postgres:
    secrets:
      - postgres_password
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

### Firewall Rules

Only expose necessary ports:
```bash
# Allow only from specific IP
ufw allow from 192.168.1.0/24 to any port 64738
ufw allow from 192.168.1.0/24 to any port 5002
```

## Performance Tuning

### Increase Max Connections

PostgreSQL config:
```ini
max_connections = 100
shared_buffers = 256MB
```

### Ollama Performance

```bash
# Use faster models for better responsiveness
OLLAMA_MODEL=llama3.2:1b  # Fastest
OLLAMA_MODEL=llama3.2:3b  # Balance
OLLAMA_MODEL=llama3.2:8b  # Best quality
```

### Memory Limits

Add to docker-compose.yml:

```yaml
services:
  mumble-bot:
    mem_limit: 2g
    memswap_limit: 2g
```

## Troubleshooting Configuration

### View Current Config

```bash
# Database config
docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT * FROM bot_config;"

# Environment
docker exec mumble-bot env | grep OLLAMA

# SIP Bridge config
docker exec sip-mumble-bridge env | grep SIP

# Web client status
docker exec mumble-web ps aux
```

### Service-Specific Troubleshooting

#### SIP Bridge Issues

```bash
# Check SIP bridge logs
docker logs sip-mumble-bridge

# Test SIP port accessibility
netstat -an | grep 5060

# Verify RTP ports
netstat -an | grep 10000
```

#### Web Client Issues

```bash
# Check web client logs
docker logs mumble-web

# Test web client connectivity
curl http://localhost:8081

# Check if Mumble server is accessible
docker exec mumble-web ping mumble-server
```

#### Mumble Web Simple Build Issues

```bash
# Check build logs
cd mumble-web-simple
npm run build 2>&1 | tee build.log

# Clean and rebuild
rm -rf node_modules dist
npm ci
npm run build
```

### Reset to Defaults

```bash
docker-compose down -v  # WARNING: Deletes all data
docker-compose up -d
```
