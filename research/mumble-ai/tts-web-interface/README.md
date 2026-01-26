# TTS Web Interface

A beautiful web interface for generating and downloading text-to-speech audio using the Piper TTS service. This service provides a modern, responsive UI for selecting voices, entering text, and generating high-quality audio files.

## Features

- **Beautiful Modern UI**: Clean, responsive design with gradient backgrounds and smooth animations
- **Comprehensive Voice Catalog**: 50+ voices from 9 different languages and regions
- **Advanced Filtering**: Filter voices by region, gender, and quality level
- **Real-time Preview**: Preview voices before generating full audio
- **Text Input Validation**: Character counting and input validation
- **Audio Player**: Built-in audio player with duration display
- **Download Support**: Generate and download WAV audio files
- **Mobile Responsive**: Works perfectly on desktop, tablet, and mobile devices

## Available Voices

### English (US)
- **Female**: Lessac, Amy, HFC Female, Kristin, Kathleen
- **Male**: HFC Male, Joe, Bryce, Danny, John, Kusal
- **Multi-Speaker**: L2 Arctic, Arctic, LibriTTS

### English (UK)
- **Female**: Alba, Jenny Dioco, Southern English Female
- **Male**: Northern English Male, Alan
- **Multi-Speaker**: Cori, Semaine, Aru, VCTK

### Spanish
- **Female**: Daniela (Argentina), MLS voices (Spain)
- **Male**: Carlfm, Davefx, Sharvard (Spain), Ald, Claude (Mexico)

### Other Languages
- **Czech**: Jirka (Male)
- **Hindi**: Pratham (Male), Priyamvada (Female)
- **Malayalam**: Meera (Female)
- **Nepali**: Chitwan, Google voices (Male)
- **Vietnamese**: 25hours Single, Vais1000, Vivos (Female)
- **Chinese**: Huayan (Female)

## API Endpoints

### GET /api/voices
Returns the complete voice catalog organized by region and gender.

### POST /api/synthesize
Generates TTS audio from text input.

**Request Body:**
```json
{
  "text": "Your text here",
  "voice": "en_US-lessac-medium"
}
```

**Response:** WAV audio file

### POST /api/preview
Generates a short preview of the selected voice.

**Request Body:**
```json
{
  "voice": "en_US-lessac-medium"
}
```

**Response:** WAV audio file with preview text

### GET /health
Health check endpoint.

## Usage

1. **Start the service**: The service runs on port 5003 by default
2. **Select a voice**: Browse the voice catalog and click on a voice card
3. **Enter text**: Type or paste your text (up to 5000 characters)
4. **Preview**: Click "Preview Voice" to hear a sample
5. **Generate**: Click "Generate & Download" to create the full audio file

## Configuration

The service connects to the Piper TTS service via the `PIPER_TTS_URL` environment variable (default: `http://piper-tts:5001`).

## Dependencies

- Flask 2.3.3
- Requests 2.31.0
- Werkzeug 2.3.7

## Docker

The service is containerized and included in the main docker-compose.yml file. It depends on the piper-tts service and will start automatically when the stack is launched.

## Browser Support

- Chrome/Chromium 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## License

Part of the Mumble-AI project.
