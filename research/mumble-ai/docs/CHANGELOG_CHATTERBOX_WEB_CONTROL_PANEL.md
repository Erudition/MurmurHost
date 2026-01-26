# Changelog: Chatterbox TTS Integration in Web Control Panel

**Date**: October 10, 2025
**Component**: Web Control Panel
**Type**: Feature Addition

## Summary

Added full Chatterbox TTS (voice cloning) support to the web control panel, allowing users to select and preview cloned voices directly from the configuration interface. This completes the TTS engine integration, bringing the total number of supported engines to three: Piper, Silero, and Chatterbox.

## Changes Made

### Backend (`web-control-panel/app.py`)

#### 1. Database Configuration
- Added `chatterbox_voice` config key to `bot_config` table (defaults to voice ID '1')
- Updated `set_tts_engine()` validation to accept 'chatterbox' as valid engine

#### 2. New API Endpoints
Three new endpoints for Chatterbox voice management:

**`GET /api/chatterbox/voices`**
- Returns list of all active cloned voices from `chatterbox_voices` table
- Response includes: id, name, description, language, created_at, tags
- Ordered by creation date (newest first)

**`GET /api/chatterbox/current`**
- Returns currently selected chatterbox voice ID from bot_config
- Defaults to voice ID '1' if not set

**`POST /api/chatterbox/current`**
- Updates the selected chatterbox voice in bot_config
- Parameter: `voice` (voice ID)
- Returns success status

**`POST /api/chatterbox/preview`**
- Generates preview audio for a cloned voice
- Parameter: `voice_id` (cloned voice ID)
- Calls tts-web-interface synthesize endpoint with test text
- Returns WAV audio file (24kHz mono)
- Timeout: 300 seconds (voice cloning can be slow)

#### 3. Bug Fix: Silero Preview Timeout
- **Issue**: Silero preview was timing out after 10 seconds
- **Fix**: Increased timeout from 10 to 30 seconds
- **Additional**: Removed undefined `logging` reference that was causing NameError

### Frontend (`web-control-panel/templates/index.html`)

#### 1. TTS Engine Dropdown
- Added "Chatterbox TTS (Voice Cloning)" as third option
- Updated help text to mention voice cloning capability

#### 2. Chatterbox Voice Selection Section
New UI section with:
- **Yellow alert box**: Informs users to use TTS Voice Generator (localhost:5003) for cloning new voices
- **Voice dropdown**: Displays all cloned voices with format "Name - Description (Language)"
- **Preview button**: "🔊 Preview Cloned Voice" - generates and plays sample audio
- **Refresh button**: "🔄 Refresh Voice List" - reloads voices from database

#### 3. JavaScript Functions

**`loadChatterboxVoices()`**
- Fetches cloned voices from `/api/chatterbox/voices`
- Fetches current selection from `/api/chatterbox/current`
- Populates dropdown with formatted voice labels
- Marks currently selected voice
- Shows "No cloned voices available" if empty

**`selectChatterboxVoice(voiceId)`**
- Saves selected voice to database via `/api/chatterbox/current`
- Shows success message
- Called automatically on dropdown change

**`previewChatterboxVoice()`**
- Validates voice is selected
- Shows "⏳ Generating..." state on button
- Calls `/api/chatterbox/preview` endpoint
- Plays audio using Audio API
- Handles errors with user-friendly alerts
- Restores button to normal state when done

**Updated `changeTTSEngine(engine)`**
- Added handling for 'chatterbox' engine
- Shows/hides appropriate voice selection section
- Loads voices when Chatterbox is selected

**Updated `loadTTSEngine()`**
- Added handling for 'chatterbox' engine on page load
- Ensures correct section visibility based on selected engine

### Documentation Updates

#### CLAUDE.md
1. **Config keys**: Added `chatterbox_voice` and `tts_engine` to list
2. **TTS Engine Support**: Updated from "Dual" to "Triple" TTS Engine Support
   - Added Chatterbox description
   - Documented voice preview feature
   - Added voice cloning instructions
3. **Service Dependencies**: Added chatterbox-tts service (port 5005)
4. **Accessing the System**: Updated descriptions for web control panel and TTS Voice Generator

## Technical Details

