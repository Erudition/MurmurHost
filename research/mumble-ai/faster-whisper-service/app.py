from flask import Flask, request, jsonify
from faster_whisper import WhisperModel, download_model
import os
import tempfile
import logging
import sys
import time
import threading

# Configure environment for better download visibility
os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '0'  # Disable hf_transfer
os.environ['HF_HUB_DISABLE_XET_BACKEND'] = '1'  # Disable XET backend (use regular HTTP)

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Also set huggingface_hub logger to INFO
logging.getLogger('huggingface_hub').setLevel(logging.INFO)
logging.getLogger('huggingface_hub.file_download').setLevel(logging.INFO)

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Initialize model
model_size = os.getenv('MODEL_SIZE', 'base')
device = os.getenv('DEVICE', 'cpu')
compute_type = "int8"

logger.info("=" * 80)
logger.info(f"Faster Whisper Service - Starting Up")
logger.info("=" * 80)
logger.info(f"Model: {model_size}")
logger.info(f"Device: {device}")
logger.info(f"Compute Type: {compute_type}")
logger.info("=" * 80)

try:
    logger.info("📥 Downloading/Loading model from Hugging Face...")
    logger.info(f"Model size: ~3GB for 'large', ~140MB for 'base'")
    logger.info("Download progress will be shown below...")
    logger.info("")

    # Download model first (this will show progress)
    start_time = time.time()
    logger.info(f"Fetching model files for: {model_size}...")

    # Initialize model (downloads if needed)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    load_time = time.time() - start_time

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"✓ Model '{model_size}' loaded successfully!")
    logger.info(f"✓ Load time: {load_time:.1f} seconds")
    logger.info(f"✓ Running on: {device.upper()}")
    logger.info(f"✓ Service ready to accept transcription requests on port 5000")
    logger.info("=" * 80)
except Exception as e:
    logger.error("=" * 80)
    logger.error(f"✗ Failed to load model: {e}")
    logger.error("=" * 80)
    import traceback
    traceback.print_exc()
    raise


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200


@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']

        # Get optional language parameter from form data
        language = request.form.get('language', None)
        if language and language.lower() == 'auto':
            language = None  # None means auto-detect

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_path = tmp_file.name

        try:
            # Transcribe with beam_size=1 for faster performance
            # Pass language parameter if specified (None for auto-detection)
            segments, info = model.transcribe(tmp_path, beam_size=1, language=language)

            # Collect all segments
            text = ' '.join([segment.text for segment in segments])

            logging.info(f"Transcribed: {text} (language: {info.language})")

            return jsonify({
                'text': text.strip(),
                'language': info.language,
                'language_probability': info.language_probability
            }), 200

        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except Exception as e:
        logging.error(f"Transcription error: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
