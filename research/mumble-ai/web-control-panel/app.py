from flask import Flask, render_template, jsonify, request
import psycopg2
import os
import requests
import json
import subprocess
import pytz
import uuid
import redis
import chromadb
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'mumble_ai')
DB_USER = os.getenv('DB_USER', 'mumbleai')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'mumbleai123')

# Memory system configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
CHROMADB_URL = os.getenv('CHROMADB_URL', 'http://chromadb:8000')

# Timezone configuration
NY_TZ = pytz.timezone('America/New_York')

def format_timestamp_ny(timestamp):
    """Convert UTC timestamp to NY time and format as ISO string"""
    if timestamp is None:
        return None
    # Ensure timezone-aware (assume UTC if naive)
    if timestamp.tzinfo is None:
        timestamp = pytz.utc.localize(timestamp)
    # Convert to NY time
    ny_time = timestamp.astimezone(NY_TZ)
    return ny_time.isoformat()

def get_redis_connection():
    """Get Redis connection for memory system monitoring"""
    try:
        return redis.from_url(REDIS_URL)
    except Exception as e:
        print(f"Redis connection error: {e}")
        return None

def get_chromadb_client():
    """Get ChromaDB client for memory system monitoring"""
    try:
        # Parse the URL properly
        url_parts = CHROMADB_URL.replace('http://', '').split(':')
        host = url_parts[0]
        port = int(url_parts[1]) if len(url_parts) > 1 else 8000
        return chromadb.HttpClient(host=host, port=port)
    except Exception as e:
        print(f"ChromaDB connection error: {e}")
        return None

# Config storage in database
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def init_config_table():
    """Initialize config table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Initialize schedule_events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_events (
            id SERIAL PRIMARY KEY,
            user_name VARCHAR(255) NOT NULL,
            title VARCHAR(500) NOT NULL,
            event_date DATE NOT NULL,
            event_time TIME,
            description TEXT,
            importance INTEGER DEFAULT 5 CHECK (importance >= 1 AND importance <= 10),
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert default values if not exists
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('ollama_url', 'http://host.docker.internal:11434')
        ON CONFLICT (key) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('ollama_model', 'llama3.2:latest')
        ON CONFLICT (key) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('ollama_vision_model', 'moondream:latest')
        ON CONFLICT (key) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('piper_voice', 'en_US-lessac-medium')
        ON CONFLICT (key) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('bot_persona', '')
        ON CONFLICT (key) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('whisper_language', 'auto')
        ON CONFLICT (key) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('tts_engine', 'piper')
        ON CONFLICT (key) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('silero_voice', 'en_0')
        ON CONFLICT (key) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO bot_config (key, value) VALUES ('chatterbox_voice', '1')
        ON CONFLICT (key) DO NOTHING
    """)

    conn.commit()
    cursor.close()
    conn.close()

# Initialize on startup
init_config_table()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schedule')
def schedule():
    return render_template('schedule.html')

@app.route('/memory')
def memory():
    return render_template('memory.html')

# Memory System API Endpoints
@app.route('/api/memory/status', methods=['GET'])
def get_memory_status():
    """Get status of all memory system components"""
    try:
        status = {}

        # Test ChromaDB
        try:
            chroma_client = get_chromadb_client()
            if chroma_client:
                heartbeat = chroma_client.heartbeat()
                collections = chroma_client.list_collections()
                status['chromadb'] = {
                    'status': 'healthy',
                    'info': {
                        'heartbeat': heartbeat,
                        'collections': len(collections)
                    }
                }
            else:
                status['chromadb'] = {'status': 'error', 'error': 'Failed to connect'}
        except Exception as e:
            status['chromadb'] = {'status': 'error', 'error': str(e)}

        # Test Redis
        try:
            redis_client = get_redis_connection()
            if redis_client:
                redis_client.ping()
                info = redis_client.info('memory')
                status['redis'] = {
                    'status': 'healthy',
                    'info': {
                        'used_memory': info.get('used_memory_human', 'N/A'),
                        'connected_clients': redis_client.info('clients').get('connected_clients', 0),
                        'keyspace_hits': redis_client.info('stats').get('keyspace_hits', 0),
                        'keyspace_misses': redis_client.info('stats').get('keyspace_misses', 0)
                    }
                }
            else:
                status['redis'] = {'status': 'error', 'error': 'Failed to connect'}
        except Exception as e:
            status['redis'] = {'status': 'error', 'error': str(e)}

        # Test PostgreSQL
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            status['postgresql'] = {
                'status': 'healthy',
                'info': {}
            }
        except Exception as e:
            status['postgresql'] = {'status': 'error', 'error': str(e)}

        # Get entity stats from database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get total count
            cursor.execute("SELECT COUNT(*) FROM entity_mentions")
            entity_count = cursor.fetchone()[0]

            # Get recent entities
            cursor.execute("""
                SELECT entity_text, entity_type, created_at
                FROM entity_mentions
                ORDER BY created_at DESC
                LIMIT 5
            """)
            recent_entities = []
            for row in cursor.fetchall():
                recent_entities.append({
                    'text': row[0],
                    'type': row[1],
                    'created_at': row[2].isoformat() if row[2] else None
                })

            cursor.close()
            conn.close()

            status['entities'] = {
                'count': entity_count,
                'recent': recent_entities
            }
        except Exception as e:
            status['entities'] = {
                'count': 0,
                'recent': [],
                'error': str(e)
            }

        # Get consolidation stats from database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get last run info
            cursor.execute("""
                SELECT run_at, messages_consolidated, summaries_created, tokens_saved_estimate
                FROM memory_consolidation_log
                ORDER BY run_at DESC
                LIMIT 1
            """)
            last_run = cursor.fetchone()

            cursor.close()
            conn.close()

            if last_run:
                status['consolidation'] = {
                    'last_run': last_run[0].isoformat() if last_run[0] else None,
                    'stats': {
                        'messages_consolidated': last_run[1],
                        'summaries_created': last_run[2],
                        'tokens_saved': last_run[3]
                    }
                }
            else:
                status['consolidation'] = {
                    'last_run': None,
                    'stats': {}
                }
        except Exception as e:
            status['consolidation'] = {
                'last_run': None,
                'stats': {},
                'error': str(e)
            }

        return create_success_response(status)

    except Exception as e:
        return create_error_response('MEMORY_STATUS_ERROR', 'Failed to get memory status', str(e)), 500

@app.route('/api/memory/entities', methods=['GET'])
def get_memory_entities():
    """Get entity mentions from database"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        user_filter = request.args.get('user')
        entity_type_filter = request.args.get('entity_type')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with filters
        query = """
            SELECT id, user_name, entity_text, canonical_id, entity_type,
                   message_id, confidence, context_info, created_at, updated_at
            FROM entity_mentions
            WHERE 1=1
        """
        count_query = "SELECT COUNT(*) FROM entity_mentions WHERE 1=1"
        params = []
        count_params = []

        if user_filter:
            query += " AND user_name = %s"
            count_query += " AND user_name = %s"
            params.append(user_filter)
            count_params.append(user_filter)

        if entity_type_filter:
            query += " AND entity_type = %s"
            count_query += " AND entity_type = %s"
            params.append(entity_type_filter)
            count_params.append(entity_type_filter)

        # Get total count
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]

        # Get paginated results
        offset = (page - 1) * per_page
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        entities = []
        for row in rows:
            entities.append({
                'id': row[0],
                'user_name': row[1],
                'entity_text': row[2],
                'canonical_id': row[3],
                'entity_type': row[4],
                'message_id': row[5],
                'confidence': row[6],
                'context_info': row[7],
                'created_at': row[8].isoformat() if row[8] else None,
                'updated_at': row[9].isoformat() if row[9] else None
            })

        cursor.close()
        conn.close()

        total_pages = (total + per_page - 1) // per_page

        return create_success_response({
            'entities': entities,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': total_pages
            }
        })
    except Exception as e:
        return create_error_response('ENTITIES_ERROR', 'Failed to get entities', str(e)), 500

@app.route('/api/memory/consolidation', methods=['GET'])
def get_memory_consolidation():
    """Get consolidation history from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get summary stats
        cursor.execute("""
            SELECT COUNT(*) as total_runs,
                   COALESCE(SUM(messages_consolidated), 0) as total_messages,
                   COALESCE(SUM(summaries_created), 0) as total_summaries,
                   COALESCE(SUM(tokens_saved_estimate), 0) as total_tokens
            FROM memory_consolidation_log
        """)
        summary_row = cursor.fetchone()

        summary = {
            'total_runs': summary_row[0],
            'total_messages_consolidated': summary_row[1],
            'total_summaries_created': summary_row[2],
            'total_tokens_saved': summary_row[3]
        }

        # Get recent history (last 20 runs)
        cursor.execute("""
            SELECT id, user_name, messages_consolidated, summaries_created,
                   tokens_saved_estimate, cutoff_date, run_at
            FROM memory_consolidation_log
            ORDER BY run_at DESC
            LIMIT 20
        """)
        history_rows = cursor.fetchall()

        history = []
        for row in history_rows:
            history.append({
                'id': row[0],
                'user_name': row[1],
                'messages_consolidated': row[2],
                'summaries_created': row[3],
                'tokens_saved_estimate': row[4],
                'cutoff_date': row[5].isoformat() if row[5] else None,
                'run_at': row[6].isoformat() if row[6] else None
            })

        cursor.close()
        conn.close()

        return create_success_response({
            'summary': summary,
            'history': history
        })
    except Exception as e:
        return create_error_response('CONSOLIDATION_ERROR', 'Failed to get consolidation data', str(e)), 500

