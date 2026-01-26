# Changelog: Whisper Web Interface Enhancements

**Date**: October 26, 2025
**Component**: Whisper Web Transcription Service & Landing Page
**Version**: Enhanced Title Generation & Dynamic URLs

## Summary

Enhanced the Whisper Web Interface with improved title generation capabilities and added dynamic URL support to the landing page for better deployment flexibility.

---

## Changes

### 🎯 Title Generation Improvements

#### Extended Timeout Duration
- **Previous**: 30-second timeout for title generation
- **Updated**: 5-minute (300-second) timeout for title generation
- **Rationale**: Large AI models (especially reasoning models like deepseek-r1) can take longer to generate quality titles
- **Impact**: More reliable title generation with complex models, prevents premature timeout failures

#### Magic Title Regeneration Feature
Added user-initiated title regeneration capability with beautiful UI integration:

**Backend (`whisper-web-interface/app.py`):**
- New API endpoint: `POST /api/regenerate-title`
- Accepts `transcription_id` and `transcription_text` parameters
- Uses same 5-minute timeout as initial generation
- Updates database with newly generated title
- Returns success status and new title

**Frontend (`TranscriptionDetailPage.jsx`):**
- New "✨ Magic Title" button next to transcription title
- Purple button with Sparkles icon for visual appeal
- Animated spinning icon during generation
- Button states:
  - Default: "Magic Title" with sparkles icon
  - Active: "Generating..." with spinning animation
  - Disabled state during processing
- Confirmation dialog warns user about 5-minute potential wait
- Success alert on completion
- Error handling with user-friendly messages

**API Layer (`api.js`):**
- New `regenerateTitle()` function
- Proper error handling and response parsing
- Integrated with existing timeout configuration

**Use Cases:**
- Initial title generation fails or times out
- User wants a different/better title
- Original title isn't descriptive enough
- Testing different title styles

---

### 🌐 Landing Page Dynamic URL Support

#### Problem Solved
Previously, all service links were hardcoded to `localhost`, making the landing page unsuitable for:
- IP address-based access (e.g., `http://192.168.1.100:5007`)
- Domain name deployments (e.g., `http://mumble-ai.local:5007`)
- Remote access scenarios
- Production deployments

#### Implementation
**Dynamic URL Generation (`landing-page/views/index.html`):**
- New JavaScript function: `getServiceUrl(port, useHttps = false)`
- Reads hostname from `window.location.hostname`
- Builds URLs dynamically based on current access method
- Preserves HTTPS flag for Mumble Web Client (port 8081)

**Updated Components:**
1. **Quick Access Section**:
   - Web Control Panel: Dynamic URL to port 5002
   - TTS Voice Generator: Dynamic URL to port 5003
   - Whisper Transcription: Dynamic URL to port 5008
   - Mumble Web Client: Dynamic HTTPS URL to port 8081

2. **Footer Quick Links**:
   - All service links now use dynamic URLs
   - GitHub links remain static (external)

**Service Status Monitoring:**
- **Unchanged**: Still uses internal container names for health checks
- **Reason**: Backend monitoring must use Docker internal network
- **User-facing links**: Use dynamic hostname from browser

**Benefits:**
- Single build works for all deployment scenarios
- No configuration changes needed for different environments
- Better user experience in distributed/remote setups
- Supports both development (localhost) and production (domain/IP) access

**Example URL Generation:**
```javascript
// Accessing via localhost:5007
getServiceUrl(5002) → "http://localhost:5002"

// Accessing via 192.168.1.100:5007
getServiceUrl(5002) → "http://192.168.1.100:5002"

// Accessing via mumble-ai.local:5007
getServiceUrl(5002) → "http://mumble-ai.local:5002"

// Mumble Web (HTTPS)
getServiceUrl(8081, true) → "https://[hostname]:8081"
```

---

## Technical Details

### Files Modified

**Backend Changes:**
- `whisper-web-interface/app.py`:
  - Line 889: Updated timeout from 30 to 300 seconds
  - Lines 865-912: Added `/api/regenerate-title` endpoint

**Frontend Changes:**
- `whisper-web-interface/client/src/pages/TranscriptionDetailPage.jsx`:
  - Added Sparkles icon import
  - Added `regeneratingTitle` state
  - Added `handleRegenerateTitle()` function
  - Updated UI with Magic Title button

- `whisper-web-interface/client/src/services/api.js`:
  - Added `regenerateTitle()` API function

**Landing Page Changes:**
- `landing-page/views/index.html`:
  - Lines 145-180: Updated Quick Access links to use dynamic URLs
  - Lines 292-295: Updated Footer Quick Links to use dynamic URLs
  - Lines 408-412: Added `getServiceUrl()` function

### Database Schema
No database schema changes required.

### API Changes

**New Endpoint:**
```http
POST /api/regenerate-title
Content-Type: application/json

Request Body:
{
  "transcription_id": 123,
  "transcription_text": "Full transcription text..."
}

Response (Success):
{
  "success": true,
  "title": "AI-Generated Title Here"
}

Response (Error):
{
  "error": "Error message here"
}
```

---

## Deployment

### Services Updated
1. **whisper-web-interface** (port 5008)
   - Rebuilt with title generation improvements
   - Restarted to apply changes

2. **landing-page** (port 5007)
   - Rebuilt with dynamic URL support
   - Restarted to apply changes

### Docker Commands Used
```bash
# Whisper Web Interface
docker-compose build whisper-web-interface
docker-compose stop whisper-web-interface
docker-compose up -d whisper-web-interface

# Landing Page
docker-compose build landing-page
docker-compose stop landing-page
docker-compose up -d landing-page
```

---

## User Impact

### Positive Changes
✅ **More Reliable Titles**: 5-minute timeout prevents failures with slow models
✅ **User Control**: Magic Title button allows manual regeneration
✅ **Better UX**: Beautiful button with clear feedback during generation
✅ **Deployment Flexibility**: Landing page works with any hostname/IP
✅ **Zero Configuration**: Dynamic URLs work automatically
✅ **Consistent Experience**: Same UI across all access methods

### Breaking Changes
❌ **None**: All changes are additive and backward-compatible

### Migration Required
❌ **None**: Existing transcriptions and data remain unchanged

---

## Testing Recommendations

### Title Generation Testing
1. Navigate to any transcription detail page
2. Click "✨ Magic Title" button
3. Confirm the dialog
4. Verify:
   - Button shows "Generating..." with spinning icon
   - Button is disabled during generation
   - Title updates on success
   - Error message shown on failure

### Landing Page URL Testing
1. Access landing page via `http://localhost:5007`
   - Verify all links use `localhost` hostname
2. Access landing page via `http://[IP]:5007`
   - Verify all links use IP address hostname
3. Access landing page via `http://[domain]:5007`
   - Verify all links use domain hostname
4. Verify service status checks still work (backend monitoring)

---

## Future Enhancements

### Potential Improvements
- Add title editing capability (inline editing)
- Title history/versioning
- Title templates/presets
- AI model selection for title generation
- Title suggestions (multiple options)

---

## Related Documentation

- **Main Documentation**: `docs/WHISPER_WEB_INTERFACE.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **API Reference**: See inline API documentation above

---

## Credits

**Developed with**: Claude Code
**Testing Environment**: Docker Compose on Windows
**AI Models Used**: Ollama (configurable model for title generation)
