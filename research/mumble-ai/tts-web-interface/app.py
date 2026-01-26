from flask import Flask, render_template, request, jsonify, send_file
import requests
import tempfile
import os
import logging
import json
from typing import Dict, List, Optional
from pydub import AudioSegment

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration
PIPER_TTS_URL = os.getenv('PIPER_TTS_URL', 'http://piper-tts:5001')
SILERO_TTS_URL = os.getenv('SILERO_TTS_URL', 'http://silero-tts:5004')
CHATTERBOX_TTS_URL = os.getenv('CHATTERBOX_TTS_URL', 'http://chatterbox-tts:5005')
PORT = int(os.getenv('PORT', 5003))

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'mumble_ai'),
    'user': os.getenv('DB_USER', 'mumbleai'),
    'password': os.getenv('DB_PASSWORD', 'mumbleai123')
}

# Comprehensive voice catalog with metadata
VOICE_CATALOG = {
    "en_US": {
        "name": "English (US)",
        "voices": {
            "female": [
                {"id": "en_US-lessac-medium", "name": "Lessac (Medium)", "quality": "medium"},
                {"id": "en_US-lessac-high", "name": "Lessac (High)", "quality": "high"},
                {"id": "en_US-amy-medium", "name": "Amy (Medium)", "quality": "medium"},
                {"id": "en_US-amy-low", "name": "Amy (Low)", "quality": "low"},
                {"id": "en_US-hfc_female-medium", "name": "HFC Female (Medium)", "quality": "medium"},
                {"id": "en_US-kristin-medium", "name": "Kristin (Medium)", "quality": "medium"},
                {"id": "en_US-kathleen-low", "name": "Kathleen (Low)", "quality": "low"},
            ],
            "male": [
                {"id": "en_US-hfc_male-medium", "name": "HFC Male (Medium)", "quality": "medium"},
                {"id": "en_US-joe-medium", "name": "Joe (Medium)", "quality": "medium"},
                {"id": "en_US-bryce-medium", "name": "Bryce (Medium)", "quality": "medium"},
                {"id": "en_US-danny-low", "name": "Danny (Low)", "quality": "low"},
                {"id": "en_US-john-medium", "name": "John (Medium)", "quality": "medium"},
                {"id": "en_US-kusal-medium", "name": "Kusal (Medium)", "quality": "medium"},
            ],
            "multi": [
                {"id": "en_US-l2arctic-medium", "name": "L2 Arctic (Medium)", "quality": "medium"},
                {"id": "en_US-arctic-medium", "name": "Arctic (Medium)", "quality": "medium"},
                {"id": "en_US-libritts_r-medium", "name": "LibriTTS R (Medium)", "quality": "medium"},
                {"id": "en_US-libritts-high", "name": "LibriTTS (High)", "quality": "high"},
            ]
        }
    },
    "en_GB": {
        "name": "English (UK)",
        "voices": {
            "female": [
                {"id": "en_GB-alba-medium", "name": "Alba (Medium)", "quality": "medium"},
                {"id": "en_GB-jenny_dioco-medium", "name": "Jenny Dioco (Medium)", "quality": "medium"},
                {"id": "en_GB-southern_english_female-low", "name": "Southern English Female (Low)", "quality": "low"},
            ],
            "male": [
                {"id": "en_GB-northern_english_male-medium", "name": "Northern English Male (Medium)", "quality": "medium"},
                {"id": "en_GB-alan-low", "name": "Alan (Low)", "quality": "low"},
                {"id": "en_GB-alan-medium", "name": "Alan (Medium)", "quality": "medium"},
            ],
            "multi": [
                {"id": "en_GB-cori-medium", "name": "Cori (Medium)", "quality": "medium"},
                {"id": "en_GB-cori-high", "name": "Cori (High)", "quality": "high"},
                {"id": "en_GB-semaine-medium", "name": "Semaine (Medium)", "quality": "medium"},
                {"id": "en_GB-aru-medium", "name": "Aru (Medium)", "quality": "medium"},
                {"id": "en_GB-vctk-medium", "name": "VCTK (Medium)", "quality": "medium"},
            ]
        }
    },
    "es": {
        "name": "Spanish",
        "voices": {
            "female": [
                {"id": "es_AR-daniela-high", "name": "Daniela (Argentina, High)", "quality": "high"},
                {"id": "es_ES-mls_10246-low", "name": "MLS 10246 (Spain, Low)", "quality": "low"},
                {"id": "es_ES-mls_9972-low", "name": "MLS 9972 (Spain, Low)", "quality": "low"},
            ],
            "male": [
                {"id": "es_ES-carlfm-x_low", "name": "Carlfm (Spain, X-Low)", "quality": "x_low"},
                {"id": "es_ES-davefx-medium", "name": "Davefx (Spain, Medium)", "quality": "medium"},
                {"id": "es_ES-sharvard-medium", "name": "Sharvard (Spain, Medium)", "quality": "medium"},
                {"id": "es_MX-ald-medium", "name": "Ald (Mexico, Medium)", "quality": "medium"},
                {"id": "es_MX-claude-high", "name": "Claude (Mexico, High)", "quality": "high"},
            ]
        }
    },
    "cs_CZ": {
        "name": "Czech",
        "voices": {
            "male": [
                {"id": "cs_CZ-jirka-low", "name": "Jirka (Low)", "quality": "low"},
                {"id": "cs_CZ-jirka-medium", "name": "Jirka (Medium)", "quality": "medium"},
            ]
        }
    },
    "hi_IN": {
        "name": "Hindi (India)",
        "voices": {
            "male": [
                {"id": "hi_IN-pratham-medium", "name": "Pratham (Medium)", "quality": "medium"},
            ],
            "female": [
                {"id": "hi_IN-priyamvada-medium", "name": "Priyamvada (Medium)", "quality": "medium"},
            ]
        }
    },
    "ml_IN": {
        "name": "Malayalam (India)",
        "voices": {
            "female": [
                {"id": "ml_IN-meera-medium", "name": "Meera (Medium)", "quality": "medium"},
            ]
        }
    },
    "ne_NP": {
        "name": "Nepali",
        "voices": {
            "male": [
                {"id": "ne_NP-chitwan-medium", "name": "Chitwan (Medium)", "quality": "medium"},
                {"id": "ne_NP-google-x_low", "name": "Google (X-Low)", "quality": "x_low"},
                {"id": "ne_NP-google-medium", "name": "Google (Medium)", "quality": "medium"},
            ]
        }
    },
    "vi_VN": {
        "name": "Vietnamese",
        "voices": {
            "female": [
                {"id": "vi_VN-25hours_single-low", "name": "25hours Single (Low)", "quality": "low"},
                {"id": "vi_VN-vais1000-medium", "name": "Vais1000 (Medium)", "quality": "medium"},
                {"id": "vi_VN-vivos-x_low", "name": "Vivos (X-Low)", "quality": "x_low"},
            ]
        }
    },
    "zh_CN": {
        "name": "Chinese (Simplified)",
        "voices": {
            "female": [
                {"id": "zh_CN-huayan-x_low", "name": "Huayan (X-Low)", "quality": "x_low"},
                {"id": "zh_CN-huayan-medium", "name": "Huayan (Medium)", "quality": "medium"},
            ]
        }
    }
}