@app.route('/api/memory/consolidation/run', methods=['POST'])
def run_consolidation():
    """Trigger memory consolidation for old conversations"""
    try:
        data = request.get_json() or {}
        cutoff_days = data.get('cutoff_days', 7)
        user_name = data.get('user_name')  # Optional: consolidate for specific user

        logger.info(f"Starting manual consolidation: cutoff_days={cutoff_days}, user={user_name or 'all'}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=cutoff_days)

        # Get users with old messages to consolidate
        if user_name:
            user_filter = "AND user_name = %s"
            user_params = [cutoff_date, user_name]
        else:
            user_filter = ""
            user_params = [cutoff_date]

        cursor.execute(f"""
            SELECT DISTINCT user_name
            FROM conversation_history
            WHERE timestamp < %s
            {user_filter}
            AND role = 'user'
        """, user_params)

        users_to_consolidate = [row[0] for row in cursor.fetchall()]

        if not users_to_consolidate:
            cursor.close()
            conn.close()
            return create_success_response({
                'message': 'No old conversations to consolidate',
                'messages_consolidated': 0,
                'summaries_created': 0,
                'tokens_saved': 0
            })

        total_messages_consolidated = 0
        total_summaries_created = 0
        total_tokens_saved_estimate = 0

        # Get Ollama config from bot_config
        cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
        row = cursor.fetchone()
        ollama_url = row[0] if row else os.environ.get('OLLAMA_URL', 'http://host.docker.internal:11434')

        cursor.execute("SELECT value FROM bot_config WHERE key = 'memory_extraction_model'")
        row = cursor.fetchone()
        ollama_model = row[0] if row else 'qwen2.5:3b'

        for user in users_to_consolidate:
            try:
                # Get old messages for this user
                cursor.execute("""
                    SELECT id, role, message, timestamp
                    FROM conversation_history
                    WHERE user_name = %s
                    AND timestamp < %s
                    ORDER BY timestamp ASC
                """, (user, cutoff_date))

                old_messages = cursor.fetchall()

                if len(old_messages) < 5:  # Don't consolidate if too few messages
                    logger.debug(f"Skipping {user}: only {len(old_messages)} old messages")
                    continue

                # Format conversation for summarization
                conversation_text = ""
                message_ids = []
                for msg_id, role, message, timestamp in old_messages:
                    message_ids.append(msg_id)
                    conversation_text += f"[{timestamp}] {role}: {message}\n"

                # Use Ollama to create summary
                summary_prompt = f"""Summarize this conversation history for user "{user}".
Extract the key topics discussed, important facts mentioned, and any decisions or action items.
Be concise but preserve critical information.

Conversation:
{conversation_text}

Provide a structured summary in this format:
- Main topics: [list]
- Key facts: [list]
- Important events/dates: [list]
- Action items: [list]
- Overall context: [brief description]

Summary:"""

                logger.info(f"Consolidating {len(old_messages)} messages for {user} using model: {ollama_model}")

                try:
                    response = requests.post(
                        f"{ollama_url}/api/generate",
                        json={
                            'model': ollama_model,
                            'prompt': summary_prompt,
                            'stream': False,
                            'options': {
                                'temperature': 0.3,
                                'num_predict': 1000
                            }
                        },
                        timeout=300  # 5 minute timeout
                    )

                    if response and response.status_code == 200:
                        summary = response.json().get('response', '').strip()

                        if summary:
                            # Save summary as a persistent memory
                            cursor.execute("""
                                INSERT INTO persistent_memories
                                (user_name, category, content, importance, active)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (
                                user,
                                'consolidated_history',
                                f"Summary of conversations before {cutoff_date.date()}:\n{summary}",
                                7,  # Medium-high importance
                                True
                            ))

                            # Estimate tokens saved
                            original_tokens = len(conversation_text) // 4
                            summary_tokens = len(summary) // 4
                            tokens_saved = max(0, original_tokens - summary_tokens)

                            # Delete old messages
                            cursor.execute("""
                                DELETE FROM conversation_history
                                WHERE id = ANY(%s)
                            """, (message_ids,))

                            total_messages_consolidated += len(old_messages)
                            total_summaries_created += 1
                            total_tokens_saved_estimate += tokens_saved

                            logger.info(f"Consolidated {len(old_messages)} messages for {user}, saved ~{tokens_saved} tokens")
                        else:
                            logger.warning(f"Empty summary for {user}, skipping")
                    else:
                        logger.error(f"Ollama error for {user}: {response.status_code if response else 'No response'}")

                except requests.exceptions.Timeout:
                    logger.warning(f"Consolidation timeout for {user}, skipping")
                except requests.exceptions.RequestException as e:
                    logger.error(f"Network error for {user}: {e}")

            except Exception as e:
                logger.error(f"Error consolidating for {user}: {e}", exc_info=True)

        # Log consolidation run
        if total_summaries_created > 0:
            cursor.execute("""
                INSERT INTO memory_consolidation_log
                (user_name, messages_consolidated, summaries_created, tokens_saved_estimate, cutoff_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                user_name if user_name else 'all_users',
                total_messages_consolidated,
                total_summaries_created,
                total_tokens_saved_estimate,
                cutoff_date.date()
            ))

            conn.commit()
            logger.info(f"Consolidation complete: {total_messages_consolidated} messages → {total_summaries_created} summaries")

        cursor.close()
        conn.close()

        return create_success_response({
            'message': 'Consolidation completed successfully',
            'messages_consolidated': total_messages_consolidated,
            'summaries_created': total_summaries_created,
            'tokens_saved': total_tokens_saved_estimate
        })

    except Exception as e:
        logger.error(f"Error running consolidation: {e}", exc_info=True)
        return create_error_response('CONSOLIDATION_RUN_ERROR', 'Failed to run consolidation', str(e)), 500

@app.route('/api/memory/search', methods=['GET'])
def search_memory():
    """Search conversations and entities"""
    try:
        query = request.args.get('q', '')
        limit = request.args.get('limit', 20, type=int)

        if not query:
            return create_error_response('INVALID_QUERY', 'Search query is required'), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Search conversations
        cursor.execute("""
            SELECT user_name, message, message_type, timestamp
            FROM conversation_history
            WHERE message ILIKE %s
            ORDER BY timestamp DESC
            LIMIT %s
        """, (f'%{query}%', limit))

        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                'user_name': row[0],
                'message': row[1],
                'message_type': row[2],
                'created_at': format_timestamp_ny(row[3]) if row[3] else None
            })

        cursor.close()
        conn.close()

        return create_success_response({
            'conversations': conversations,
            'entities': []  # Placeholder
        })

    except Exception as e:
        return create_error_response('SEARCH_ERROR', 'Search failed', str(e)), 500

# Ollama Management
@app.route('/api/ollama/config', methods=['GET'])
def get_ollama_config():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
    url = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
    model = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    return jsonify({'url': url, 'model': model})

@app.route('/api/ollama/config', methods=['POST'])
def update_ollama_config():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    if 'url' in data:
        cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'ollama_url'", (data['url'],))

    if 'model' in data:
        cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'ollama_model'", (data['model'],))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/ollama/models', methods=['GET'])
def get_ollama_models():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
    url = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    try:
        response = requests.get(f"{url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return jsonify({'models': [m['name'] for m in models]})
        else:
            return jsonify({'error': 'Failed to fetch models'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Vision Model Configuration
@app.route('/api/ollama/vision_config', methods=['GET'])
def get_vision_config():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_vision_model'")
    row = cursor.fetchone()
    vision_model = row[0] if row else 'moondream:latest'
    cursor.close()
    conn.close()

    return jsonify({'vision_model': vision_model})

@app.route('/api/ollama/vision_config', methods=['POST'])
def update_vision_config():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()

    if 'vision_model' in data:
        cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'ollama_vision_model'", (data['vision_model'],))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

# Memory Extraction Model Configuration
@app.route('/api/ollama/memory_model_config', methods=['GET'])
def get_memory_model_config():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'memory_extraction_model'")
    row = cursor.fetchone()
    memory_model = row[0] if row else 'qwen2.5:3b'
    cursor.close()
    conn.close()

    return jsonify({'memory_extraction_model': memory_model})

@app.route('/api/ollama/memory_model_config', methods=['POST'])
def update_memory_model_config():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()

    if 'memory_extraction_model' in data:
        cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'memory_extraction_model'", (data['memory_extraction_model'],))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/ollama/vision_models', methods=['GET'])
def get_vision_models():
    """Get available vision models from Ollama"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
    url = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    try:
        response = requests.get(f"{url}/api/tags", timeout=5)
        if response.status_code == 200:
            all_models = response.json().get('models', [])
            # Filter for vision models (models that typically support images)
            vision_keywords = ['vision', 'llava', 'moondream', 'bakllava', 'llama3.2-vision']
            vision_models = [m['name'] for m in all_models if any(keyword in m['name'].lower() for keyword in vision_keywords)]
            
            # If no vision models found, return common vision model names as suggestions
            if not vision_models:
                vision_models = ['moondream:latest', 'llava:latest', 'bakllava:latest', 'llama3.2-vision:latest']
            
            return jsonify({'models': vision_models})
        else:
            # Return default suggestions if can't connect
            return jsonify({'models': ['moondream:latest', 'llava:latest', 'bakllava:latest']})
    except Exception as e:
        # Return default suggestions on error
        return jsonify({'models': ['moondream:latest', 'llava:latest', 'bakllava:latest']})

# Conversation History
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    limit = request.args.get('limit', 100, type=int)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_name, message_type, role, message, timestamp
        FROM conversation_history
        ORDER BY timestamp DESC
        LIMIT %s
    """, (limit,))

    conversations = []
    for row in cursor.fetchall():
        conversations.append({
            'id': row[0],
            'user_name': row[1],
            'message_type': row[2],
            'role': row[3],
            'message': row[4],
            'timestamp': format_timestamp_ny(row[5])
        })

    cursor.close()
    conn.close()

    return jsonify({'conversations': conversations})

@app.route('/api/conversations/reset', methods=['POST'])
def reset_conversations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversation_history")
    deleted_count = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'deleted': deleted_count})

