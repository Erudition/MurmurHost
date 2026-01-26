# Mumble AI Bot - Connection Information

## System Status
✅ All services are running successfully!

### Running Services:
- **Mumble Server**: Port 64738 (TCP/UDP)
- **Faster-Whisper**: Port 5000 (HTTP)
- **Piper TTS**: Port 5001 (HTTP)
- **AI Bot**: Connected as "AI-Assistant"
- **Ollama**: Using llama3.2:latest model

## How to Connect

### Option 1: Download Mumble Client
1. Download from: https://www.mumble.info/
2. Install and open the Mumble client
3. Click "Add New..."
4. Configure:
   - **Label**: Mumble AI Server
   - **Address**: localhost
   - **Port**: 64738
   - **Username**: Your name (anything you want)
   - **Password**: Leave empty
5. Connect!

### Option 2: Use Existing Mumble Client
If you already have Mumble installed:
- **Server**: localhost:64738
- **Username**: Your choice
- **Password**: (none needed for users)

## Usage

### Voice Interaction
1. Connect to the server with your Mumble client
2. You'll see "AI-Assistant" bot in the channel
3. Press your Push-to-Talk key and speak
4. The bot will:
   - Listen to your voice
   - Transcribe it using Faster-Whisper
   - Send to Ollama (llama3.2)
   - Respond back with synthesized speech (Piper TTS)

### Text Chat Interaction
1. Send a text message in the Mumble chat
2. The bot will:
   - Read your message
   - Send to Ollama (llama3.2)
   - Respond back with a text message

**Note**: The bot automatically detects how you communicate:
- **Voice → Voice response** (with speech synthesis)
- **Text → Text response** (in chat)

## Managing the Stack

### View logs:
```bash
docker-compose logs -f mumble-bot
docker-compose logs -f faster-whisper
docker-compose logs -f piper-tts
docker-compose logs -f mumble-server
```

### Stop services:
```bash
docker-compose down
```

### Start services:
```bash
docker-compose up -d
```

### Restart a specific service:
```bash
docker restart mumble-bot
```

## Troubleshooting

### Bot not responding?
Check logs: `docker logs mumble-bot`

### Audio quality issues?
Edit `.env` and change `WHISPER_MODEL` to `small` or `medium`

### Change AI model?
Edit `.env` and update `OLLAMA_MODEL` to any model you have in Ollama

## Server Admin Access
- **SuperUser Password**: mumbleai2024
- Right-click the server in Mumble and authenticate as SuperUser to access admin features

## Notes
- The bot detects silence after 1.5 seconds of no audio before processing
- All conversations are processed locally (privacy-friendly)
- First response might be slower as models warm up