### Cross-Container Communication
The preview functionality requires cross-container communication:
1. Web control panel receives preview request
2. Verifies voice exists in database
3. Calls tts-web-interface synthesize endpoint
4. TTS-web-interface retrieves reference audio from database
5. TTS-web-interface sends request to chatterbox-tts with base64-encoded audio
6. Chatterbox generates audio using XTTS-v2 model
7. Audio streams back through tts-web-interface to web control panel
8. Browser plays audio

### Audio Format
- Preview text: "Hello, this is a preview of this voice. How do I sound?"
- Output format: WAV, 24kHz mono
- Processing time: Can take several minutes for first generation (model loading)
- Subsequent generations: Much faster due to model caching

### Database Schema
Uses existing `chatterbox_voices` table:
```sql
CREATE TABLE chatterbox_voices (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    language VARCHAR(50),
    reference_audio_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tags TEXT[],
    is_active BOOLEAN DEFAULT TRUE
);
```

Uses existing `bot_config` table:
```sql
-- New config key
INSERT INTO bot_config (key, value) VALUES ('chatterbox_voice', '1');
```

## User Experience

### Voice Selection Workflow
1. User navigates to Web Control Panel (http://localhost:5002)
2. Scrolls to "🎵 TTS Voice Configuration" section
3. Selects "Chatterbox TTS (Voice Cloning)" from dropdown
4. Sees yellow alert with link to voice cloning page
5. Selects desired cloned voice from dropdown
6. Voice selection automatically saved to database
7. Clicks preview button to hear sample
8. Audio generates and plays in browser

### Voice Cloning Workflow
1. User clicks link in yellow alert → redirects to http://localhost:5003
2. Selects "Chatterbox" tab in TTS Voice Generator
3. Uploads reference audio file (.wav, .mp3, .m4a supported)
4. Enters voice name, description, language, tags
5. Clicks "Clone Voice" button
6. Returns to Web Control Panel
7. Clicks "🔄 Refresh Voice List" to see new voice
8. Selects new voice from dropdown

## Testing

### Functionality Verified
✅ Chatterbox voice list retrieval (2 test voices)
✅ Current voice selection (returns voice ID '1')
✅ Voice selection update (persists to database)
✅ Preview generation (257KB WAV, 24kHz mono)
✅ Silero preview timeout fix (30 seconds)
✅ All three engines selectable and functional

### Test Commands
```bash
# Test voice list endpoint
curl http://localhost:5002/api/chatterbox/voices

# Test current voice endpoint
curl http://localhost:5002/api/chatterbox/current

# Test voice selection
curl -X POST http://localhost:5002/api/chatterbox/current \
  -H "Content-Type: application/json" \
  -d '{"voice":"2"}'

# Test preview (saves audio to file)
curl -X POST http://localhost:5002/api/chatterbox/preview \
  -H "Content-Type: application/json" \
  -d '{"voice_id":"1"}' \
  -o preview.wav
```

## Files Modified

1. `web-control-panel/app.py` - Backend API endpoints
2. `web-control-panel/templates/index.html` - Frontend UI and JavaScript
3. `CLAUDE.md` - Updated documentation
4. `docs/CHANGELOG_CHATTERBOX_WEB_CONTROL_PANEL.md` - This changelog

## Deployment Notes

### Build and Restart
```bash
cd H:\Mumble-AI
docker-compose stop web-control-panel
docker-compose build web-control-panel
docker-compose up -d web-control-panel
```

### Verify Deployment
```bash
# Check logs
docker-compose logs --tail=20 web-control-panel

# Test health endpoint
curl http://localhost:5002/health

# Test Chatterbox endpoints
curl http://localhost:5002/api/chatterbox/voices
```

## Future Enhancements

Potential improvements for future iterations:
- Add voice testing directly from voice cloning page
- Bulk voice import/export functionality
- Voice usage statistics (which voices are used most)
- Voice similarity search (find similar cloned voices)
- Voice editing/re-cloning capabilities
- Voice sharing between users
- Advanced voice parameters (speed, pitch adjustment)

## Related Documentation

- `docs/CHATTERBOX_INTEGRATION.md` - Complete Chatterbox integration guide
- `docs/HOW_TO_USE_VOICE_CLONING.md` - Voice cloning tutorial
- `docs/CHATTERBOX_WEB_INTEGRATION.md` - TTS web interface integration
- `docs/API.md` - API reference (should be updated with new endpoints)

## Contributors

- Implementation: Claude Code
- Testing: User verification
- Documentation: This changelog