@app.route('/api/conversations/ai_chat', methods=['POST'])
def log_ai_chat():
    try:
        data = request.get_json()
        user_message = data.get('user_message')
        ai_response = data.get('ai_response')
        timestamp = data.get('timestamp')
        
        if not user_message or not ai_response:
            return jsonify({'error': 'Missing user_message or ai_response'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert user message
        cursor.execute("""
            INSERT INTO conversation_history (user_name, message_type, role, message, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, ('Flutter App', 'ai_chat', 'user', user_message, timestamp))
        
        # Insert AI response
        cursor.execute("""
            INSERT INTO conversation_history (user_name, message_type, role, message, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, ('AI Assistant', 'ai_chat', 'assistant', ai_response, timestamp))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"AI Chat logged - User: {user_message[:50]}... AI: {ai_response[:50]}...")
        
        return jsonify({'success': True, 'logged_messages': 2})
        
    except Exception as e:
        print(f"Error logging AI chat: {e}")
        return jsonify({'error': str(e)}), 500

# Voice metadata mapping
VOICE_METADATA = {
    # English - US
    'en_US': {'region': 'English - US', 'lang': 'English'},
    # English - GB
    'en_GB': {'region': 'English - UK', 'lang': 'English'},
    # Czech
    'cs_CZ': {'region': 'Czech', 'lang': 'Czech'},
    # Spanish
    'es_AR': {'region': 'Spanish - Argentina', 'lang': 'Spanish'},
    'es_ES': {'region': 'Spanish - Spain', 'lang': 'Spanish'},
    'es_MX': {'region': 'Spanish - Mexico', 'lang': 'Spanish'},
    # Hindi
    'hi_IN': {'region': 'Hindi - India', 'lang': 'Hindi'},
    # Malayalam
    'ml_IN': {'region': 'Malayalam - India', 'lang': 'Malayalam'},
    # Nepali
    'ne_NP': {'region': 'Nepali', 'lang': 'Nepali'},
    # Vietnamese
    'vi_VN': {'region': 'Vietnamese', 'lang': 'Vietnamese'},
    # Chinese
    'zh_CN': {'region': 'Chinese - Mandarin', 'lang': 'Chinese'},
}

# Gender indicators in voice names
FEMALE_NAMES = ['lessac', 'amy', 'kristin', 'kathleen', 'hfc_female', 'alba', 'jenny', 'female', 'daniela', 'priyamvada', 'meera']
MALE_NAMES = ['joe', 'bryce', 'danny', 'john', 'kusal', 'hfc_male', 'alan', 'male', 'carlfm', 'davefx', 'pratham']

def get_voice_gender(voice_name):
    """Determine gender from voice name"""
    voice_lower = voice_name.lower()
    for female in FEMALE_NAMES:
        if female in voice_lower:
            return 'Female'
    for male in MALE_NAMES:
        if male in voice_lower:
            return 'Male'
    return 'Neutral'

def parse_voice_name(voice_name):
    """Parse voice name into components"""
    parts = voice_name.split('-')
    if len(parts) >= 3:
        region_code = parts[0]
        speaker = parts[1]
        quality = parts[2]

        region_info = VOICE_METADATA.get(region_code, {'region': region_code, 'lang': region_code})
        gender = get_voice_gender(speaker)

        return {
            'name': voice_name,
            'region': region_info['region'],
            'language': region_info['lang'],
            'speaker': speaker,
            'quality': quality,
            'gender': gender
        }
    return {
        'name': voice_name,
        'region': 'Unknown',
        'language': 'Unknown',
        'speaker': voice_name,
        'quality': 'unknown',
        'gender': 'Neutral'
    }

# Piper Voice Management
@app.route('/api/piper/voices', methods=['GET'])
def get_piper_voices():
    voices_dir = '/app/piper_voices'
    voices = []

    if os.path.exists(voices_dir):
        for filename in os.listdir(voices_dir):
            if filename.endswith('.onnx'):
                voice_name = filename.replace('.onnx', '')
                voice_info = parse_voice_name(voice_name)
                voices.append(voice_info)

    # Sort by region, then gender, then speaker name
    voices.sort(key=lambda x: (x['region'], x['gender'], x['speaker']))

    return jsonify({'voices': voices})

@app.route('/api/piper/current', methods=['GET'])
def get_current_voice():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'piper_voice'")
    voice = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    return jsonify({'voice': voice})

@app.route('/api/piper/current', methods=['POST'])
def set_current_voice():
    data = request.json
    voice = data.get('voice')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'piper_voice'", (voice,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/piper/preview', methods=['POST'])
def preview_voice():
    """Preview a voice by generating sample audio"""
    data = request.json
    voice = data.get('voice')

    if not voice:
        return jsonify({'error': 'No voice specified'}), 400

    # Update the current voice temporarily for preview
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'piper_voice'")
    original_voice = cursor.fetchone()[0]

    # Set the voice to preview
    cursor.execute("UPDATE bot_config SET value = %s WHERE key = 'piper_voice'", (voice,))
    conn.commit()
    cursor.close()
    conn.close()

    try:
        # Generate preview audio
        preview_text = "Hello, this is a preview of this voice. How do I sound?"
        response = requests.post(
            'http://piper-tts:5001/synthesize',
            json={'text': preview_text},
            timeout=10
        )

        if response.status_code == 200:
            # Restore original voice
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE bot_config SET value = %s WHERE key = 'piper_voice'", (original_voice,))
            conn.commit()
            cursor.close()
            conn.close()

            # Return audio as response
            return response.content, 200, {'Content-Type': 'audio/wav'}
        else:
            return jsonify({'error': 'Failed to generate preview'}), 500

    except Exception as e:
        # Restore original voice on error
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE bot_config SET value = %s WHERE key = 'piper_voice'", (original_voice,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'error': str(e)}), 500

# Persona Management
@app.route('/api/persona', methods=['GET'])
def get_persona():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'bot_persona'")
    result = cursor.fetchone()
    persona = result[0] if result else ''
    cursor.close()
    conn.close()

    return jsonify({'persona': persona})

@app.route('/api/persona', methods=['POST'])
def set_persona():
    data = request.json
    persona = data.get('persona', '')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'bot_persona'", (persona,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/persona/enhance', methods=['POST'])
def enhance_persona():
    """Use Ollama to enhance the persona description"""
    data = request.json
    current_persona = data.get('persona', '')

    if not current_persona:
        return jsonify({'error': 'No persona provided'}), 400

    try:
        # Get Ollama config
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
        ollama_url = cursor.fetchone()[0]
        cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
        ollama_model = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        # Create enhancement prompt
        enhancement_prompt = f"""You are an expert at creating detailed AI assistant personas.

The user has provided this basic persona description:
"{current_persona}"

Expand and enhance this persona description to create a comprehensive, detailed character profile that an AI can use to guide its behavior and responses. Include:
- Personality traits and communication style
- Tone and manner of speaking
- Areas of expertise or interests
- How they should interact with users
- Any quirks or distinctive characteristics

Keep it concise but detailed (2-4 paragraphs). Write in second person (e.g., "You are...").

Enhanced persona:"""

        # Call Ollama
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                'model': ollama_model,
                'prompt': enhancement_prompt,
                'stream': False
            },
            timeout=60
        )

        if response.status_code == 200:
            enhanced_persona = response.json().get('response', '').strip()
            return jsonify({'enhanced_persona': enhanced_persona})
        else:
            return jsonify({'error': 'Failed to enhance persona'}), 500

    except Exception as e:
        print(f"Error enhancing persona: {e}")
        return jsonify({'error': str(e)}), 500

# Whisper Language Configuration
@app.route('/api/whisper/language', methods=['GET'])
def get_whisper_language():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'whisper_language'")
    result = cursor.fetchone()
    language = result[0] if result else 'auto'
    cursor.close()
    conn.close()

    return jsonify({'language': language})

@app.route('/api/whisper/language', methods=['POST'])
def set_whisper_language():
    data = request.json
    language = data.get('language', 'auto')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'whisper_language'", (language,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

# TTS Engine Configuration
@app.route('/api/tts/engine', methods=['GET'])
def get_tts_engine():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'tts_engine'")
    result = cursor.fetchone()
    engine = result[0] if result else 'piper'
    cursor.close()
    conn.close()

    return jsonify({'engine': engine})

