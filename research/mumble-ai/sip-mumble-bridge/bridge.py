#!/usr/bin/env python3
"""
SIP-Mumble Bridge - Full SIP/RTP Implementation
This bridge receives SIP calls and routes audio to/from Mumble server
"""

import sys
import time
import threading
import logging
import socket
import struct
import queue
import random
import re
import audioop
import io
import os
import wave
import requests
import psycopg2
import uuid
import hashlib
from psycopg2 import pool
from collections import deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional

from pymumble_py3 import Mumble
from pymumble_py3.constants import PYMUMBLE_AUDIO_PER_PACKET
import numpy as np

import config

# Import the new memory manager
from memory_manager import MemoryManager

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SIPCall:
    """Represents a single SIP call with RTP audio"""

    def __init__(self, invite_msg, caller_addr, sip_socket):
        self.invite_msg = invite_msg
        self.caller_addr = caller_addr
        self.sip_socket = sip_socket
        self.rtp_socket = None
        self.rtp_port = None
        self.remote_rtp_ip = None
        self.remote_rtp_port = None
        self.running = False
        self.call_id = None
        self.from_tag = None
        self.to_tag = None

    def parse_sdp(self):
        """Parse SDP from INVITE message"""
        try:
            # Extract remote RTP info from SDP
            lines = self.invite_msg.split('\r\n')

            # Find connection address (c=)
            for line in lines:
                if line.startswith('c='):
                    # c=IN IP4 10.0.0.66
                    parts = line.split()
                    if len(parts) >= 3:
                        self.remote_rtp_ip = parts[2]

            # Find media port (m=) and codecs
            for line in lines:
                if line.startswith('m=audio'):
                    # m=audio 16970 RTP/AVP 0 8 101
                    parts = line.split()
                    if len(parts) >= 2:
                        self.remote_rtp_port = int(parts[1])
                        # Extract payload types (codecs)
                        if len(parts) >= 4:
                            codecs = ' '.join(parts[3:])
                            logger.info(f"Client offered codecs (payload types): {codecs}")

            logger.info(f"Parsed SDP: Remote RTP at {self.remote_rtp_ip}:{self.remote_rtp_port}")
            return self.remote_rtp_ip and self.remote_rtp_port

        except Exception as e:
            logger.error(f"Error parsing SDP: {e}")
            return False

    def create_rtp_socket(self):
        """Create RTP socket for audio within configured port range"""
        try:
            self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.rtp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Try to bind to a port in the configured range
            for port in range(config.RTP_PORT_MIN, config.RTP_PORT_MAX + 1):
                try:
                    self.rtp_socket.bind(('0.0.0.0', port))
                    self.rtp_port = port
                    logger.info(f"Created RTP socket on port {self.rtp_port}")
                    return True
                except OSError:
                    continue

            # If all ports in range are busy, use any available port
            self.rtp_socket.bind(('0.0.0.0', 0))
            self.rtp_port = self.rtp_socket.getsockname()[1]
            logger.warning(f"RTP port range exhausted, using port {self.rtp_port}")
            return True

        except Exception as e:
            logger.error(f"Error creating RTP socket: {e}")
            return False

    def send_rtp(self, audio_data, payload_type=0):
        """Send RTP packet"""
        try:
            if not self.rtp_socket or not self.remote_rtp_ip:
                return

            # Build RTP header
            version = 2
            padding = 0
            extension = 0
            cc = 0
            marker = 0
            sequence = random.randint(0, 65535)
            timestamp = int(time.time() * 8000) & 0xFFFFFFFF
            ssrc = random.randint(0, 0xFFFFFFFF)

            # Pack RTP header (12 bytes)
            header = struct.pack('!BBHII',
                (version << 6) | (padding << 5) | (extension << 4) | cc,
                (marker << 7) | payload_type,
                sequence,
                timestamp,
                ssrc
            )

            packet = header + audio_data
            self.rtp_socket.sendto(packet, (self.remote_rtp_ip, self.remote_rtp_port))

        except Exception as e:
            logger.error(f"Error sending RTP: {e}")

    def close(self):
        """Close RTP socket"""
        self.running = False
        if self.rtp_socket:
            self.rtp_socket.close()


