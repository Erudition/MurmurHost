#!/usr/bin/env python3
"""
Chatterbox TTS Service
A voice cloning TTS service with CUDA support and CPU fallback
"""

import os
import io
import sys
import json
import logging
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import torch
import numpy as np
import soundfile as sf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
PORT = int(os.environ.get('PORT', 5005))
DEVICE = os.environ.get('DEVICE', 'auto')
MODEL_DIR = os.environ.get('MODEL_DIR', '/app/models')

# Database configuration (optional)
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'postgres'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'mumble_ai'),
    'user': os.environ.get('DB_USER', 'mumbleai'),
    'password': os.environ.get('DB_PASSWORD', 'mumbleai123')
}

# Global TTS model
tts_model = None
current_device = None


def get_device():
    """Determine the best available device (CUDA or CPU)"""
    global current_device
    
    if current_device:
        return current_device
    
    if DEVICE == 'cuda':
        if torch.cuda.is_available():
            current_device = 'cuda'
            logger.info(f"Using CUDA device: {torch.cuda.get_device_name(0)}")
        else:
            logger.warning("CUDA requested but not available, falling back to CPU")
            current_device = 'cpu'
    elif DEVICE == 'cpu':
        current_device = 'cpu'
        logger.info("Using CPU device")
    else:  # auto
        if torch.cuda.is_available():
            current_device = 'cuda'
            logger.info(f"Auto-selected CUDA device: {torch.cuda.get_device_name(0)}")
        else:
            current_device = 'cpu'
            logger.info("Auto-selected CPU device (CUDA not available)")
    
    return current_device


def initialize_tts_model():
    """Initialize the TTS model"""
    global tts_model
    
    try:
        from TTS.api import TTS as TTSModel
        
        device = get_device()
        
        # Use XTTS-v2 model for voice cloning
        model_name = os.environ.get('TTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2')
        
        # Set environment variable to agree to CPML license (non-commercial use)
        os.environ['COQUI_TOS_AGREED'] = '1'
        
        logger.info(f"Loading TTS model: {model_name} on device: {device}")
        tts_model = TTSModel(model_name, progress_bar=False).to(device)
        logger.info("TTS model loaded successfully")
        
        return True
    except Exception as e:
        logger.error(f"Failed to initialize TTS model: {str(e)}")
        return False


def get_db_connection():
    """Get database connection (optional)"""
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.warning(f"Database connection failed: {str(e)}")
        return None


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    device = get_device()
    
    health_status = {
        'status': 'healthy',
        'service': 'chatterbox-tts',
        'device': device,
        'cuda_available': torch.cuda.is_available(),
        'model_loaded': tts_model is not None
    }
    
    if torch.cuda.is_available():
        health_status['cuda_version'] = torch.version.cuda
        health_status['gpu_name'] = torch.cuda.get_device_name(0)
        health_status['gpu_memory_allocated'] = torch.cuda.memory_allocated(0)
        health_status['gpu_memory_reserved'] = torch.cuda.memory_reserved(0)
    
    status_code = 200 if tts_model is not None else 503
    return jsonify(health_status), status_code


@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    """
    Generate speech from text using voice cloning
    
    Request JSON:
    {
        "text": "Text to synthesize",
        "speaker_wav": "path/to/reference/audio.wav" or base64 encoded audio,
        "language": "en" (optional, default: "en"),
        "speed": 1.0 (optional)
    }
    """
    global tts_model
    
    if tts_model is None:
        return jsonify({'error': 'TTS model not initialized'}), 503
    
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'Missing required field: text'}), 400
        
        text = data['text']
        language = data.get('language', 'en')
        speed = float(data.get('speed', 1.0))
        
        # Handle speaker reference audio
        speaker_wav = data.get('speaker_wav')
        
        if not speaker_wav:
            return jsonify({'error': 'Missing speaker_wav for voice cloning'}), 400
        
        # Create temporary file for output
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_output:
            output_path = temp_output.name
        
        # Generate speech
        logger.info(f"Generating speech for text: {text[:50]}...")
        
        tts_model.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=language,
            file_path=output_path,
            speed=speed
        )
        
        # Read generated audio
        audio_data, sample_rate = sf.read(output_path)
        
        # Convert to bytes
        audio_io = io.BytesIO()
        sf.write(audio_io, audio_data, sample_rate, format='WAV')
        audio_io.seek(0)
        
        # Clean up temporary file
        os.unlink(output_path)
        
        logger.info("Speech generated successfully")
        
        return send_file(
            audio_io,
            mimetype='audio/wav',
            as_attachment=False,
            download_name='output.wav'
        )
        
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/models', methods=['GET'])
def list_models():
    """List available TTS models"""
    try:
        from TTS.api import TTS as TTSModel
        
        # Get list of available models
        models = TTSModel().list_models()
        
        return jsonify({
            'models': models,
            'current_model': os.environ.get('TTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2')
        })
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/voices', methods=['GET'])
def list_voices():
    """List available voice presets (if stored in database)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'voices': []})
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, description, reference_audio_path
            FROM chatterbox_voices
            ORDER BY name
        """)
        
        voices = []
        for row in cursor.fetchall():
            voices.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'reference_audio': row[3]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({'voices': voices})
        
    except Exception as e:
        logger.warning(f"Error listing voices: {str(e)}")
        return jsonify({'voices': []})


@app.route('/api/info', methods=['GET'])
def get_info():
    """Get service information"""
    device = get_device()
    
    info = {
        'service': 'Chatterbox TTS Service',
        'version': '1.0.0',
        'device': device,
        'cuda_available': torch.cuda.is_available(),
        'model_loaded': tts_model is not None,
        'supported_languages': ['en', 'es', 'fr', 'de', 'it', 'pt', 'pl', 'tr', 'ru', 'nl', 'cs', 'ar', 'zh-cn', 'ja', 'hu', 'ko'],
        'features': [
            'Voice cloning',
            'Multi-language support',
            'Adjustable speed',
            'High-quality synthesis'
        ]
    }
    
    if torch.cuda.is_available():
        info['gpu_info'] = {
            'name': torch.cuda.get_device_name(0),
            'memory_total': torch.cuda.get_device_properties(0).total_memory,
            'cuda_version': torch.version.cuda
        }
    
    return jsonify(info)


if __name__ == '__main__':
    logger.info("Starting Chatterbox TTS Service...")
    logger.info(f"Device configuration: {DEVICE}")
    
    # Initialize TTS model
    if not initialize_tts_model():
        logger.error("Failed to initialize TTS model, service may not work correctly")
    
    # Start Flask server
    app.run(host='0.0.0.0', port=PORT, debug=False)