@app.route('/api/tts/engine', methods=['POST'])
def set_tts_engine():
    data = request.json
    engine = data.get('engine', 'piper')

    if engine not in ['piper', 'silero', 'chatterbox']:
        return jsonify({'error': 'Invalid TTS engine'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'tts_engine'", (engine,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

# Silero Voice Configuration
@app.route('/api/silero/voices', methods=['GET'])
def get_silero_voices():
    """Get available Silero voices from the Silero service"""
    try:
        response = requests.get('http://silero-tts:5004/voices', timeout=10)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'voices': [], 'error': 'Silero service unavailable'}), 200
    except requests.exceptions.ConnectionError:
        # Service not available - return empty list instead of error
        return jsonify({'voices': [], 'error': 'Silero service not running'}), 200
    except requests.exceptions.Timeout:
        return jsonify({'voices': [], 'error': 'Silero service timeout'}), 200
    except Exception as e:
        return jsonify({'voices': [], 'error': str(e)}), 200

@app.route('/api/silero/current', methods=['GET'])
def get_current_silero_voice():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'silero_voice'")
    result = cursor.fetchone()
    voice = result[0] if result else 'en_0'
    cursor.close()
    conn.close()

    return jsonify({'voice': voice})

@app.route('/api/silero/current', methods=['POST'])
def set_current_silero_voice():
    data = request.json
    voice = data.get('voice')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'silero_voice'", (voice,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/silero/preview', methods=['POST'])
def preview_silero_voice():
    """Preview a Silero voice by generating sample audio"""
    from flask import Response
    data = request.json
    voice = data.get('voice')

    if not voice:
        return jsonify({'error': 'No voice specified'}), 400

    try:
        # Generate preview audio
        preview_text = "Hello, this is a preview of this voice. How do I sound?"
        response = requests.post(
            'http://silero-tts:5004/synthesize',
            json={'text': preview_text, 'voice': voice},
            timeout=30  # Increased timeout for Silero
        )

        if response.status_code == 200:
            # Return audio as response using Flask Response
            return Response(response.content, mimetype='audio/wav')
        else:
            return jsonify({'error': 'Failed to generate preview'}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Chatterbox Voice Configuration
@app.route('/api/chatterbox/voices', methods=['GET'])
def get_chatterbox_voices():
    """Get cloned voices from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, description, language, created_at, tags
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
                'language': row[3],
                'created_at': row[4].isoformat() if row[4] else None,
                'tags': row[5] if row[5] else []
            })

        cursor.close()
        conn.close()

        return jsonify({'voices': voices})
    except Exception as e:
        # Return empty list on error so app doesn't crash
        return jsonify({'voices': [], 'error': str(e)}), 200

@app.route('/api/chatterbox/current', methods=['GET'])
def get_current_chatterbox_voice():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'chatterbox_voice'")
    result = cursor.fetchone()
    voice = result[0] if result else '1'
    cursor.close()
    conn.close()

    return jsonify({'voice': voice})

@app.route('/api/chatterbox/current', methods=['POST'])
def set_current_chatterbox_voice():
    data = request.json
    voice = data.get('voice')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = 'chatterbox_voice'", (voice,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/chatterbox/preview', methods=['POST'])
def preview_chatterbox_voice():
    """Preview a Chatterbox cloned voice by generating sample audio"""
    from flask import Response

    data = request.json
    voice_id = data.get('voice_id')

    if not voice_id:
        return jsonify({'error': 'No voice_id specified'}), 400

    try:
        # Verify the voice exists in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id
            FROM chatterbox_voices
            WHERE id = %s AND is_active = true
        """, (voice_id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({'error': 'Voice not found'}), 404

        # Call the tts-web-interface synthesize endpoint which has access to the cloned voices
        preview_text = "Hello, this is a preview of this voice. How do I sound?"
        response = requests.post(
            'http://tts-web-interface:5003/api/synthesize',
            json={
                'text': preview_text,
                'voice': int(voice_id),  # voice parameter is the cloned voice ID
                'engine': 'chatterbox'
            },
            timeout=300  # Voice cloning can take a while
        )

        if response.status_code == 200:
            # Return audio as response using Flask Response
            return Response(response.content, mimetype='audio/wav')
        else:
            error_msg = response.json().get('error', 'Failed to generate preview') if response.content else 'Failed to generate preview'
            return jsonify({'error': error_msg}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Statistics
@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM conversation_history")
    total_messages = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT user_name) FROM conversation_history")
    unique_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM conversation_history WHERE message_type = 'voice'")
    voice_messages = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM conversation_history WHERE message_type = 'text'")
    text_messages = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return jsonify({
        'total_messages': total_messages,
        'unique_users': unique_users,
        'voice_messages': voice_messages,
        'text_messages': text_messages
    })

# Enhanced Memory APIs for Flutter
@app.route('/api/memories', methods=['GET'])
def get_memories():
    """Get persistent memories with enhanced filtering for mobile"""
    try:
        # Get query parameters
        user_name = request.args.get('user_name')  # Optional - if not provided, return all users' memories
        category = request.args.get('category')
        importance = request.args.get('importance', type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # user_name is optional - if not provided, return all users' memories

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with filters
        query = """
            SELECT id, user_name, category, content, extracted_at, importance, tags, active, event_date, event_time
            FROM persistent_memories
            WHERE active = TRUE
        """
        params = []

        if user_name:
            query += " AND user_name = %s"
            params.append(user_name)

        if category:
            query += " AND category = %s"
            params.append(category)

        if importance is not None:
            query += " AND importance >= %s"
            params.append(importance)

        query += " ORDER BY importance DESC, extracted_at DESC"
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        memories = cursor.fetchall()

        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) FROM persistent_memories
            WHERE active = TRUE
        """
        count_params = []

        if user_name:
            count_query += " AND user_name = %s"
            count_params.append(user_name)

        if category:
            count_query += " AND category = %s"
            count_params.append(category)

        if importance is not None:
            count_query += " AND importance >= %s"
            count_params.append(importance)
            
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        memories_data = [{
            'id': m[0],
            'user_name': m[1],
            'category': m[2],
            'content': m[3],
            'extracted_at': format_timestamp_ny(m[4]) if m[4] else None,
            'importance': m[5],
            'tags': m[6] or [],
            'active': m[7],
            'event_date': m[8].isoformat() if m[8] else None,
            'event_time': str(m[9]) if m[9] else None
        } for m in memories]

        return create_success_response({
            'memories': memories_data,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            }
        })
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to retrieve memories', str(e)), 500

@app.route('/api/memories/categories', methods=['GET'])
def get_memory_categories():
    """Get available memory categories"""
    return create_success_response({
        'categories': ['schedule', 'fact', 'preference', 'task', 'reminder', 'other']
    })

@app.route('/api/memories', methods=['POST'])
def add_memory():
    """Manually add a persistent memory"""
    try:
        data = request.get_json()
        if not data:
            return create_error_response('INVALID_FORMAT', 'Request body must be JSON'), 400
        
        # Validate required fields
        user_name = data.get('user_name')
        content = data.get('content')
        
        if not user_name:
            return create_error_response('MISSING_PARAMETER', 'user_name is required'), 400
        if not content:
            return create_error_response('MISSING_PARAMETER', 'content is required'), 400
        
        # Validate category
        category = data.get('category', 'other')
        valid_categories = ['schedule', 'fact', 'preference', 'task', 'reminder', 'other']
        if category not in valid_categories:
            return create_error_response('INVALID_FORMAT', f'category must be one of: {valid_categories}'), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO persistent_memories (user_name, category, content, importance, tags, event_date, event_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_name,
            category,
            content,
            data.get('importance', 5),
            data.get('tags', []),
            data.get('event_date'),
            data.get('event_time')
        ))

        memory_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        return create_success_response({
            'id': memory_id,
            'status': 'created'
        })
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to create memory', str(e)), 500

@app.route('/api/memories/<int:memory_id>', methods=['DELETE'])
def delete_memory(memory_id):
    """Delete (deactivate) a memory"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE persistent_memories
            SET active = FALSE
            WHERE id = %s
        """, (memory_id,))

        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return create_error_response('NOT_FOUND', 'Memory not found'), 404

        conn.commit()
        cursor.close()
        conn.close()

        return create_success_response({'status': 'deleted'})
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to delete memory', str(e)), 500

@app.route('/api/memories/<int:memory_id>', methods=['PUT'])
def update_memory(memory_id):
    """Update a memory"""
    try:
        data = request.get_json()
        if not data:
            return create_error_response('INVALID_FORMAT', 'Request body must be JSON'), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build update query dynamically based on provided fields
        updates = []
        params = []

        if 'content' in data:
            updates.append("content = %s")
            params.append(data['content'])

        if 'category' in data:
            # Validate category
            valid_categories = ['schedule', 'fact', 'preference', 'task', 'reminder', 'other']
            if data['category'] not in valid_categories:
                cursor.close()
                conn.close()
                return create_error_response('INVALID_FORMAT', f'category must be one of: {valid_categories}'), 400
            updates.append("category = %s")
            params.append(data['category'])

        if 'importance' in data:
            updates.append("importance = %s")
            params.append(data['importance'])

        if 'tags' in data:
            updates.append("tags = %s")
            params.append(data['tags'])
            
        if 'event_date' in data:
            updates.append("event_date = %s")
            params.append(data['event_date'])
            
        if 'event_time' in data:
            updates.append("event_time = %s")
            params.append(data['event_time'])

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(memory_id)

            query = f"UPDATE persistent_memories SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return create_error_response('NOT_FOUND', 'Memory not found'), 404
                
            conn.commit()

        cursor.close()
        conn.close()

        return create_success_response({'status': 'updated'})
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to update memory', str(e)), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get list of users who have memories"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT user_name
        FROM persistent_memories
        WHERE active = TRUE
        ORDER BY user_name
    """)

    users = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify(users)

# Email Settings API
@app.route('/api/email/settings', methods=['GET'])
def get_email_settings():
    """Get email configuration settings"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT smtp_host, smtp_port, smtp_username, smtp_use_tls, smtp_use_ssl,
               from_email, recipient_email, daily_summary_enabled, summary_time,
               timezone, last_sent, imap_enabled, imap_host, imap_port, imap_username,
               imap_use_ssl, imap_mailbox, auto_reply_enabled, reply_signature,
               check_interval_seconds, last_checked
        FROM email_settings
        WHERE id = 1
    """)

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return jsonify({'error': 'Email settings not found'}), 404

    return jsonify({
        'smtp_host': row[0],
        'smtp_port': row[1],
        'smtp_username': row[2],
        'smtp_use_tls': row[3],
        'smtp_use_ssl': row[4],
        'from_email': row[5],
        'recipient_email': row[6],
        'daily_summary_enabled': row[7],
        'summary_time': str(row[8]) if row[8] else '22:00:00',
        'timezone': row[9],
        'last_sent': format_timestamp_ny(row[10]) if row[10] else None,
        'imap_enabled': row[11] if row[11] is not None else False,
        'imap_host': row[12],
        'imap_port': row[13] if row[13] is not None else 993,
        'imap_username': row[14],
        'imap_use_ssl': row[15] if row[15] is not None else True,
        'imap_mailbox': row[16] if row[16] else 'INBOX',
        'auto_reply_enabled': row[17] if row[17] is not None else False,
        'reply_signature': row[18] if row[18] else '',
        'check_interval_seconds': row[19] if row[19] is not None else 300,
        'last_checked': format_timestamp_ny(row[20]) if row[20] else None
    })

