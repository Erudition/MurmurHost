# How to Access Voice Cloning in TTS Web Interface

## ✅ Container Updated Successfully!

The TTS web interface container has been rebuilt and restarted with all Chatterbox TTS voice cloning features.

## Access the Interface

### Step 1: Open Your Browser
Go to: **http://localhost:5003**

### Step 2: Find the Chatterbox Engine
You'll see 3 TTS engine options:
1. **Piper TTS** (default)
2. **Silero TTS**
3. **Chatterbox TTS** ← **SELECT THIS ONE** 🎯

### Step 3: Voice Cloning Section Appears
When you select "Chatterbox TTS", you'll see:

#### A. Upload Section
- **File upload box** - Drop or click to upload audio (WAV, MP3, etc.)
- **Language selector** - Choose from 16 languages (English is default)
- **Test Voice button** - Preview the cloned voice
- **Save to Library button** - Save the voice permanently

#### B. Voice Library
- **"Your Cloned Voices"** section
- Grid showing all your saved voices
- Click a voice to use it for TTS

## Quick Start - Clone Your First Voice

### Option 1: Using the Web Interface

1. **Open:** http://localhost:5003
2. **Select Engine:** Click "Chatterbox TTS" (3rd radio button)
3. **Upload Audio:**
   - Click the upload box
   - Select a 3-10 second audio file (WAV, MP3, etc.)
   - The file name will appear
4. **Choose Language:** Select language from dropdown (default: English)
5. **Test It:**
   - Click "Test Voice" button
   - Audio preview will download
6. **Save It:**
   - Click "Save to Library" button
   - Enter voice name (required)
   - Add description (optional)
   - Add tags (optional)
   - Click "Save Voice"
7. **Use It:**
   - Voice appears in "Your Cloned Voices"
   - Select it
   - Enter text in the text box at top
   - Click "Generate & Download"

### Option 2: Using API (Command Line)

```bash
# Clone and test a voice
curl -X POST http://localhost:5003/api/chatterbox/clone \
  -F "audio=@your_audio_file.wav" \
  -F "text=Hello, this is a test of voice cloning" \
  -F "language=en" \
  --output test_voice.wav

# Save voice to library
curl -X POST http://localhost:5003/api/chatterbox/save \
  -F "audio=@your_audio_file.wav" \
  -F "name=My Voice" \
  -F "description=My cloned voice" \
  -F "language=en"

# Get all saved voices
curl http://localhost:5003/api/chatterbox/voices

# Generate TTS with cloned voice (voice ID from above)
curl -X POST http://localhost:5003/api/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Your text here","voice":"1","engine":"chatterbox"}' \
  --output output.wav
```

## What You'll See

### Engine Selection (Top of Page)
```
┌─────────────────────────────────────────────────┐
│ TTS Engine                                      │
│                                                 │
│ ○ Piper TTS                                     │
│   Wide variety of voices and languages          │
│                                                 │
│ ○ Silero TTS                                    │
│   High-quality neural voices with GPU           │
│                                                 │
│ ● Chatterbox TTS ← SELECT THIS                 │
│   AI voice cloning - Clone any voice!           │
└─────────────────────────────────────────────────┘
```

### Voice Cloning Section (Appears When Chatterbox Selected)
```
┌─────────────────────────────────────────────────┐
│ Voice Cloning                                   │
│ Upload a 3-10 second audio sample to clone     │
│                                                 │
│ ┌─────────────────────────────────────┐         │
│ │  📤 Drop audio file here             │         │
│ │     or click to upload               │         │
│ │     (WAV, MP3, etc. 3-10 sec)       │         │
│ └─────────────────────────────────────┘         │
│                                                 │
│ Language: [English ▼]                           │
│                                                 │
│ [▶ Test Voice]  [💾 Save to Library]           │
│                                                 │
│ ─────────────────────────────────────────────  │
│                                                 │
│ 📚 Your Cloned Voices                           │
│ ┌──────┐ ┌──────┐ ┌──────┐                     │
│ │Voice1│ │Voice2│ │Voice3│                     │
│ └──────┘ └──────┘ └──────┘                     │
└─────────────────────────────────────────────────┘
```

## Supported Audio Formats
- WAV (recommended)
- MP3
- OGG
- FLAC
- M4A
- Most common audio formats

## Tips for Best Results

### Audio Quality
- **Length:** 3-10 seconds is optimal
- **Quality:** Clear audio, no background noise
- **Content:** Single speaker only
- **Format:** WAV format recommended for best quality

### Languages Supported
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

## Troubleshooting

### Can't See Chatterbox Option?
1. Hard refresh the page: **Ctrl + F5** (Windows) or **Cmd + Shift + R** (Mac)
2. Clear browser cache
3. Try a different browser

### Voice Cloning Section Not Showing?
1. Make sure "Chatterbox TTS" radio button is selected
2. Refresh the page
3. Check browser console for errors (F12)

### Upload Not Working?
1. Check file format (WAV, MP3, etc.)
2. Check file size (should be < 10MB)
3. Try a different audio file

### Test/Save Buttons Disabled?
1. Make sure you've uploaded an audio file
2. File name should appear after upload
3. Check browser console (F12) for errors

## Verify Services Running

```bash
# Check if services are running
docker-compose ps tts-web-interface chatterbox-tts

# Check logs
docker-compose logs tts-web-interface --tail 20
docker-compose logs chatterbox-tts --tail 20

# Test health endpoints
curl http://localhost:5003/health  # TTS web interface
curl http://localhost:5005/health  # Chatterbox service
```

## Performance

- **Voice Cloning:** 2-5 seconds (GPU) or 10-30 seconds (CPU)
- **TTS Generation:** 2-15 seconds depending on text length
- **Storage:** ~100KB - 1MB per saved voice

## Current Status

✅ Container rebuilt with latest code
✅ Chatterbox TTS engine added
✅ Voice cloning section added
✅ Voice library implemented
✅ Database connected
✅ API endpoints working
✅ Chatterbox service running (Port 5005)
✅ Web interface running (Port 5003)

## Quick Test

1. Open http://localhost:5003 in your browser
2. Look for **3 engine options** (Piper, Silero, Chatterbox)
3. Click **"Chatterbox TTS"** (the 3rd option with clone icon)
4. You should see the voice cloning upload section appear
5. You should see "Your Cloned Voices" library section

**If you see all of the above, the integration is working!** 🎉

## Need Help?

Check the logs:
```bash
docker-compose logs tts-web-interface
docker-compose logs chatterbox-tts
```

Or restart services:
```bash
docker-compose restart tts-web-interface chatterbox-tts
```

---

**The voice cloning feature is now live at http://localhost:5003!**

Select "Chatterbox TTS" engine to access it. 🎤✨