class SimpleSIPServer:
    """
    SIP server with proper SDP/RTP support
    """

    def __init__(self, host='0.0.0.0', port=5060):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.call_handler = None
        self.active_calls = {}

    def start(self):
        """Start the SIP server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.running = True

            logger.info(f"SIP Server listening on {self.host}:{self.port}")

            # Start listening thread
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()

            return True

        except Exception as e:
            logger.error(f"Failed to start SIP server: {e}")
            return False

    def _listen_loop(self):
        """Listen for incoming SIP messages"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(8192)
                message = data.decode('utf-8', errors='ignore')

                logger.debug(f"Received SIP message from {addr}:\n{message[:300]}")

                # Handle SIP message
                self._handle_sip_message(message, addr)

            except Exception as e:
                if self.running:
                    logger.error(f"Error in listen loop: {e}")

    def _handle_sip_message(self, message, addr):
        """Handle incoming SIP message"""
        lines = message.split('\r\n')
        if not lines:
            return

        request_line = lines[0]

        if request_line.startswith('INVITE'):
            logger.info(f"Incoming INVITE from {addr}")
            self._handle_invite(message, addr)

        elif request_line.startswith('ACK'):
            logger.info(f"ACK received from {addr}")
            # Call is now established, trigger handler
            call_id = self._extract_header(message, 'Call-ID')
            if call_id and call_id in self.active_calls:
                call = self.active_calls[call_id]
                # Only start handler once per call (check if call is not already running)
                if not hasattr(call, 'session_started'):
                    call.session_started = True
                    if self.call_handler:
                        threading.Thread(target=self.call_handler, args=(call,), daemon=True).start()
                else:
                    logger.debug(f"ACK for already-started call {call_id}, ignoring")

        elif request_line.startswith('BYE'):
            logger.info(f"Call ended by {addr}")
            self._send_response(200, 'OK', addr, message)

            # Clean up call
            call_id = self._extract_header(message, 'Call-ID')
            if call_id and call_id in self.active_calls:
                self.active_calls[call_id].close()
                del self.active_calls[call_id]

        elif request_line.startswith('OPTIONS'):
            self._send_response(200, 'OK', addr, message)

        elif request_line.startswith('CANCEL'):
            logger.info(f"Call cancelled by {addr}")
            self._send_response(200, 'OK', addr, message)

    def _handle_invite(self, message, addr):
        """Handle INVITE - send 180 Ringing then 200 OK with SDP"""
        try:
            # Check if this is a retransmitted INVITE for an existing call
            call_id = self._extract_header(message, 'Call-ID')
            if call_id and call_id in self.active_calls:
                logger.debug(f"Retransmitted INVITE for existing call {call_id}, re-sending 200 OK")
                call = self.active_calls[call_id]
                # Re-send responses
                self._send_response(100, 'Trying', addr, message)
                time.sleep(0.1)
                self._send_response(180, 'Ringing', addr, message, to_tag=call.to_tag)
                time.sleep(0.2)
                self._send_invite_ok(addr, message, call)
                return

            # Create call object
            call = SIPCall(message, addr, self.socket)

            # Parse SDP to get remote RTP info
            if not call.parse_sdp():
                logger.error("Failed to parse SDP from INVITE")
                self._send_response(400, 'Bad Request', addr, message)
                return

            # Create RTP socket
            if not call.create_rtp_socket():
                logger.error("Failed to create RTP socket")
                self._send_response(500, 'Internal Server Error', addr, message)
                return

            # Extract call info
            call.call_id = call_id
            from_header = self._extract_header(message, 'From')

            # Extract from-tag
            if from_header and 'tag=' in from_header:
                call.from_tag = from_header.split('tag=')[1].split(';')[0].split('>')[0]

            # Generate to-tag
            call.to_tag = f"tag-{random.randint(100000, 999999)}"

            # Store call
            if call.call_id:
                self.active_calls[call.call_id] = call

            # Send 100 Trying
            self._send_response(100, 'Trying', addr, message)

            # Send 180 Ringing
            time.sleep(0.1)
            self._send_response(180, 'Ringing', addr, message, to_tag=call.to_tag)

            # Send 200 OK with SDP
            time.sleep(0.2)
            self._send_invite_ok(addr, message, call)

        except Exception as e:
            logger.error(f"Error handling INVITE: {e}", exc_info=True)
            self._send_response(500, 'Internal Server Error', addr, message)

    def _send_invite_ok(self, addr, request, call):
        """Send 200 OK response with SDP"""
        try:
            # Use the IP that VitalPBX sent the INVITE to (from the request line)
            # This ensures we advertise the externally accessible IP
            request_lines = request.split('\r\n')
            request_line = request_lines[0]

            # Extract IP from "INVITE sip:10.0.0.56:5060 SIP/2.0"
            local_ip = '10.0.0.56'  # Default fallback
            if 'sip:' in request_line:
                try:
                    uri_part = request_line.split('sip:')[1].split()[0]
                    if ':' in uri_part:
                        local_ip = uri_part.split(':')[0]
                    else:
                        local_ip = uri_part
                except:
                    pass

            # Build SDP
            sdp = f"""v=0
o=MumbleBridge 0 0 IN IP4 {local_ip}
s=Call
c=IN IP4 {local_ip}
t=0 0
m=audio {call.rtp_port} RTP/AVP 0 8 101
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:101 telephone-event/8000
a=ptime:20
a=sendrecv
"""

            # Extract headers from request
            call_id = self._extract_header(request, 'Call-ID')
            from_header = self._extract_header(request, 'From')
            to_header = self._extract_header(request, 'To')
            cseq = self._extract_header(request, 'CSeq')
            via = self._extract_header(request, 'Via')

            # Add to-tag if not present
            if to_header and 'tag=' not in to_header:
                to_header = f"{to_header};{call.to_tag}"

            # Build response
            response = f"SIP/2.0 200 OK\r\n"
            if via:
                response += f"Via: {via}\r\n"
            if from_header:
                response += f"From: {from_header}\r\n"
            if to_header:
                response += f"To: {to_header}\r\n"
            else:
                response += f"To: <sip:5000@{local_ip}>;{call.to_tag}\r\n"
            if call_id:
                response += f"Call-ID: {call_id}\r\n"
            if cseq:
                response += f"CSeq: {cseq}\r\n"

            response += f"Contact: <sip:mumble-bridge@{local_ip}:{self.port}>\r\n"
            response += f"Content-Type: application/sdp\r\n"
            response += f"Content-Length: {len(sdp)}\r\n"
            response += "\r\n"
            response += sdp

            self.socket.sendto(response.encode('utf-8'), addr)
            logger.info(f"Sent 200 OK with SDP to {addr}")
            logger.debug(f"SDP:\n{sdp}")

        except Exception as e:
            logger.error(f"Error sending 200 OK: {e}", exc_info=True)

    def _send_response(self, code, reason, addr, request, to_tag=None):
        """Send SIP response"""
        try:
            # Extract Call-ID, From, To, CSeq from request
            call_id = self._extract_header(request, 'Call-ID')
            from_header = self._extract_header(request, 'From')
            to_header = self._extract_header(request, 'To')
            cseq = self._extract_header(request, 'CSeq')
            via = self._extract_header(request, 'Via')

            # Add to-tag if provided and not already present
            if to_tag and to_header and 'tag=' not in to_header:
                to_header = f"{to_header};{to_tag}"

            response = f"SIP/2.0 {code} {reason}\r\n"
            if via:
                response += f"Via: {via}\r\n"
            if from_header:
                response += f"From: {from_header}\r\n"
            if to_header:
                response += f"To: {to_header}\r\n"
            if call_id:
                response += f"Call-ID: {call_id}\r\n"
            if cseq:
                response += f"CSeq: {cseq}\r\n"
            response += f"Content-Length: 0\r\n"
            response += "\r\n"

            self.socket.sendto(response.encode('utf-8'), addr)
            logger.debug(f"Sent {code} {reason} to {addr}")

        except Exception as e:
            logger.error(f"Error sending response: {e}")

    def _extract_header(self, message, header_name):
        """Extract header value from SIP message"""
        for line in message.split('\r\n'):
            if line.startswith(f"{header_name}:"):
                return line.split(':', 1)[1].strip()
        return None

    def set_call_handler(self, handler):
        """Set callback for incoming calls"""
        self.call_handler = handler

    def stop(self):
        """Stop the SIP server"""
        self.running = False

        # Close all active calls
        for call in list(self.active_calls.values()):
            call.close()
        self.active_calls.clear()

        if self.socket:
            self.socket.close()
        logger.info("SIP server stopped")


class AudioBridge:
    """Legacy Mumble bridge (unused in SIP AI flow). Kept for compatibility."""

    def __init__(self):
        self.mumble_to_phone = queue.Queue(maxsize=100)
        self.phone_to_mumble = queue.Queue(maxsize=100)
        self.running = False

    def start(self):
        self.running = True
        logger.info("Audio bridge started")

    def stop(self):
        self.running = False
        while not self.mumble_to_phone.empty():
            try:
                self.mumble_to_phone.get_nowait()
            except:
                pass
        while not self.phone_to_mumble.empty():
            try:
                self.phone_to_mumble.get_nowait()
            except:
                pass
        logger.info("Audio bridge stopped")


class MumbleClient:
    """Legacy Mumble client (unused). Kept for compatibility."""

    def __init__(self, audio_bridge):
        self.audio_bridge = audio_bridge
        self.mumble = None
        self.connected = False

    def connect(self):
        logger.debug("Mumble client disabled in SIP AI flow")
        return False

    def disconnect(self):
        pass