@app.route('/api/email/settings', methods=['POST'])
def update_email_settings():
    """Update email configuration settings"""
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build update query
    updates = []
    params = []

    # SMTP settings
    if 'smtp_host' in data:
        updates.append("smtp_host = %s")
        params.append(data['smtp_host'])

    if 'smtp_port' in data:
        updates.append("smtp_port = %s")
        params.append(data['smtp_port'])

    if 'smtp_username' in data:
        updates.append("smtp_username = %s")
        params.append(data['smtp_username'])

    if 'smtp_password' in data:
        updates.append("smtp_password = %s")
        params.append(data['smtp_password'])

    if 'smtp_use_tls' in data:
        updates.append("smtp_use_tls = %s")
        params.append(data['smtp_use_tls'])

    if 'smtp_use_ssl' in data:
        updates.append("smtp_use_ssl = %s")
        params.append(data['smtp_use_ssl'])

    if 'from_email' in data:
        updates.append("from_email = %s")
        params.append(data['from_email'])

    if 'recipient_email' in data:
        updates.append("recipient_email = %s")
        params.append(data['recipient_email'])

    # Daily summary settings
    if 'daily_summary_enabled' in data:
        updates.append("daily_summary_enabled = %s")
        params.append(data['daily_summary_enabled'])

    if 'summary_time' in data:
        updates.append("summary_time = %s")
        params.append(data['summary_time'])

    if 'timezone' in data:
        updates.append("timezone = %s")
        params.append(data['timezone'])

    # IMAP settings
    if 'imap_enabled' in data:
        updates.append("imap_enabled = %s")
        params.append(data['imap_enabled'])

    if 'imap_host' in data:
        updates.append("imap_host = %s")
        params.append(data['imap_host'])

    if 'imap_port' in data:
        updates.append("imap_port = %s")
        params.append(data['imap_port'])

    if 'imap_username' in data:
        updates.append("imap_username = %s")
        params.append(data['imap_username'])

    if 'imap_password' in data:
        updates.append("imap_password = %s")
        params.append(data['imap_password'])

    if 'imap_use_ssl' in data:
        updates.append("imap_use_ssl = %s")
        params.append(data['imap_use_ssl'])

    if 'imap_mailbox' in data:
        updates.append("imap_mailbox = %s")
        params.append(data['imap_mailbox'])

    # AI reply settings
    if 'auto_reply_enabled' in data:
        updates.append("auto_reply_enabled = %s")
        params.append(data['auto_reply_enabled'])

    if 'reply_signature' in data:
        updates.append("reply_signature = %s")
        params.append(data['reply_signature'])

    if 'check_interval_seconds' in data:
        updates.append("check_interval_seconds = %s")
        params.append(data['check_interval_seconds'])

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(1)  # id = 1

        query = f"UPDATE email_settings SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(query, params)
        conn.commit()

    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/email/test', methods=['POST'])