# Silero voice catalog - matches actual available voices in Silero service
SILERO_VOICE_CATALOG = {
    "en": {
        "name": "English",
        "voices": {
            "female": [
                {"id": "en_0", "name": "Clear Female - Professional", "quality": "high"},
                {"id": "en_1", "name": "Warm Female - Friendly", "quality": "high"},
                {"id": "en_5", "name": "Young Female - Energetic", "quality": "high"},
                {"id": "en_12", "name": "Mature Female - Authoritative", "quality": "high"},
                {"id": "en_18", "name": "Soft Female - Gentle", "quality": "high"},
                {"id": "en_24", "name": "Bright Female - Cheerful", "quality": "high"},
                {"id": "en_30", "name": "Professional Female", "quality": "high"},
                {"id": "en_36", "name": "Natural Female", "quality": "high"},
                {"id": "en_42", "name": "Expressive Female", "quality": "high"},
                {"id": "en_48", "name": "Calm Female", "quality": "high"},
            ],
            "male": [
                {"id": "en_2", "name": "Deep Male - Authoritative", "quality": "high"},
                {"id": "en_3", "name": "Clear Male - Professional", "quality": "high"},
                {"id": "en_6", "name": "Warm Male - Friendly", "quality": "high"},
                {"id": "en_10", "name": "Young Male - Energetic", "quality": "high"},
                {"id": "en_15", "name": "Mature Male - Deep", "quality": "high"},
                {"id": "en_20", "name": "Natural Male", "quality": "high"},
                {"id": "en_25", "name": "Smooth Male", "quality": "high"},
                {"id": "en_31", "name": "Professional Male", "quality": "high"},
                {"id": "en_37", "name": "Rich Male", "quality": "high"},
                {"id": "en_43", "name": "Strong Male", "quality": "high"},
            ]
        }
    }
}