class AIPipeline:
    """AI pipeline: STT -> LLM -> TTS + DB logging using shared config."""

    def __init__(self):
        # Service endpoints
        self.whisper_url = config.WHISPER_URL
        self.piper_url = config.PIPER_URL
        self.silero_url = config.SILERO_URL

        # Ollama defaults (will be overridden by DB config)
        self.ollama_url = config.DEFAULT_OLLAMA_URL
        self.ollama_model = config.DEFAULT_OLLAMA_MODEL

        # DB config
        self.db_host = config.DB_HOST
        self.db_port = config.DB_PORT
        self.db_name = config.DB_NAME
        self.db_user = config.DB_USER
        self.db_password = config.DB_PASSWORD
        self.db_pool = None
        self._init_db_pool()
        self._wait_for_services()

        # Memory manager will be initialized in start() method after database is ready
        self.memory_manager = None

        # Semantic memory and session tracking
        self.user_sessions = {}  # Track active sessions per user
        self.session_lock = threading.Lock()
        self.embedding_cache = {}  # Cache embeddings to reduce API calls
        
        # Topic state tracking
        self.active_topics = {}  # Track current topic per user/session
        self.resolved_topics = {}  # Track recently resolved topics per user/session

    def _wait_for_services(self):
        """Wait for dependent services to be ready"""
        services = [
            (f"{self.whisper_url}/health", "Whisper"),
            (f"{self.piper_url}/health", "Piper"),
        ]

        for url, name in services:
            while True:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"{name} service is ready")
                        break
                except Exception as e:
                    logger.info(f"Waiting for {name} service... ({e})")
                    time.sleep(2)

    def _init_db_pool(self):
        """Initialize database connection pool"""
        try:
            self.db_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            self.db_pool = None

    def get_db_connection(self):
        """Get a connection from the pool"""
        if self.db_pool:
            return self.db_pool.getconn()
        else:
            # Fallback to direct connection
            return psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
            )

    def release_db_connection(self, conn):
        """Release a connection back to the pool"""
        if self.db_pool and conn:
            self.db_pool.putconn(conn)
        elif conn:
            conn.close()

    def db_conn(self):
        """Legacy method for compatibility"""
        return self.get_db_connection()

    def get_config(self, key, default=None):
        conn = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_config WHERE key = %s", (key,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return result[0]
            return default
        except Exception as e:
            logger.error(f"Error getting config {key}: {e}")
            return default
        finally:
            if conn:
                self.release_db_connection(conn)

    def save_message(self, user_name, user_session, message_type, role, message, session_id=None):
        """Save a message using MemoryManager (non-blocking)"""
        if not self.memory_manager:
            logger.warning("MemoryManager not available in SIP bridge, falling back to old method")
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
            logger.debug(f"Saved {role} {message_type} message from {user_name} via MemoryManager in SIP bridge")
            return True
        except Exception as e:
            logger.error(f"Error saving message via MemoryManager in SIP bridge: {e}")
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
                conn.rollback()
            return False
        finally:
            if conn:
                self.release_db_connection(conn)

    def get_conversation_history(self, user_name=None, limit=10, session_id=None):
        conn = None
        try:
            conn = self.get_db_connection()
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

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text using Ollama's embedding model"""
        # Check cache first
        text_hash = hashlib.md5(text.encode()).hexdigest()
        if text_hash in self.embedding_cache:
            return self.embedding_cache[text_hash]

        try:
            embedding_model = self.get_config('embedding_model', 'nomic-embed-text:latest')
            ollama_url = self.get_config('ollama_url', config.DEFAULT_OLLAMA_URL)
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
                # Cache the embedding
                self.embedding_cache[text_hash] = embedding
                return embedding
            else:
                logger.warning(f"Failed to generate embedding: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def get_or_create_session(self, user_name: str, user_session: int) -> str:
        """Get or create a conversation session ID for a user"""
        with self.session_lock:
            # Check if user has an active session
            if user_name in self.user_sessions:
                session_id = self.user_sessions[user_name]
                # Update session activity
                self._update_session_activity(session_id)
                return session_id

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
                        INSERT INTO conversation_sessions (user_name, session_id, started_at, last_activity)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (session_id) DO UPDATE SET last_activity = EXCLUDED.last_activity
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
        import json
        
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

    def extract_and_save_memory(self, user_message: str, assistant_response: str, user_name: str, session_id: str):
        """Extract important information from conversation and save as persistent memory"""
        try:
            ollama_url = self.get_config('ollama_url', config.DEFAULT_OLLAMA_URL)
            # Use specialized memory extraction model for better precision
            ollama_model = self.get_config('memory_extraction_model', 'qwen2.5:3b')
            logger.info(f"Memory extraction using model: {ollama_model}")

            # Get current date for context
            from zoneinfo import ZoneInfo
            from datetime import datetime
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
                            'options': {'temperature': 0.3}  # Lower temp for more consistent extraction
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

                # Try to parse and save memories
                memories = self._parse_memory_json(result)
                if memories is not None:
                    # Filter out memories with empty or whitespace-only content
                    valid_memories = []
                    for mem in memories:
                        if isinstance(mem, dict) and 'content' in mem and 'category' in mem:
                            content = mem.get('content', '')
                            # Skip if content is not a string or is empty/whitespace
                            if isinstance(content, str) and content.strip():
                                valid_memories.append(mem)
                            else:
                                # Debug level for expected LLM artifacts
                                logger.debug(f"Filtered out empty memory: category={mem.get('category')}, importance={mem.get('importance')}")

                    # Save each valid extracted memory
                    for memory in valid_memories:
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

        except Exception as e:
            logger.error(f"Error extracting memory: {e}")

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
                        from datetime import datetime, timedelta
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
                cursor.execute(
                    """
                    INSERT INTO persistent_memories
                    (user_name, category, content, session_id, importance, tags, event_date, event_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_name, category, content, session_id, importance, tags or [], event_date, event_time)
                )
                conn.commit()
                cursor.close()
                logger.info(f"Saved new {category} memory for {user_name}")
        except Exception as e:
            logger.error(f"Error saving persistent memory: {e}")
            if conn:
                conn.rollback()
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
            ollama_url = self.get_config('ollama_url', config.DEFAULT_OLLAMA_URL)
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
            # Pre-flight validation: Detect if this is clearly a query, not a command
            query_indicators = ['what', 'when', 'do i have', 'tell me', 'show me', 'any', 'check', 'am i free', 'busy', 'available']
            action_indicators = ['schedule', 'add', 'create', 'book', 'set', 'remind me', 'appointment', 'meeting', 'plan']
            
            message_lower = user_message.lower()
            has_query = any(indicator in message_lower for indicator in query_indicators)
            has_action = any(indicator in message_lower for indicator in action_indicators)
            
            # If it's clearly a query without action words, skip extraction entirely
            if has_query and not has_action:
                logger.info(f"Detected schedule query (not action), skipping extraction: {user_message}")
                return
            
            # Additional validation: Check for explicit query patterns
            explicit_query_patterns = [
                'what\'s on my', 'what is on my', 'tell me about my', 'show me my',
                'do i have anything', 'am i free', 'when is my', 'what time is my',
                'check my', 'look at my', 'review my', 'see my', 'view my'
            ]
            
            if any(pattern in message_lower for pattern in explicit_query_patterns):
                logger.info(f"Detected explicit schedule query pattern, skipping extraction: {user_message}")
                return
            
            ollama_url = self.get_config('ollama_url', self.ollama_url)
            ollama_model = self.get_config('ollama_model', self.ollama_model)
            logger.info(f"Schedule action extraction using model: {ollama_model} for message: {user_message}")

            # Get current date for context
            from zoneinfo import ZoneInfo
            from datetime import timedelta
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

User: "Am I free on Friday?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "When is my dentist appointment?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Show me my schedule for next week"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Check my calendar for tomorrow"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "What am I doing this weekend?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Any plans for today?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "I'm busy tomorrow" (just stating fact, not scheduling)
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "I have a meeting tomorrow" (just stating fact, not scheduling)
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

REMEMBER: When in doubt, use "NOTHING". It's better to miss a scheduling request than to create unwanted events.
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

                    # Post-extraction validation: Verify the action makes sense given the user message
                    if action == 'ADD':
                        # Verify the user message actually sounds like they want to add something
                        add_validation_words = ['schedule', 'add', 'book', 'set', 'remind', 'appointment', 'meeting', 'plan', 'create']
                        if not any(word in user_message.lower() for word in add_validation_words):
                            logger.warning(f"ADD action rejected - user message doesn't sound like scheduling: {user_message}")
                            return
                        logger.info(f"ADD action validated for message: {user_message}")
                        
                    elif action == 'UPDATE':
                        # Verify the user message sounds like they want to modify something
                        update_validation_words = ['change', 'update', 'modify', 'reschedule', 'move', 'edit']
                        if not any(word in user_message.lower() for word in update_validation_words):
                            logger.warning(f"UPDATE action rejected - user message doesn't sound like updating: {user_message}")
                            return
                        logger.info(f"UPDATE action validated for message: {user_message}")
                        
                    elif action == 'DELETE':
                        # Verify the user message sounds like they want to cancel/delete something
                        delete_validation_words = ['cancel', 'delete', 'remove', 'clear', 'drop']
                        if not any(word in user_message.lower() for word in delete_validation_words):
                            logger.warning(f"DELETE action rejected - user message doesn't sound like deleting: {user_message}")
                            return
                        logger.info(f"DELETE action validated for message: {user_message}")

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

    def get_persistent_memories(self, user_name: str, category: str = None, limit: int = 20) -> List[Dict]:
        """Retrieve persistent memories for a user"""
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

            return memories

        except Exception as e:
            logger.error(f"Error retrieving persistent memories: {e}")
            return []
        finally:
            if conn:
                self.release_db_connection(conn)

    def get_semantic_context(self, query_text: str, user_name: str, current_session_id: str, limit: int = 10) -> List[Dict]:
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

    def is_schedule_query(self, message):
        """Detect if user is asking about their schedule/calendar"""
        schedule_keywords = [
            'schedule', 'calendar', 'appointment', 'meeting', 'event',
            'what do i have', 'what\'s on', 'do i have', 'am i free',
            'busy', 'available', 'plans', 'what\'s coming up',
            'tomorrow', 'today', 'tonight', 'next week', 'this week',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'when is', 'what time', 'upcoming', 'when\'s my', 'find my', 'tell me about my',
            'any plans', 'what am i doing', 'free time', 'what\'s my', 'show me my',
            'check my', 'look at my', 'review my', 'see my', 'view my'
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

    def format_schedule_for_prompt(self, schedule_events, current_datetime):
        """Format schedule events for AI prompt with clear date headers and time formatting"""
        if not schedule_events:
            return "📅 SCHEDULE: Empty - no events scheduled. Clearly tell the user their calendar is clear."
        
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        
        # Group events by date categories
        today = current_datetime.date()
        tomorrow = today + timedelta(days=1)
        week_end = today + timedelta(days=7)
        month_end = today + timedelta(days=30)
        
        today_events = []
        tomorrow_events = []
        week_events = []
        later_events = []
        
        for event in schedule_events:
            event_date = event['event_date']
            if isinstance(event_date, str):
                from datetime import datetime
                event_date = datetime.strptime(event_date, '%Y-%m-%d').date()
            
            if event_date == today:
                today_events.append(event)
            elif event_date == tomorrow:
                tomorrow_events.append(event)
            elif event_date <= week_end:
                week_events.append(event)
            else:
                later_events.append(event)
        
        # Format time for display
        def format_event_time(event):
            if event['event_time']:
                try:
                    if isinstance(event['event_time'], str):
                        from datetime import datetime
                        time_obj = datetime.strptime(event['event_time'], '%H:%M:%S').time()
                    else:
                        time_obj = event['event_time']
                    return time_obj.strftime('%I:%M %p')
                except:
                    return "All day"
            return "All day"
        
        # Format importance indicator
        def format_importance(event):
            importance = event.get('importance', 5)
            if importance >= 9:
                return "🔴"  # Critical
            elif importance >= 7:
                return "🟠"  # High
            elif importance >= 5:
                return "🔵"  # Medium
            else:
                return "⚪"  # Low
        
        # Build formatted output
        formatted = "📅 YOUR UPCOMING SCHEDULE:\n\n"
        
        if today_events:
            formatted += f"TODAY ({today.strftime('%A, %B %d')}):\n"
            for event in sorted(today_events, key=lambda x: x['event_time'] or '00:00:00'):
                time_str = format_event_time(event)
                importance_icon = format_importance(event)
                formatted += f"  {importance_icon} {event['title']} at {time_str}\n"
            formatted += "\n"
        
        if tomorrow_events:
            formatted += f"TOMORROW ({tomorrow.strftime('%A, %B %d')}):\n"
            for event in sorted(tomorrow_events, key=lambda x: x['event_time'] or '00:00:00'):
                time_str = format_event_time(event)
                importance_icon = format_importance(event)
                formatted += f"  {importance_icon} {event['title']} at {time_str}\n"
            formatted += "\n"
        
        if week_events:
            formatted += "THIS WEEK:\n"
            for event in sorted(week_events, key=lambda x: (x['event_date'], x['event_time'] or '00:00:00')):
                event_date = event['event_date']
                if isinstance(event_date, str):
                    from datetime import datetime
                    event_date = datetime.strptime(event_date, '%Y-%m-%d').date()
                date_str = event_date.strftime('%A, %B %d')
                time_str = format_event_time(event)
                importance_icon = format_importance(event)
                formatted += f"  {importance_icon} {event['title']} - {date_str} at {time_str}\n"
            formatted += "\n"
        
        if later_events:
            formatted += "LATER THIS MONTH:\n"
            for event in sorted(later_events, key=lambda x: (x['event_date'], x['event_time'] or '00:00:00')):
                event_date = event['event_date']
                if isinstance(event_date, str):
                    from datetime import datetime
                    event_date = datetime.strptime(event_date, '%Y-%m-%d').date()
                date_str = event_date.strftime('%A, %B %d')
                time_str = format_event_time(event)
                importance_icon = format_importance(event)
                formatted += f"  {importance_icon} {event['title']} - {date_str} at {time_str}\n"
            formatted += "\n"
        
        # Add instructions for AI
        total_events = len(schedule_events)
        formatted += f"TOTAL: {total_events} upcoming events\n"
        formatted += "INSTRUCTIONS: When the user asks about their schedule, use this information to provide accurate, helpful responses. "
        formatted += "Be specific about dates and times. If they ask about a specific day, focus on events for that day. "
        formatted += "If they ask about availability, clearly state when they're free or busy.\n"
        
        return formatted

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

            ollama_url = self.get_config('ollama_url', config.DEFAULT_OLLAMA_URL)
            ollama_model = self.get_config('ollama_model', config.DEFAULT_OLLAMA_MODEL)
            
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
                timeout=30
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
                WHERE user_name = %s AND session_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
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

    def is_schedule_query(self, message):
        """Detect if user is asking about their schedule/calendar"""
        schedule_keywords = [
            'schedule', 'calendar', 'appointment', 'meeting', 'event',
            'what do i have', 'what\'s on', 'do i have', 'am i free',
            'busy', 'available', 'plans', 'what\'s coming up',
            'upcoming', 'when is', 'what time', 'upcoming', 'when\'s my', 'find my', 'tell me about my'
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in schedule_keywords)

    def build_prompt_with_context(self, current_message, user_name=None, session_id=None):
        """Build a prompt with smart memory system using MemoryManager"""
        try:
            # If memory manager is not available, fall back to simple prompt
            if not self.memory_manager:
                logger.warning("MemoryManager not available in SIP bridge, using fallback prompt")
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
                    # Get schedule events for the next 14 days
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
                        # Format schedule for prompt
                        schedule_context = self.format_schedule_for_prompt(schedule_events, current_datetime)
                        full_prompt += f"\n{schedule_context}\n\n"
                    else:
                        full_prompt += "\n📅 SCHEDULE: No events found in the next 14 days. Your calendar appears to be clear.\n\n"
                        
                except Exception as e:
                    logger.error(f"Error retrieving schedule events: {e}")
                    full_prompt += "\n📅 SCHEDULE: Unable to retrieve schedule information at this time.\n\n"

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

            # Get comprehensive context with limits
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

    def transcribe_wav_file(self, wav_path):
        try:
            # Get language setting from database
            language = self.get_config('whisper_language', 'auto')

            with open(wav_path, 'rb') as f:
                resp = requests.post(
                    f"{self.whisper_url}/transcribe",
                    files={'audio': f},
                    data={'language': language},
                    timeout=300
                )
            if resp.status_code == 200:
                return resp.json().get('text', '').strip()
            logger.error(f"Whisper error: {resp.text}")
            return ''
        except Exception as e:
            logger.error(f"Transcription request failed: {e}")
            return ''

    def ollama_generate(self, message, user_name=None, session_id=None):
        try:
            # Get Ollama configuration from database (same as mumble-bot)
            ollama_url = self.get_config('ollama_url', config.DEFAULT_OLLAMA_URL)
            ollama_model = self.get_config('ollama_model', config.DEFAULT_OLLAMA_MODEL)
            use_chain_of_thought = self.get_config('use_chain_of_thought', 'false').lower() == 'true'
            enable_parallel_processing = self.get_config('enable_parallel_processing', 'false').lower() == 'true'
            logger.info(f"Using Ollama: {ollama_url} with model: {ollama_model}")

            # Detect conversation closure before building prompt
            closure_detected, closure_type = self.detect_conversation_closure(message, user_name, session_id)
            if closure_detected:
                logger.info(f"Conversation closure detected: {closure_type}")
                # Mark previous topic as resolved
                self.mark_topic_resolved(user_name, session_id, f"Resolved via {closure_type}")

            prompt = self.build_prompt_with_context(message, user_name, session_id)
            
            # Adjust generation parameters based on closure detection
            if closure_detected:
                # Shorter, warmer responses for closure messages
                generation_options = {
                    "temperature": 0.9,  # More natural/warm
                    "top_p": 0.95,  # More creative
                    "num_predict": 30,   # Very brief
                    "stop": ["\n\n", "User:", "Assistant:"]
                }
            else:
                # Standard parameters for regular responses
                generation_options = {
                    "temperature": 0.7,  # Lower temperature for more consistent, focused responses
                    "top_p": 0.9,  # Nucleus sampling for better quality
                    "num_predict": 100,  # Limit response length (roughly 1-2 sentences)
                    "stop": ["\n\n", "User:", "Assistant:"]  # Stop at conversation breaks
                }
            
            # CoT hidden instruction
            cot_instruction = """

IMPORTANT: Think step by step privately. Do NOT reveal your chain-of-thought. Provide ONLY the final concise answer.
"""
            base_prompt = prompt + (cot_instruction if use_chain_of_thought else "")

            def _once(p):
                r = requests.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": ollama_model,
                        "prompt": p,
                        "stream": False,
                        "options": generation_options
                    },
                    timeout=300,
                )
                if r.status_code != 200:
                    raise requests.RequestException(f"Ollama error: {r.text}")
                out = r.json().get('response', '').strip()
                return out or 'I did not understand that.'

            if use_chain_of_thought:
                if enable_parallel_processing:
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    outs = []
                    with ThreadPoolExecutor(max_workers=3) as ex:
                        fs = [ex.submit(_once, base_prompt) for _ in range(3)]
                        for f in as_completed(fs):
                            try:
                                outs.append(f.result())
                            except Exception as e:
                                logger.error(f"Parallel CoT error: {e}")
                    if not outs:
                        outs = [_once(base_prompt)]
                else:
                    outs = [_once(base_prompt) for _ in range(3)]
                from collections import Counter
                key = lambda s: s.strip().lower()
                counts = Counter(key(o) for o in outs)
                best_norm, _ = counts.most_common(1)[0]
                generated_response = next((o for o in outs if key(o) == best_norm), outs[0])
            else:
                generated_response = _once(base_prompt)

            # Log warning if response is empty
            if not generated_response:
                logger.warning(f"Empty LLM response received. Model: {ollama_model}, User query: '{message[:100]}...'")
                return 'I did not understand that.'

            return generated_response
            logger.error(f"Ollama error: {resp.text}")
            return 'Sorry, I encountered an error.'
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return 'Sorry, I am having trouble connecting to my language model.'

    def tts_wav(self, text):
        try:
            # Get TTS engine configuration from database (same as mumble-bot)
            tts_engine = self.get_config('tts_engine', 'piper')

            if tts_engine == 'silero':
                # Use Silero TTS
                logger.info("Using Silero TTS engine")
                resp = requests.post(f"{self.silero_url}/synthesize", json={'text': text}, timeout=300)
            else:
                # Use Piper TTS (default)
                voice_config = self.get_config('piper_voice', 'en_US-lessac-medium')
                logger.info(f"Using Piper TTS engine with voice: {voice_config}")
                resp = requests.post(f"{self.piper_url}/synthesize", json={'text': text}, timeout=300)

            if resp.status_code == 200:
                return io.BytesIO(resp.content)
            logger.error(f"TTS error ({tts_engine}): {resp.text}")
            return None
        except Exception as e:
            logger.error(f"TTS request failed: {e}")
            return None

    def play_tts_over_rtp(self, sip_call: 'SIPCall', wav_bytes: io.BytesIO):
        if not wav_bytes:
            return
        try:
            wav_bytes.seek(0)
            with tempfile_named(suffix='.wav') as tmp_in:
                with open(tmp_in, 'wb') as f:
                    f.write(wav_bytes.read())
                # Read PCM from WAV
                with wave.open(tmp_in, 'rb') as w:
                    n_channels = w.getnchannels()
                    sampwidth = w.getsampwidth()
                    framerate = w.getframerate()
                    frames = w.readframes(w.getnframes())

                # Ensure mono 16-bit
                if n_channels > 1:
                    frames = audioop.tomono(frames, sampwidth, 0.5, 0.5)
                if sampwidth != 2:
                    frames = audioop.lin2lin(frames, sampwidth, 2)
                # Resample to 8kHz for PCMU
                if framerate != 8000:
                    frames, _ = audioop.ratecv(frames, 2, 1, framerate, 8000, None)

                # Chunk into 20ms (160 samples @ 8kHz -> 320 bytes 16-bit)
                chunk_size = 160 * 2
                for i in range(0, len(frames), chunk_size):
                    chunk = frames[i:i + chunk_size]
                    if len(chunk) == 0:
                        continue
                    # μ-law encode
                    ulaw = audioop.lin2ulaw(chunk, 2)
                    sip_call.send_rtp(ulaw, payload_type=0)
                    time.sleep(0.02)
        except Exception as e:
            logger.error(f"Error playing TTS over RTP: {e}")


class tempfile_named:
    """Context manager to create and auto-clean a temp file."""

    def __init__(self, suffix=''):
        self.suffix = suffix
        self.name = None

    def __enter__(self):
        import tempfile
        f = tempfile.NamedTemporaryFile(delete=False, suffix=self.suffix)
        self.name = f.name
        f.close()
        return self.name

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.name and os.path.exists(self.name):
                os.unlink(self.name)
        except Exception:
            pass


class CallSession:
    """Manages a single call session with RTP audio and AI pipeline."""

    def __init__(self, sip_call, pipeline=None):
        self.sip_call = sip_call
        self.active = False
        self.rtp_thread = None
        self.pipeline = pipeline if pipeline else AIPipeline()
        # Voice activity detection on 8kHz PCM
        # Check if manual override is set via config
        if config.VOICE_THRESHOLD > 0:
            self.voice_threshold = config.VOICE_THRESHOLD
            self.adaptive_threshold = False  # Manual override disables adaptive calibration
            logger.info(f"Using manual voice threshold: {self.voice_threshold}")
        else:
            self.voice_threshold = 100  # Initial threshold before calibration
            self.adaptive_threshold = True  # Enable adaptive calibration
            logger.info("Using adaptive voice threshold calibration")
        
        self.silence_threshold = config.SILENCE_THRESHOLD
        self.recording = False
        self.last_audio_time = None
        self.audio_buffer_8k = []  # list of 16-bit PCM @8kHz
        self.processing = False
        # RMS monitoring for debugging
        self.rms_samples = []
        self.max_rms = 0
        # Adaptive threshold for cellular/low-volume audio
        self.baseline_rms_samples = []  # Collect baseline noise floor
        self.baseline_collection_time = 3.0  # seconds to collect baseline
        self.baseline_collected = False if self.adaptive_threshold else True
        # Identify caller
        self.caller_name = self._extract_caller_name()
        self.user_session = 0
        # Audio muting during TTS playback to prevent feedback loop
        # Start muted to prevent processing audio during welcome message
        self.muted = True
        self.mute_lock = threading.Lock()

    def start(self):
        """Start the call session"""
        try:
            logger.info(f"Starting call session with {self.sip_call.caller_addr}")

            self.active = True

            # Start RTP receive thread first (starts muted to prevent feedback during welcome)
            self.rtp_thread = threading.Thread(target=self._rtp_receive_loop, daemon=True)
            self.rtp_thread.start()

            # Small delay to ensure RTP loop is running
            time.sleep(0.2)

            # Play immediate greeting first
            self._play_immediate_greeting()

            # Then play personalized welcome message (will handle mute/unmute)
            self._play_welcome_message()

            # Clear any accumulated audio buffer from acoustic echo and reset baseline
            with self.mute_lock:
                self.audio_buffer_8k = []
                self.recording = False
                self.last_audio_time = None
                # Reset adaptive threshold calibration to start fresh after welcome message
                self.baseline_rms_samples = []
                self.baseline_collected = False

            logger.info("Call session active, ready for user input. Adaptive threshold calibration will begin.")
            return True

        except Exception as e:
            logger.error(f"Error starting call session: {e}")
            self.stop()
            return False

    def _rtp_receive_loop(self):
        """Receive RTP packets, detect utterances, and run AI pipeline."""
        logger.info("RTP receive loop started")
        self.sip_call.rtp_socket.settimeout(0.1)
        packet_count = 0

        while self.active and self.sip_call.rtp_socket:
            try:
                data, addr = self.sip_call.rtp_socket.recvfrom(2048)

                if len(data) < 12:
                    continue  # Invalid RTP packet

                # Parse RTP header (12 bytes)
                header = struct.unpack('!BBHII', data[:12])
                payload = data[12:]
                
                # Extract payload type from header
                payload_type = header[1] & 0x7F  # Lower 7 bits

                packet_count += 1
                if packet_count % 100 == 1:  # Log every 100th packet
                    logger.debug(f"Received RTP packet {packet_count}, payload type: {payload_type}, payload size: {len(payload)} bytes")

                # μ-law (8-bit) -> 16-bit PCM @8kHz
                try:
                    pcm_8k = audioop.ulaw2lin(payload, 1)

                    # Check if we're muted (bot is speaking) - discard incoming audio to prevent feedback
                    with self.mute_lock:
                        is_muted = self.muted

                    if is_muted:
                        # Bot is speaking, discard incoming audio to prevent echo/feedback
                        # Still track RMS for debugging but don't record
                        rms = audioop.rms(pcm_8k, 2)
                        self.rms_samples.append(rms)
                        if packet_count % 200 == 1:
                            avg_rms = sum(self.rms_samples[-200:]) / min(len(self.rms_samples), 200)
                            logger.debug(f"Audio muted (bot speaking) - RMS: {rms}, Avg: {avg_rms:.1f}")
                        continue  # Skip processing this audio

                    # Voice activity detection
                    rms = audioop.rms(pcm_8k, 2)

                    # Track RMS statistics
                    self.rms_samples.append(rms)
                    if rms > self.max_rms:
                        self.max_rms = rms

                    # Adaptive threshold: collect baseline noise floor during first few seconds
                    if self.adaptive_threshold and not self.baseline_collected:
                        self.baseline_rms_samples.append(rms)
                        # After collecting baseline, calculate adaptive threshold
                        if len(self.baseline_rms_samples) >= int(self.baseline_collection_time * 50):  # 50 packets/sec
                            # Calculate noise floor statistics
                            sorted_baseline = sorted(self.baseline_rms_samples)
                            noise_floor = sorted_baseline[len(sorted_baseline) // 2]  # Median
                            
                            # Calculate 75th percentile (peak background noise)
                            percentile_75_idx = int(len(sorted_baseline) * 0.75)
                            peak_noise = sorted_baseline[percentile_75_idx]
                            
                            # For cellular/low-volume audio: set threshold between noise floor and peak
                            # This is more sensitive than 3x multiplier
                            # Use: noise_floor + (peak_noise - noise_floor) * 1.5
                            # With minimum of 40 and maximum of 300
                            adaptive_value = noise_floor + int((peak_noise - noise_floor) * 1.5)
                            self.voice_threshold = max(40, min(300, adaptive_value))
                            self.baseline_collected = True
                            logger.info(f"Adaptive threshold calibrated: noise_floor={noise_floor}, peak_noise={peak_noise}, new_threshold={self.voice_threshold}")

                    # Log RMS levels more frequently for debugging cellular issues
                    if packet_count % 50 == 1:  # Log every 50 packets instead of 200
                        avg_rms = sum(self.rms_samples[-200:]) / min(len(self.rms_samples), 200)
                        calibration_status = "CALIBRATING" if (self.adaptive_threshold and not self.baseline_collected) else "ACTIVE"
                        logger.info(f"Audio stats [{calibration_status}] - Current RMS: {rms}, Avg RMS: {avg_rms:.1f}, Max RMS: {self.max_rms}, Threshold: {self.voice_threshold}")
                        # Log last 10 RMS values for pattern analysis
                        recent_rms = self.rms_samples[-10:] if len(self.rms_samples) >= 10 else self.rms_samples
                        logger.info(f"Recent RMS values: {recent_rms}")

                    if rms > self.voice_threshold:
                        self.audio_buffer_8k.append(pcm_8k)
                        self.last_audio_time = time.time()
                        if not self.recording:
                            self.recording = True
                            logger.info(f"Started recording from caller (RMS: {rms}, threshold: {self.voice_threshold})")
                    elif self.recording:
                        # still buffer tail during trailing silence
                        self.audio_buffer_8k.append(pcm_8k)

                    # Check for end of utterance
                    if self.recording and self.last_audio_time:
                        if (time.time() - self.last_audio_time) >= self.silence_threshold and not self.processing:
                            # finalize current buffer and process in background
                            audio_chunks = self.audio_buffer_8k
                            self.audio_buffer_8k = []
                            self.recording = False
                            self.last_audio_time = None
                            self.processing = True
                            threading.Thread(target=self._process_utterance, args=(audio_chunks,), daemon=True).start()
                except Exception as e:
                    logger.error(f"Error handling incoming audio: {e}", exc_info=True)

            except socket.timeout:
                continue
            except OSError as e:
                # Socket closed (Bad file descriptor) - call ended
                if e.errno == 9:  # EBADF
                    logger.info("RTP socket closed, stopping receive loop")
                    break
                elif self.active:
                    logger.error(f"Error in RTP receive: {e}")
                    break
            except Exception as e:
                if self.active:
                    logger.error(f"Error in RTP receive: {e}")
                    break

        logger.info("RTP receive loop stopped")

    def _play_tts(self, wav_bytes, description="audio"):
        """Play TTS audio while muting incoming audio to prevent feedback"""
        if not wav_bytes:
            logger.warning(f"No audio to play for {description}")
            return

        try:
            # Mute incoming audio to prevent feedback loop
            with self.mute_lock:
                self.muted = True
            logger.debug(f"Muted incoming audio for {description} playback")

            # Play the audio
            self.pipeline.play_tts_over_rtp(self.sip_call, wav_bytes)

            # Add delay after playback to allow acoustic echo to settle
            # Longer delay for welcome message to ensure echo fully dissipates
            if "welcome" in description.lower():
                delay = 1.0  # 1 second for welcome message
            else:
                delay = 0.5  # 500ms for other audio

            logger.debug(f"Waiting {delay}s for acoustic echo to settle")
            time.sleep(delay)

        finally:
            # Clear any audio buffer that accumulated during playback (acoustic echo)
            with self.mute_lock:
                if self.audio_buffer_8k:
                    logger.debug(f"Clearing {len(self.audio_buffer_8k)} buffered audio chunks from feedback")
                    self.audio_buffer_8k = []
                    self.recording = False
                    self.last_audio_time = None
                # Unmute incoming audio
                self.muted = False
            logger.debug(f"Unmuted incoming audio after {description} playback")

    def _process_utterance(self, chunks_8k):
        try:
            logger.info(f"Silence detected, processing and transcribing audio ({len(chunks_8k)} chunks)...")

            if not chunks_8k:
                logger.warning("No audio chunks to process")
                self.processing = False
                return

            # Combine all 8kHz chunks
            combined_8k = b''.join(chunks_8k)
            duration_8k = len(combined_8k) / 2 / 8000  # 16-bit samples at 8kHz
            logger.info(f"Processing {duration_8k:.2f} seconds of audio ({len(combined_8k)} bytes @ 8kHz)")

            # Check if we have enough audio
            if duration_8k < 0.3:  # Less than 300ms
                logger.warning(f"Audio too short ({duration_8k:.2f}s), skipping transcription")
                self.processing = False
                return

            # Upsample from 8kHz to 16kHz for better Whisper accuracy
            logger.debug(f"Upsampling audio from 8kHz to 16kHz")
            combined_16k, _ = audioop.ratecv(combined_8k, 2, 1, 8000, 16000, None)

            # Apply audio normalization to improve quality
            # Find peak amplitude
            max_amp = audioop.max(combined_16k, 2)
            avg_amp = audioop.rms(combined_16k, 2)
            logger.info(f"Audio levels - Peak: {max_amp}, RMS: {avg_amp}")

            # Check if audio has sufficient energy to be real speech
            # Whisper often hallucinates "Thank you" or similar on silence/noise
            if avg_amp < 50:  # Very low RMS indicates silence or noise, not speech
                logger.warning(f"Audio RMS too low ({avg_amp}), likely silence/noise. Skipping transcription to avoid Whisper hallucination.")
                self.processing = False
                return

            if max_amp > 0:
                # Normalize to 90% of maximum to avoid clipping while maximizing signal
                target_amp = int(32767 * 0.9)
                factor = target_amp / max_amp
                combined_16k = audioop.mul(combined_16k, 2, factor)
                logger.info(f"Normalized audio by factor {factor:.2f}")

            # Write enhanced 16kHz PCM to WAV
            with tempfile_named(suffix='.wav') as wav_path:
                with wave.open(wav_path, 'wb') as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(16000)  # 16kHz for better Whisper performance
                    w.writeframes(combined_16k)

                logger.info("Sending audio to Whisper for transcription...")
                # Transcribe
                transcript = self.pipeline.transcribe_wav_file(wav_path)

            if not transcript:
                logger.info("Transcript empty; skipping LLM/TTS")
                self.processing = False
                return

            # Filter out common Whisper hallucinations (phrases it generates from silence/noise)
            hallucinations = [
                "thank you", "thank you.", "thanks", "thanks.",
                "bye", "bye.", "goodbye", "goodbye.",
                "thank you for watching", "thank you for watching.",
                "you", "you."
            ]
            if transcript.strip().lower() in hallucinations:
                logger.warning(f"Detected Whisper hallucination: '{transcript}' - skipping (likely silence/acoustic echo)")
                self.processing = False
                return

            logger.info(f"Transcribed: {transcript}")

            # Get or create session for this user
            session_id = self.pipeline.get_or_create_session(self.caller_name, self.user_session)

            # Save user message SYNCHRONOUSLY first so it's in the context for immediate follow-ups
            self.pipeline.save_message(self.caller_name, self.user_session, 'voice', 'user', transcript, session_id)

            # Track new topics (before getting response)
            self.pipeline.track_new_topic(transcript, self.caller_name, session_id)

            # Cue: "Let me think about that..." before LLM
            logger.info("Playing thinking cue...")
            thinking_cue = self.pipeline.tts_wav("Let me think about that...")
            self._play_tts(thinking_cue, "thinking cue")

            # LLM with session context (now with user message in DB)
            response_text = self.pipeline.ollama_generate(transcript, user_name=self.caller_name, session_id=session_id)
            logger.info(f"Ollama response: {response_text}")

            # Save assistant response asynchronously (not needed for immediate context)
            self.pipeline.save_message(self.caller_name, self.user_session, 'voice', 'assistant', response_text, session_id=session_id)

            # Extract and save memories in background (non-blocking)
            threading.Thread(
                target=self.pipeline.extract_and_save_memory,
                args=(transcript, response_text, self.caller_name, session_id),
                daemon=True
            ).start()

            # Extract and manage schedule in background (non-blocking)
            threading.Thread(
                target=self.pipeline.extract_and_manage_schedule,
                args=(transcript, response_text, self.caller_name),
                daemon=True
            ).start()
            
            # Extract and track entities in background (non-blocking)
            threading.Thread(
                target=self.pipeline.extract_and_save_entities,
                args=(transcript, response_text, self.caller_name, session_id),
                daemon=True
            ).start()

            # Cue 3: "Here's my response..." before final response
            logger.info("Playing response cue...")
            response_cue = self.pipeline.tts_wav("Here's my response...")
            self._play_tts(response_cue, "response cue")

            # TTS
            wav_bytes = self.pipeline.tts_wav(response_text)

            # Play over RTP
            self._play_tts(wav_bytes, "response")

        except Exception as e:
            logger.error(f"Error processing utterance: {e}", exc_info=True)
        finally:
            self.processing = False

    def stop(self):
        """Stop the call session"""
        self.active = False

        if self.sip_call:
            self.sip_call.close()

        logger.info("Call session stopped")

    def _extract_caller_name(self):
        try:
            from_header = self.sip_call.invite_msg
            # Prefer From header
            m = re.search(r"^From:\s*(.*)$", self.sip_call.invite_msg, re.MULTILINE)
            if m:
                from_val = m.group(1)
                # Try display name "Name" <sip:user@host>
                mname = re.search(r'"([^"]+)"', from_val)
                if mname:
                    return mname.group(1)
                # Try user part sip:user@
                muser = re.search(r'sip:([^@;>]+)', from_val)
                if muser:
                    return muser.group(1)
            return "SIP-Caller"
        except Exception:
            return "SIP-Caller"

    def _play_immediate_greeting(self):
        """Play an immediate greeting while the personalized welcome is generated"""
        try:
            greeting_text = "Hello! Just a moment while I get ready for you"
            logger.info(f"Playing immediate greeting: {greeting_text}")
            
            wav_bytes = self.pipeline.tts_wav(greeting_text)
            if wav_bytes:
                self._play_tts(wav_bytes, "immediate greeting")
                logger.info("Immediate greeting played successfully")
            else:
                logger.warning("Failed to generate immediate greeting TTS")
        except Exception as e:
            logger.error(f"Error playing immediate greeting: {e}")
            # Don't fail the call if greeting fails
            pass

    def _play_welcome_message(self):
        """Generate and play a personalized welcome message using persona and Ollama"""
        try:
            logger.info("Generating welcome message...")

            # Generate welcome message using persona and Ollama
            welcome_text = self._generate_welcome_message()

            if welcome_text:
                logger.info(f"Playing welcome message: {welcome_text}")

                # Convert to speech and play over RTP
                wav_bytes = self.pipeline.tts_wav(welcome_text)
                if wav_bytes:
                    self._play_tts(wav_bytes, "welcome message")
                    logger.info("Welcome message played successfully")
                else:
                    logger.error("Failed to generate TTS for welcome message")
            else:
                logger.warning("No welcome message generated, using default")
                # Fallback to a simple default message
                default_welcome = "Hello! I'm your AI assistant. How can I help you today?"
                wav_bytes = self.pipeline.tts_wav(default_welcome)
                if wav_bytes:
                    self._play_tts(wav_bytes, "default welcome message")

        except Exception as e:
            logger.error(f"Error playing welcome message: {e}")
            # Don't fail the call if welcome message fails
            pass

    def _generate_welcome_message(self):
        """Generate a personalized welcome message using persona and Ollama"""
        try:
            # Get bot persona from config
            persona = self.pipeline.get_config('bot_persona', '')
            
            # Build a prompt specifically for welcome message generation
            welcome_prompt = self._build_welcome_prompt(persona)
            
            # Get Ollama configuration
            ollama_url = self.pipeline.get_config('ollama_url', config.DEFAULT_OLLAMA_URL)
            ollama_model = self.pipeline.get_config('ollama_model', config.DEFAULT_OLLAMA_MODEL)
            
            logger.info(f"Generating welcome message using Ollama: {ollama_url} with model: {ollama_model}")
            
            # Call Ollama to generate welcome message
            response = requests.post(
                f"{ollama_url}/api/generate",
                json={"model": ollama_model, "prompt": welcome_prompt, "stream": False},
                timeout=300,  # 5 minutes for welcome message generation
            )
            
            if response.status_code == 200:
                welcome_text = response.json().get('response', '').strip()
                if welcome_text:
                    # Clean up the response (remove any assistant prefix if present)
                    welcome_text = welcome_text.replace('Assistant:', '').strip()
                    return welcome_text
                else:
                    logger.warning("Ollama returned empty response for welcome message")
                    return None
            else:
                logger.error(f"Ollama error generating welcome message: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating welcome message: {e}")
            return None

    def _build_welcome_prompt(self, persona):
        """Build a prompt specifically for generating welcome messages"""
        prompt = "Generate a brief, friendly welcome message for when someone calls you. "
        prompt += "Keep it conversational and welcoming (1-2 sentences). "
        prompt += "Never use emojis. "
        
        if persona and persona.strip():
            prompt += f"Use this persona: {persona.strip()}\n\n"
        else:
            prompt += "\n\n"
            
        prompt += "Generate a welcome message for an incoming phone call:"
        
        return prompt


class SIPMumbleBridge:
    """Main SIP-Mumble bridge application"""

    def __init__(self):
        self.sip_server = SimpleSIPServer(port=config.SIP_PORT)
        self.active_calls = {}
        # Create shared pipeline for session management
        self.pipeline = AIPipeline()

    def _session_cleanup_thread(self):
        """Background thread for session cleanup"""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                logger.info("Running periodic session cleanup...")
                self.pipeline.close_idle_sessions()
            except Exception as e:
                logger.error(f"Error in session cleanup thread: {e}")

    def start(self):
        """Start the bridge"""
        logger.info("=" * 60)
        logger.info("SIP-Mumble Bridge Starting")
        logger.info("=" * 60)
        logger.info(f"SIP Port: {config.SIP_PORT}")
        logger.info(f"Mumble Server: {config.MUMBLE_HOST}:{config.MUMBLE_PORT}")
        logger.info("=" * 60)

        # Initialize memory manager now that database pool is ready
        try:
            self.memory_manager = MemoryManager(
                chromadb_url=os.getenv('CHROMADB_URL', 'http://chromadb:8000'),
                redis_url=os.getenv('REDIS_URL', 'redis://redis:6379'),
                db_pool=self.pipeline.db_pool,
                ollama_url=self.pipeline.ollama_url
            )
            logger.info("MemoryManager initialized successfully in SIP bridge")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager in SIP bridge: {e}")
            self.memory_manager = None

        # Start session cleanup thread
        cleanup_thread = threading.Thread(target=self._session_cleanup_thread, daemon=True)
        cleanup_thread.start()
        logger.info("Session cleanup thread started")

        # Set call handler
        self.sip_server.set_call_handler(self._handle_incoming_call)

        # Start SIP server
        if not self.sip_server.start():
            logger.error("Failed to start SIP server")
            return False

        logger.info("SIP-Mumble Bridge is ready and waiting for calls")
        return True

    def _handle_incoming_call(self, sip_call):
        """Handle incoming call after ACK is received"""
        try:
            logger.info(f"Handling call from {sip_call.caller_addr}")

            # Create call session with shared pipeline
            session = CallSession(sip_call, pipeline=self.pipeline)

            if session.start():
                self.active_calls[sip_call.call_id] = session
                logger.info(f"Call session created for {sip_call.caller_addr}")
            else:
                logger.error(f"Failed to start session for {sip_call.caller_addr}")

        except Exception as e:
            logger.error(f"Error handling call: {e}")

    def run(self):
        """Run the bridge"""
        if not self.start():
            return

        try:
            # Keep running
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.shutdown()

    def shutdown(self):
        """Shutdown the bridge"""
        # Stop all active calls
        for addr, session in list(self.active_calls.items()):
            session.stop()

        self.active_calls.clear()

        # Stop SIP server
        self.sip_server.stop()

        logger.info("Bridge shutdown complete")


def main():
    """Main entry point"""
    bridge = SIPMumbleBridge()
    bridge.run()


if __name__ == "__main__":
    main()