def send_test_email():
    """Send a test email using current settings"""
    try:
        # Import the email service functionality
        import sys
        sys.path.insert(0, '/email-summary-service')

        # Get email settings
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT smtp_host, smtp_port, smtp_username, smtp_password,
                   smtp_use_tls, smtp_use_ssl, from_email, recipient_email, timezone
            FROM email_settings
            WHERE id = 1
        """)

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({'error': 'Email settings not configured'}), 400

        settings = {
            'smtp_host': row[0],
            'smtp_port': row[1],
            'smtp_username': row[2],
            'smtp_password': row[3],
            'smtp_use_tls': row[4],
            'smtp_use_ssl': row[5],
            'from_email': row[6],
            'recipient_email': row[7],
            'timezone': row[8]
        }

        if not settings['recipient_email']:
            return jsonify({'error': 'No recipient email configured'}), 400

        # Send test email inline
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.utils import formatdate
        from datetime import datetime
        import pytz

        msg = MIMEMultipart('alternative')
        msg['Subject'] = '[TEST] Mumble AI Email System'
        msg['From'] = settings['from_email']
        msg['To'] = settings['recipient_email']
        msg['Date'] = formatdate(localtime=True)

        plain_text = "This is a test email from Mumble AI. If you received this, your email settings are configured correctly!"
        html_text = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; }
        .content { padding: 20px; background: #f4f4f4; border-radius: 8px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">🤖 Mumble AI Test Email</h1>
        </div>
        <div class="content">
            <p><strong>This is a test email from Mumble AI.</strong></p>
            <p>If you received this, your email settings are configured correctly!</p>
            <p>Daily summaries will be sent at your configured time.</p>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(plain_text, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_text, 'html', 'utf-8'))

        # Send email
        if settings['smtp_use_ssl']:
            smtp = smtplib.SMTP_SSL(settings['smtp_host'], settings['smtp_port'], timeout=30)
        else:
            smtp = smtplib.SMTP(settings['smtp_host'], settings['smtp_port'], timeout=30)
            if settings['smtp_use_tls']:
                smtp.starttls()

        # Login if credentials provided
        if settings['smtp_username'] and settings['smtp_password']:
            smtp.login(settings['smtp_username'], settings['smtp_password'])

        smtp.send_message(msg)
        smtp.quit()

        return jsonify({'success': True, 'message': 'Test email sent successfully'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/email/generate-signature', methods=['POST'])
def generate_email_signature():
    """Generate an email signature based on the bot's persona using AI"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get bot persona and Ollama config
        cursor.execute("SELECT value FROM bot_config WHERE key = 'bot_persona'")
        row = cursor.fetchone()
        bot_persona = row[0] if row else "a helpful AI assistant"

        cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
        row = cursor.fetchone()
        ollama_url = row[0] if row else 'http://host.docker.internal:11434'

        cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
        row = cursor.fetchone()
        ollama_model = row[0] if row else 'llama3.2:latest'

        cursor.close()
        conn.close()

        # Generate signature using Ollama
        import requests

        signature_prompt = f"""You are {bot_persona}.

Generate a professional email signature for yourself that will be used in email replies. The signature should:
- Be concise (2-4 lines maximum)
- Reflect your personality/persona
- Be professional but friendly
- Include a sign-off like "Best regards" or similar
- DO NOT include contact information, emails, or phone numbers
- Just the text - no HTML or markdown formatting

Example format:
Best regards,
[Your Name/Title]
[Optional tagline]

Your signature:"""

        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                'model': ollama_model,
                'prompt': signature_prompt,
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'num_predict': 150
                }
            },
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            signature = result.get('response', '').strip()
            return jsonify({'success': True, 'signature': signature})
        else:
            return jsonify({'error': 'Failed to generate signature from Ollama'}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Email User Mappings API
@app.route('/api/email/mappings', methods=['GET'])
def get_email_mappings():
    """Get all email user mappings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, email_address, user_name, notes, created_at, updated_at
            FROM email_user_mappings
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        mappings = []
        for row in rows:
            mappings.append({
                'id': row[0],
                'email_address': row[1],
                'user_name': row[2],
                'notes': row[3],
                'created_at': format_timestamp_ny(row[4]) if row[4] else None,
                'updated_at': format_timestamp_ny(row[5]) if row[5] else None
            })

        return jsonify(mappings)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/email/mappings', methods=['POST'])
def add_email_mapping():
    """Add a new email user mapping"""
    try:
        data = request.json
        email_address = data.get('email_address', '').strip()
        user_name = data.get('user_name', '').strip()
        notes = data.get('notes', '').strip()

        if not email_address or not user_name:
            return jsonify({'error': 'email_address and user_name are required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO email_user_mappings (email_address, user_name, notes)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (email_address, user_name, notes if notes else None))

        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'id': new_id})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/email/mappings/<int:mapping_id>', methods=['PUT'])
def update_email_mapping(mapping_id):
    """Update an existing email user mapping"""
    try:
        data = request.json
        email_address = data.get('email_address', '').strip()
        user_name = data.get('user_name', '').strip()
        notes = data.get('notes', '').strip()

        if not email_address or not user_name:
            return jsonify({'error': 'email_address and user_name are required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE email_user_mappings
            SET email_address = %s,
                user_name = %s,
                notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (email_address, user_name, notes if notes else None, mapping_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/email/mappings/<int:mapping_id>', methods=['DELETE'])
def delete_email_mapping(mapping_id):
    """Delete an email user mapping"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM email_user_mappings
            WHERE id = %s
        """, (mapping_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/email/logs', methods=['GET'])
def get_email_logs():
    """Get email logs with optional filtering"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get query parameters
        direction = request.args.get('direction')  # 'received' or 'sent'
        email_type = request.args.get('type')  # 'reply', 'summary', 'test', 'other'
        status = request.args.get('status')  # 'success' or 'error'
        limit = int(request.args.get('limit', 100))  # Default 100 logs
        offset = int(request.args.get('offset', 0))  # For pagination

        # Build query with filters
        query = """
            SELECT id, direction, email_type, from_email, to_email, subject,
                   body_preview, full_body, status, error_message, mapped_user,
                   timestamp, created_at, attachments_count, attachments_metadata
            FROM email_logs
            WHERE 1=1
        """
        params = []

        if direction:
            query += " AND direction = %s"
            params.append(direction)

        if email_type:
            query += " AND email_type = %s"
            params.append(email_type)

        if status:
            query += " AND status = %s"
            params.append(status)

        # Order by newest first
        query += " ORDER BY timestamp DESC"

        # Add pagination
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        logs = cursor.fetchall()

        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) FROM email_logs WHERE 1=1
        """
        count_params = []

        if direction:
            count_query += " AND direction = %s"
            count_params.append(direction)

        if email_type:
            count_query += " AND email_type = %s"
            count_params.append(email_type)

        if status:
            count_query += " AND status = %s"
            count_params.append(status)

        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({
            'logs': [{
                'id': log[0],
                'direction': log[1],
                'email_type': log[2],
                'from_email': log[3],
                'to_email': log[4],
                'subject': log[5],
                'body_preview': log[6],
                'full_body': log[7],
                'status': log[8],
                'error_message': log[9],
                'mapped_user': log[10],
                'timestamp': format_timestamp_ny(log[11]) if log[11] else None,
                'created_at': format_timestamp_ny(log[12]) if log[12] else None,
                'attachments_count': log[13] if len(log) > 13 else 0,
                'attachments_metadata': log[14] if len(log) > 14 and log[14] else []
            } for log in logs],
            'total': total_count,
            'limit': limit,
            'offset': offset
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/email/retry/<int:log_id>', methods=['POST'])
def retry_failed_email(log_id):
    """Retry sending a failed email by triggering email-summary-service"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the failed email log
        cursor.execute("""
            SELECT id, direction, email_type, from_email, to_email, subject,
                   full_body, status, error_message, mapped_user
            FROM email_logs
            WHERE id = %s AND status = 'error'
        """, (log_id,))

        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Failed email not found or already succeeded'}), 404

        log_id, direction, email_type, from_email, to_email, subject, body, status, error_message, mapped_user = row

        # Only allow retrying sent emails (summaries and replies)
        if direction != 'sent':
            cursor.close()
            conn.close()
            return jsonify({'error': 'Can only retry sent emails'}), 400

        cursor.close()
        conn.close()

        # Check if it's an Ollama failure (needs regeneration) or SMTP failure (just resend)
        is_ollama_failure = error_message and 'Ollama API failed' in error_message

        if is_ollama_failure and email_type == 'summary':
            # Trigger email-summary-service to regenerate and send
            try:
                # Delete the error log so a new one will be created
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM email_logs WHERE id = %s", (log_id,))
                conn.commit()
                cursor.close()
                conn.close()

                # Trigger summary generation
                response = requests.post('http://email-summary-service:5006/api/send-summary', timeout=5)
                
                if response.status_code == 200:
                    return jsonify({'success': True, 'message': 'Summary regeneration triggered. Check email logs for results.'}), 200
                else:
                    return jsonify({'error': 'Failed to trigger summary service'}), 500

            except Exception as e:
                return jsonify({'error': f'Failed to contact email-summary-service: {str(e)}'}), 500

        elif email_type == 'reply':
            # For reply failures, we can't easily regenerate without the original email context
            # Mark the log for deletion and inform user to wait for next email check
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE email_logs
                SET error_message = 'Retry requested - email will be retried on next check cycle'
                WHERE id = %s
            """, (log_id,))
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True, 
                'message': 'Reply will be retried automatically on next email check cycle'
            }), 200

        else:
            # For SMTP failures, try to resend directly
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.utils import formatdate

            # Get email settings
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT smtp_host, smtp_port, smtp_username, smtp_password,
                       smtp_use_tls, smtp_use_ssl, from_email
                FROM email_settings
                WHERE id = 1
            """)

            settings_row = cursor.fetchone()
            if not settings_row:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Email settings not configured'}), 400

            smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls, smtp_use_ssl, configured_from_email = settings_row
            cursor.close()
            conn.close()

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = configured_from_email
            msg['To'] = to_email
            msg['Date'] = formatdate(localtime=True)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Send email
            if smtp_use_ssl:
                smtp = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
            else:
                smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                if smtp_use_tls:
                    smtp.starttls()

            if smtp_username and smtp_password:
                smtp.login(smtp_username, smtp_password)

            smtp.send_message(msg)
            smtp.quit()

            # Update the log entry to success
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE email_logs
                SET status = 'success',
                    error_message = NULL,
                    timestamp = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (log_id,))
            conn.commit()
            cursor.close()
            conn.close()

            return jsonify({'success': True, 'message': 'Email sent successfully'}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Enhanced Schedule APIs for Flutter
@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    """Get schedule events with enhanced filtering for mobile and web"""
    try:
        # Get query parameters
        user_name = request.args.get('user_name')  # Optional - if not provided, get all users
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        upcoming = request.args.get('upcoming', type=int)  # Next N days
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with filters - make user_name optional
        query = """
            SELECT id, user_name, title, event_date, event_time, description, importance, created_at,
                   reminder_enabled, reminder_minutes, recipient_email, reminder_sent
            FROM schedule_events
            WHERE active = TRUE
        """
        params = []
        
        # Add user filter only if user_name is provided
        if user_name:
            query += " AND user_name = %s"
            params.append(user_name)

        if start_date:
            query += " AND event_date >= %s"
            params.append(start_date)

        if end_date:
            query += " AND event_date <= %s"
            params.append(end_date)
            
        if upcoming:
            query += " AND event_date >= CURRENT_DATE AND event_date <= CURRENT_DATE + INTERVAL '%s days'"
            params.append(upcoming)

        query += " ORDER BY event_date, event_time"
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        events = cursor.fetchall()

        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) FROM schedule_events
            WHERE active = TRUE
        """
        count_params = []
        
        # Add user filter only if user_name is provided
        if user_name:
            count_query += " AND user_name = %s"
            count_params.append(user_name)
        
        if start_date:
            count_query += " AND event_date >= %s"
            count_params.append(start_date)
            
        if end_date:
            count_query += " AND event_date <= %s"
            count_params.append(end_date)
            
        if upcoming:
            count_query += " AND event_date >= CURRENT_DATE AND event_date <= CURRENT_DATE + INTERVAL '%s days'"
            count_params.append(upcoming)
            
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        events_data = [{
            'id': e[0],
            'user_name': e[1],
            'title': e[2],
            'event_date': e[3].isoformat() if e[3] else None,
            'event_time': str(e[4]) if e[4] else None,
            'description': e[5],
            'importance': e[6],
            'created_at': format_timestamp_ny(e[7]) if e[7] else None,
            'reminder_enabled': e[8] if len(e) > 8 else False,
            'reminder_minutes': e[9] if len(e) > 9 else 60,
            'recipient_email': e[10] if len(e) > 10 else None,
            'reminder_sent': e[11] if len(e) > 11 else False
        } for e in events]

        return create_success_response({
            'events': events_data,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            }
        })
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to retrieve schedule events', str(e)), 500

@app.route('/api/schedule', methods=['POST'])
def add_schedule_event():
    """Add a new schedule event"""
    try:
        data = request.get_json()
        if not data:
            return create_error_response('INVALID_FORMAT', 'Request body must be JSON'), 400
        
        # Validate required fields
        user_name = data.get('user_name')
        title = data.get('title')
        event_date = data.get('event_date')
        
        if not user_name:
            return create_error_response('MISSING_PARAMETER', 'user_name is required'), 400
        if not title:
            return create_error_response('MISSING_PARAMETER', 'title is required'), 400
        if not event_date:
            return create_error_response('MISSING_PARAMETER', 'event_date is required'), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO schedule_events (user_name, title, event_date, event_time, description, importance, 
                                         reminder_enabled, reminder_minutes, recipient_email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_name,
            title,
            event_date,
            data.get('event_time'),
            data.get('description'),
            data.get('importance', 5),
            data.get('reminder_enabled', False),
            data.get('reminder_minutes', 60),
            data.get('recipient_email')
        ))

        event_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        return create_success_response({'id': event_id, 'status': 'created'})
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to create schedule event', str(e)), 500

@app.route('/api/schedule/<int:event_id>', methods=['PUT'])
def update_schedule_event(event_id):
    """Update a schedule event"""
    data = request.json

    conn = get_db_connection()
    cursor = conn.cursor()

    # Build update query dynamically based on provided fields
    updates = []
    params = []

    if 'user_name' in data:
        updates.append("user_name = %s")
        params.append(data['user_name'])

    if 'title' in data:
        updates.append("title = %s")
        params.append(data['title'])

    if 'event_date' in data:
        updates.append("event_date = %s")
        params.append(data['event_date'])

    if 'event_time' in data:
        updates.append("event_time = %s")
        params.append(data['event_time'])

    if 'description' in data:
        updates.append("description = %s")
        params.append(data['description'])

    if 'importance' in data:
        updates.append("importance = %s")
        params.append(data['importance'])

    if 'reminder_enabled' in data:
        updates.append("reminder_enabled = %s")
        params.append(data['reminder_enabled'])

    if 'reminder_minutes' in data:
        updates.append("reminder_minutes = %s")
        params.append(data['reminder_minutes'])

    if 'recipient_email' in data:
        updates.append("recipient_email = %s")
        params.append(data['recipient_email'])

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(event_id)

        query = f"UPDATE schedule_events SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(query, params)
        conn.commit()

    cursor.close()
    conn.close()

    return jsonify({'status': 'updated'})

@app.route('/api/schedule/<int:event_id>', methods=['DELETE'])
def delete_schedule_event(event_id):
    """Delete (deactivate) a schedule event"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE schedule_events
        SET active = FALSE
        WHERE id = %s
    """, (event_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'status': 'deleted'})

@app.route('/api/schedule/users', methods=['GET'])
def get_schedule_users():
    """Get list of users who have schedule events"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT user_name
        FROM schedule_events
        WHERE active = TRUE
        ORDER BY user_name
    """)

    users = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify(users)

@app.route('/api/schedule/upcoming', methods=['GET'])
def get_upcoming_events():
    """Get upcoming schedule events for the next N days"""
    days_ahead = request.args.get('days', 7, type=int)
    limit = request.args.get('limit', 10, type=int)
    user_name = request.args.get('user')

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT id, user_name, title, event_date, event_time, description, importance, created_at,
               reminder_enabled, reminder_minutes, recipient_email, reminder_sent
        FROM schedule_events
        WHERE active = TRUE
          AND event_date >= CURRENT_DATE
          AND event_date <= CURRENT_DATE + INTERVAL '%s days'
    """
    params = [days_ahead]

    if user_name:
        query += " AND user_name = %s"
        params.append(user_name)

    query += " ORDER BY event_date, event_time LIMIT %s"
    params.append(limit)

    cursor.execute(query, params)

    events = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([{
        'id': e[0],
        'user_name': e[1],
        'title': e[2],
        'event_date': e[3].isoformat() if e[3] else None,
        'event_time': str(e[4]) if e[4] else None,
        'description': e[5],
        'importance': e[6],
        'created_at': format_timestamp_ny(e[7]) if e[7] else None,
        'reminder_enabled': e[8] if len(e) > 8 else False,
        'reminder_minutes': e[9] if len(e) > 9 else 60,
        'recipient_email': e[10] if len(e) > 10 else None,
        'reminder_sent': e[11] if len(e) > 11 else False
    } for e in events])