# Audio conversion helper
def convert_audio_to_wav(input_path, output_path):
    """Convert any audio format to WAV using pydub"""
    try:
        # Detect file format from extension
        file_ext = os.path.splitext(input_path)[1].lower().replace('.', '')

        # Load audio file (pydub auto-detects format)
        audio = AudioSegment.from_file(input_path, format=file_ext if file_ext else None)

        # Export as WAV
        audio.export(output_path, format='wav')
        logging.info(f"Converted {file_ext} to WAV: {output_path}")
        return True
    except Exception as e:
        logging.error(f"Error converting audio to WAV: {str(e)}")
        return False

# Database helper functions
def get_db_connection():
    """Get database connection"""
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logging.error(f"Database connection failed: {str(e)}")
        return None

def get_cloned_voices():
    """Get all cloned voices from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, description, reference_audio_path, language, created_at, tags
            FROM chatterbox_voices
            WHERE is_active = true
            ORDER BY created_at DESC
        """)
        
        voices = []
        for row in cursor.fetchall():
            voices.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'reference_audio': row[3],
                'language': row[4],
                'created_at': row[5].isoformat() if row[5] else None,
                'tags': row[6] if row[6] else []
            })
        
        cursor.close()
        conn.close()
        return voices
        
    except Exception as e:
        logging.error(f"Error getting cloned voices: {str(e)}")
        return []

