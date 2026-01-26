# TTS Voice Generator

A standalone web interface for generating and downloading text-to-speech audio using the Piper TTS service.

## Overview

The TTS Voice Generator is an **independent service** that provides a modern, responsive web interface for users to:
- Select from 50+ high-quality voices across 9 languages and regions
- Generate TTS audio from custom text input
- Preview voices before generating full audio
- Download high-quality WAV files

**Key Point**: This service operates independently from the main Mumble-AI system and only uses the Piper TTS service on-demand when generating audio files.

## Features

### 🎨 Modern Design
- **Gradient Backgrounds**: Beautiful purple-to-blue gradient design
- **Responsive Layout**: Works perfectly on desktop, tablet, and mobile
- **Smooth Animations**: Hover effects and transitions
- **Professional UI**: Clean, modern interface with proper spacing

### 🎵 Voice Management
- **50+ Voice Options**: Comprehensive catalog from 9 languages and regions
- **Advanced Filtering**: Filter by region, gender, and quality level
- **Voice Preview**: Test voices with sample text before generating
- **Organized Display**: Voices grouped by region and gender

### 📝 Text Processing
- **Character Counter**: Real-time character count (up to 5000 characters)
- **Input Validation**: Prevents empty or invalid text submission
- **Text Area**: Large, comfortable text input area
- **Auto-resize**: Text area adjusts to content

### 🎧 Audio Features
- **Built-in Player**: HTML5 audio player with controls
- **Duration Display**: Shows audio length in minutes:seconds format
- **Download Support**: Generate and download WAV files
- **High Quality**: Professional-grade audio output

## Technical Architecture

### Standalone Design
The TTS Voice Generator is designed as a **completely independent service** that:
- Runs on its own port (5003)
- Has its own web interface and API
- Only communicates with Piper TTS when generating audio
- Does not depend on any other Mumble-AI services
- Can be used independently for voice generation needs

### Backend (Flask)
- **Framework**: Flask 2.3.3
- **API Endpoints**: RESTful API for voice catalog and synthesis
- **Error Handling**: Comprehensive error handling and logging
- **File Management**: Temporary file handling for audio generation
- **Piper Integration**: On-demand communication with Piper TTS service

### Frontend (Vanilla JavaScript)
- **No Dependencies**: Pure JavaScript, no external libraries
- **Modern ES6+**: Uses modern JavaScript features
- **Responsive Design**: CSS Grid and Flexbox for layout
- **Event Handling**: Proper event delegation and management

### Voice Catalog
The voice catalog includes voices from:
- **English**: US, UK, Australian accents
- **Spanish**: Multiple regional variants
- **French**: Standard and Canadian French
- **German**: Standard German
- **Italian**: Standard Italian
- **Portuguese**: Brazilian Portuguese
- **Dutch**: Standard Dutch
- **Norwegian**: Standard Norwegian
- **Chinese**: Mandarin Chinese

## API Endpoints

### GET /api/voices
Returns the complete voice catalog with filtering options.

**Response:**
```json
{
  "en_US": {
    "name": "English (US)",
    "voices": {
      "male": [
        {
          "id": "en_US-lessac-medium",
          "name": "Lessac (Medium)",
          "quality": "medium"
        }
      ],
      "female": [...]
    }
  }
}
```

### POST /api/synthesize
Generates TTS audio from text and voice selection.

**Request:**
```json
{
  "text": "Hello, this is a test.",
  "voice": "en_US-lessac-medium"
}
```

**Response:** WAV audio file

### POST /api/preview
Generates a short preview of the selected voice.

**Request:**
```json
{
  "voice": "en_US-lessac-medium"
}
```

**Response:** WAV audio file with sample text

## Usage

### Basic Usage
1. **Access Interface**: Navigate to `http://localhost:5003`
2. **Select Voice**: Choose from the filtered voice list
3. **Enter Text**: Type or paste your text (up to 5000 characters)
4. **Preview**: Click "Preview Voice" to test the voice
5. **Generate**: Click "Generate & Download" to create audio file

### Advanced Features

#### Voice Filtering
- **Region Filter**: Select specific language regions
- **Gender Filter**: Filter by male/female voices
- **Quality Filter**: Choose between low, medium, high quality

#### Text Input
- **Character Limit**: 5000 characters maximum
- **Real-time Counter**: Shows remaining characters
- **Validation**: Prevents empty or invalid submissions

#### Audio Controls
- **Play/Pause**: Standard audio controls
- **Duration**: Shows total audio length
- **Download**: Automatic download of generated audio

## Configuration

### Environment Variables
- `PIPER_TTS_URL`: URL of the Piper TTS service (default: `http://piper-tts:5001`)

### Docker Configuration
The service runs in a Docker container with:
- **Port**: 5003 (exposed to host)
- **Dependencies**: Requires `piper-tts` service
- **Network**: Connected to `mumble-ai-network`

## Troubleshooting

### Common Issues

#### "Text must be a string" Error
- **Cause**: Frontend sending incorrect data format
- **Solution**: Ensure text input is properly captured from the textarea

#### Voice Not Found Error
- **Cause**: Selected voice doesn't exist in catalog
- **Solution**: Refresh the page and select a valid voice

#### TTS Generation Failed
- **Cause**: Piper TTS service unavailable or error
- **Solution**: Check Piper TTS service logs and ensure it's running

#### Audio Player Not Working
- **Cause**: Browser doesn't support WAV format or file corruption
- **Solution**: Try a different browser or regenerate the audio

### Debugging

#### Check Service Status
```bash
docker-compose ps tts-web-interface
```

#### View Logs
```bash
docker-compose logs -f tts-web-interface
```

#### Test API Endpoints
```bash
# Test voice catalog
curl http://localhost:5003/api/voices

# Test synthesis
curl -X POST http://localhost:5003/api/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "en_US-lessac-medium"}' \
  --output test.wav
```

## Development

### Local Development
1. **Install Dependencies**: `pip install -r requirements.txt`
2. **Set Environment**: `export PIPER_TTS_URL=http://localhost:5001`
3. **Run Application**: `python app.py`
4. **Access**: `http://localhost:5003`

### Building Docker Image
```bash
docker build -t tts-web-interface ./tts-web-interface
```

### Code Structure
```
tts-web-interface/
├── app.py                 # Flask backend
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container definition
├── templates/
│   └── index.html        # Main HTML template
└── static/
    ├── css/
    │   └── style.css     # Stylesheet
    └── js/
        └── app.js        # JavaScript application
```

## Contributing

When contributing to the TTS Voice Generator:

1. **Follow Code Style**: Use consistent formatting and naming
2. **Add Error Handling**: Include proper error handling for new features
3. **Test Thoroughly**: Test on multiple browsers and devices
4. **Update Documentation**: Keep this documentation current
5. **Consider Accessibility**: Ensure the interface is accessible to all users

## License

This project is part of the Mumble-AI system and follows the same MIT license.
