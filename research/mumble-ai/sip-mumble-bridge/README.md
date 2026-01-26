# SIP-Mumble Bridge

This service creates a bridge between your VoIP system (VitalPBX) and the Mumble AI Bot, allowing you to call the AI assistant from any phone on your network.

## Architecture

```
Phone → VitalPBX → SIP Call → sip-mumble-bridge → Mumble Server → AI Bot
```

## How It Works

1. **Incoming SIP Call**: The bridge acts as a SIP endpoint that receives calls from VitalPBX
2. **Auto-Answer**: When a call comes in, it automatically answers
3. **Mumble Connection**: The bridge connects to the Mumble server as a client named "Phone-Bridge"
4. **Audio Routing**: Audio is routed bidirectionally:
   - Phone audio → Mumble → AI Bot (for transcription and AI response)
   - AI Bot → Mumble → Phone (for TTS playback)
5. **Call Termination**: When the call ends, the Mumble connection is closed

## Features

- ✅ Auto-answer incoming SIP calls
- ✅ **Personalized welcome messages** using bot persona and Ollama
- ✅ Automatic Mumble connection on call start
- ✅ Bidirectional audio streaming
- ✅ Automatic cleanup on call end
- ✅ Support for multiple simultaneous calls
- ✅ Configurable via environment variables

## Configuration

All configuration is done via environment variables in `docker-compose.yml`:

### SIP Settings
- `SIP_PORT`: Port for SIP endpoint (default: 5060)
- `SIP_USERNAME`: Username for SIP endpoint (default: mumble-bridge)
- `SIP_PASSWORD`: Password for authentication (default: bridge123)
- `SIP_DOMAIN`: Domain to accept calls from (default: * = all)

### Mumble Settings
- `MUMBLE_HOST`: Mumble server hostname (default: mumble-server)
- `MUMBLE_PORT`: Mumble server port (default: 64738)
- `MUMBLE_USERNAME`: Username for bridge on Mumble (default: Phone-Bridge)
- `MUMBLE_PASSWORD`: Mumble password if required (default: empty)
- `MUMBLE_CHANNEL`: Channel to join (default: Root)

### Other Settings
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Docker Ports

The service exposes:
- **5060/udp**: SIP signaling (UDP)
- **5060/tcp**: SIP signaling (TCP)

## Usage

### Starting the Service

```bash
# Build and start the bridge
docker-compose up -d sip-mumble-bridge

# Check logs
docker logs -f sip-mumble-bridge
```

### Making a Call

1. From any phone on your network, dial the extension configured in VitalPBX
2. The bridge will auto-answer and play a personalized welcome message
3. Speak to the AI bot
4. The AI will respond with voice
5. Hang up when done

### Welcome Message

The bridge now plays a personalized welcome message when answering calls:
- Uses the bot's persona from the database configuration
- Generated dynamically using Ollama for contextually appropriate greetings
- Spoken using the TTS service before normal conversation begins
- Falls back to a default message if persona is not configured

See [WELCOME_MESSAGE_FEATURE.md](WELCOME_MESSAGE_FEATURE.md) for detailed configuration and troubleshooting.

## Testing

### Test SIP Registration
```bash
# Check if the service is listening
docker logs sip-mumble-bridge | grep "SIP account created"

# Should see:
# SIP account created: sip:mumble-bridge@*
# SIP-Mumble Bridge is ready and waiting for calls
```

### Test Incoming Call
```bash
# Monitor logs while making a test call
docker logs -f sip-mumble-bridge

# You should see:
# Incoming call from sip:...
# Call answered
# Connecting to Mumble server...
# Connected to Mumble server
# Audio bridge started
```

## Troubleshooting

### No Audio Received
- Check firewall rules for UDP port 5060
- Verify VitalPBX can reach the Docker host IP
- Check Mumble server is running: `docker ps | grep mumble-server`

### Call Not Answered
- Verify SIP extension is configured correctly in VitalPBX
- Check bridge logs: `docker logs sip-mumble-bridge`
- Ensure no port conflicts on 5060

### Mumble Connection Failed
- Verify mumble-server container is running
- Check network connectivity: `docker network inspect mumble-ai_mumble-ai-network`
- Verify MUMBLE_PASSWORD if server requires authentication

### Audio Quality Issues
- Ensure adequate CPU/memory resources
- Check network latency between VitalPBX and Docker host
- Consider adjusting FRAME_SIZE in config.py for different latency/quality tradeoffs

## Technical Details

### Audio Processing
- **Mumble Audio**: 48kHz, mono, Opus codec
- **SIP Audio**: Configurable, typically 8kHz or 16kHz
- **Resampling**: Automatic conversion between formats
- **Latency**: ~40-100ms typical

### Call Flow
1. SIP INVITE received → Auto-answer (200 OK)
2. Media negotiation (SDP)
3. RTP audio stream established
4. Mumble client connects
5. Audio bridge starts
6. Bidirectional audio streaming
7. SIP BYE received → Cleanup and disconnect

## Security Notes

⚠️ **Important Security Considerations**:

1. **Authentication**: Set a strong `SIP_PASSWORD` in production
2. **Firewall**: Restrict UDP port 5060 to your VitalPBX server IP only
3. **Network**: Use isolated Docker network (already configured)
4. **Credentials**: Store passwords in `.env` file, not in docker-compose.yml

### Recommended Firewall Rule

```bash
# Allow SIP only from VitalPBX
sudo ufw allow from <VITALPBX_IP> to any port 5060 proto udp
sudo ufw allow from <VITALPBX_IP> to any port 5060 proto tcp
```

## Limitations

- Currently supports one call at a time per bridge instance
- Audio resampling may introduce slight quality degradation
- No DTMF support (can be added if needed)
- No video support (voice only)

## Future Enhancements

Potential improvements:
- [ ] Multiple simultaneous calls support
- [ ] Better audio codec negotiation
- [ ] DTMF detection for IVR menus
- [ ] Call recording
- [ ] Statistics and monitoring
- [ ] WebRTC support

## Support

For issues or questions:
1. Check the logs: `docker logs sip-mumble-bridge`
2. Review VitalPBX extension configuration
3. Verify network connectivity
4. Check Mumble AI bot is responding: Test with Mumble client first