@app.route('/api/advanced-settings', methods=['GET'])
def get_advanced_settings():
    """Get advanced AI settings"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    settings = {}
    setting_keys = [
        'short_term_memory_limit',
        'long_term_memory_limit',
        'use_chain_of_thought',
        'use_semantic_memory_ranking',
        'use_response_validation',
        'enable_parallel_processing'
    ]
    
    for key in setting_keys:
        cursor.execute("SELECT value FROM bot_config WHERE key = %s", (key,))
        result = cursor.fetchone()
        value = result[0] if result else ('10' if 'limit' in key else 'true')
        
        # Convert to appropriate type
        if 'limit' in key:
            settings[key] = int(value)
        else:
            settings[key] = value.lower() in ('true', '1', 'yes')
    
    cursor.close()
    conn.close()
    
    return jsonify(settings)

@app.route('/api/advanced-settings', methods=['POST'])
def update_advanced_settings():
    """Update advanced AI settings"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        for key, value in data.items():
            cursor.execute("""
                INSERT INTO bot_config (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
            """, (key, str(value)))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

def init_voices():
    """Ensure voices are downloaded on startup"""
    voices_dir = "/app/piper_voices"
    # Count how many .onnx files we have
    onnx_files = [f for f in os.listdir(voices_dir) if f.endswith('.onnx')]

    # If we have fewer than 25 voices, run the download script
    if len(onnx_files) < 25:
        print(f"Found only {len(onnx_files)} voices, downloading all voices...")
        try:
            subprocess.run(['python', '/app/download_voices.py'], check=True)
            print("Voice download complete!")
        except Exception as e:
            print(f"Error downloading voices: {e}")
    else:
        print(f"Found {len(onnx_files)} voices, skipping download")

# Initialize logs table
def init_logs_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flutter_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            level VARCHAR(20) NOT NULL,
            message TEXT NOT NULL,
            screen VARCHAR(100),
            data JSONB,
            device_info JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Logs endpoint for receiving logs from Flutter app
@app.route('/api/logs', methods=['POST'])
def receive_logs():
    try:
        data = request.get_json()
        logs = data.get('logs', [])
        device_info = data.get('device_info', {})
        
        print(f"Received {len(logs)} logs from Flutter app")
        print(f"Device info: {device_info}")
        
        # Store logs in database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for log_entry in logs:
            timestamp = log_entry.get('timestamp', '')
            level = log_entry.get('level', 'INFO')
            message = log_entry.get('message', '')
            screen = log_entry.get('screen', '')
            log_data = log_entry.get('data', {})
            
            # Parse timestamp
            try:
                parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                parsed_timestamp = datetime.now()
            
            # Insert into database
            cursor.execute("""
                INSERT INTO flutter_logs (timestamp, level, message, screen, data, device_info)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (parsed_timestamp, level, message, screen, json.dumps(log_data), json.dumps(device_info)))
            
            # Also print to console
            screen_prefix = f"[{screen}] " if screen else ""
            print(f"[FLUTTER] {timestamp} [{level}] {screen_prefix}{message}")
            
            if log_data:
                print(f"[FLUTTER] Data: {log_data}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'received_logs': len(logs)})
    except Exception as e:
        print(f"Error processing logs: {e}")
        return jsonify({'error': str(e)}), 500

# Get logs endpoint
@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        level = request.args.get('level')
        screen = request.args.get('screen')
        
        # Build query
        query = "SELECT * FROM flutter_logs"
        params = []
        conditions = []
        
        if level:
            conditions.append("level = %s")
            params.append(level)
        
        if screen:
            conditions.append("screen = %s")
            params.append(screen)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        
        # Convert to list of dictionaries
        log_list = []
        for log in logs:
            log_list.append({
                'id': log[0],
                'timestamp': log[1].isoformat() if log[1] else None,
                'level': log[2],
                'message': log[3],
                'screen': log[4],
                'data': log[5] if log[5] else {},
                'device_info': log[6] if log[6] else {},
                'created_at': log[7].isoformat() if log[7] else None,
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({'logs': log_list, 'count': len(log_list)})
    except Exception as e:
        print(f"Error retrieving logs: {e}")
        return jsonify({'error': str(e)}), 500

# Logs web page
@app.route('/logs')
def logs_page():
    return render_template('logs.html')

# =============================================================================
# FLUTTER API ENDPOINTS
# =============================================================================

def create_error_response(error_code, message, details=None):
    """Create standardized error response"""
    return jsonify({
        'success': False,
        'error': {
            'code': error_code,
            'message': message,
            'details': details
        },
        'timestamp': datetime.now().isoformat()
    })

def create_success_response(data=None):
    """Create standardized success response"""
    response = {
        'success': True,
        'timestamp': datetime.now().isoformat()
    }
    if data is not None:
        response['data'] = data
    return jsonify(response)

def get_ollama_config():
    """Get Ollama configuration from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
    ollama_url = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
    ollama_model = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return ollama_url, ollama_model

def get_user_memories(user_name, limit=10):
    """Get persistent memories for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, category, content, extracted_at, importance, tags
        FROM persistent_memories
        WHERE user_name = %s AND active = TRUE
        ORDER BY importance DESC, extracted_at DESC
        LIMIT %s
    """, (user_name, limit))
    
    memories = []
    for row in cursor.fetchall():
        memories.append({
            'id': row[0],
            'category': row[1],
            'content': row[2],
            'extracted_at': format_timestamp_ny(row[3]) if row[3] else None,
            'importance': row[4],
            'tags': row[5] or []
        })
    
    cursor.close()
    conn.close()
    return memories

def get_user_schedule_events(user_name, limit=10):
    """Get schedule events for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, event_date, event_time, description, importance
        FROM schedule_events
        WHERE user_name = %s AND active = TRUE
        ORDER BY event_date, event_time
        LIMIT %s
    """, (user_name, limit))
    
    events = []
    for row in cursor.fetchall():
        events.append({
            'id': row[0],
            'title': row[1],
            'event_date': row[2].isoformat() if row[2] else None,
            'event_time': str(row[3]) if row[3] else None,
            'description': row[4],
            'importance': row[5]
        })
    
    cursor.close()
    conn.close()
    return events

