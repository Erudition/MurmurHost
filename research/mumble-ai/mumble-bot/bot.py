import os
import time
import wave
import io
import logging
import threading
import requests
import subprocess
import tempfile
import psycopg2
import random
import functools
import json
import uuid
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, BaseHTTPRequestHandler
from psycopg2 import pool
from pymumble_py3 import Mumble
from pymumble_py3.constants import PYMUMBLE_AUDIO_PER_PACKET
from typing import Optional, Callable, Any, Tuple, List, Dict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Import the new memory manager
from memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Custom exception for retry failures"""
    pass


class CircuitBreakerError(Exception):
    """Custom exception for circuit breaker failures"""
    pass


class RetryConfig:
    """Configuration for retry mechanisms"""
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 60.0, exponential_base: float = 2.0, 
                 jitter: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self._lock:
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = 'HALF_OPEN'
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise CircuitBreakerError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.failure_count = 0
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                logger.info("Circuit breaker transitioning to CLOSED")

    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


def retry_with_exponential_backoff(config: RetryConfig = None):
    """Decorator for retry with exponential backoff"""
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        logger.error(f"Function {func.__name__} failed after {config.max_attempts} attempts: {e}")
                        raise RetryError(f"Function {func.__name__} failed after {config.max_attempts} attempts") from e
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{config.max_attempts}): {e}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
            
            raise RetryError(f"Function {func.__name__} failed after {config.max_attempts} attempts") from last_exception
        
        return wrapper
    return decorator


def safe_execute(func: Callable, *args, default_return: Any = None, 
                log_errors: bool = True, **kwargs) -> Any:
    """Safely execute a function with error handling"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
        return default_return


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint"""
    
    def __init__(self, bot_instance, *args, **kwargs):
        self.bot = bot_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/health':
            try:
                health_status = self.bot.check_health()
                status_code = 200 if self.bot.is_healthy else 503
                
                response = {
                    'status': 'healthy' if self.bot.is_healthy else 'unhealthy',
                    'services': health_status,
                    'timestamp': time.time()
                }
                
                self.send_response(status_code)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass


def create_health_handler(bot_instance):
    """Factory function to create health check handler with bot instance"""
    def handler(*args, **kwargs):
        return HealthCheckHandler(bot_instance, *args, **kwargs)
    return handler


class SmartCache:
    """Multi-layer caching system for AI bot"""
    def __init__(self):
        self.memory_cache = {}
        self.memory_cache_time = {}
        self.config_cache = {}
        self.config_cache_time = {}
        self.embedding_cache = {}
        self.embedding_cache_time = {}
        self.schedule_cache = {}
        self.schedule_cache_time = {}
        self.cache_ttl = 300  # 5 minutes default TTL
        self._lock = threading.Lock()
    
    def get_cached_memories(self, user_name):
        """Get cached memories if still valid"""
        with self._lock:
            if user_name in self.memory_cache:
                age = time.time() - self.memory_cache_time.get(user_name, 0)
                if age < self.cache_ttl:
                    logger.debug(f"Memory cache HIT for {user_name} (age: {age:.1f}s)")
                    return self.memory_cache[user_name]
                else:
                    logger.debug(f"Memory cache EXPIRED for {user_name} (age: {age:.1f}s)")
            return None
    
    def cache_memories(self, user_name, memories):
        """Cache memories for a user"""
        with self._lock:
            self.memory_cache[user_name] = memories
            self.memory_cache_time[user_name] = time.time()
            logger.debug(f"Cached {len(memories)} memories for {user_name}")
    
    def get_cached_config(self, key):
        """Get cached config if still valid"""
        with self._lock:
            if key in self.config_cache:
                age = time.time() - self.config_cache_time.get(key, 0)
                if age < self.cache_ttl:
                    return self.config_cache[key]
            return None
    
    def cache_config(self, key, value):
        """Cache a config value"""
        with self._lock:
            self.config_cache[key] = value
            self.config_cache_time[key] = time.time()
    
    def get_cached_embedding(self, text_hash):
        """Get cached embedding if still valid"""
        with self._lock:
            if text_hash in self.embedding_cache:
                age = time.time() - self.embedding_cache_time.get(text_hash, 0)
                if age < self.cache_ttl * 2:  # Embeddings are more expensive, cache longer
                    return self.embedding_cache[text_hash]
            return None
    
    def cache_embedding(self, text_hash, embedding):
        """Cache an embedding"""
        with self._lock:
            self.embedding_cache[text_hash] = embedding
            self.embedding_cache_time[text_hash] = time.time()
    
    def get_cached_schedule(self, user_name):
        """Get cached schedule if still valid"""
        with self._lock:
            if user_name in self.schedule_cache:
                age = time.time() - self.schedule_cache_time.get(user_name, 0)
                if age < self.cache_ttl:
                    return self.schedule_cache[user_name]
            return None
    
    def cache_schedule(self, user_name, schedule_events):
        """Cache schedule events for a user"""
        with self._lock:
            self.schedule_cache[user_name] = schedule_events
            self.schedule_cache_time[user_name] = time.time()
    
    def invalidate_user(self, user_name):
        """Invalidate all caches for a user"""
        with self._lock:
            self.memory_cache.pop(user_name, None)
            self.memory_cache_time.pop(user_name, None)
            self.schedule_cache.pop(user_name, None)
            self.schedule_cache_time.pop(user_name, None)
            logger.info(f"Invalidated all caches for {user_name}")
    
    def invalidate_config(self):
        """Invalidate config cache"""
        with self._lock:
            self.config_cache.clear()
            self.config_cache_time.clear()
            logger.info("Invalidated config cache")


class MumbleAIBot:
    def __init__(self):
        # Configuration
        self.mumble_host = os.getenv('MUMBLE_HOST', 'mumble-server')
        self.mumble_port = int(os.getenv('MUMBLE_PORT', '64738'))
        self.mumble_username = os.getenv('MUMBLE_USERNAME', 'AI-Bot')
        self.mumble_password = os.getenv('MUMBLE_PASSWORD', '')

        self.whisper_url = os.getenv('WHISPER_URL', 'http://faster-whisper:5000')
        self.piper_url = os.getenv('PIPER_URL', 'http://piper-tts:5001')
        self.silero_url = os.getenv('SILERO_URL', 'http://silero-tts:5004')
        self.ollama_url = os.getenv('OLLAMA_URL', 'http://host.docker.internal:11434')
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'llama2')

        # Database configuration
        self.db_host = os.getenv('DB_HOST', 'postgres')
        self.db_port = os.getenv('DB_PORT', '5432')
        self.db_name = os.getenv('DB_NAME', 'mumble_ai')
        self.db_user = os.getenv('DB_USER', 'mumbleai')
        self.db_password = os.getenv('DB_PASSWORD', 'mumbleai123')
        self.db_pool = None

        # Audio buffer for recording
        self.audio_buffer = {}
        self.recording = {}
        self.silence_threshold = 1.5  # seconds of silence before processing
        self.last_audio_time = {}

        self.mumble = None

        # Semantic memory and session tracking
        self.user_sessions = {}  # Track active sessions per user
        self.session_lock = threading.Lock()
        self.embedding_cache = {}  # Cache embeddings to reduce API calls
        
        # Topic state tracking
        self.active_topics = {}  # Track current topic per user/session
        self.resolved_topics = {}  # Track recently resolved topics per user/session
        
        # Initialize smart cache system for performance
        self.smart_cache = SmartCache()
        
        # Memory manager will be initialized after database pool is ready
        self.memory_manager = None
        
        # Error handling and retry configuration
        self.retry_config = RetryConfig(
            max_attempts=int(os.getenv('RETRY_MAX_ATTEMPTS', '3')),
            base_delay=float(os.getenv('RETRY_BASE_DELAY', '1.0')),
            max_delay=float(os.getenv('RETRY_MAX_DELAY', '60.0'))
        )
        
        # Circuit breakers for external services
        self.whisper_circuit_breaker = CircuitBreaker(
            failure_threshold=int(os.getenv('WHISPER_CIRCUIT_THRESHOLD', '5')),
            recovery_timeout=float(os.getenv('WHISPER_CIRCUIT_TIMEOUT', '60.0'))
        )
        self.piper_circuit_breaker = CircuitBreaker(
            failure_threshold=int(os.getenv('PIPER_CIRCUIT_THRESHOLD', '5')),
            recovery_timeout=float(os.getenv('PIPER_CIRCUIT_TIMEOUT', '60.0'))
        )
        self.ollama_circuit_breaker = CircuitBreaker(
            failure_threshold=int(os.getenv('OLLAMA_CIRCUIT_THRESHOLD', '5')),
            recovery_timeout=float(os.getenv('OLLAMA_CIRCUIT_TIMEOUT', '60.0'))
        )
        self.db_circuit_breaker = CircuitBreaker(
            failure_threshold=int(os.getenv('DB_CIRCUIT_THRESHOLD', '3')),
            recovery_timeout=float(os.getenv('DB_CIRCUIT_TIMEOUT', '30.0'))
        )
        
        # Health check tracking
        self.last_health_check = {}
        self.health_check_interval = float(os.getenv('HEALTH_CHECK_INTERVAL', '60.0'))  # Increased to 60 seconds
        self.is_healthy = True
        
        # Health server configuration
        self.health_port = int(os.getenv('HEALTH_PORT', '8080'))
        self.health_server = None

    @retry_with_exponential_backoff(RetryConfig(max_attempts=30, base_delay=2.0, max_delay=30.0))
    def wait_for_services(self):
        """Wait for dependent services to be ready with retry logic"""
        services = [
            (f"{self.whisper_url}/health", "Whisper"),
            (f"{self.piper_url}/health", "Piper"),
        ]

        for url, name in services:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"{name} service is ready")
                    self.last_health_check[name] = time.time()
                else:
                    raise requests.RequestException(f"Service {name} returned status {response.status_code}")
            except Exception as e:
                logger.warning(f"Service {name} not ready: {e}")
                raise

    @retry_with_exponential_backoff(RetryConfig(max_attempts=10, base_delay=2.0, max_delay=30.0))
    def init_database(self):
        """Initialize database connection pool with retry logic"""
        try:
            logger.info("Initializing database connection...")
            self.db_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            logger.info("Database connection pool initialized")
            self.last_health_check['database'] = time.time()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_db_connection(self):
        """Get a connection from the pool with circuit breaker protection"""
        try:
            return self.db_circuit_breaker.call(self._get_db_connection_internal)
        except CircuitBreakerError:
            logger.error("Database circuit breaker is open, cannot get connection")
            return None

    def _get_db_connection_internal(self):
        """Internal method to get database connection"""
        if not self.db_pool:
            raise Exception("Database pool not initialized")
        return self.db_pool.getconn()

    def release_db_connection(self, conn):
        """Release a connection back to the pool"""
        if conn and self.db_pool:
            try:
                self.db_pool.putconn(conn)
            except Exception as e:
                logger.error(f"Error releasing database connection: {e}")

    def save_message(self, user_name, user_session, message_type, role, message, session_id=None):
        """Save a message using MemoryManager (non-blocking)"""
        if not self.memory_manager:
            logger.warning("MemoryManager not available, falling back to old method")
            # Fallback to old method
            threading.Thread(
                target=self._save_message_sync,
                args=(user_name, user_session, message_type, role, message, session_id),
                daemon=True
            ).start()
            return True
        
        # Use MemoryManager to store message
        try:
            self.memory_manager.store_message(
                user=user_name,
                message=message,
                role=role,
                session_id=session_id,
                message_type=message_type,
                user_session=user_session
            )
            logger.debug(f"Saved {role} {message_type} message from {user_name} via MemoryManager")
            return True
        except Exception as e:
            logger.error(f"Error saving message via MemoryManager: {e}")
            # Fallback to old method
            threading.Thread(
                target=self._save_message_sync,
                args=(user_name, user_session, message_type, role, message, session_id),
                daemon=True
            ).start()
            return True

    def _save_message_sync(self, user_name, user_session, message_type, role, message, session_id=None):
        """Internal synchronous save method run in background thread"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                logger.warning("Cannot save message: database connection unavailable")
                return False

            # Generate embedding for the message
            embedding = self.generate_embedding(message)

            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversation_history
                (user_name, user_session, session_id, message_type, role, message, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (user_name, user_session, session_id, message_type, role, message, embedding)
            )
            conn.commit()
            cursor.close()
            logger.debug(f"Saved {role} {message_type} message from {user_name} (session: {session_id})")
            return True
        except Exception as e:
            logger.error(f"Error saving message to database: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error during rollback: {rollback_error}")
            return False
        finally:
            if conn:
                self.release_db_connection(conn)

    def get_conversation_history(self, user_name=None, limit=10, session_id=None):
        """Retrieve recent conversation history with error handling"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                logger.warning("Cannot retrieve conversation history: database connection unavailable")
                return []

            cursor = conn.cursor()

            if session_id:
                # Get history for specific session
                cursor.execute(
                    """
                    SELECT role, message, message_type, timestamp
                    FROM conversation_history
                    WHERE session_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (session_id, limit)
                )
            elif user_name:
                cursor.execute(
                    """
                    SELECT role, message, message_type, timestamp
                    FROM conversation_history
                    WHERE user_name = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (user_name, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT role, message, message_type, timestamp
                    FROM conversation_history
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (limit,)
                )

            results = cursor.fetchall()
            cursor.close()

            # Reverse to get chronological order
            return list(reversed(results))
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []
        finally:
            if conn:
                self.release_db_connection(conn)

    def get_config(self, key, default=None):
        """Get a config value from the database with caching for performance"""
        # Check cache first
        cached_value = self.smart_cache.get_cached_config(key)
        if cached_value is not None:
            return cached_value
        
        # Cache miss, fetch from database
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                logger.warning(f"Cannot get config {key}: database connection unavailable")
                return default
                
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_config WHERE key = %s", (key,))
            result = cursor.fetchone()
            cursor.close()

            if result:
                value = result[0]
                # Cache the value
                self.smart_cache.cache_config(key, value)
                return value
            return default
        except Exception as e:
            logger.error(f"Error getting config {key}: {e}")
            return default
        finally:
            if conn:
                self.release_db_connection(conn)

    @retry_with_exponential_backoff(RetryConfig(max_attempts=10, base_delay=3.0, max_delay=60.0))
    def connect(self):
        """Connect to Mumble server with retry logic"""
        logger.info(f"Connecting to Mumble server at {self.mumble_host}:{self.mumble_port}")

        try:
            self.mumble = Mumble(self.mumble_host, self.mumble_username,
                                port=self.mumble_port, password=self.mumble_password)

            self.mumble.callbacks.set_callback('sound_received', self.on_sound_received)
            self.mumble.callbacks.set_callback('text_received', self.on_text_received)
            self.mumble.set_receive_sound(True)

            self.mumble.start()
            self.mumble.is_ready()

            logger.info("Connected to Mumble server")
            self.last_health_check['mumble'] = time.time()
        except Exception as e:
            logger.error(f"Failed to connect to Mumble server: {e}")
            raise

    def on_sound_received(self, user, sound):
        """Called when audio is received from a user"""
        if user['session'] == self.mumble.users.myself['session']:
            return  # Ignore our own audio

        user_id = user['session']
        current_time = time.time()

        # Initialize buffer for new user
        if user_id not in self.audio_buffer:
            self.audio_buffer[user_id] = []
            self.recording[user_id] = False
            self.last_audio_time[user_id] = current_time

        # Add audio to buffer
        self.audio_buffer[user_id].append(sound.pcm)
        self.last_audio_time[user_id] = current_time

        if not self.recording[user_id]:
            self.recording[user_id] = True
            logger.info(f"Started recording from {user['name']}")

            # Start a thread to check for silence
            threading.Thread(target=self.check_silence, args=(user_id, user['name'])).start()

    def on_text_received(self, text):
        """Called when a text message is received"""
        try:
            message = text.message.strip()
            sender = text.actor

            # Ignore our own messages
            if sender == self.mumble.users.myself['session']:
                return

            # Get sender name
            sender_name = self.mumble.users[sender]['name'] if sender in self.mumble.users else "Unknown"

            # Ignore empty messages
            if not message:
                return

            # Ignore server notifications and warnings (they contain HTML tags and specific keywords)
            server_message_indicators = [
                '<b>[WARNING]</b>',
                'ChannelListener',
                'upgrade to Mumble',
                'upgrading to Mumble',
                '<b>[NOTICE]</b>',
                '<b>[INFO]</b>',
                'server has the',
                'feature enabled'
            ]

            # Check if this is a server message
            is_server_message = any(indicator in message for indicator in server_message_indicators)

            if is_server_message:
                logger.info(f"Ignoring server notification from {sender_name}: {message[:100]}...")
                return

            logger.info(f"Text message from {sender_name}: {message}")

            # Process in a separate thread to not block
            threading.Thread(target=self.process_text_message, args=(message, sender_name, sender)).start()

        except Exception as e:
            logger.error(f"Error handling text message: {e}", exc_info=True)

    def process_text_message(self, message, sender_name, sender_session=0):
        """Process a text message and send a text-only response"""
        try:
            # Get or create session for this user
            session_id = self.get_or_create_session(sender_name, sender_session)

            # Save user message SYNCHRONOUSLY first so it's in the context for immediate follow-ups
            self._save_message_sync(sender_name, sender_session, 'text', 'user', message, session_id)

            # Track new topics (before getting response)
            self.track_new_topic(message, sender_name, session_id)

            # Get Ollama response (now with user message in DB)
            logger.info(f"Getting Ollama response for text from {sender_name}...")
            response_text = self.get_ollama_response(message, user_name=sender_name, session_id=session_id)
            logger.info(f"Ollama text response: {response_text}")

            # Save assistant response asynchronously (not needed for immediate context)
            self.save_message(sender_name, sender_session, 'text', 'assistant', response_text, session_id=session_id)

            # Extract and save memories in background (non-blocking)
            threading.Thread(
                target=self.extract_and_save_memory,
                args=(message, response_text, sender_name, session_id),
                daemon=True
            ).start()

            # Extract and manage schedule in background (non-blocking)
            threading.Thread(
                target=self.extract_and_manage_schedule,
                args=(message, response_text, sender_name),
                daemon=True
            ).start()
            
            # Extract and track entities in background (non-blocking)
            threading.Thread(
                target=self.extract_and_save_entities,
                args=(message, response_text, sender_name, session_id),
                daemon=True
            ).start()

            # Send text-only response (no TTS for text messages)
            self.mumble.my_channel().send_text_message(response_text)
            logger.info("Text response sent")

        except Exception as e:
            logger.error(f"Error processing text message: {e}", exc_info=True)

    def check_silence(self, user_id, user_name):
        """Check if user has stopped speaking and process audio"""
        while True:
            time.sleep(0.5)

            if user_id not in self.last_audio_time:
                break

            time_since_audio = time.time() - self.last_audio_time[user_id]

            if time_since_audio > self.silence_threshold:
                logger.info(f"Silence detected from {user_name}, processing audio")
                self.process_audio(user_id, user_name)
                break

    def process_audio(self, user_id, user_name):
        """Process recorded audio through the AI pipeline"""
        if user_id not in self.audio_buffer or len(self.audio_buffer[user_id]) == 0:
            return

        try:
            # Get or create session for this user
            session_id = self.get_or_create_session(user_name, user_id)

            # Get audio buffer
            audio_data = self.audio_buffer[user_id]
            self.audio_buffer[user_id] = []
            self.recording[user_id] = False

            # Convert PCM to WAV
            wav_data = self.pcm_to_wav(audio_data)

            # Transcribe with Whisper
            logger.info("Transcribing audio...")
            transcript = self.transcribe(wav_data)

            if not transcript or len(transcript.strip()) == 0:
                logger.info("No speech detected")
                return

            logger.info(f"Transcribed: {transcript}")

            # Save user message SYNCHRONOUSLY first so it's in the context for immediate follow-ups
            self._save_message_sync(user_name, user_id, 'voice', 'user', transcript, session_id)

            # Get response from Ollama (now with user message in DB)
            logger.info("Getting response from Ollama...")
            response_text = self.get_ollama_response(transcript, user_name=user_name, session_id=session_id)
            logger.info(f"Ollama response: {response_text}")

            # Save assistant response asynchronously (not needed for immediate context)
            self.save_message(user_name, user_id, 'voice', 'assistant', response_text, session_id=session_id)

            # Extract and save memories in background (non-blocking)
            threading.Thread(
                target=self.extract_and_save_memory,
                args=(transcript, response_text, user_name, session_id),
                daemon=True
            ).start()

            # Extract and manage schedule in background (non-blocking)
            threading.Thread(
                target=self.extract_and_manage_schedule,
                args=(transcript, response_text, user_name),
                daemon=True
            ).start()
            
            # Extract and track entities in background (non-blocking)
            threading.Thread(
                target=self.extract_and_save_entities,
                args=(transcript, response_text, user_name, session_id),
                daemon=True
            ).start()

            # Synthesize speech
            logger.info("Synthesizing speech...")
            audio = self.synthesize_speech(response_text)

            # Play audio back to Mumble
            logger.info("Playing response...")
            self.play_audio(audio)

        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)

    def pcm_to_wav(self, pcm_chunks):
        """Convert PCM audio chunks to WAV format"""
        output = io.BytesIO()

        with wave.open(output, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(48000)  # 48kHz

            for chunk in pcm_chunks:
                wav_file.writeframes(chunk)

        output.seek(0)
        return output

    def transcribe(self, audio_data):
        """Send audio to Whisper for transcription with circuit breaker protection"""
        try:
            return self.whisper_circuit_breaker.call(self._transcribe_internal, audio_data)
        except CircuitBreakerError:
            logger.error("Whisper circuit breaker is open, cannot transcribe audio")
            return None

    def _transcribe_internal(self, audio_data):
        """Internal transcription method"""
        # Get language setting from database
        language = self.get_config('whisper_language', 'auto')

        files = {'audio': ('audio.wav', audio_data, 'audio/wav')}
        data = {'language': language}
        response = requests.post(f"{self.whisper_url}/transcribe", files=files, data=data, timeout=300)

        if response.status_code == 200:
            return response.json().get('text', '')
        else:
            raise requests.RequestException(f"Transcription failed: {response.text}")

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text using Ollama's embedding model with smart caching"""
        # Check smart cache first (longer TTL for embeddings)
        text_hash = hashlib.md5(text.encode()).hexdigest()
        cached_embedding = self.smart_cache.get_cached_embedding(text_hash)
        if cached_embedding is not None:
            return cached_embedding
        
        # Also check legacy cache for backward compatibility
        if text_hash in self.embedding_cache:
            return self.embedding_cache[text_hash]

        try:
            embedding_model = self.get_config('embedding_model', 'nomic-embed-text:latest')
            ollama_url = self.get_config('ollama_url', self.ollama_url)
            logger.debug(f"Generating embedding using model: {embedding_model}")

            response = requests.post(
                f"{ollama_url}/api/embeddings",
                json={
                    'model': embedding_model,
                    'prompt': text
                },
                timeout=300  # 5 minutes for embedding generation
            )

            if response.status_code == 200:
                embedding = response.json().get('embedding', [])
                # Cache the embedding in smart cache
                self.smart_cache.cache_embedding(text_hash, embedding)
                # Also keep in legacy cache for backward compatibility
                self.embedding_cache[text_hash] = embedding
                return embedding
            else:
                logger.warning(f"Failed to generate embedding: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def get_or_create_session(self, user_name: str, user_session: int) -> str:
        """Get or create a conversation session ID for a user
        
        This method ensures the bot remains available by:
        1. Reusing active sessions if they exist
        2. Reactivating idle sessions if recent enough
        3. Creating new sessions when needed
        """
        with self.session_lock:
            # Check if user has an active session in memory
            if user_name in self.user_sessions:
                session_id = self.user_sessions[user_name]
                # Verify session is still valid in database
                if self._verify_session_active(session_id):
                    # Update session activity
                    self._update_session_activity(session_id)
                    logger.debug(f"Reusing active session {session_id} for {user_name}")
                    return session_id
                else:
                    # Session no longer valid, remove from memory
                    logger.info(f"Removing invalid session {session_id} from memory for {user_name}")
                    del self.user_sessions[user_name]

            # Check if there's a recent idle session in the database that can be reactivated
            recent_session_id = self._get_recent_idle_session(user_name)
            if recent_session_id:
                # Reactivate the idle session
                self._reactivate_session(recent_session_id)
                self.user_sessions[user_name] = recent_session_id
                logger.info(f"Reactivated idle session {recent_session_id} for {user_name}")
                return recent_session_id

            # Create new session
            session_id = f"{user_name}_{uuid.uuid4().hex[:8]}_{int(time.time())}"
            self.user_sessions[user_name] = session_id

            # Store in database
            conn = None
            try:
                conn = self.get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO conversation_sessions (user_name, session_id, started_at, last_activity, state)
                        VALUES (%s, %s, %s, %s, 'active')
                        ON CONFLICT (session_id) DO UPDATE 
                        SET last_activity = EXCLUDED.last_activity, state = 'active'
                        """,
                        (user_name, session_id, datetime.now(), datetime.now())
                    )
                    conn.commit()
                    cursor.close()
                    logger.info(f"Created new session {session_id} for {user_name}")
            except Exception as e:
                logger.error(f"Error creating session: {e}")
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    self.release_db_connection(conn)

            return session_id

    def _verify_session_active(self, session_id: str) -> bool:
        """Verify that a session is still active in the database"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT state FROM conversation_sessions
                WHERE session_id = %s
                """,
                (session_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            # Session is valid if it exists and is in 'active' state
            return result is not None and result[0] == 'active'
            
        except Exception as e:
            logger.error(f"Error verifying session {session_id}: {e}")
            return False
        finally:
            if conn:
                self.release_db_connection(conn)

    def _get_recent_idle_session(self, user_name: str) -> Optional[str]:
        """Get the most recent idle session for a user if within reactivation window"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return None
            
            # Get reactivation window from config (default 10 minutes)
            reactivation_window_minutes = int(self.get_config('session_reactivation_minutes', '10'))
            
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT session_id FROM conversation_sessions
                WHERE user_name = %s 
                  AND state = 'idle'
                  AND last_activity > %s
                ORDER BY last_activity DESC
                LIMIT 1
                """,
                (user_name, datetime.now() - timedelta(minutes=reactivation_window_minutes))
            )
            result = cursor.fetchone()
            cursor.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error getting recent idle session for {user_name}: {e}")
            return None
        finally:
            if conn:
                self.release_db_connection(conn)

    def _reactivate_session(self, session_id: str):
        """Reactivate an idle session"""
        conn = None
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE conversation_sessions
                    SET state = 'active', last_activity = %s
                    WHERE session_id = %s
                    """,
                    (datetime.now(), session_id)
                )
                conn.commit()
                cursor.close()
        except Exception as e:
            logger.error(f"Error reactivating session {session_id}: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self.release_db_connection(conn)

    def _update_session_activity(self, session_id: str):
        """Update the last activity timestamp for a session"""
        conn = None
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE conversation_sessions
                    SET last_activity = %s, message_count = message_count + 1
                    WHERE session_id = %s
                    """,
                    (datetime.now(), session_id)
                )
                conn.commit()
                cursor.close()
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self.release_db_connection(conn)

    def close_idle_sessions(self):
        """Close sessions that have been idle for too long"""
        timeout_minutes = int(self.get_config('session_timeout_minutes', '30'))
        timeout_delta = timedelta(minutes=timeout_minutes)

        conn = None
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE conversation_sessions
                    SET state = 'idle'
                    WHERE state = 'active' AND last_activity < %s
                    RETURNING session_id, user_name
                    """,
                    (datetime.now() - timeout_delta,)
                )
                idle_sessions = cursor.fetchall()
                conn.commit()
                cursor.close()

                # Remove from active sessions
                with self.session_lock:
                    for session_id, user_name in idle_sessions:
                        if user_name in self.user_sessions and self.user_sessions[user_name] == session_id:
                            del self.user_sessions[user_name]
                            logger.info(f"Closed idle session {session_id} for {user_name}")
        except Exception as e:
            logger.error(f"Error closing idle sessions: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self.release_db_connection(conn)

    def extract_and_save_memory(self, user_message: str, assistant_response: str, user_name: str, session_id: str):
        """Extract important information from conversation and save as persistent memory"""
        try:
            ollama_url = self.get_config('ollama_url', self.ollama_url)
            # Use specialized memory extraction model for better precision
            ollama_model = self.get_config('memory_extraction_model', 'qwen2.5:3b')
            logger.info(f"Memory extraction using model: {ollama_model}")

            # Get current date for context
            from zoneinfo import ZoneInfo
            ny_tz = ZoneInfo("America/New_York")
            current_datetime = datetime.now(ny_tz)
            current_date_str = current_datetime.strftime("%Y-%m-%d (%A, %B %d, %Y)")

            # Prompt to extract important information with stricter JSON format requirements
            extraction_prompt = f"""Analyze this conversation and extract ONLY truly important information worth remembering long-term.

CURRENT DATE: {current_date_str}

User: "{user_message}"
Assistant: "{assistant_response}"

Categories:
- schedule: appointments, meetings, events with dates/times (must have specific date/time)
- fact: personal information, preferences, relationships, important details
- task: significant action items with lasting value (not immediate/temporary tasks)
- preference: likes, dislikes, habits
- other: other important information

CRITICAL RULES - BE VERY SELECTIVE:
1. ONLY extract information that would be valuable to remember weeks or months from now
2. Do NOT create entries with empty content
3. If there's nothing important to remember, return an empty array: []
4. You MUST respond with ONLY valid JSON, nothing else
5. When in doubt, DO NOT extract - it's better to miss something than to save junk

DO NOT EXTRACT:
- Immediate/temporary tasks (e.g., "get the bath going", "clean up", "turn on the light")
- Conversational pleasantries (e.g., "good morning", "I'm excited", "feeling nervous")
- Vague or incomplete statements (e.g., "follows boundaries", "review this", "clean up")
- Meta-instructions about calendar (e.g., "make sure it's on your calendar", "review attachment")
- Query questions (e.g., "What's on my schedule?", "Do I have anything tomorrow?")
- Confirmations or reminders of existing events (e.g., "Your flight confirmation", "Reminder: appointment")
- Tasks that are happening RIGHT NOW or within the next few hours
- Emotional states or feelings unless medically significant
- Fragments or partial sentences that lack context

ONLY EXTRACT:
- Schedule: Specific appointments/events with clear dates (e.g., "Doctor appointment next Tuesday 2pm")
- Facts: Significant personal details (e.g., "Allergic to peanuts", "Works as IT Consultant at Acme Corp")
- Tasks: Important action items with lasting value (e.g., "File taxes by April 15", "Renew passport")
- Preferences: Meaningful preferences (e.g., "Prefers vegetarian meals", "Dislikes horror movies")

SCHEDULE RULES:
- DO NOT extract when user is ASKING about their schedule
- ONLY extract when user is TELLING you about NEW events
- DO NOT extract from confirmation emails or reminders
- Must have specific details (who, what, when)
- Must include date_expression and be parseable

TASK RULES:
- Task must have value beyond today
- Must be specific and actionable
- NO temporary household tasks (cleaning, cooking, bathing)
- NO immediate requests (happening in next few hours)

FACT RULES:
- Must be objectively important personal information
- NO conversational fluff or emotions
- NO incomplete fragments
- Must add value to future conversations

EXAMPLES OF WHAT NOT TO EXTRACT:
❌ "Wait for you to get in the bath" (immediate, temporary)
❌ "Clean up" (vague, temporary)
❌ "Review this and make sure it's on your calendar" (meta-instruction)
❌ "Lovely morning! Feeling nervous..." (conversational fluff)
❌ "follows boundaries that work for both of us" (fragment, vague)
❌ "Baby showers" (too vague, no details)
❌ "Travel Dates review" (vague, meta-instruction)
❌ "What's on my schedule?" (query question)

EXAMPLES OF WHAT TO EXTRACT:
✅ {{"category": "schedule", "content": "Dr. Smith annual checkup", "importance": 7, "date_expression": "next Tuesday", "event_time": "14:00"}}
✅ {{"category": "fact", "content": "Works as IT Consultant at Microsoft", "importance": 6}}
✅ {{"category": "task", "content": "Renew driver's license before it expires in March", "importance": 8}}
✅ {{"category": "preference", "content": "Prefers decaf coffee after 3pm", "importance": 4}}

For SCHEDULE category memories:
- Extract the date expression as spoken: "next Friday", "tomorrow", "October 15", etc.
- Use date_expression field for the raw expression
- Use HH:MM format (24-hour) for event_time, or use actual null (not the string "null") if no specific time
- Include specific description in content field (who, what)

Format (return empty array if nothing important):
[
  {{"category": "schedule", "content": "Haircut appointment with Jane", "importance": 6, "date_expression": "next Friday", "event_time": "09:30"}},
  {{"category": "fact", "content": "Allergic to shellfish", "importance": 8}}
]

Valid categories: schedule, fact, task, preference, other
Importance: 1-10 (1=low, 10=critical)

REMEMBER: When in doubt, return []. Better to miss something than save junk!

JSON:"""

            # Retry logic for memory extraction (up to 3 attempts with 3 minute timeout)
            max_retries = 3
            retry_count = 0
            response = None

            while retry_count < max_retries:
                try:
                    response = requests.post(
                        f"{ollama_url}/api/generate",
                        json={
                            'model': ollama_model,
                            'prompt': extraction_prompt,
                            'stream': False,
                            'options': {
                                'temperature': 0.2,  # Very low temp for consistent JSON
                                'num_predict': 500   # Limit response length
                            }
                        },
                        timeout=300  # 5 minutes timeout for memory extraction
                    )
                    break  # Success, exit retry loop
                except requests.exceptions.Timeout as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"Memory extraction timeout (attempt {retry_count}/{max_retries}), retrying...")
                        time.sleep(2)  # Brief delay before retry
                    else:
                        logger.error(f"Memory extraction failed after {max_retries} attempts: {e}")
                        return
                except requests.exceptions.RequestException as e:
                    logger.error(f"Network error during memory extraction: {e}")
                    return

            if response and response.status_code == 200:
                result = response.json().get('response', '').strip()
                logger.debug(f"Memory extraction raw response: {result[:200]}...")

                # Try to parse and save memories
                memories = self._parse_memory_json(result)
                if memories is not None:
                    # Filter out memories with empty or whitespace-only content
                    valid_memories = []
                    for mem in memories:
                        if isinstance(mem, dict) and 'content' in mem:
                            content = mem.get('content', '')
                            # Skip if content is not a string or is empty/whitespace
                            if isinstance(content, str) and content.strip():
                                valid_memories.append(mem)
                            else:
                                # Debug level for expected LLM artifacts
                                logger.debug(f"Filtered out empty memory: category={mem.get('category')}, importance={mem.get('importance')}")

                    saved_count = 0
                    for memory in valid_memories:
                        if self._validate_memory(memory):
                            # Parse date expression for schedule memories
                            event_date = None
                            event_time = memory.get('event_time')

                            if memory.get('category') == 'schedule':
                                date_expression = memory.get('date_expression') or memory.get('event_date')
                                if date_expression:
                                    event_date = self.parse_date_expression(date_expression)
                                
                                # Skip schedule memories with unparseable dates
                                if event_date is None:
                                    logger.warning(f"Skipping schedule memory with unparseable date: '{date_expression}' - {memory['content']}")
                                    continue

                            self.save_persistent_memory(
                                user_name=user_name,
                                category=memory.get('category', 'other'),
                                content=memory['content'],
                                session_id=session_id,
                                importance=memory.get('importance', 5),
                                event_date=event_date,
                                event_time=event_time
                            )
                            if event_date:
                                logger.info(f"Extracted memory for {user_name}: [{memory.get('category')}] {memory['content']} on {event_date} at {event_time or 'all day'}")
                            else:
                                logger.info(f"Extracted memory for {user_name}: [{memory.get('category')}] {memory['content']}")
                            saved_count += 1
                        else:
                            # Only warn if content exists but other validation failed
                            logger.warning(f"Skipping invalid memory (failed validation): {memory}")
                    
                    if saved_count == 0 and len(memories) == 0:
                        logger.debug(f"No important memories found in conversation with {user_name}")
                else:
                    logger.warning(f"Failed to extract valid JSON from memory extraction response")

        except Exception as e:
            logger.error(f"Error extracting memory: {e}", exc_info=True)

    def extract_and_save_entities(self, user_message: str, assistant_response: str, user_name: str, session_id: str):
        """Extract entities from conversation and save to entity_mentions table"""
        try:
            ollama_url = self.get_config('ollama_url', self.ollama_url)
            ollama_model = self.get_config('memory_extraction_model', 'qwen2.5:3b')
            logger.info(f"Entity extraction using model: {ollama_model}")

            # Prompt to extract entities
            extraction_prompt = f"""Analyze this conversation and extract entities (people, places, organizations, dates, times, events).

User: "{user_message}"
Assistant: "{assistant_response}"

Extract entities in the following categories:
- PERSON: Names of people (e.g., "John Smith", "Dr. Johnson", "Mom")
- PLACE: Locations, addresses, cities, buildings (e.g., "New York", "Central Hospital", "123 Main St")
- ORGANIZATION: Companies, institutions, groups (e.g., "Microsoft", "City Council", "Red Cross")
- DATE: Specific dates or date references (e.g., "next Monday", "October 15", "tomorrow")
- TIME: Specific times (e.g., "3pm", "14:00", "noon")
- EVENT: Named events or occasions (e.g., "Birthday party", "Annual conference", "Summer BBQ")
- OTHER: Other relevant entities not fitting above categories

Rules:
1. Only extract explicitly mentioned entities
2. Return empty array if no entities found
3. Provide confidence score (0.0-1.0) for each entity
4. Include surrounding context in context_info field
5. Respond ONLY with valid JSON array

Format:
[
  {{"entity_text": "John Smith", "entity_type": "PERSON", "confidence": 0.95, "context_info": "Meeting with John Smith"}},
  {{"entity_text": "next Tuesday", "entity_type": "DATE", "confidence": 0.9, "context_info": "Appointment scheduled for next Tuesday"}}
]

JSON:"""

            # Call Ollama with timeout
            try:
                response = requests.post(
                    f"{ollama_url}/api/generate",
                    json={
                        'model': ollama_model,
                        'prompt': extraction_prompt,
                        'stream': False,
                        'options': {
                            'temperature': 0.2,
                            'num_predict': 500
                        }
                    },
                    timeout=300  # 5 minutes timeout for entity extraction
                )
            except requests.exceptions.Timeout:
                logger.warning("Entity extraction timeout, skipping")
                return
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error during entity extraction: {e}")
                return

            if response and response.status_code == 200:
                result = response.json().get('response', '').strip()
                logger.debug(f"Entity extraction raw response: {result[:200]}...")

                # Parse JSON response
                try:
                    # Clean up response
                    result = result.strip()
                    if result.startswith('```json'):
                        result = result[7:]
                    if result.startswith('```'):
                        result = result[3:]
                    if result.endswith('```'):
                        result = result[:-3]
                    result = result.strip()

                    entities = json.loads(result)

                    if not isinstance(entities, list):
                        logger.warning("Entity extraction did not return a list")
                        return

                    if len(entities) == 0:
                        logger.debug("No entities extracted from conversation")
                        return

                    # Get the message_id for linking
                    conn = None
                    try:
                        conn = self.get_db_connection()
                        if not conn:
                            logger.warning("Cannot save entities: database connection unavailable")
                            return

                        cursor = conn.cursor()

                        # Get most recent message ID for this user/session
                        cursor.execute("""
                            SELECT id FROM conversation_history
                            WHERE user_name = %s AND session_id = %s
                            ORDER BY timestamp DESC
                            LIMIT 1
                        """, (user_name, session_id))

                        message_row = cursor.fetchone()
                        if not message_row:
                            logger.warning(f"Could not find message for entity linking: {user_name}/{session_id}")
                            cursor.close()
                            return

                        message_id = message_row[0]

                        # Save each entity
                        saved_count = 0
                        for entity in entities:
                            if not isinstance(entity, dict):
                                continue

                            entity_text = entity.get('entity_text', '').strip()
                            entity_type = entity.get('entity_type', 'OTHER').upper()
                            confidence = entity.get('confidence', 1.0)
                            context_info = entity.get('context_info', '')

                            if not entity_text:
                                continue

                            # Validate entity_type
                            valid_types = ['PERSON', 'PLACE', 'ORGANIZATION', 'DATE', 'TIME', 'EVENT', 'OTHER']
                            if entity_type not in valid_types:
                                entity_type = 'OTHER'

                            try:
                                cursor.execute("""
                                    INSERT INTO entity_mentions
                                    (user_name, entity_text, entity_type, message_id, confidence, context_info)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (user_name, entity_text, entity_type, message_id, confidence, context_info))
                                saved_count += 1
                            except Exception as e:
                                logger.error(f"Error saving entity {entity_text}: {e}")

                        conn.commit()
                        cursor.close()
                        logger.info(f"Saved {saved_count} entities from conversation with {user_name}")

                    except Exception as e:
                        logger.error(f"Database error saving entities: {e}")
                        if conn:
                            conn.rollback()
                    finally:
                        if conn:
                            self.release_db_connection(conn)

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse entity extraction JSON: {e}")
                except Exception as e:
                    logger.error(f"Error processing entities: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error extracting entities: {e}", exc_info=True)

    def consolidate_old_conversations(self, cutoff_days: int = 7, user_name: Optional[str] = None):
        """
        Consolidate old conversations into summaries to save tokens.

        Args:
            cutoff_days: Messages older than this many days will be consolidated
            user_name: Optional - consolidate for specific user only
        """
        try:
            conn = self.get_db_connection()
            if not conn:
                logger.warning("Cannot consolidate: database connection unavailable")
                return

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
                logger.info("No old conversations to consolidate")
                cursor.close()
                return

            logger.info(f"Starting consolidation for {len(users_to_consolidate)} users (cutoff: {cutoff_date})")

            total_messages_consolidated = 0
            total_summaries_created = 0
            total_tokens_saved_estimate = 0

            ollama_url = self.get_config('ollama_url', self.ollama_url)
            ollama_model = self.get_config('memory_extraction_model', 'qwen2.5:3b')

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
                            timeout=300  # 5 minute timeout for consolidation
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

                                # Estimate tokens saved (rough estimate: 1 token ≈ 4 characters)
                                original_tokens = len(conversation_text) // 4
                                summary_tokens = len(summary) // 4
                                tokens_saved = max(0, original_tokens - summary_tokens)

                                # Delete or mark old messages as consolidated
                                cursor.execute("""
                                    DELETE FROM conversation_history
                                    WHERE id = ANY(%s)
                                """, (message_ids,))

                                total_messages_consolidated += len(old_messages)
                                total_summaries_created += 1
                                total_tokens_saved_estimate += tokens_saved

                                logger.info(f"Consolidated {len(old_messages)} messages for {user}, saved ~{tokens_saved} tokens")
                            else:
                                logger.warning(f"Empty summary for {user}, skipping consolidation")
                        else:
                            logger.error(f"Ollama error during consolidation for {user}: {response.status_code if response else 'No response'}")

                    except requests.exceptions.Timeout:
                        logger.warning(f"Consolidation timeout for {user}, skipping")
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Network error during consolidation for {user}: {e}")

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
                logger.info(f"Consolidation complete: {total_messages_consolidated} messages → {total_summaries_created} summaries, ~{total_tokens_saved_estimate} tokens saved")
            else:
                logger.info("No consolidation performed")

            cursor.close()

        except Exception as e:
            logger.error(f"Error in consolidate_old_conversations: {e}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if conn:
                self.release_db_connection(conn)

    def _normalize_null_values(self, memories: List[Dict]) -> List[Dict]:
        """Convert string 'null' to actual None in memory objects"""
        null_fields = ['event_time', 'event_date', 'date_expression', 'description', 'time']
        
        for memory in memories:
            if isinstance(memory, dict):
                for field in null_fields:
                    if field in memory and memory[field] == "null":
                        memory[field] = None
        
        return memories

    def _parse_memory_json(self, text: str) -> Optional[List[Dict]]:
        """Parse JSON from LLM response with multiple fallback strategies"""
        import re
        
        # Strategy 1: Try direct JSON parsing
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return self._normalize_null_values(parsed)
            logger.warning("Parsed JSON is not a list, trying extraction...")
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract JSON array with regex
        try:
            # Look for JSON array, being more careful about matching
            json_match = re.search(r'\[\s*(?:\{.*?\}\s*,?\s*)*\]', text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    return self._normalize_null_values(parsed)
        except (json.JSONDecodeError, AttributeError):
            pass

        # Strategy 3: Clean common issues and retry
        try:
            # Remove common text before/after JSON
            cleaned = text
            
            # Remove markdown code blocks
            cleaned = re.sub(r'```json\s*', '', cleaned)
            cleaned = re.sub(r'```\s*', '', cleaned)
            
            # Find content between first [ and last ]
            start_idx = cleaned.find('[')
            end_idx = cleaned.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_str = cleaned[start_idx:end_idx + 1]
                
                # Try to fix common JSON issues
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
                
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    return self._normalize_null_values(parsed)
        except (json.JSONDecodeError, AttributeError, ValueError):
            pass

        # Strategy 4: Return empty list if response suggests nothing to remember
        if any(phrase in text.lower() for phrase in ['nothing important', 'no important', 'empty array', '[]']):
            logger.debug("LLM indicated no important memories")
            return []

        # All strategies failed
        logger.error(f"Could not parse JSON from memory extraction. Response: {text[:500]}")
        return None

    def _validate_memory(self, memory: Dict) -> bool:
        """Validate a memory object has required fields and valid values"""
        if not isinstance(memory, dict):
            return False
        
        # Must have content and category
        if 'content' not in memory or 'category' not in memory:
            return False
        
        # Content must be non-empty string
        if not isinstance(memory['content'], str) or not memory['content'].strip():
            return False
        
        # Category must be valid
        valid_categories = ['schedule', 'fact', 'task', 'preference', 'other']
        if memory['category'] not in valid_categories:
            logger.warning(f"Invalid category '{memory['category']}', defaulting to 'other'")
            memory['category'] = 'other'
        
        # Importance should be 1-10 if present
        if 'importance' in memory:
            try:
                importance = int(memory['importance'])
                if importance < 1 or importance > 10:
                    logger.warning(f"Importance {importance} out of range, clamping to 1-10")
                    memory['importance'] = max(1, min(10, importance))
            except (ValueError, TypeError):
                logger.warning(f"Invalid importance value, defaulting to 5")
                memory['importance'] = 5
        
        return True

    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two content strings based on word overlap"""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0

    def save_persistent_memory(self, user_name: str, category: str, content: str, session_id: str = None, importance: int = 5, tags: List[str] = None, event_date: str = None, event_time: str = None):
        """Save a persistent memory to the database (with deduplication)"""
        conn = None
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Check for duplicates based on category type
                if category == 'schedule' and event_date:
                    # For schedule memories, check exact match first
                    cursor.execute(
                        """
                        SELECT id, content, importance
                        FROM persistent_memories
                        WHERE user_name = %s AND category = %s AND event_date = %s
                        AND event_time IS NOT DISTINCT FROM %s AND active = TRUE
                        """,
                        (user_name, category, event_date, event_time)
                    )
                    
                    existing = cursor.fetchone()
                    
                    # If no exact match, check for similar events within ±3 days
                    if not existing:
                        try:
                            target_date = datetime.strptime(event_date, '%Y-%m-%d').date()
                            date_range_start = (target_date - timedelta(days=3)).strftime('%Y-%m-%d')
                            date_range_end = (target_date + timedelta(days=3)).strftime('%Y-%m-%d')
                            
                            cursor.execute(
                                """
                                SELECT id, content, importance, event_date
                                FROM persistent_memories
                                WHERE user_name = %s AND category = %s 
                                AND event_date BETWEEN %s AND %s
                                AND active = TRUE
                                """,
                                (user_name, category, date_range_start, date_range_end)
                            )
                            
                            nearby_events = cursor.fetchall()
                            
                            # Check for similar content using fuzzy matching
                            for event_id, event_content, event_importance, event_date_str in nearby_events:
                                similarity = self._calculate_content_similarity(content, event_content)
                                if similarity > 0.6:  # >60% word overlap
                                    logger.info(f"Similar schedule event detected for {user_name}: '{content}' vs '{event_content}' (similarity: {similarity:.2f}). Skipping. Existing ID: {event_id}")
                                    cursor.close()
                                    return
                        except Exception as e:
                            logger.debug(f"Error in fuzzy deduplication check: {e}")
                            # Continue with normal processing if fuzzy matching fails
                    
                    if existing:
                        existing_id, existing_content, existing_importance = existing
                        logger.info(f"Duplicate schedule memory detected for {user_name} on {event_date}. Skipping. Existing ID: {existing_id}")
                        
                        # If new importance is higher, update it
                        if importance > existing_importance:
                            cursor.execute(
                                "UPDATE persistent_memories SET importance = %s WHERE id = %s",
                                (importance, existing_id)
                            )
                            conn.commit()
                            logger.info(f"Updated importance of existing memory ID {existing_id} from {existing_importance} to {importance}")
                        
                        cursor.close()
                        return
                else:
                    # For non-schedule memories, check for exact content match
                    cursor.execute(
                        """
                        SELECT id, importance
                        FROM persistent_memories
                        WHERE user_name = %s AND category = %s AND content = %s AND active = TRUE
                        """,
                        (user_name, category, content)
                    )

                existing = cursor.fetchone()

                if existing:
                    if category == 'schedule':
                        existing_id, existing_content, existing_importance = existing
                        logger.info(f"Duplicate schedule memory detected for {user_name} on {event_date}. Skipping. Existing ID: {existing_id}")
                    else:
                        existing_id, existing_importance = existing
                        logger.info(f"Duplicate {category} memory detected for {user_name}: '{content[:50]}...'. Skipping. Existing ID: {existing_id}")

                    # If new importance is higher, update it
                    if importance > existing_importance:
                        cursor.execute(
                            "UPDATE persistent_memories SET importance = %s WHERE id = %s",
                            (importance, existing_id)
                        )
                        conn.commit()
                        logger.info(f"Updated importance of existing memory ID {existing_id} from {existing_importance} to {importance}")

                    cursor.close()
                    return

                # No duplicate found, insert new memory
                # Generate embedding for semantic search
                embedding = self.generate_embedding(content)
                
                cursor.execute(
                    """
                    INSERT INTO persistent_memories
                    (user_name, category, content, session_id, importance, tags, event_date, event_time, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_name, category, content, session_id, importance, tags or [], event_date, event_time, embedding)
                )
                conn.commit()
                cursor.close()
                # Invalidate cache since we added a new memory
                self.smart_cache.invalidate_user(user_name)
                logger.info(f"Saved new {category} memory for {user_name} with embedding")
        except Exception as e:
            logger.error(f"Error saving persistent memory: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self.release_db_connection(conn)

    def get_relevant_memories(self, query: str, user_name: str, top_k: int = 5) -> List[Dict]:
        """Get most relevant memories using semantic similarity ranking"""
        conn = None
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                logger.warning("Failed to generate query embedding, falling back to basic retrieval")
                return self.get_persistent_memories(user_name, limit=top_k)
            
            conn = self.get_db_connection()
            if not conn:
                return []
            
            cursor = conn.cursor()
            
            # Fetch all active memories with embeddings and calculate relevance
            cursor.execute(
                """
                SELECT id, category, content, extracted_at, importance, tags, event_date, event_time, embedding
                FROM persistent_memories
                WHERE user_name = %s AND active = TRUE AND embedding IS NOT NULL
                ORDER BY extracted_at DESC
                """,
                (user_name,)
            )
            
            rows = cursor.fetchall()
            memories_with_scores = []
            
            for row in rows:
                memory_embedding = row[8] if len(row) > 8 else None
                if memory_embedding:
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(query_embedding, memory_embedding)
                    # Weight by importance (1-10) and relevance (0-1)
                    # Combined score: relevance * (importance/10)
                    importance = row[4] if len(row) > 4 else 5
                    combined_score = similarity * (importance / 10.0)
                    
                    memories_with_scores.append({
                        'id': row[0],
                        'category': row[1],
                        'content': row[2],
                        'extracted_at': row[3],
                        'importance': importance,
                        'tags': row[5] if len(row) > 5 else [],
                        'event_date': row[6] if len(row) > 6 else None,
                        'event_time': row[7] if len(row) > 7 else None,
                        'relevance_score': similarity,
                        'combined_score': combined_score
                    })
            
            # Sort by combined score
            memories_with_scores.sort(key=lambda x: x['combined_score'], reverse=True)
            
            # Return top K
            top_memories = memories_with_scores[:top_k]
            logger.info(f"Retrieved {len(top_memories)} relevant memories for {user_name} (query: {query[:50]}...)")
            
            return top_memories
            
        except Exception as e:
            logger.error(f"Error getting relevant memories: {e}")
            return []
        finally:
            if conn:
                self.release_db_connection(conn)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def get_persistent_memories(self, user_name: str, category: str = None, limit: int = 20) -> List[Dict]:
        """Retrieve persistent memories for a user with caching"""
        # Check cache first (only for basic retrieval without category)
        if not category:
            cached_memories = self.smart_cache.get_cached_memories(user_name)
            if cached_memories is not None:
                return cached_memories[:limit]
        
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return []

            cursor = conn.cursor()

            if category:
                cursor.execute(
                    """
                    SELECT id, category, content, extracted_at, importance, tags, event_date, event_time
                    FROM persistent_memories
                    WHERE user_name = %s AND category = %s AND active = TRUE
                    ORDER BY importance DESC, extracted_at DESC
                    LIMIT %s
                    """,
                    (user_name, category, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, category, content, extracted_at, importance, tags, event_date, event_time
                    FROM persistent_memories
                    WHERE user_name = %s AND active = TRUE
                    ORDER BY importance DESC, extracted_at DESC
                    LIMIT %s
                    """,
                    (user_name, limit)
                )

            results = cursor.fetchall()
            cursor.close()

            memories = []
            for row in results:
                memories.append({
                    'id': row[0],
                    'category': row[1],
                    'content': row[2],
                    'extracted_at': row[3],
                    'importance': row[4],
                    'tags': row[5] or [],
                    'event_date': row[6],
                    'event_time': row[7]
                })

            # Cache the memories if this was a basic retrieval
            if not category:
                self.smart_cache.cache_memories(user_name, memories)
            
            return memories

        except Exception as e:
            logger.error(f"Error retrieving persistent memories: {e}")
            return []
        finally:
            if conn:
                self.release_db_connection(conn)

    def get_schedule_events(self, user_name: str = None, start_date: str = None, end_date: str = None, limit: int = 50) -> List[Dict]:
        """Retrieve schedule events for a user within a date range"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return []

            cursor = conn.cursor()

            # Build query based on filters
            query = """
                SELECT id, user_name, title, event_date, event_time, description, importance, created_at
                FROM schedule_events
                WHERE active = TRUE
            """
            params = []

            if user_name:
                query += " AND user_name = %s"
                params.append(user_name)

            if start_date:
                query += " AND event_date >= %s"
                params.append(start_date)

            if end_date:
                query += " AND event_date <= %s"
                params.append(end_date)

            query += " ORDER BY event_date, event_time LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()

            events = []
            for row in results:
                events.append({
                    'id': row[0],
                    'user_name': row[1],
                    'title': row[2],
                    'event_date': row[3],
                    'event_time': row[4],
                    'description': row[5],
                    'importance': row[6],
                    'created_at': row[7]
                })

            logger.info(f"Retrieved {len(events)} schedule events for {user_name}")
            return events

        except Exception as e:
            logger.error(f"Error retrieving schedule events: {e}")
            return []
        finally:
            if conn:
                self.release_db_connection(conn)

    def add_schedule_event(self, user_name: str, title: str, event_date: str, event_time: str = None,
                          description: str = None, importance: int = 5) -> int:
        """Add a new schedule event (with deduplication)"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return None

            cursor = conn.cursor()

            # Check for duplicate: same user, title, and date
            cursor.execute(
                """
                SELECT id, event_time, description, importance
                FROM schedule_events
                WHERE user_name = %s AND title = %s AND event_date = %s AND active = TRUE
                """,
                (user_name, title, event_date)
            )

            existing = cursor.fetchone()

            if existing:
                existing_id, existing_time, existing_desc, existing_importance = existing
                logger.info(f"Duplicate schedule event detected for {user_name}: '{title}' on {event_date}. Using existing ID {existing_id}")

                # If new info is more detailed, update the existing event
                should_update = False
                updates = []
                params = []

                if event_time and not existing_time:
                    updates.append("event_time = %s")
                    params.append(event_time)
                    should_update = True

                if description and not existing_desc:
                    updates.append("description = %s")
                    params.append(description)
                    should_update = True

                if importance and importance > existing_importance:
                    updates.append("importance = %s")
                    params.append(importance)
                    should_update = True

                if should_update:
                    params.append(existing_id)
                    update_query = f"UPDATE schedule_events SET {', '.join(updates)} WHERE id = %s"
                    cursor.execute(update_query, params)
                    conn.commit()
                    logger.info(f"Updated existing schedule event ID {existing_id} with new details")

                cursor.close()
                return existing_id

            # No duplicate found, create new event
            cursor.execute(
                """
                INSERT INTO schedule_events (user_name, title, event_date, event_time, description, importance)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_name, title, event_date, event_time, description, importance)
            )

            event_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()

            logger.info(f"Added schedule event ID {event_id} for {user_name}: {title} on {event_date}")
            return event_id

        except Exception as e:
            logger.error(f"Error adding schedule event: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                self.release_db_connection(conn)

    def update_schedule_event(self, event_id: int, title: str = None, event_date: str = None,
                             event_time: str = None, description: str = None, importance: int = None) -> bool:
        """Update an existing schedule event"""
        # Validate event_id is an integer
        if not isinstance(event_id, int):
            logger.error(f"Invalid event_id type: {type(event_id)}. Expected int, got {event_id}")
            return False
            
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return False

            cursor = conn.cursor()

            # Build update query dynamically
            updates = []
            params = []

            if title is not None:
                updates.append("title = %s")
                params.append(title)
            if event_date is not None:
                updates.append("event_date = %s")
                params.append(event_date)
            if event_time is not None:
                updates.append("event_time = %s")
                params.append(event_time)
            if description is not None:
                updates.append("description = %s")
                params.append(description)
            if importance is not None:
                updates.append("importance = %s")
                params.append(importance)

            if not updates:
                return False

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(event_id)

            query = f"UPDATE schedule_events SET {', '.join(updates)} WHERE id = %s AND active = TRUE"
            cursor.execute(query, params)

            affected = cursor.rowcount
            conn.commit()
            cursor.close()

            logger.info(f"Updated schedule event ID {event_id}, affected rows: {affected}")
            return affected > 0

        except Exception as e:
            logger.error(f"Error updating schedule event: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self.release_db_connection(conn)

    def delete_schedule_event(self, event_id: int) -> bool:
        """Delete (deactivate) a schedule event"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return False

            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE schedule_events
                SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (event_id,)
            )

            affected = cursor.rowcount
            conn.commit()
            cursor.close()

            logger.info(f"Deleted schedule event ID {event_id}, affected rows: {affected}")
            return affected > 0

        except Exception as e:
            logger.error(f"Error deleting schedule event: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self.release_db_connection(conn)

    def search_schedule_by_title(self, user_name: str, search_query: str, start_date: str = None, 
                                end_date: str = None, timeout: int = 300, max_retries: int = 3) -> List[Dict]:
        """
        Three-tier search for schedule events by title/name with timeout and retry logic
        
        Tier 1: Semantic AI search (primary)
        Tier 2: Fuzzy matching (fallback) 
        Tier 3: Full-text search (verification, runs in parallel)
        """
        import signal
        import threading
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
        
        logger.info(f"Starting three-tier search for '{search_query}' by {user_name}")
        search_start_time = time.time()
        
        # Get all events for the user in the date range first
        all_events = self.get_schedule_events(user_name, start_date, end_date, limit=100)
        if not all_events:
            logger.info("No events found for user in date range")
            return []
        
        results = []
        tier_used = "none"
        verification_results = []
        
        try:
            # Start Tier 3 (verification) in parallel with Tier 1/2
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit Tier 3 verification search
                tier3_future = executor.submit(self._tier3_fulltext_search, user_name, search_query, start_date, end_date)
                
                # Try Tier 1 (Semantic AI) first
                try:
                    tier1_future = executor.submit(self._tier1_semantic_search, user_name, search_query, all_events, timeout)
                    results = tier1_future.result(timeout=timeout)
                    tier_used = "tier1"
                    logger.info(f"Tier 1 (semantic) found {len(results)} results")
                except (FutureTimeoutError, Exception) as e:
                    logger.warning(f"Tier 1 (semantic) failed: {e}")
                    
                    # Fallback to Tier 2 (Fuzzy matching)
                    try:
                        results = self._tier2_fuzzy_search(search_query, all_events)
                        tier_used = "tier2"
                        logger.info(f"Tier 2 (fuzzy) found {len(results)} results")
                    except Exception as e2:
                        logger.error(f"Tier 2 (fuzzy) also failed: {e2}")
                        results = []
                
                # Get Tier 3 verification results
                try:
                    verification_results = tier3_future.result(timeout=timeout)
                    logger.info(f"Tier 3 (fulltext) found {len(verification_results)} results")
                except (FutureTimeoutError, Exception) as e:
                    logger.warning(f"Tier 3 (fulltext) failed: {e}")
                    verification_results = []
        
        except Exception as e:
            logger.error(f"Search failed completely: {e}")
            return []
        
        # Log search metrics
        search_duration = time.time() - search_start_time
        logger.info(f"Search completed: tier={tier_used}, duration={search_duration:.2f}s, "
                   f"results={len(results)}, verification={len(verification_results)}")
        
        # Compare results if both tiers found something
        if results and verification_results:
            self._compare_search_results(results, verification_results, search_query)
        
        return results

    def _tier1_semantic_search(self, user_name: str, search_query: str, events: List[Dict], timeout: int) -> List[Dict]:
        """Tier 1: Use Ollama for semantic event search"""
        try:
            # Extract search terms from natural language
            extraction_prompt = f"""Extract the main event name or keywords from this query: "{search_query}"

Return only the key terms that would be in an event title, no extra words.
Examples:
- "when is my baby shower" → "baby shower"
- "find my dentist appointment" → "dentist appointment" 
- "what time is the meeting" → "meeting"

Key terms:"""

            # Get Ollama URL and model from config
            ollama_url = self.get_config('ollama_url', self.ollama_url)
            ollama_model = self.get_config('ollama_model', 'llama3.2:latest')
            
            # Call Ollama with 5 minute timeout
            response = requests.post(
                f'{ollama_url}/api/generate',
                json={
                    'model': ollama_model,
                    'prompt': extraction_prompt,
                    'stream': False,
                    'options': {'temperature': 0.1}
                },
                timeout=300  # 5 minutes
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            extracted_terms = response.json().get('response', '').strip()
            if not extracted_terms:
                raise Exception("No terms extracted from query")
            
            logger.info(f"Extracted search terms: '{extracted_terms}'")
            
            # Now use extracted terms to find matching events
            matches = []
            for event in events:
                similarity = self._calculate_semantic_similarity(extracted_terms, event['title'])
                if similarity > 0.3:  # Threshold for semantic match
                    matches.append((event, similarity))
            
            # Sort by similarity and return events
            matches.sort(key=lambda x: x[1], reverse=True)
            return [event for event, _ in matches[:10]]  # Top 10 matches
            
        except Exception as e:
            logger.error(f"Tier 1 semantic search failed: {e}")
            raise

    def _tier2_fuzzy_search(self, search_query: str, events: List[Dict]) -> List[Dict]:
        """Tier 2: Fuzzy string matching fallback"""
        try:
            matches = []
            query_lower = search_query.lower()
            
            for event in events:
                title_lower = event['title'].lower()
                
                # Direct substring match
                if query_lower in title_lower:
                    matches.append((event, 1.0))
                    continue
                
                # Word-by-word matching
                query_words = set(query_lower.split())
                title_words = set(title_lower.split())
                
                if query_words.intersection(title_words):
                    # Calculate word overlap score
                    overlap = len(query_words.intersection(title_words))
                    total_words = len(query_words.union(title_words))
                    score = overlap / total_words if total_words > 0 else 0
                    
                    if score > 0.2:  # Threshold for word overlap
                        matches.append((event, score))
            
            # Sort by score and return events
            matches.sort(key=lambda x: x[1], reverse=True)
            return [event for event, _ in matches[:10]]  # Top 10 matches
            
        except Exception as e:
            logger.error(f"Tier 2 fuzzy search failed: {e}")
            raise

    def _tier3_fulltext_search(self, user_name: str, search_query: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Tier 3: PostgreSQL full-text search verification"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return []

            cursor = conn.cursor()
            
            # Sanitize search query for tsquery - extract just words
            import re
            # Extract alphanumeric words and join with spaces
            words = re.findall(r'\b\w+\b', search_query)
            if not words:
                return []
            # Join words with & for AND query, or use | for OR
            sanitized_query = ' & '.join(words[:5])  # Limit to first 5 words
            
            # Build full-text search query
            query = """
                SELECT id, user_name, title, event_date, event_time, description, importance, created_at,
                       ts_rank(to_tsvector('english', title), to_tsquery('english', %s)) as rank
                FROM schedule_events
                WHERE active = TRUE
                  AND to_tsvector('english', title) @@ to_tsquery('english', %s)
            """
            params = [sanitized_query, sanitized_query]

            if user_name:
                query += " AND user_name = %s"
                params.append(user_name)

            if start_date:
                query += " AND event_date >= %s"
                params.append(start_date)

            if end_date:
                query += " AND event_date <= %s"
                params.append(end_date)

            query += " ORDER BY rank DESC, event_date, event_time LIMIT 10"

            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()

            events = []
            for row in results:
                events.append({
                    'id': row[0],
                    'user_name': row[1],
                    'title': row[2],
                    'event_date': row[3],
                    'event_time': row[4],
                    'description': row[5],
                    'importance': row[6],
                    'created_at': row[7],
                    'rank': row[8]
                })

            return events

        except Exception as e:
            logger.error(f"Tier 3 fulltext search failed: {e}")
            return []
        finally:
            if conn:
                self.release_db_connection(conn)

    def _calculate_semantic_similarity(self, query: str, title: str) -> float:
        """Calculate semantic similarity between query and title using simple word overlap"""
        query_words = set(query.lower().split())
        title_words = set(title.lower().split())
        
        if not query_words or not title_words:
            return 0.0
        
        intersection = query_words.intersection(title_words)
        union = query_words.union(title_words)
        
        return len(intersection) / len(union) if union else 0.0

    def _compare_search_results(self, tier1_results: List[Dict], tier3_results: List[Dict], search_query: str):
        """Compare and log differences between search tiers"""
        tier1_titles = {event['title'] for event in tier1_results}
        tier3_titles = {event['title'] for event in tier3_results}
        
        only_tier1 = tier1_titles - tier3_titles
        only_tier3 = tier3_titles - tier1_titles
        common = tier1_titles.intersection(tier3_titles)
        
        logger.info(f"Search comparison for '{search_query}': "
                   f"common={len(common)}, only_tier1={len(only_tier1)}, only_tier3={len(only_tier3)}")
        
        if only_tier1:
            logger.debug(f"Only Tier 1 found: {list(only_tier1)}")
        if only_tier3:
            logger.debug(f"Only Tier 3 found: {list(only_tier3)}")

    def extract_event_name_from_query(self, query: str) -> Optional[str]:
        """Extract event name from natural language query"""
        query_lower = query.lower()
        
        # Common patterns for event name queries
        patterns = [
            r"when is my (.+?)(?:\?|$)",
            r"when's my (.+?)(?:\?|$)", 
            r"what time is my (.+?)(?:\?|$)",
            r"find my (.+?)(?:\?|$)",
            r"where is my (.+?)(?:\?|$)",
            r"tell me about my (.+?)(?:\?|$)"
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                event_name = match.group(1).strip()
                # Clean up common words
                event_name = re.sub(r'\b(the|a|an|my|our)\b', '', event_name).strip()
                if event_name:
                    return event_name
        
        return None

    def parse_date_expression(self, date_expr: str, reference_date: datetime = None) -> Optional[str]:
        """Parse natural language date expressions into YYYY-MM-DD format"""
        if not date_expr or date_expr == "null":
            return None

        from zoneinfo import ZoneInfo
        import re

        ny_tz = ZoneInfo("America/New_York")
        if reference_date is None:
            reference_date = datetime.now(ny_tz)

        date_expr = date_expr.lower().strip()

        # Already in YYYY-MM-DD format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_expr):
            return date_expr

        # Handle "tomorrow"
        if date_expr == "tomorrow":
            result_date = reference_date + timedelta(days=1)
            return result_date.strftime('%Y-%m-%d')

        # Handle "today"
        if date_expr == "today":
            return reference_date.strftime('%Y-%m-%d')

        # Handle "in X days/weeks/months"
        in_match = re.match(r'in (\d+) (day|days|week|weeks|month|months)', date_expr)
        if in_match:
            count = int(in_match.group(1))
            unit = in_match.group(2)
            if 'day' in unit:
                result_date = reference_date + timedelta(days=count)
            elif 'week' in unit:
                result_date = reference_date + timedelta(weeks=count)
            elif 'month' in unit:
                result_date = reference_date + timedelta(days=count * 30)  # Approximate
            return result_date.strftime('%Y-%m-%d')

        # Handle day names: "this Monday", "next Friday", "Monday", etc.
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        for i, day_name in enumerate(day_names):
            if day_name in date_expr:
                current_weekday = reference_date.weekday()  # Monday is 0
                target_weekday = i

                # Determine if "this" or "next"
                if 'next' in date_expr:
                    # "next Friday" means next week's Friday
                    days_ahead = (target_weekday - current_weekday) % 7
                    if days_ahead == 0:
                        days_ahead = 7  # If today is Friday, "next Friday" is 7 days away
                    else:
                        days_ahead += 7  # Always go to next week
                elif 'this' in date_expr:
                    # "this Friday" means this week's Friday
                    days_ahead = (target_weekday - current_weekday) % 7
                    if days_ahead == 0:
                        days_ahead = 7  # If today is Friday, "this Friday" might mean next occurrence
                else:
                    # Just "Friday" - means upcoming Friday (could be this week or next)
                    days_ahead = (target_weekday - current_weekday) % 7
                    if days_ahead == 0:
                        days_ahead = 7  # If today is Friday, assume next Friday

                result_date = reference_date + timedelta(days=days_ahead)
                return result_date.strftime('%Y-%m-%d')

        # Handle multiple dates: "October 11th and October 18th" -> use first date
        if ' and ' in date_expr or ',' in date_expr:
            # Split on common separators
            parts = re.split(r'\s+and\s+|,\s*', date_expr)
            if len(parts) > 1:
                logger.warning(f"Multiple dates detected in '{date_expr}', using first date: '{parts[0]}'")
                # Recursively parse the first date
                return self.parse_date_expression(parts[0].strip(), reference_date)

        # Handle date ranges: "October 21-25" -> use start date
        range_match = re.match(r'([a-z]+\s+\d{1,2})(?:st|nd|rd|th)?\s*-\s*(\d{1,2})(?:st|nd|rd|th)?', date_expr)
        if range_match:
            start_date_expr = range_match.group(1)
            end_day = range_match.group(2)
            logger.info(f"Date range detected in '{date_expr}', using start date: '{start_date_expr}'")
            # Recursively parse the start date
            return self.parse_date_expression(start_date_expr, reference_date)

        # Handle month name + ordinal day: "October 17th", "january 3rd"
        month_names = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
            'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
        }
        
        for month_name, month_num in month_names.items():
            # Match "October 17" or "October 17th" (with optional ordinal suffix)
            month_pattern = rf'{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?'
            month_match = re.search(month_pattern, date_expr)
            if month_match:
                day = int(month_match.group(1))
                year = reference_date.year
                
                # If the date has passed this year, assume next year
                try:
                    result_date = datetime(year, month_num, day, tzinfo=ny_tz)
                    if result_date < reference_date:
                        result_date = datetime(year + 1, month_num, day, tzinfo=ny_tz)
                    return result_date.strftime('%Y-%m-%d')
                except ValueError:
                    # Invalid date (e.g., February 30)
                    logger.warning(f"Invalid date: {month_name} {day}")
                    continue

        # Try parsing common date formats
        try:
            from dateutil import parser
            parsed_date = parser.parse(date_expr, fuzzy=True)
            return parsed_date.strftime('%Y-%m-%d')
        except:
            pass

        logger.warning(f"Could not parse date expression: {date_expr}")
        return None

    def extract_and_manage_schedule(self, user_message: str, assistant_response: str, user_name: str):
        """Extract scheduling information from conversation and manage schedule events"""
        try:
            ollama_url = self.get_config('ollama_url', self.ollama_url)
            ollama_model = self.get_config('ollama_model', self.ollama_model)
            logger.info(f"Schedule action extraction using model: {ollama_model}")

            # Get current date for context
            from zoneinfo import ZoneInfo
            ny_tz = ZoneInfo("America/New_York")
            current_datetime = datetime.now(ny_tz)
            current_date_str = current_datetime.strftime("%Y-%m-%d (%A, %B %d, %Y)")

            extraction_prompt = f"""You are a scheduling assistant analyzing a conversation to manage calendar events.

CURRENT DATE: {current_date_str}

Conversation:
User: {user_message}
Assistant: {assistant_response}

Analyze this conversation and determine if the user wants to:
1. ADD a new event to their schedule
2. UPDATE an existing event
3. DELETE/CANCEL an event
4. NOTHING - just asking about schedule or casual conversation

If scheduling action is needed, extract:
- Action: ADD, UPDATE, DELETE, or NOTHING
- Event title (brief description)
- Date expression (use these formats):
  * Specific date: "2025-10-15" or "October 15" or "Oct 15"
  * Relative: "tomorrow", "next Monday", "next Friday", "in 3 days"
- Time (HH:MM format in 24-hour, or null if not specified)
- Description (optional additional details)
- Importance (1-10, default 5)
- Event ID (if updating/deleting - look for "that event", "the appointment", etc.)

CRITICAL INSTRUCTIONS:
- ONLY use action "ADD" if the user is CREATING or SCHEDULING a NEW event
- ONLY use action "UPDATE" if the user explicitly wants to MODIFY an existing event (e.g., "change my meeting time", "reschedule my appointment")
- ONLY use action "DELETE" if the user explicitly wants to CANCEL or REMOVE an event (e.g., "cancel my meeting", "delete my appointment")
- If the user is ASKING, QUERYING, READING, or CHECKING their schedule, ALWAYS use action "NOTHING"
- DO NOT create events when the user asks "what's on my calendar", "tell me my schedule", "what do I have", "do I have anything", etc.
- DO NOT update events when the user is just asking about existing events
- When in doubt, use "NOTHING" - it's better to not create than to create a duplicate

IMPORTANT: For relative dates like "next Friday", just return "next Friday" - do NOT calculate the actual date.

Respond ONLY with a JSON object (no markdown, no extra text):
{{"action": "ADD|UPDATE|DELETE|NOTHING", "title": "...", "date_expression": "next Friday", "time": "HH:MM or null", "description": "...", "importance": 5, "event_id": null}}

Examples:
User: "I have a dentist appointment tomorrow at 3pm"
{{"action": "ADD", "title": "Dentist appointment", "date_expression": "tomorrow", "time": "15:00", "description": null, "importance": 7, "event_id": null}}

User: "Schedule me for next Friday at 9:30am for my haircut"
{{"action": "ADD", "title": "haircut", "date_expression": "next Friday", "time": "09:30", "description": null, "importance": 5, "event_id": null}}

User: "Cancel my meeting on Monday"
{{"action": "DELETE", "title": "meeting", "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "What's on my schedule?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Tell me about my calendar"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Do I have anything tomorrow?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "What do I have next week?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Do I have any travel dates for the month of October?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Tell me about my travel plans"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Do you know if I've got any meetings tomorrow?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}
"""

            response = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    'model': ollama_model,
                    'prompt': extraction_prompt,
                    'stream': False,
                    'temperature': 0.1
                },
                timeout=300  # 5 minutes for schedule action extraction
            )

            if response.status_code == 200:
                import json
                result_text = response.json().get('response', '').strip()

                # Parse JSON response
                try:
                    result = json.loads(result_text)
                    action = result.get('action', 'NOTHING')

                    if action == 'ADD':
                        # Parse the date expression into YYYY-MM-DD format
                        date_expression = result.get('date_expression') or result.get('date')
                        parsed_date = self.parse_date_expression(date_expression, current_datetime)

                        event_id = self.add_schedule_event(
                            user_name=user_name,
                            title=result.get('title', 'Untitled Event'),
                            event_date=parsed_date,
                            event_time=result.get('time'),
                            description=result.get('description'),
                            importance=result.get('importance', 5)
                        )
                        if event_id:
                            logger.info(f"Added schedule event {event_id} for {user_name}: {result.get('title')} on {parsed_date}")

                    elif action == 'UPDATE':
                        # Find matching event by title and/or date instead of using LLM-provided event_id
                        title_search = result.get('title', '')
                        date_expression = result.get('date_expression') or result.get('date')
                        
                        if title_search:
                            events = self.get_schedule_events(user_name=user_name)
                            matching_event = None
                            
                            # Find event by title (case-insensitive partial match)
                            for event in events:
                                if title_search.lower() in event['title'].lower():
                                    matching_event = event
                                    break
                            
                            if matching_event:
                                # Parse the date expression if present
                                parsed_date = self.parse_date_expression(date_expression, current_datetime) if date_expression else None
                                
                                success = self.update_schedule_event(
                                    event_id=matching_event['id'],  # Use actual numeric ID
                                    title=result.get('title') if result.get('title') != title_search else None,
                                    event_date=parsed_date,
                                    event_time=result.get('time'),
                                    description=result.get('description'),
                                    importance=result.get('importance')
                                )
                                if success:
                                    logger.info(f"Updated schedule event {matching_event['id']} for {user_name}")
                            else:
                                logger.warning(f"No matching event found for update: '{title_search}'")
                        else:
                            logger.warning(f"UPDATE action requires a title to find the event to update")

                    elif action == 'DELETE':
                        # Find and delete matching events
                        title_search = result.get('title', '')
                        if title_search:
                            events = self.get_schedule_events(user_name=user_name)
                            for event in events:
                                if title_search.lower() in event['title'].lower():
                                    self.delete_schedule_event(event['id'])
                                    logger.info(f"Deleted schedule event {event['id']} for {user_name}")
                                    break

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse schedule extraction result: {result_text}")

        except Exception as e:
            logger.error(f"Error in schedule extraction: {e}")
            import traceback
            traceback.print_exc()

    def get_semantic_context(self, query_text: str, user_name: str, current_session_id: str, limit: int = 3) -> List[Dict]:
        """Retrieve semantically similar messages from long-term memory"""
        # Generate embedding for the query
        query_embedding = self.generate_embedding(query_text)
        if not query_embedding:
            return []

        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                return []

            cursor = conn.cursor()

            # Get similarity threshold from config
            threshold = float(self.get_config('semantic_similarity_threshold', '0.7'))

            # Find similar messages from past conversations (excluding current session and resolved topics)
            cursor.execute(
                """
                SELECT id, role, message, message_type, timestamp, embedding, topic_state,
                       cosine_similarity(%s::FLOAT8[], embedding) as similarity
                FROM conversation_history
                WHERE user_name = %s
                  AND session_id != %s
                  AND embedding IS NOT NULL
                  AND cosine_similarity(%s::FLOAT8[], embedding) > %s
                  AND (topic_state IS NULL OR topic_state != 'resolved')
                ORDER BY similarity DESC, timestamp DESC
                LIMIT %s
                """,
                (query_embedding, user_name, current_session_id, query_embedding, threshold, limit)
            )

            results = cursor.fetchall()
            cursor.close()

            context = []
            for row in results:
                context.append({
                    'role': row[1],
                    'message': row[2],
                    'message_type': row[3],
                    'timestamp': row[4],
                    'topic_state': row[6],
                    'similarity': row[7]
                })

            return context

        except Exception as e:
            logger.error(f"Error retrieving semantic context: {e}")
            return []
        finally:
            if conn:
                self.release_db_connection(conn)

    def get_ollama_response(self, text, user_name=None, session_id=None):
        """Get response from Ollama with conversation history context and circuit breaker protection"""
        try:
            return self.ollama_circuit_breaker.call(self._get_ollama_response_internal, text, user_name, session_id)
        except CircuitBreakerError:
            logger.error("Ollama circuit breaker is open, cannot get response")
            return "Sorry, I am temporarily unavailable due to service issues."

    def _get_ollama_response_internal(self, text, user_name=None, session_id=None):
        """Internal Ollama response method with optional response validation"""
        # Get current Ollama config from database
        ollama_url = self.get_config('ollama_url', self.ollama_url)
        ollama_model = self.get_config('ollama_model', self.ollama_model)
        use_validation = self.get_config('use_response_validation', 'false').lower() == 'true'
        use_chain_of_thought = self.get_config('use_chain_of_thought', 'false').lower() == 'true'
        enable_parallel_processing = self.get_config('enable_parallel_processing', 'false').lower() == 'true'
        logger.info(f"Generating response using model: {ollama_model}")

        # Detect conversation closure before building prompt
        closure_detected, closure_type = self.detect_conversation_closure(text, user_name, session_id)
        if closure_detected:
            logger.info(f"Conversation closure detected: {closure_type}")
            # Mark previous topic as resolved
            self.mark_topic_resolved(user_name, session_id, f"Resolved via {closure_type}")

        # Build prompt with conversation history
        prompt = self.build_prompt_with_context(text, user_name, session_id)

        # Apply Chain-of-Thought hinting (hidden reasoning) if enabled
        cot_instruction = """

IMPORTANT: Think through the problem step by step privately. Do NOT reveal your chain-of-thought. Provide ONLY the final concise answer in 1-2 short sentences.
"""
        cot_prompt = prompt + (cot_instruction if use_chain_of_thought else "")

        # Adjust generation parameters based on closure detection
        if closure_detected:
            # Shorter, warmer responses for closure messages
            generation_options = {
                'temperature': 0.9,  # More natural/warm
                'top_p': 0.95,  # More creative
                'num_predict': 30,   # Very brief
                'stop': ['\n\n', 'User:', 'Assistant:']
            }
        else:
            # Standard parameters for regular responses
            generation_options = {
                'temperature': 0.7,  # Lower temperature for more consistent, focused responses
                'top_p': 0.9,  # Nucleus sampling for better quality
                'num_predict': 100,  # Limit response length (roughly 1-2 sentences)
                'stop': ['\n\n', 'User:', 'Assistant:']  # Stop at conversation breaks
            }

        # Helper to request a single completion
        def _request_once(prompt_text: str):
            resp = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    'model': ollama_model,
                    'prompt': prompt_text,
                    'stream': False,
                    'options': generation_options
                },
                timeout=300
            )
            if resp.status_code != 200:
                raise requests.RequestException(f"Ollama request failed: {resp.text}")
            out = resp.json().get('response', '').strip()
            if not out:
                logger.warning(f"Empty LLM response received. Model: {ollama_model}, User query: '{text[:100]}...'")
                out = 'I did not understand that.'
            return out

        # CoT self-consistency with optional parallel fan-out
        max_attempts = 3 if use_validation else 1
        attempt = 0
        current_prompt = cot_prompt
        while attempt < max_attempts:
            attempt += 1
            if use_chain_of_thought:
                # Generate 3 candidates
                if enable_parallel_processing:
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    candidates = []
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        futures = [executor.submit(_request_once, current_prompt) for _ in range(3)]
                        for f in as_completed(futures):
                            try:
                                candidates.append(f.result())
                            except Exception as e:
                                logger.error(f"Parallel generation error: {e}")
                    if not candidates:
                        candidates = [_request_once(current_prompt)]
                else:
                    candidates = [_request_once(current_prompt) for _ in range(3)]

                # Simple self-consistency: choose most common normalized response
                norm = lambda s: s.strip().lower()
                from collections import Counter
                counts = Counter(norm(c) for c in candidates)
                best_norm, _ = counts.most_common(1)[0]
                chosen = next((c for c in candidates if norm(c) == best_norm), candidates[0])
            else:
                chosen = _request_once(current_prompt)

            if use_validation and attempt < max_attempts:
                is_valid, reason = self.validate_response(chosen, text, user_name)
                if is_valid:
                    logger.debug(f"Response passed validation on attempt {attempt}")
                    return chosen
                logger.warning(f"Response failed validation (attempt {attempt}): {reason}")
                # Strengthen prompt and retry
                current_prompt = prompt + "\n\nIMPORTANT: Previous response was inaccurate. Only state facts you are certain about."
                continue
            return chosen
        
        # If we get here, all attempts failed validation
        return "I apologize, but I want to make sure I give you accurate information. Could you rephrase your question?"

    def analyze_query_complexity(self, message: str) -> str:
        """Analyze if a query is complex or simple to determine prompting strategy"""
        message_lower = message.lower().strip()
        
        # Complex query indicators
        complex_indicators = [
            # Multi-step reasoning
            'why', 'how', 'explain', 'compare', 'difference between', 'what if',
            # Planning/scheduling
            'plan', 'schedule', 'arrange', 'organize',
            # Analysis/evaluation
            'should i', 'would it be', 'is it better', 'recommend',
            # Multi-part questions
            'and then', 'after that', 'first', 'second', 'finally',
            # Conditional reasoning
            'if', 'unless', 'provided that', 'in case'
        ]
        
        # Count complexity indicators
        complexity_score = sum(1 for indicator in complex_indicators if indicator in message_lower)
        
        # Also consider length (longer queries tend to be more complex)
        word_count = len(message.split())
        if word_count > 20:
            complexity_score += 1
        
        # Classify complexity
        if complexity_score >= 2:
            return 'complex'
        elif complexity_score == 1:
            return 'moderate'
        else:
            return 'simple'
    
    def validate_response(self, response: str, user_message: str, user_name: str = None) -> Tuple[bool, str]:
        """Validate AI response for accuracy and hallucination detection"""
        try:
            # Get known facts from memories
            memories_context = ""
            if user_name:
                memories = self.get_persistent_memories(user_name, limit=5)
                if memories:
                    memories_context = "\n".join([f"- {mem['content']}" for mem in memories])
            
            # Build validation prompt
            validation_prompt = f"""Review this AI response for accuracy and quality:

User asked: {user_message}
Bot responded: {response}

Known facts about user:
{memories_context if memories_context else "No specific facts stored"}

Validation criteria:
1. Is the response accurate based on known facts? (yes/no)
2. Is the response helpful and relevant? (yes/no)
3. Does the response avoid making up information? (yes/no)
4. If mentioning schedules/dates, are they based on actual stored events? (yes/no/N/A)

Answer ONLY with: VALID or INVALID
Then on the next line, briefly explain why in 10 words or less.

Format:
VALID
Reason: [brief explanation]

or

INVALID
Reason: [brief explanation]"""

            ollama_url = self.get_config('ollama_url', self.ollama_url)
            ollama_model = self.get_config('ollama_model', self.ollama_model)
            logger.info(f"Response validation using model: {ollama_model}")

            validation_response = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    'model': ollama_model,
                    'prompt': validation_prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,  # Very low temp for consistent validation
                        'num_predict': 100
                    }
                },
                timeout=300  # 5 minutes for validation
            )

            if validation_response.status_code == 200:
                validation_text = validation_response.json().get('response', '').strip().upper()
                is_valid = 'VALID' in validation_text and 'INVALID' not in validation_text
                
                # Extract reason
                lines = validation_response.json().get('response', '').strip().split('\n')
                reason = ' '.join(lines[1:]) if len(lines) > 1 else validation_text

                # Lightweight grounding heuristic checks
                resp_lower = (response or '').lower()
                msg_lower = (user_message or '').lower()
                mentions_added_calendar = 'added to your calendar' in resp_lower or 'i added' in resp_lower
                user_did_not_request_add = not any(w in msg_lower for w in ['add ', 'schedule', 'put on calendar', 'create event'])
                if mentions_added_calendar and user_did_not_request_add:
                    logger.warning("Grounding check: Response claims calendar change without user request")
                    return False, "Grounding check failed: unsolicited calendar change"
                
                logger.debug(f"Response validation: {'VALID' if is_valid else 'INVALID'} - {reason}")
                return is_valid, reason
            else:
                logger.warning("Response validation failed, assuming valid")
                return True, "Validation check failed"

        except Exception as e:
            logger.error(f"Error validating response: {e}")
            # On error, assume valid to avoid blocking responses
            return True, f"Validation error: {str(e)}"
    
    def is_schedule_query(self, message):
        """Detect if user is asking about their schedule/calendar"""
        schedule_keywords = [
            'schedule', 'calendar', 'appointment', 'meeting', 'event',
            'what do i have', 'what\'s on', 'do i have', 'am i free',
            'busy', 'available', 'plans', 'what\'s coming up',
            'tomorrow', 'today', 'tonight', 'next week', 'this week',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'when is', 'what time', 'upcoming', 'when\'s my', 'find my', 'tell me about my'
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in schedule_keywords)

    def is_event_name_query(self, message):
        """Detect if user is asking about a specific event by name"""
        event_name_patterns = [
            'when is my', 'when\'s my', 'what time is my', 'find my',
            'where is my', 'tell me about my', 'show me my'
        ]
        message_lower = message.lower()
        return any(pattern in message_lower for pattern in event_name_patterns)

    def extract_date_context(self, message):
        """Extract date context from user query for smart filtering"""
        message_lower = message.lower()

        # Specific day queries
        if any(word in message_lower for word in ['tomorrow']):
            return 'tomorrow'
        if any(word in message_lower for word in ['today', 'tonight']):
            return 'today'
        if 'next week' in message_lower or 'this week' in message_lower:
            return 'week'
        if 'next month' in message_lower or 'this month' in message_lower:
            return 'month'

        # Specific day names
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in days:
            if day in message_lower:
                return day

        # Default to full calendar view
        return 'all'

    def detect_conversation_closure(self, text, user_name, session_id):
        """Detect if user message indicates conversation closure using hybrid approach"""
        try:
            text_lower = text.lower().strip()
            
            # Pattern-based detection (fast)
            gratitude_patterns = [
                'thank you', 'thanks', 'appreciate', 'you\'re the best', 'lifesaver',
                'perfect', 'awesome', 'great', 'excellent', 'wonderful'
            ]
            
            acknowledgment_patterns = [
                'ok', 'okay', 'got it', 'understood', 'sounds good', 'alright',
                'cool', 'nice', 'sweet', 'amazing'
            ]
            
            affection_patterns = [
                '❤️', '💕', '💖', 'baby', 'love you', 'honey', 'sweetie', 'dear'
            ]
            
            # Check for gratitude + acknowledgment
            has_gratitude = any(pattern in text_lower for pattern in gratitude_patterns)
            has_acknowledgment = any(pattern in text_lower for pattern in acknowledgment_patterns)
            has_affection = any(pattern in text_lower for pattern in affection_patterns)
            
            # Strong closure signals
            if has_gratitude and (has_acknowledgment or has_affection):
                return True, 'gratitude_acknowledgment'
            elif has_gratitude and len(text.split()) <= 10:  # Short gratitude
                return True, 'gratitude'
            elif has_acknowledgment and has_affection:
                return True, 'acknowledgment_affection'
            
            # LLM-based analysis for ambiguous cases
            if has_gratitude or has_acknowledgment:
                return self._analyze_closure_with_llm(text, user_name, session_id)
            
            return False, 'none'
            
        except Exception as e:
            logger.error(f"Error detecting conversation closure: {e}")
            return False, 'error'

    def _analyze_closure_with_llm(self, text, user_name, session_id):
        """Use LLM to analyze if message indicates topic closure"""
        try:
            # Get recent conversation context
            recent_history = self.get_conversation_history(session_id=session_id, limit=5)
            context = ""
            for role, message, msg_type, timestamp in recent_history:
                context += f"{role}: {message}\n"
            
            analysis_prompt = f"""Analyze if this user message indicates they are satisfied with the previous response and the topic is resolved:

Recent conversation:
{context}
User: {text}

Does this message indicate:
1. Gratitude/acknowledgment that the previous topic is resolved?
2. Satisfaction with the information provided?
3. A desire to move on from the current topic?

Answer ONLY: YES or NO
Then briefly explain why in 5 words or less."""

            ollama_url = self.get_config('ollama_url', self.ollama_url)
            ollama_model = self.get_config('ollama_model', self.ollama_model)
            
            response = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    'model': ollama_model,
                    'prompt': analysis_prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,
                        'num_predict': 20
                    }
                },
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json().get('response', '').strip().upper()
                if result.startswith('YES'):
                    return True, 'llm_analysis'
                else:
                    return False, 'llm_analysis'
            else:
                # Fallback to pattern-based result
                return False, 'llm_fallback'
                
        except Exception as e:
            logger.error(f"Error in LLM closure analysis: {e}")
            return False, 'llm_error'

    def mark_topic_resolved(self, user_name, session_id, topic_summary=None):
        """Mark the current topic as resolved and update tracking"""
        try:
            session_key = f"{user_name}_{session_id}"
            
            # Get current active topic
            current_topic = self.active_topics.get(session_key)
            if current_topic:
                # Move to resolved topics
                if session_key not in self.resolved_topics:
                    self.resolved_topics[session_key] = []
                self.resolved_topics[session_key].append({
                    'topic': current_topic,
                    'summary': topic_summary,
                    'timestamp': datetime.now()
                })
                
                # Keep only last 5 resolved topics
                if len(self.resolved_topics[session_key]) > 5:
                    self.resolved_topics[session_key] = self.resolved_topics[session_key][-5:]
                
                # Clear active topic
                del self.active_topics[session_key]
                
                # Update database
                self._update_topic_state_in_db(user_name, session_id, 'resolved', topic_summary)
                
                logger.info(f"Marked topic as resolved for {user_name}: {current_topic}")
            
        except Exception as e:
            logger.error(f"Error marking topic resolved: {e}")

    def get_active_topic(self, user_name, session_id):
        """Get the current active topic for a user/session"""
        session_key = f"{user_name}_{session_id}"
        return self.active_topics.get(session_key)

    def detect_topic_switch(self, current_message, conversation_history):
        """Detect if user is switching to a new topic"""
        try:
            if not conversation_history or len(conversation_history) < 2:
                return False
            
            # Get the last few messages
            recent_messages = conversation_history[:3]
            
            # Simple heuristics for topic switching
            current_lower = current_message.lower()
            
            # New question patterns
            new_topic_indicators = [
                'what about', 'how about', 'can you', 'do you know',
                'tell me about', 'i need to', 'i want to', 'i have a question',
                'quick question', 'another thing', 'also', 'by the way'
            ]
            
            # Check if current message starts a new topic
            if any(indicator in current_lower for indicator in new_topic_indicators):
                return True
            
            # Check for topic shift keywords
            topic_shift_keywords = [
                'actually', 'wait', 'oh', 'hey', 'so', 'anyway', 'moving on',
                'different topic', 'change of subject'
            ]
            
            if any(keyword in current_lower for keyword in topic_shift_keywords):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting topic switch: {e}")
            return False

    def _update_topic_state_in_db(self, user_name, session_id, topic_state, topic_summary=None):
        """Update topic state in database"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE conversation_history 
                SET topic_state = %s, topic_summary = %s
                WHERE id = (
                    SELECT id FROM conversation_history
                    WHERE user_name = %s AND session_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                )
                """,
                (topic_state, topic_summary, user_name, session_id)
            )
            conn.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Error updating topic state in DB: {e}")

    def track_new_topic(self, current_message, user_name, session_id):
        """Detect and track new topics when they emerge"""
        try:
            session_key = f"{user_name}_{session_id}"
            
            # Check if this is a new topic (not a closure message)
            closure_detected, _ = self.detect_conversation_closure(current_message, user_name, session_id)
            if closure_detected:
                return  # Don't track closure messages as new topics
            
            # Check if this is a topic switch
            recent_history = self.get_conversation_history(session_id=session_id, limit=5)
            is_topic_switch = self.detect_topic_switch(current_message, recent_history)
            
            # Simple topic detection based on question patterns or new requests
            current_lower = current_message.lower()
            new_topic_indicators = [
                'what', 'how', 'when', 'where', 'why', 'can you', 'do you know',
                'tell me', 'i need', 'i want', 'help me', 'find my', 'show me'
            ]
            
            is_new_topic = any(indicator in current_lower for indicator in new_topic_indicators)
            
            if is_new_topic or is_topic_switch:
                # Extract a simple topic summary
                topic_summary = self._extract_topic_summary(current_message)
                
                # Update active topic
                self.active_topics[session_key] = topic_summary
                
                # Update database
                self._update_topic_state_in_db(user_name, session_id, 'active', topic_summary)
                
                logger.info(f"Tracked new topic for {user_name}: {topic_summary}")
            
        except Exception as e:
            logger.error(f"Error tracking new topic: {e}")

    def _extract_topic_summary(self, message):
        """Extract a simple topic summary from a message"""
        try:
            # Simple keyword-based topic extraction
            message_lower = message.lower()
            
            if any(word in message_lower for word in ['appointment', 'meeting', 'schedule', 'calendar']):
                return "schedule/appointment"
            elif any(word in message_lower for word in ['weather', 'temperature', 'rain', 'sunny']):
                return "weather"
            elif any(word in message_lower for word in ['food', 'eat', 'restaurant', 'cook', 'recipe']):
                return "food/cooking"
            elif any(word in message_lower for word in ['work', 'job', 'office', 'meeting']):
                return "work"
            elif any(word in message_lower for word in ['travel', 'trip', 'vacation', 'flight']):
                return "travel"
            elif any(word in message_lower for word in ['health', 'doctor', 'medical', 'medicine']):
                return "health"
            else:
                # Extract first few words as topic
                words = message.split()[:4]
                return " ".join(words).lower()
                
        except Exception as e:
            logger.error(f"Error extracting topic summary: {e}")
            return "general"

    def build_prompt_with_context(self, current_message, user_name=None, session_id=None):
        """Build a prompt with smart memory system using MemoryManager"""
        try:
            # If memory manager is not available, fall back to simple prompt
            if not self.memory_manager:
                logger.warning("MemoryManager not available, using fallback prompt")
                return f"User: {current_message}\nYou:"
            
            # Get current date and time in New York timezone
            ny_tz = ZoneInfo("America/New_York")
            current_datetime = datetime.now(ny_tz)
            current_date_str = current_datetime.strftime("%A, %B %d, %Y")
            current_time_str = current_datetime.strftime("%I:%M %p %Z")
            
            # Get bot persona from config
            persona = self.get_config('bot_persona', '')
            
            # Build the full prompt
            full_prompt = ""

            # Add system instructions with anti-repetition and anti-hallucination guidance
            full_prompt += f"""You are having a natural, flowing conversation. CRITICAL RULES - FOLLOW EXACTLY:

CURRENT DATE AND TIME (New York): {current_date_str} at {current_time_str}
Use this information when answering questions about scheduling, planning, or time-sensitive topics.

1. BREVITY: Keep responses to 1-2 short sentences maximum. Be conversational but concise.
2. TRUTH: NEVER make up information. If you don't know something, say "I don't know" or "I'm not sure."
3. NO HALLUCINATION: Do NOT invent schedules, events, plans, or details that weren't mentioned by the user.
4. NO EMOJIS: Never use emojis in your responses.
5. NO REPETITION: Do NOT repeat or rephrase what you just said in previous messages.
6. NO SUMMARIES: Do NOT summarize the conversation.
7. BUILD NATURALLY: Add new information or perspectives, don't restate previous points.
8. STAY GROUNDED: Only discuss things that were actually mentioned in the conversation.
9. RESPOND TO CURRENT MESSAGE: Focus ONLY on what the user just said. Do NOT bring up unrelated topics from past conversations.

"""

            # Add persona if configured
            if persona and persona.strip():
                full_prompt += f"Your personality/character: {persona.strip()}\n\n"
                full_prompt += "IMPORTANT: Stay in character BUT prioritize truthfulness over role-playing.\n\n"

            # Always include schedule information so AI has access to user's calendar
            if user_name:
                try:
                    # Get today's date and 14 days ahead
                    today = current_datetime.date()
                    end_date = today + timedelta(days=14)
                    
                    # Retrieve schedule events
                    schedule_events = self.get_schedule_events(
                        user_name=user_name,
                        start_date=today.strftime('%Y-%m-%d'),
                        end_date=end_date.strftime('%Y-%m-%d'),
                        limit=50
                    )
                    
                    if schedule_events:
                        full_prompt += "SCHEDULE INFORMATION:\n"
                        for event in schedule_events:
                            event_date = event['event_date']
                            event_time = event['event_time']
                            title = event['title']
                            description = event['description'] or ''
                            
                            # Format the event
                            if event_time:
                                time_str = event_time.strftime('%I:%M %p') if hasattr(event_time, 'strftime') else str(event_time)
                                full_prompt += f"- {event_date} at {time_str}: {title}"
                            else:
                                full_prompt += f"- {event_date}: {title}"
                            
                            if description:
                                full_prompt += f" ({description})"
                            full_prompt += "\n"
                        full_prompt += "\n"
                    else:
                        full_prompt += "SCHEDULE INFORMATION: No upcoming events found.\n\n"
                        
                except Exception as e:
                    logger.error(f"Error retrieving schedule events: {e}")
                    full_prompt += "SCHEDULE INFORMATION: Unable to retrieve schedule at this time.\n\n"

            # Advanced settings: limits and semantic ranking
            short_term_limit_cfg = self.get_config('short_term_memory_limit', '10')
            long_term_limit_cfg = self.get_config('long_term_memory_limit', '10')
            use_semantic_ranking = self.get_config('use_semantic_memory_ranking', 'false').lower() == 'true'

            try:
                short_term_limit = max(1, int(str(short_term_limit_cfg)))
            except Exception:
                short_term_limit = 10
            try:
                long_term_limit = max(1, int(str(long_term_limit_cfg)))
            except Exception:
                long_term_limit = 10

            # Get comprehensive context from MemoryManager with limits
            context = self.memory_manager.get_conversation_context(
                user=user_name,
                query=current_message,
                session_id=session_id,
                include_entities=True,
                include_consolidated=True,
                short_term_limit=short_term_limit,
                long_term_limit=long_term_limit,
                semantic_ranking=use_semantic_ranking
            )
            
            # Add entities if available
            if context.get('entities'):
                full_prompt += "KNOWN ENTITIES:\n"
                for entity in context['entities']:
                    full_prompt += f"- {entity.text} ({entity.entity_type}): {entity.context}\n"
                full_prompt += "\n"
            
            # Add relevant memories (mix of recent full + old consolidated)
            if context.get('memories'):
                full_prompt += "RELEVANT CONTEXT:\n"
                for memory in context['memories']:
                    role = memory.get('metadata', {}).get('role', 'user')
                    content = memory.get('content', '')
                    full_prompt += f"{role}: {content}\n"
                full_prompt += "\n"
            
            # Add consolidated memories if available
            if context.get('consolidated'):
                full_prompt += "SUMMARY OF PAST CONVERSATIONS:\n"
                for consolidated in context['consolidated']:
                    full_prompt += f"- {consolidated.get('content', '')}\n"
                full_prompt += "\n"
            
            # Add current session
            if context.get('session'):
                full_prompt += "Current conversation:\n"
                for msg in context['session']:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    full_prompt += f"{role}: {content}\n"
                full_prompt += "\n"
            
            # Add current message
            full_prompt += f"User: {current_message}\nYou:"
            
            return full_prompt

        except Exception as e:
            logger.error(f"Error building prompt with context: {e}")
            # Fallback to just the current message if there's an error
            return f"User: {current_message}\nYou:"

    def synthesize_speech(self, text):
        """Send text to Piper for TTS with circuit breaker protection"""
        try:
            return self.piper_circuit_breaker.call(self._synthesize_speech_internal, text)
        except CircuitBreakerError:
            logger.error("Piper circuit breaker is open, cannot synthesize speech")
            return None

    def _synthesize_speech_internal(self, text):
        """Internal TTS synthesis method - routes to Piper or Silero based on config"""
        # Get TTS engine from database
        tts_engine = self.get_config('tts_engine', 'piper')

        if tts_engine == 'silero':
            # Use Silero TTS
            response = requests.post(
                f"{self.silero_url}/synthesize",
                json={'text': text},
                timeout=300  # 5 minutes for TTS generation
            )
        else:
            # Use Piper TTS (default)
            response = requests.post(
                f"{self.piper_url}/synthesize",
                json={'text': text},
                timeout=300  # 5 minutes for TTS generation
            )

        if response.status_code == 200:
            return io.BytesIO(response.content)
        else:
            # Parse error details
            error_details = f"Status {response.status_code}"
            try:
                error_json = response.json()
                if 'error' in error_json:
                    error_msg = error_json['error']
                    if error_msg:
                        error_details += f", Error: {error_msg}"
                    else:
                        error_details += ", Error message empty"
                else:
                    error_details += f", Response: {response.text[:200]}"
            except:
                error_details += f", Response: {response.text[:200]}"

            text_preview = text[:100] + "..." if len(text) > 100 else text
            raise requests.RequestException(f"TTS ({tts_engine}) failed: {error_details}, Text: '{text_preview}'")

    def play_audio(self, audio_data):
        """Play audio to Mumble channel"""
        if not audio_data:
            return

        try:
            # Save input audio to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as input_tmp:
                input_tmp.write(audio_data.read())
                input_path = input_tmp.name

            # Resample to 48kHz mono 16-bit PCM for Mumble
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as output_tmp:
                output_path = output_tmp.name

            try:
                # Use ffmpeg to resample audio to Mumble's expected format
                subprocess.run([
                    'ffmpeg', '-i', input_path,
                    '-ar', '48000',  # Sample rate 48kHz
                    '-ac', '1',      # Mono
                    '-sample_fmt', 's16',  # 16-bit PCM
                    '-y',            # Overwrite output
                    output_path
                ], check=True, capture_output=True)

                # Read resampled audio and send to Mumble
                with wave.open(output_path, 'rb') as wav_file:
                    frames = wav_file.readframes(wav_file.getnframes())
                    self.mumble.sound_output.add_sound(frames)

            finally:
                # Clean up temp files
                try:
                    os.unlink(input_path)
                    os.unlink(output_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"Error playing audio: {e}")

    def check_health(self):
        """Check health of all services"""
        current_time = time.time()
        health_status = {}
        
        # Check Whisper service
        try:
            response = requests.get(f"{self.whisper_url}/health", timeout=5)
            health_status['whisper'] = response.status_code == 200
            if health_status['whisper']:
                self.last_health_check['whisper'] = current_time
        except Exception as e:
            health_status['whisper'] = False
            logger.warning(f"Whisper health check failed: {e}")

        # Check Piper service
        try:
            response = requests.get(f"{self.piper_url}/health", timeout=5)
            health_status['piper'] = response.status_code == 200
            if health_status['piper']:
                self.last_health_check['piper'] = current_time
        except Exception as e:
            health_status['piper'] = False
            logger.warning(f"Piper health check failed: {e}")

        # Check database
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                self.release_db_connection(conn)
                health_status['database'] = True
                self.last_health_check['database'] = current_time
            else:
                health_status['database'] = False
        except Exception as e:
            health_status['database'] = False
            logger.warning(f"Database health check failed: {e}")

        # Check Mumble connection
        try:
            if self.mumble:
                # Check if we can access the users object, which indicates connection
                try:
                    # Try to access a simple property to test connection
                    _ = self.mumble.users
                    health_status['mumble'] = True
                    self.last_health_check['mumble'] = current_time
                except Exception:
                    health_status['mumble'] = False
            else:
                health_status['mumble'] = False
        except Exception as e:
            health_status['mumble'] = False
            logger.warning(f"Mumble health check failed: {e}")

        # Overall health status
        self.is_healthy = all(health_status.values())
        
        if not self.is_healthy:
            logger.warning(f"Health check failed: {health_status}")
        else:
            logger.debug(f"All services healthy: {health_status}")
            
        return health_status

    def auto_recovery(self):
        """Attempt to recover from service failures"""
        # Prevent multiple simultaneous recovery attempts
        if hasattr(self, '_reconnecting') and self._reconnecting:
            logger.info("Auto-recovery already in progress, skipping...")
            return
            
        self._reconnecting = True
        logger.info("Attempting auto-recovery...")
        
        try:
            # Only try to reconnect to Mumble if it's actually disconnected
            if not self.mumble:
                try:
                    logger.info("Attempting to reconnect to Mumble...")
                    self.connect()
                    logger.info("Mumble reconnection successful")
                except Exception as e:
                    logger.error(f"Mumble reconnection failed: {e}")
            else:
                logger.info("Mumble connection appears to be active, skipping reconnection")

            # Reset circuit breakers if services are healthy
            health_status = self.check_health()
            if health_status.get('whisper', False):
                if self.whisper_circuit_breaker.state == 'OPEN':
                    logger.info("Resetting Whisper circuit breaker")
                    self.whisper_circuit_breaker.state = 'HALF_OPEN'
                    self.whisper_circuit_breaker.failure_count = 0

            if health_status.get('piper', False):
                if self.piper_circuit_breaker.state == 'OPEN':
                    logger.info("Resetting Piper circuit breaker")
                    self.piper_circuit_breaker.state = 'HALF_OPEN'
                    self.piper_circuit_breaker.failure_count = 0

            if health_status.get('database', False):
                if self.db_circuit_breaker.state == 'OPEN':
                    logger.info("Resetting database circuit breaker")
                    self.db_circuit_breaker.state = 'HALF_OPEN'
                    self.db_circuit_breaker.failure_count = 0
                    
        finally:
            self._reconnecting = False

    def run(self):
        """Main run loop with health monitoring and auto-recovery"""
        logger.info("Starting Mumble AI Bot")

        # Initialize database
        self.init_database()

        # Initialize memory manager now that database pool is ready
        try:
            self.memory_manager = MemoryManager(
                chromadb_url=os.getenv('CHROMADB_URL', 'http://chromadb:8000'),
                redis_url=os.getenv('REDIS_URL', 'redis://redis:6379'),
                db_pool=self.db_pool,
                ollama_url=self.ollama_url
            )
            logger.info("MemoryManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager: {e}")
            self.memory_manager = None

        # Wait for services
        self.wait_for_services()

        # Connect to Mumble
        self.connect()

        logger.info("Bot is ready and listening...")

        # Start health monitoring thread
        health_thread = threading.Thread(target=self._health_monitor, daemon=True)
        health_thread.start()

        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            if self.mumble:
                self.mumble.stop()

    def _health_monitor(self):
        """Background health monitoring thread"""
        last_session_cleanup = time.time()
        session_cleanup_interval = 300  # Clean up idle sessions every 5 minutes

        while True:
            try:
                time.sleep(self.health_check_interval)

                # Check if we need to perform health check
                current_time = time.time()
                last_check = min(self.last_health_check.values()) if self.last_health_check else 0

                if current_time - last_check > self.health_check_interval:
                    health_status = self.check_health()

                    # Only attempt auto-recovery if we've been unhealthy for a while
                    # and not currently in the middle of a reconnection
                    if not self.is_healthy and not hasattr(self, '_reconnecting'):
                        # Add a delay before auto-recovery to prevent rapid reconnection loops
                        time.sleep(5)
                        if not self.is_healthy:
                            self.auto_recovery()

                # Periodically clean up idle sessions
                if current_time - last_session_cleanup > session_cleanup_interval:
                    logger.info("Running periodic session cleanup...")
                    self.close_idle_sessions()
                    last_session_cleanup = current_time

            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                time.sleep(10)  # Wait before retrying

    def start_health_server(self):
        """Start the health check HTTP server"""
        try:
            handler = create_health_handler(self)
            self.health_server = HTTPServer(('0.0.0.0', self.health_port), handler)
            health_thread = threading.Thread(target=self.health_server.serve_forever, daemon=True)
            health_thread.start()
            logger.info(f"Health check server started on port {self.health_port}")
        except Exception as e:
            logger.error(f"Failed to start health server: {e}")

    def stop_health_server(self):
        """Stop the health check HTTP server"""
        if self.health_server:
            try:
                self.health_server.shutdown()
                self.health_server.server_close()
                logger.info("Health check server stopped")
            except Exception as e:
                logger.error(f"Error stopping health server: {e}")

    def check_mumble_connection(self):
        """Check if Mumble connection is alive and reconnect if needed"""
        try:
            if not self.mumble or not hasattr(self.mumble, 'is_alive') or not self.mumble.is_alive():
                logger.warning("Mumble connection lost, attempting to reconnect...")
                try:
                    self.connect()
                    logger.info("Successfully reconnected to Mumble server")
                    return True
                except Exception as e:
                    logger.error(f"Failed to reconnect to Mumble: {e}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error checking Mumble connection: {e}")
            return False

    def run(self):
        """Main run loop with health monitoring and auto-recovery"""
        logger.info("Starting Mumble AI Bot")

        # Initialize database
        self.init_database()

        # Initialize memory manager now that database pool is ready
        try:
            self.memory_manager = MemoryManager(
                chromadb_url=os.getenv('CHROMADB_URL', 'http://chromadb:8000'),
                redis_url=os.getenv('REDIS_URL', 'redis://redis:6379'),
                db_pool=self.db_pool,
                ollama_url=self.ollama_url
            )
            logger.info("MemoryManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager: {e}")
            self.memory_manager = None

        # Wait for services
        self.wait_for_services()

        # Connect to Mumble with retry
        max_connection_attempts = 10
        for attempt in range(max_connection_attempts):
            try:
                self.connect()
                break
            except Exception as e:
                if attempt < max_connection_attempts - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed, retrying in 5 seconds... ({e})")
                    time.sleep(5)
                else:
                    logger.error(f"Failed to connect after {max_connection_attempts} attempts")
                    raise

        # Start health server
        self.start_health_server()

        logger.info("Bot is ready and listening...")

        # Start health monitoring thread
        health_thread = threading.Thread(target=self._health_monitor, daemon=True)
        health_thread.start()

        # Keep running with connection monitoring
        try:
            connection_check_interval = 30  # Check connection every 30 seconds
            last_connection_check = time.time()
            
            while True:
                time.sleep(1)
                
                # Periodically check Mumble connection
                current_time = time.time()
                if current_time - last_connection_check > connection_check_interval:
                    self.check_mumble_connection()
                    last_connection_check = current_time
                    
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop_health_server()
            if self.mumble:
                self.mumble.stop()
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            # Try to gracefully shutdown
            try:
                self.stop_health_server()
                if self.mumble:
                    self.mumble.stop()
            except:
                pass
            raise


if __name__ == '__main__':
    bot = MumbleAIBot()
    bot.run()
