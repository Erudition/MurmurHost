# Welcome Message Feature

## Overview

The SIP bridge now includes a personalized welcome message feature that plays when a call is answered. The welcome message is generated using the bot's persona from the database and Ollama, then spoken using the TTS service.

## How It Works

1. **Call Answer**: When a SIP call is answered (ACK received), the `CallSession.start()` method is called
2. **Welcome Message Generation**: The system generates a personalized welcome message using:
   - The bot's persona from the `bot_config` table in the database
   - Ollama API to generate contextually appropriate welcome text
3. **TTS Playback**: The generated message is converted to speech using the Piper TTS service
4. **RTP Audio**: The welcome message is played over the RTP audio stream to the caller
5. **Normal Flow**: After the welcome message, the normal call flow begins (voice activity detection, STT, LLM, TTS)

## Configuration

The welcome message feature uses the same configuration as the main AI bot:

### Database Configuration
- `bot_persona`: The persona/character description for the AI bot
- `ollama_url`: URL of the Ollama service (default: http://host.docker.internal:11434)
- `ollama_model`: Model to use for text generation (default: llama3.2:latest)
- `piper_voice`: Voice configuration for TTS (default: en_US-lessac-medium)

### Environment Variables
All configuration can be overridden via environment variables in `docker-compose.yml`:
- `OLLAMA_URL`: Ollama service URL
- `OLLAMA_MODEL`: Ollama model name
- `PIPER_VOICE`: TTS voice configuration

## Implementation Details

### New Methods Added

#### `CallSession._play_welcome_message()`
- Main method that orchestrates the welcome message flow
- Generates the message, converts to speech, and plays over RTP
- Includes fallback to default message if generation fails

#### `CallSession._generate_welcome_message()`
- Generates personalized welcome message using Ollama
- Retrieves persona from database configuration
- Builds appropriate prompt for welcome message generation
- Handles errors gracefully with fallback

#### `CallSession._build_welcome_prompt(persona)`
- Builds a specialized prompt for welcome message generation
- Includes persona context if available
- Optimized for brief, conversational welcome messages

### Error Handling

The welcome message feature is designed to be non-blocking:
- If Ollama is unavailable, falls back to default message
- If TTS fails, logs error but doesn't fail the call
- If persona is not configured, generates generic welcome message
- All errors are logged but don't interrupt the call flow

### Performance Considerations

- Welcome message generation has a 30-second timeout (shorter than normal LLM calls)
- Uses the same TTS service as the main conversation flow
- RTP audio playback is optimized for real-time streaming

## Usage Examples

### With Persona
If the database contains:
```sql
UPDATE bot_config SET value = 'You are a friendly customer service assistant specializing in technical support.' WHERE key = 'bot_persona';
```

The generated welcome message might be:
> "Hello! I'm your friendly customer service assistant. I'm here to help with any technical questions you might have. How can I assist you today?"

### Without Persona
If no persona is configured, the system generates a generic welcome:
> "Hello! I'm your AI assistant. How can I help you today?"

## Testing

The feature has been tested with:
- ✅ Persona-based welcome message generation
- ✅ Fallback behavior when no persona is configured
- ✅ Error handling for Ollama service failures
- ✅ TTS integration and RTP audio playback
- ✅ Caller name extraction from SIP headers

## Integration

The welcome message feature integrates seamlessly with the existing SIP bridge:
- No changes to SIP protocol handling
- Uses existing database connection and configuration
- Leverages existing TTS and Ollama services
- Maintains backward compatibility

## Troubleshooting

### Welcome Message Not Playing
1. Check Ollama service is running and accessible
2. Verify database configuration is correct
3. Check TTS service (Piper) is running
4. Review logs for error messages

### Generic Welcome Message
1. Check if `bot_persona` is configured in database
2. Verify Ollama is responding correctly
3. Check network connectivity to Ollama service

### Audio Issues
1. Verify RTP audio is working for normal conversation
2. Check TTS service is generating audio correctly
3. Review RTP packet transmission logs