def get_conversation_history(session_id, limit=10):
    """Get recent conversation history for a session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, message, message_type, timestamp
        FROM conversation_history
        WHERE session_id = %s
        ORDER BY timestamp DESC
        LIMIT %s
    """, (session_id, limit))
    
    history = []
    for row in cursor.fetchall():
        history.append({
            'role': row[0],
            'message': row[1],
            'message_type': row[2],
            'timestamp': format_timestamp_ny(row[3]) if row[3] else None
        })
    
    cursor.close()
    conn.close()
    return list(reversed(history))  # Return in chronological order

def build_ai_prompt(user_message, user_name, session_id, include_memories=True, include_schedule=True):
    """Build AI prompt with context"""
    # Get bot persona
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_config WHERE key = 'bot_persona'")
    result = cursor.fetchone()
    bot_persona = result[0] if result else "You are a helpful AI assistant."
    cursor.close()
    conn.close()
    
    # Build context
    context_parts = [bot_persona]
    
    # Add memories if requested
    if include_memories:
        memories = get_user_memories(user_name, limit=5)
        if memories:
            context_parts.append("\nImportant information about this user:")
            for mem in memories:
                context_parts.append(f"- {mem['content']}")
    
    # Add schedule if requested
    if include_schedule:
        events = get_user_schedule_events(user_name, limit=5)
        if events:
            context_parts.append("\nUser's upcoming schedule:")
            for event in events:
                date_str = event['event_date']
                time_str = f" at {event['event_time']}" if event['event_time'] else ""
                context_parts.append(f"- {event['title']} on {date_str}{time_str}")
    
    # Add recent conversation history
    if session_id:
        history = get_conversation_history(session_id, limit=5)
        if history:
            context_parts.append("\nRecent conversation:")
            for msg in history:
                context_parts.append(f"{msg['role']}: {msg['message']}")
    
    # Add current message
    context_parts.append(f"\nUser: {user_message}")
    context_parts.append("Assistant:")
    
    return "\n".join(context_parts)

def call_ollama_api(prompt, ollama_url, ollama_model):
    """Call Ollama API to generate response"""
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                'model': ollama_model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'num_predict': 200,
                    'stop': ['\n\n', 'User:', 'Assistant:']
                }
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json().get('response', 'I did not understand that.').strip()
        else:
            raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
    except Exception as e:
        raise Exception(f"Failed to call Ollama API: {str(e)}")

def log_conversation(user_name, session_id, role, message, message_type='text'):
    """Log conversation to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO conversation_history (user_name, session_id, role, message, message_type, timestamp)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """, (user_name, session_id, role, message, message_type))
    conn.commit()
    cursor.close()
    conn.close()

# Core AI Chat Endpoint
@app.route('/api/chat', methods=['POST'])
def flutter_chat():
    """Main AI chat endpoint for Flutter app"""
    try:
        data = request.get_json()
        if not data:
            return create_error_response('INVALID_FORMAT', 'Request body must be JSON'), 400
        
        # Validate required fields
        user_name = data.get('user_name')
        message = data.get('message')
        
        if not user_name:
            return create_error_response('MISSING_PARAMETER', 'user_name is required'), 400
        if not message:
            return create_error_response('MISSING_PARAMETER', 'message is required'), 400
        
        # Optional fields
        session_id = data.get('session_id')
        include_memories = data.get('include_memories', True)
        include_schedule = data.get('include_schedule', True)
        
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get Ollama configuration
        try:
            ollama_url, ollama_model = get_ollama_config()
        except Exception as e:
            return create_error_response('CONFIG_ERROR', 'Failed to get AI configuration', str(e)), 500
        
        # Build prompt with context
        try:
            prompt = build_ai_prompt(message, user_name, session_id, include_memories, include_schedule)
        except Exception as e:
            return create_error_response('CONTEXT_ERROR', 'Failed to build context', str(e)), 500
        
        # Get AI response
        try:
            ai_response = call_ollama_api(prompt, ollama_url, ollama_model)
        except Exception as e:
            return create_error_response('OLLAMA_ERROR', 'Failed to generate AI response', str(e)), 500
        
        # Log conversation
        try:
            log_conversation(user_name, session_id, 'user', message)
            log_conversation(user_name, session_id, 'assistant', ai_response)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Warning: Failed to log conversation: {e}")
        
        # Get context counts for response
        memories_count = len(get_user_memories(user_name, limit=5)) if include_memories else 0
        schedule_count = len(get_user_schedule_events(user_name, limit=5)) if include_schedule else 0
        
        return create_success_response({
            'response': ai_response,
            'session_id': session_id,
            'context_used': {
                'memories_count': memories_count,
                'schedule_events_count': schedule_count
            }
        })
        
    except Exception as e:
        return create_error_response('INTERNAL_ERROR', 'An unexpected error occurred', str(e)), 500

# Enhanced Conversation APIs for Flutter
@app.route('/api/conversations', methods=['GET'])
def get_conversations_mobile():
    """Get conversation history with enhanced filtering for mobile"""
    try:
        # Get query parameters
        user_name = request.args.get('user_name')  # Required for Flutter
        session_id = request.args.get('session_id')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Validate required parameters
        if not user_name:
            return create_error_response('MISSING_PARAMETER', 'user_name is required'), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with filters
        query = """
            SELECT id, user_name, message_type, role, message, timestamp
            FROM conversation_history
            WHERE user_name = %s
        """
        params = [user_name]

        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)

        query += " ORDER BY timestamp DESC"
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        conversations = cursor.fetchall()

        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) FROM conversation_history
            WHERE user_name = %s
        """
        count_params = [user_name]
        
        if session_id:
            count_query += " AND session_id = %s"
            count_params.append(session_id)
            
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        conversations_data = [{
            'id': c[0],
            'user_name': c[1],
            'message_type': c[2],
            'role': c[3],
            'message': c[4],
            'timestamp': format_timestamp_ny(c[5]) if c[5] else None
        } for c in conversations]

        return create_success_response({
            'conversations': conversations_data,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            }
        })
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to retrieve conversations', str(e)), 500

@app.route('/api/conversations/sessions', methods=['GET'])
def get_conversation_sessions():
    """Get conversation sessions for a user"""
    try:
        user_name = request.args.get('user_name')
        if not user_name:
            return create_error_response('MISSING_PARAMETER', 'user_name is required'), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT session_id, user_name, started_at, last_activity, message_count
            FROM conversation_sessions
            WHERE user_name = %s
            ORDER BY last_activity DESC
        """, (user_name,))
        
        sessions = cursor.fetchall()
        cursor.close()
        conn.close()

        sessions_data = [{
            'session_id': s[0],
            'user_name': s[1],
            'started_at': format_timestamp_ny(s[2]) if s[2] else None,
            'last_activity': format_timestamp_ny(s[3]) if s[3] else None,
            'message_count': s[4]
        } for s in sessions]

        return create_success_response({'sessions': sessions_data})
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to retrieve sessions', str(e)), 500

# User Profile API
@app.route('/api/users/<user_name>/profile', methods=['GET'])
def get_user_profile(user_name):
    """Get user profile with statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get memory count
        cursor.execute("SELECT COUNT(*) FROM persistent_memories WHERE user_name = %s AND active = TRUE", (user_name,))
        memory_count = cursor.fetchone()[0]
        
        # Get schedule count
        cursor.execute("SELECT COUNT(*) FROM schedule_events WHERE user_name = %s AND active = TRUE", (user_name,))
        schedule_count = cursor.fetchone()[0]
        
        # Get conversation count
        cursor.execute("SELECT COUNT(*) FROM conversation_history WHERE user_name = %s", (user_name,))
        conversation_count = cursor.fetchone()[0]
        
        # Get last activity
        cursor.execute("SELECT MAX(timestamp) FROM conversation_history WHERE user_name = %s", (user_name,))
        last_active = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()

        return create_success_response({
            'user_name': user_name,
            'memory_count': memory_count,
            'schedule_count': schedule_count,
            'conversation_count': conversation_count,
            'last_active': format_timestamp_ny(last_active) if last_active else None
        })
        
    except Exception as e:
        return create_error_response('DATABASE_ERROR', 'Failed to retrieve user profile', str(e)), 500

# Mobile Configuration API
@app.route('/api/config/mobile', methods=['GET'])
def get_mobile_config():
    """Get mobile-specific configuration"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get Ollama model
        cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
        ollama_model = cursor.fetchone()[0] if cursor.fetchone() else 'llama3.2:latest'
        
        # Get bot persona
        cursor.execute("SELECT value FROM bot_config WHERE key = 'bot_persona'")
        result = cursor.fetchone()
        bot_persona = result[0] if result else ''
        
        cursor.close()
        conn.close()

        return create_success_response({
            'ollama_model': ollama_model,
            'bot_persona': bot_persona,
            'features_enabled': {
                'memories': True,
                'schedules': True,
                'voice': False
            }
        })
        
    except Exception as e:
        return create_error_response('CONFIG_ERROR', 'Failed to retrieve configuration', str(e)), 500

# Health Check for Mobile
@app.route('/api/health/mobile', methods=['GET'])
def mobile_health_check():
    """Health check for mobile API"""
    try:
        # Test database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        # Test Ollama connection
        try:
            ollama_url, ollama_model = get_ollama_config()
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            ollama_status = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            ollama_status = "unhealthy"
        
        return create_success_response({
            'status': 'healthy',
            'database': 'connected',
            'ollama': ollama_status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return create_error_response('HEALTH_CHECK_FAILED', 'Health check failed', str(e)), 500

if __name__ == '__main__':
    init_config_table()
    init_logs_table()
    init_voices()
    app.run(host='0.0.0.0', port=5002, debug=False)