def save_cloned_voice(name, description, reference_audio_path, language='en', tags=None):
    """Save a cloned voice to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chatterbox_voices
            (name, description, reference_audio_path, language, tags, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, description, reference_audio_path, language, tags, 'web-interface'))
        
        voice_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return voice_id
        
    except Exception as e:
        logging.error(f"Error saving cloned voice: {str(e)}")
        if conn:
            conn.rollback()
        return None

@app.route('/')
def index():
    """Main TTS interface page"""
    return render_template('index.html')

@app.route('/api/voices', methods=['GET'])
def get_voices():
    """Get all available voices organized by region and gender"""
    engine = request.args.get('engine', 'piper')

    if engine == 'silero':
        return jsonify(SILERO_VOICE_CATALOG)
    elif engine == 'chatterbox':
        # Return cloned voices from database - use 'voices' key for consistency with JS
        cloned_voices = get_cloned_voices()
        return jsonify({'voices': cloned_voices})
    else:
        return jsonify(VOICE_CATALOG)

@app.route('/api/synthesize', methods=['POST'])
def synthesize():
    """Generate TTS audio using either piper-tts or silero-tts service"""
    try:
        data = request.get_json()
        logging.info(f"Received data: {data}")
        logging.info(f"Data type: {type(data)}")

        if not data or 'text' not in data or 'voice' not in data:
            return jsonify({'error': 'Text and voice are required'}), 400

        text = data['text']
        voice = data['voice']
        engine = data.get('engine', 'piper')  # Default to piper

        logging.info(f"Engine: {engine}, Text: {text}, Voice: {voice}")

        # Ensure text is a string
        if not isinstance(text, str):
            return jsonify({'error': 'Text must be a string'}), 400

        if not text.strip():
            return jsonify({'error': 'Text cannot be empty'}), 400

        # Validate voice exists (skip validation for chatterbox as they're from database)
        if engine != 'chatterbox':
            voice_found = False
            catalog = SILERO_VOICE_CATALOG if engine == 'silero' else VOICE_CATALOG

            for region_data in catalog.values():
                for gender_voices in region_data['voices'].values():
                    for voice_info in gender_voices:
                        if voice_info['id'] == voice:
                            voice_found = True
                            break
                    if voice_found:
                        break
                if voice_found:
                    break

            if not voice_found:
                return jsonify({'error': 'Invalid voice selected'}), 400

        logging.info(f"Generating TTS with {engine} for voice: {voice}, text: {text[:50]}...")

        # Route to appropriate TTS service
        if engine == 'chatterbox':
            # For Chatterbox, need to get reference audio path from database
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500

            cursor = conn.cursor()
            cursor.execute("SELECT reference_audio_path, language FROM chatterbox_voices WHERE id = %s", (voice,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if not result:
                return jsonify({'error': 'Voice not found'}), 404

            reference_audio_path, lang = result

            # Read the audio file and encode as base64 for cross-container communication
            import base64
            try:
                with open(reference_audio_path, 'rb') as audio_file:
                    audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')

                # Call Chatterbox TTS service with base64-encoded audio
                payload = {
                    "text": text,
                    "speaker_wav": f"data:audio/wav;base64,{audio_base64}",
                    "language": lang,
                    "speed": 1.0
                }
                logging.info(f"Sending payload to Chatterbox (audio size: {len(audio_base64)} bytes base64)")
            except FileNotFoundError:
                logging.error(f"Reference audio file not found: {reference_audio_path}")
                return jsonify({'error': 'Reference audio file not found'}), 404
            except Exception as e:
                logging.error(f"Error reading reference audio: {str(e)}")
                return jsonify({'error': 'Failed to read reference audio'}), 500

            tts_response = requests.post(
                f"{CHATTERBOX_TTS_URL}/api/tts",
                json=payload,
                timeout=300  # Voice cloning takes longer, especially on CPU
            )
        elif engine == 'silero':
            # Call Silero TTS service
            payload = {"text": text, "voice": voice}
            logging.info(f"Sending payload to Silero: {payload}")

            tts_response = requests.post(
                f"{SILERO_TTS_URL}/synthesize",
                json=payload,
                timeout=30
            )
        else:
            # Call Piper TTS service
            payload = {"text": text, "voice": voice}
            logging.info(f"Sending payload to Piper: {payload}")

            tts_response = requests.post(
                f"{PIPER_TTS_URL}/synthesize",
                json=payload,
                timeout=30
            )

        if tts_response.status_code != 200:
            logging.error(f"{engine.upper()} TTS error: {tts_response.text}")
            return jsonify({'error': 'TTS generation failed'}), 500

        # Create temporary file for the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file.write(tts_response.content)
            tmp_path = tmp_file.name

        # Return the audio file
        return send_file(
            tmp_path,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=f'tts_{engine}_{voice}_{hash(text) % 10000}.wav'
        )

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
        return jsonify({'error': 'Failed to connect to TTS service'}), 500
    except AttributeError as e:
        logging.error(f"Attribute error: {str(e)}")
        logging.error(f"Request data: {request.get_data()}")
        logging.error(f"Request JSON: {request.get_json()}")
        return jsonify({'error': f'Data format error: {str(e)}'}), 500
    except Exception as e:
        import traceback
        logging.error(f"Synthesis error: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temp file
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

@app.route('/api/preview', methods=['POST'])
def preview():
    """Generate a short preview of the voice"""
    try:
        data = request.get_json()
        if not data or 'voice' not in data:
            return jsonify({'error': 'Voice is required'}), 400

        voice = data['voice']
        preview_text = "Hello! This is a preview of this voice. How does it sound?"

        # Create a new request context for synthesis
        from flask import g
        g.preview_text = preview_text
        g.preview_voice = voice
        
        # Call synthesis with preview data
        return synthesize_preview(preview_text, voice)

    except Exception as e:
        logging.error(f"Preview error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def synthesize_preview(text, voice):
    """Generate TTS audio for preview using the piper-tts service"""
    try:
        logging.info(f"Generating preview for voice: {voice}, text: {text[:50]}...")
        logging.info(f"Text type: {type(text)}, Voice type: {type(voice)}")

        # Call piper-tts service
        payload = {"text": text, "voice": voice}
        logging.info(f"Sending payload to piper: {payload}")
        
        piper_response = requests.post(
            f"{PIPER_TTS_URL}/synthesize",
            json=payload,
            timeout=30
        )

        if piper_response.status_code != 200:
            logging.error(f"Piper TTS error: {piper_response.text}")
            return jsonify({'error': 'TTS generation failed'}), 500

        # Create temporary file for the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file.write(piper_response.content)
            tmp_path = tmp_file.name

        # Return the audio file
        return send_file(
            tmp_path,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=f'preview_{voice}_{hash(text) % 10000}.wav'
        )

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
        return jsonify({'error': 'Failed to connect to TTS service'}), 500
    except Exception as e:
        import traceback
        logging.error(f"Preview synthesis error: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temp file
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

@app.route('/api/chatterbox/clone', methods=['POST'])
def clone_voice():
    """Clone a voice using reference audio"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        text = request.form.get('text', 'Hello! This is a preview of the cloned voice.')
        language = request.form.get('language', 'en')
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save audio file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.filename)[1]) as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_original_path = tmp_file.name

        # Convert to WAV if not already WAV
        tmp_audio_path = tmp_original_path
        if not tmp_original_path.lower().endswith('.wav'):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_wav:
                tmp_audio_path = tmp_wav.name
            if not convert_audio_to_wav(tmp_original_path, tmp_audio_path):
                os.unlink(tmp_original_path)
                return jsonify({'error': 'Failed to convert audio to WAV format'}), 500
            os.unlink(tmp_original_path)  # Clean up original

        try:
            # Read the audio file and encode as base64
            import base64
            with open(tmp_audio_path, 'rb') as audio_file:
                audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')

            # Test the voice cloning with Chatterbox
            payload = {
                "text": text,
                "speaker_wav": f"data:audio/wav;base64,{audio_base64}",
                "language": language,
                "speed": 1.0
            }

            logging.info(f"Sending voice cloning request to Chatterbox (audio size: {len(audio_base64)} bytes base64)")

            tts_response = requests.post(
                f"{CHATTERBOX_TTS_URL}/api/tts",
                json=payload,
                timeout=300  # Voice cloning with XTTS-v2 can take several minutes
            )
            
            if tts_response.status_code != 200:
                return jsonify({'error': 'Voice cloning failed', 'details': tts_response.text}), 500
            
            # Create temporary file for the audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_output:
                tmp_output.write(tts_response.content)
                tmp_output_path = tmp_output.name
            
            # Return the cloned audio
            return send_file(
                tmp_output_path,
                mimetype='audio/wav',
                as_attachment=True,
                download_name='cloned_voice_preview.wav'
            )
            
        finally:
            # Clean up temp files
            if os.path.exists(tmp_audio_path):
                os.unlink(tmp_audio_path)
            if 'tmp_output_path' in locals() and os.path.exists(tmp_output_path):
                try:
                    os.unlink(tmp_output_path)
                except:
                    pass
                    
    except Exception as e:
        logging.error(f"Voice cloning error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chatterbox/save', methods=['POST'])
def save_voice():
    """Save a cloned voice to the library"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        name = request.form.get('name')
        description = request.form.get('description', '')
        language = request.form.get('language', 'en')

        # Parse tags - can be JSON string or list
        tags_input = request.form.get('tags', '[]')
        try:
            tags = json.loads(tags_input) if isinstance(tags_input, str) else tags_input
        except json.JSONDecodeError:
            # If not valid JSON, treat as comma-separated string
            tags = [t.strip() for t in tags_input.split(',') if t.strip()]

        if not name:
            return jsonify({'error': 'Voice name is required'}), 400

        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Save audio file to permanent storage
        upload_dir = '/app/cloned_voices'
        os.makedirs(upload_dir, exist_ok=True)

        # Generate unique filename (always .wav)
        import hashlib
        import time
        filename = f"{hashlib.md5(name.encode()).hexdigest()}_{int(time.time())}.wav"
        audio_path = os.path.join(upload_dir, filename)

        # Save to temp first, then convert if needed
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.filename)[1]) as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_audio_path = tmp_file.name

        # Convert to WAV if not already WAV
        if not tmp_audio_path.lower().endswith('.wav'):
            if not convert_audio_to_wav(tmp_audio_path, audio_path):
                os.unlink(tmp_audio_path)
                return jsonify({'error': 'Failed to convert audio to WAV format'}), 500
            os.unlink(tmp_audio_path)
        else:
            # Just move the file if it's already WAV
            import shutil
            shutil.move(tmp_audio_path, audio_path)

        # Save to database
        voice_id = save_cloned_voice(name, description, audio_path, language, tags)

        if voice_id:
            return jsonify({
                'success': True,
                'voice_id': voice_id,
                'message': 'Voice saved successfully'
            }), 200
        else:
            return jsonify({'error': 'Failed to save voice to database'}), 500

    except Exception as e:
        logging.error(f"Save voice error: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chatterbox/voices', methods=['GET'])
def get_chatterbox_voices():
    """Get all cloned voices"""
    try:
        voices = get_cloned_voices()
        return jsonify({'voices': voices}), 200
    except Exception as e:
        logging.error(f"Get voices error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chatterbox/voices/<int:voice_id>', methods=['DELETE'])
def delete_voice(voice_id):
    """Delete a cloned voice"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        # Soft delete by setting is_active to false
        cursor.execute("""
            UPDATE chatterbox_voices 
            SET is_active = false 
            WHERE id = %s
        """, (voice_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Voice deleted successfully'}), 200
        
    except Exception as e:
        logging.error(f"Delete voice error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'tts-web-interface'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
