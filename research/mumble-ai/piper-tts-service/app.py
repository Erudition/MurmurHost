from flask import Flask, request, send_file, jsonify
import subprocess
import tempfile
import os
import logging
import psycopg2

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'mumble_ai')
DB_USER = os.getenv('DB_USER', 'mumbleai')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'mumbleai123')

DEFAULT_MODEL_PATH = "/app/models/en_US-lessac-medium.onnx"


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def get_current_voice():
    """Get the current voice model from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_config WHERE key = 'piper_voice'")
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            voice_name = result[0]
            model_path = f"/app/models/{voice_name}.onnx"

            # Check if the model file exists
            if os.path.exists(model_path):
                return model_path
            else:
                logging.warning(f"Voice model {model_path} not found, using default")
                return DEFAULT_MODEL_PATH
        else:
            return DEFAULT_MODEL_PATH
    except Exception as e:
        logging.error(f"Error getting current voice: {e}")
        return DEFAULT_MODEL_PATH


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200


@app.route('/synthesize', methods=['POST'])
def synthesize():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        text = data['text']
        voice_id = data.get('voice')  # Optional voice parameter
        
        logging.info(f"Received data: {data}")
        logging.info(f"Text type: {type(text)}, Text value: {text}")
        logging.info(f"Voice type: {type(voice_id)}, Voice value: {voice_id}")
        
        # Ensure text is a string
        if not isinstance(text, str):
            logging.error(f"Text is not a string: {type(text)} = {text}")
            return jsonify({'error': 'Text must be a string'}), 400
        
        logging.info(f"Synthesizing: {text[:50]}...")

        # Get voice model - use specified voice or current default
        if voice_id:
            model_path = f"/app/models/{voice_id}.onnx"
            if not os.path.exists(model_path):
                logging.warning(f"Voice model {model_path} not found, using default")
                model_path = get_current_voice()
        else:
            model_path = get_current_voice()
            
        logging.info(f"Using voice model: {model_path}")

        # Create temporary output file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            output_path = tmp_file.name

        try:
            # Run piper TTS
            result = subprocess.run(
                ['piper', '--model', model_path, '--output_file', output_path],
                input=text,
                text=True,
                capture_output=True,
                check=True
            )

            # Return the audio file
            return send_file(
                output_path,
                mimetype='audio/wav',
                as_attachment=True,
                download_name='speech.wav'
            )

        except subprocess.CalledProcessError as e:
            logging.error(f"Piper error: {e.stderr}")
            return jsonify({'error': f'TTS failed: {e.stderr}'}), 500

        finally:
            # Clean up temp file after sending
            if os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                except:
                    pass

    except Exception as e:
        logging.error(f"Synthesis error: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
