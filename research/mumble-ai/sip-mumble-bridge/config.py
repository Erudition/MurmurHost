import os

# SIP Configuration
SIP_PORT = int(os.getenv('SIP_PORT', '5060'))
SIP_USERNAME = os.getenv('SIP_USERNAME', 'mumble-bridge')
SIP_PASSWORD = os.getenv('SIP_PASSWORD', 'bridge123')
SIP_DOMAIN = os.getenv('SIP_DOMAIN', '*')  # Accept calls from any domain

# RTP Configuration
RTP_PORT_MIN = int(os.getenv('RTP_PORT_MIN', '10000'))
RTP_PORT_MAX = int(os.getenv('RTP_PORT_MAX', '10010'))

# Optional legacy Mumble configuration (kept for compatibility; not used by SIP AI pipeline)
MUMBLE_HOST = os.getenv('MUMBLE_HOST', 'mumble-server')
MUMBLE_PORT = int(os.getenv('MUMBLE_PORT', '64738'))
MUMBLE_USERNAME = os.getenv('MUMBLE_USERNAME', 'Phone-Bridge')
MUMBLE_PASSWORD = os.getenv('MUMBLE_PASSWORD', '')
MUMBLE_CHANNEL = os.getenv('MUMBLE_CHANNEL', 'Root')  # Channel to join

# AI Service Endpoints
WHISPER_URL = os.getenv('WHISPER_URL', 'http://faster-whisper:5000')
PIPER_URL = os.getenv('PIPER_URL', 'http://piper-tts:5001')
SILERO_URL = os.getenv('SILERO_URL', 'http://silero-tts:5004')

# Database Configuration (shared with mumble-bot)
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'mumble_ai')
DB_USER = os.getenv('DB_USER', 'mumbleai')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'mumbleai123')

# Optional defaults if DB lookup fails
DEFAULT_OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://host.docker.internal:11434')
DEFAULT_OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama2')

# Audio Configuration
SAMPLE_RATE = 48000  # Mumble uses 48kHz
FRAME_SIZE = 960     # 20ms at 48kHz
CHANNELS = 1         # Mono

# Voice Activity Detection Configuration
# Set VOICE_THRESHOLD to override automatic calibration (useful for cellular debugging)
# Set to 0 or leave unset to use adaptive calibration
# Typical values: 100 for internal calls, 40-80 for cellular calls
VOICE_THRESHOLD = int(os.getenv('VOICE_THRESHOLD', '0'))
SILENCE_THRESHOLD = float(os.getenv('SILENCE_THRESHOLD', '2.0'))  # seconds of silence to end utterance

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
