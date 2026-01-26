from flask import Flask, request, send_file, jsonify
import torch
import torchaudio
import tempfile
import os
import logging
import psycopg2
import io

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'mumble_ai')
DB_USER = os.getenv('DB_USER', 'mumbleai')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'mumbleai123')

# Use CUDA if available, otherwise CPU
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
logging.info(f"Using device: {device}")

# Load Silero model
MODEL_PATH = '/app/models/en_v4.pt'
model = None
sample_rate = 24000  # Silero v4 uses 24kHz

# Voice metadata - subset of best voices (mix of male and female)
AVAILABLE_VOICES = {
    # Female voices - clear and natural
    'en_0': {'gender': 'female', 'description': 'Clear female voice, professional'},
    'en_1': {'gender': 'female', 'description': 'Warm female voice, friendly'},
    'en_5': {'gender': 'female', 'description': 'Young female voice, energetic'},
    'en_12': {'gender': 'female', 'description': 'Mature female voice, authoritative'},
    'en_18': {'gender': 'female', 'description': 'Soft female voice, gentle'},
    'en_24': {'gender': 'female', 'description': 'Bright female voice, cheerful'},
    'en_30': {'gender': 'female', 'description': 'Professional female voice'},
    'en_36': {'gender': 'female', 'description': 'Natural female voice'},
    'en_42': {'gender': 'female', 'description': 'Expressive female voice'},
    'en_48': {'gender': 'female', 'description': 'Calm female voice'},

    # Male voices - clear and natural
    'en_2': {'gender': 'male', 'description': 'Deep male voice, authoritative'},
    'en_3': {'gender': 'male', 'description': 'Clear male voice, professional'},
    'en_6': {'gender': 'male', 'description': 'Warm male voice, friendly'},
    'en_10': {'gender': 'male', 'description': 'Young male voice, energetic'},
    'en_15': {'gender': 'male', 'description': 'Mature male voice, deep'},
    'en_20': {'gender': 'male', 'description': 'Natural male voice'},
    'en_25': {'gender': 'male', 'description': 'Smooth male voice'},
    'en_31': {'gender': 'male', 'description': 'Professional male voice'},
    'en_37': {'gender': 'male', 'description': 'Rich male voice'},
    'en_43': {'gender': 'male', 'description': 'Strong male voice'},
}

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_current_voice():
    """Get the current Silero voice from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_config WHERE key = 'silero_voice'")
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            voice_id = result[0]
            if voice_id in AVAILABLE_VOICES:
                return voice_id
            else:
                logging.warning(f"Voice {voice_id} not found, using default")
                return 'en_0'
        else:
            return 'en_0'
    except Exception as e:
        logging.error(f"Error getting current voice: {e}")
        return 'en_0'

def load_model():
    """Load the Silero model (downloads if not present)"""
    global model
    try:
        logging.info("Loading Silero TTS model...")

        # Use torch.hub to download/load the model (handles caching automatically)
        model, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-models',
            model='silero_tts',
            language='en',
            speaker='v3_en',
            force_reload=False
        )

        model.to(device)
        logging.info(f"Silero model loaded successfully on {device}")
    except Exception as e:
        logging.error(f"Error loading model: {e}")
        raise

# Load model on startup
load_model()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'device': str(device)
    }), 200

@app.route('/voices', methods=['GET'])
def get_voices():
    """Get list of available voices"""
    voices = []
    for voice_id, metadata in AVAILABLE_VOICES.items():
        voices.append({
            'id': voice_id,
            'gender': metadata['gender'],
            'description': metadata['description']
        })
    return jsonify({'voices': voices}), 200

@app.route('/synthesize', methods=['POST'])
def synthesize():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        text = data['text']
        voice_id = data.get('voice')  # Optional voice parameter

        logging.info(f"Received request - text: {text[:50]}...")
        logging.info(f"Received voice_id: {voice_id}, type: {type(voice_id)}")
        logging.info(f"Full request data: {data}")

        # Ensure text is a string
        if not isinstance(text, str):
            logging.error(f"Text is not a string: {type(text)} = {text}")
            return jsonify({'error': 'Text must be a string'}), 400

        # Get voice - use specified voice or current default
        if voice_id and voice_id in AVAILABLE_VOICES:
            speaker = voice_id
            logging.info(f"Voice {voice_id} found in AVAILABLE_VOICES")
        else:
            speaker = get_current_voice()
            logging.info(f"Voice {voice_id} NOT found in AVAILABLE_VOICES or was None, using default: {speaker}")

        logging.info(f"Using voice: {speaker} on {device}")

        # Generate audio with Silero
        with torch.no_grad():
            audio = model.apply_tts(
                text=text,
                speaker=speaker,
                sample_rate=sample_rate,
                put_accent=True,
                put_yo=True
            )

        # Convert to WAV format
        audio_tensor = torch.tensor(audio).unsqueeze(0)

        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            output_path = tmp_file.name

        try:
            # Save as WAV
            torchaudio.save(
                output_path,
                audio_tensor,
                sample_rate,
                format='wav'
            )

            # Return the audio file
            return send_file(
                output_path,
                mimetype='audio/wav',
                as_attachment=True,
                download_name='speech.wav'
            )

        finally:
            # Clean up temp file after sending
            if os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                except:
                    pass

    except Exception as e:
        logging.error(f"Synthesis error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=False)
