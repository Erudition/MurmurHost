#!/usr/bin/env python3
"""
Email Summary Service for Mumble AI
Sends daily conversation summaries via email at scheduled times.
Receives and replies to emails using AI.
"""

import os
import sys
import time
import logging
import smtplib
import psycopg2
import requests
import imaplib
import email
from email import policy
from email.parser import BytesParser
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, parseaddr
import pytz
from typing import List, Dict, Optional, Tuple
import re
import threading
from requests.exceptions import Timeout, RequestException
from flask import Flask, jsonify, request as flask_request
import base64
import json
import shutil
import tempfile
from pathlib import Path
from PIL import Image
import PyPDF2
from docx import Document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Environment variables
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'mumble_ai')
DB_USER = os.getenv('DB_USER', 'mumbleai')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'mumbleai123')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://host.docker.internal:11434')

# Check interval (how often to check if we should send email)
CHECK_INTERVAL_SECONDS = int(os.getenv('CHECK_INTERVAL_SECONDS', '60'))  # Check every minute


class EmailSummaryService:
    """Service that sends daily conversation summaries via email"""

    def __init__(self):
        self.db_conn = None
        self.last_check_date = None
        self.connect_db()

    def call_ollama_with_retry(self, prompt: str, max_retries: int = 3, timeout: int = 300) -> Optional[str]:
        """
        Call Ollama API with retry logic.

        Args:
            prompt: The prompt to send to Ollama
            max_retries: Maximum number of retry attempts (default: 3)
            timeout: Timeout in seconds for each attempt (default: 300)
            
        Returns:
            Generated text response or None if all retries failed
        """
        # Get Ollama model from database
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'llama3.2:latest'
        finally:
            conn.close()

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Ollama API call attempt {attempt}/{max_retries}")
                
                response = requests.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        'model': ollama_model,
                        'prompt': prompt,
                        'stream': False,
                        'options': {
                            'temperature': 0.7,
                            'num_predict': 1000
                        }
                    },
                    timeout=timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    generated_text = result.get('response', '').strip()

                    # Log warning if response is empty
                    if not generated_text:
                        logger.warning(f"Empty LLM response received on attempt {attempt}. Model: {ollama_model}, Prompt preview: '{prompt[:150]}...'")
                        if attempt < max_retries:
                            continue  # Retry
                        return None

                    logger.info(f"Ollama API call succeeded on attempt {attempt}")
                    return generated_text
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"Ollama request failed on attempt {attempt}: {last_error}")

            except Timeout as e:
                last_error = f"Timeout after {timeout}s"
                logger.warning(f"Ollama request timed out on attempt {attempt}/{max_retries}: {e}")
            except RequestException as e:
                last_error = f"Request error: {str(e)}"
                logger.warning(f"Ollama request failed on attempt {attempt}/{max_retries}: {e}")
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"Unexpected error on Ollama attempt {attempt}/{max_retries}: {e}")

            # Wait before retrying (exponential backoff)
            if attempt < max_retries:
                wait_time = 2 ** attempt  # 2, 4, 8 seconds
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        # All retries failed
        logger.error(f"All {max_retries} Ollama API attempts failed. Last error: {last_error}")
        return None

    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            logger.info("Connected to database successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def get_db_connection(self):
        """Get database connection, reconnect if necessary"""
        try:
            # Test connection
            with self.db_conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError):
            logger.info("Database connection lost, reconnecting...")
            self.connect_db()
        return self.db_conn

    def get_email_settings(self) -> Optional[Dict]:
        """Retrieve email settings from database"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT smtp_host, smtp_port, smtp_username, smtp_password,
                           smtp_use_tls, smtp_use_ssl, from_email, recipient_email,
                           daily_summary_enabled, summary_time, timezone, last_sent,
                           imap_enabled, imap_host, imap_port, imap_username, imap_password,
                           imap_use_ssl, imap_mailbox, auto_reply_enabled, reply_signature,
                           check_interval_seconds, last_checked
                    FROM email_settings
                    WHERE id = 1
                """)
                row = cursor.fetchone()

                if not row:
                    logger.warning("No email settings found in database")
                    return None

                return {
                    'smtp_host': row[0],
                    'smtp_port': row[1],
                    'smtp_username': row[2],
                    'smtp_password': row[3],
                    'smtp_use_tls': row[4],
                    'smtp_use_ssl': row[5],
                    'from_email': row[6],
                    'recipient_email': row[7],
                    'daily_summary_enabled': row[8],
                    'summary_time': row[9],
                    'timezone': row[10],
                    'last_sent': row[11],
                    'imap_enabled': row[12],
                    'imap_host': row[13],
                    'imap_port': row[14],
                    'imap_username': row[15],
                    'imap_password': row[16],
                    'imap_use_ssl': row[17],
                    'imap_mailbox': row[18] or 'INBOX',
                    'auto_reply_enabled': row[19],
                    'reply_signature': row[20] or '',
                    'check_interval_seconds': row[21] or 300,
                    'last_checked': row[22]
                }
        except Exception as e:
            logger.error(f"Error getting email settings: {e}")
            return None

    def update_last_sent(self):
        """Update the last_sent timestamp in database"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE email_settings
                    SET last_sent = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                """, (datetime.now(),))
            conn.commit()
            logger.info("Updated last_sent timestamp")
        except Exception as e:
            logger.error(f"Error updating last_sent: {e}")
            conn.rollback()

    def should_send_summary(self, settings: Dict) -> bool:
        """Determine if we should send a summary email now"""
        if not settings['daily_summary_enabled']:
            return False

        if not settings['recipient_email']:
            logger.warning("Daily summaries enabled but no recipient email configured")
            return False

        # Get current time in configured timezone
        tz = pytz.timezone(settings['timezone'])
        now = datetime.now(tz)

        # Get the target time today
        target_time = settings['summary_time']
        target_datetime = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0
        )

        # Check if we're within the window (current minute matches target minute)
        time_matches = (now.hour == target_time.hour and now.minute == target_time.minute)

        if not time_matches:
            return False

        # Check if we already sent today
        if settings['last_sent']:
            last_sent_date = settings['last_sent'].date()
            today_date = now.date()

            if last_sent_date >= today_date:
                logger.debug("Already sent summary today")
                return False

        logger.info(f"Time to send daily summary! Current time: {now.strftime('%Y-%m-%d %H:%M %Z')}")
        return True

    def get_conversation_history(self, hours: int = 24) -> List[Dict]:
        """Get conversation history from the last N hours"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT user_name, role, message, timestamp, message_type
                    FROM conversation_history
                    WHERE timestamp >= NOW() - INTERVAL '%s hours'
                    ORDER BY timestamp ASC
                """, (hours,))

                rows = cursor.fetchall()

                conversations = []
                for row in rows:
                    conversations.append({
                        'user_name': row[0],
                        'role': row[1],
                        'message': row[2],
                        'timestamp': row[3],
                        'message_type': row[4]
                    })

                logger.info(f"Retrieved {len(conversations)} messages from last {hours} hours")
                return conversations
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []

    def get_schedule_events(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming schedule events"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT user_name, title, event_date, event_time, description, importance, created_at
                    FROM schedule_events
                    WHERE active = TRUE
                      AND event_date >= CURRENT_DATE
                      AND event_date <= CURRENT_DATE + INTERVAL '%s days'
                    ORDER BY event_date, event_time
                """, (days_ahead,))

                rows = cursor.fetchall()

                events = []
                for row in rows:
                    events.append({
                        'user_name': row[0],
                        'title': row[1],
                        'event_date': row[2],
                        'event_time': row[3],
                        'description': row[4],
                        'importance': row[5],
                        'created_at': row[6]
                    })

                logger.info(f"Retrieved {len(events)} upcoming events")
                return events
        except Exception as e:
            logger.error(f"Error getting schedule events: {e}")
            return []

    def get_schedule_changes(self, hours: int = 24) -> List[Dict]:
        """Get schedule events created or modified in the last N hours"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT user_name, title, event_date, event_time, description, importance, created_at
                    FROM schedule_events
                    WHERE active = TRUE
                      AND created_at >= NOW() - INTERVAL '%s hours'
                    ORDER BY created_at DESC
                """, (hours,))

                rows = cursor.fetchall()

                changes = []
                for row in rows:
                    changes.append({
                        'user_name': row[0],
                        'title': row[1],
                        'event_date': row[2],
                        'event_time': row[3],
                        'description': row[4],
                        'importance': row[5],
                        'created_at': row[6]
                    })

                logger.info(f"Retrieved {len(changes)} schedule changes from last {hours} hours")
                return changes
        except Exception as e:
            logger.error(f"Error getting schedule changes: {e}")
            return []

    def get_recent_memories(self, hours: int = 24) -> List[Dict]:
        """Get persistent memories created in the last N hours"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT user_name, category, content, importance, extracted_at, event_date, event_time
                    FROM persistent_memories
                    WHERE active = TRUE
                      AND extracted_at >= NOW() - INTERVAL '%s hours'
                    ORDER BY importance DESC, extracted_at DESC
                """, (hours,))

                rows = cursor.fetchall()

                memories = []
                for row in rows:
                    memories.append({
                        'user_name': row[0],
                        'category': row[1],
                        'content': row[2],
                        'importance': row[3],
                        'extracted_at': row[4],
                        'event_date': row[5],
                        'event_time': row[6]
                    })

                logger.info(f"Retrieved {len(memories)} memories from last {hours} hours")
                return memories
        except Exception as e:
            logger.error(f"Error getting recent memories: {e}")
            return []

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
        all_events = self.get_schedule_events(days_ahead=365)  # Get all events for user
        user_events = [e for e in all_events if e['user_name'] == user_name]
        if not user_events:
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
                    tier1_future = executor.submit(self._tier1_semantic_search, user_name, search_query, user_events, timeout)
                    results = tier1_future.result(timeout=timeout)
                    tier_used = "tier1"
                    logger.info(f"Tier 1 (semantic) found {len(results)} results")
                except (FutureTimeoutError, Exception) as e:
                    logger.warning(f"Tier 1 (semantic) failed: {e}")
                    
                    # Fallback to Tier 2 (Fuzzy matching)
                    try:
                        results = self._tier2_fuzzy_search(search_query, user_events)
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
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
                row = cursor.fetchone()
                ollama_url = row[0] if row else 'http://host.docker.internal:11434'
                
                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'llama3.2:latest'
            
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
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
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

    def is_event_name_query(self, message: str) -> bool:
        """Detect if user is asking about a specific event by name"""
        event_name_patterns = [
            'when is my', 'when\'s my', 'what time is my', 'find my',
            'where is my', 'tell me about my', 'show me my'
        ]
        message_lower = message.lower()
        return any(pattern in message_lower for pattern in event_name_patterns)

    def generate_summary_with_ollama(self, conversations: List[Dict], schedule_events: List[Dict],
                                     schedule_changes: List[Dict], memories: List[Dict]) -> str:
        """Generate a conversation summary using Ollama"""
        if not conversations and not schedule_changes and not memories:
            return "No activity in the last 24 hours."

        # Format conversations for Ollama
        conversation_text = ""
        if conversations:
            for conv in conversations:
                timestamp_str = conv['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                role = "User" if conv['role'] == 'user' else "Assistant"
                conversation_text += f"[{timestamp_str}] {role} ({conv['user_name']}): {conv['message']}\n\n"
        else:
            conversation_text = "No conversations in the last 24 hours.\n\n"

        # Format schedule changes
        schedule_text = ""
        if schedule_changes:
            schedule_text = "**Schedule Changes Made:**\n"
            for event in schedule_changes:
                date_str = event['event_date'].strftime('%A, %B %d, %Y')
                time_str = event['event_time'].strftime('%I:%M %p') if event['event_time'] else 'All day'
                schedule_text += f"- {event['title']} - {date_str} at {time_str} (Added by {event['user_name']})\n"
            schedule_text += "\n"

        # Format upcoming events
        upcoming_text = ""
        if schedule_events:
            upcoming_text = "**Upcoming Events (Next 7 Days):**\n"
            for event in schedule_events:
                date_str = event['event_date'].strftime('%A, %B %d, %Y')
                time_str = event['event_time'].strftime('%I:%M %p') if event['event_time'] else 'All day'
                upcoming_text += f"- {event['title']} - {date_str} at {time_str} ({event['user_name']})\n"
            upcoming_text += "\n"

        # Format memories
        memory_text = ""
        if memories:
            memory_text = "**New Memories Extracted:**\n"
            category_icons = {'schedule': '📅', 'fact': '💡', 'task': '✓', 'preference': '❤️', 'reminder': '⏰', 'other': '📌'}
            for mem in memories:
                icon = category_icons.get(mem['category'], '📌')
                memory_text += f"- {icon} [{mem['category'].upper()}] {mem['content']} ({mem['user_name']})\n"
            memory_text += "\n"

        # Create summary prompt
        summary_prompt = f"""You are summarizing a day's worth of activity from a Mumble AI voice assistant. Create a well-organized, friendly summary.

{schedule_text}{upcoming_text}{memory_text}

Conversations from the last 24 hours:
{conversation_text}

Create a comprehensive summary with these sections:
1. **Overview**: Brief summary of overall activity
2. **Highlights**: Most important conversations or events
3. **New Information**: Any new schedules, tasks, facts, or preferences learned

Keep it concise and friendly. Use markdown formatting:"""

        try:
            logger.info("Generating summary with Ollama...")
            
            # Use retry logic for Ollama call
            # Respect advanced settings: CoT and parallel multi-sample (n=3) if enabled
            conn = self.get_db_connection()
            use_cot = False
            enable_parallel = False
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT value FROM bot_config WHERE key = 'use_chain_of_thought'")
                    row = cursor.fetchone()
                    use_cot = (row and str(row[0]).lower() == 'true')
                    cursor.execute("SELECT value FROM bot_config WHERE key = 'enable_parallel_processing'")
                    row = cursor.fetchone()
                    enable_parallel = (row and str(row[0]).lower() == 'true')
            finally:
                conn.close()

            cot_instruction = """

IMPORTANT: Think step by step privately. Do NOT reveal your chain-of-thought. Provide ONLY the final concise summary.
"""
            base_prompt = summary_prompt + (cot_instruction if use_cot else "")

            if use_cot:
                def _once(p):
                    return self.call_ollama_with_retry(p, max_retries=3, timeout=300)
                samples = []
                if enable_parallel:
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    with ThreadPoolExecutor(max_workers=3) as ex:
                        futs = [ex.submit(_once, base_prompt) for _ in range(3)]
                        for f in as_completed(futs):
                            try:
                                res = f.result()
                                if res:
                                    samples.append(res)
                            except Exception as e:
                                logger.error(f"Parallel CoT summary error: {e}")
                    if not samples:
                        samples = [self.call_ollama_with_retry(base_prompt, max_retries=3, timeout=300)]
                else:
                    for _ in range(3):
                        s = self.call_ollama_with_retry(base_prompt, max_retries=3, timeout=300)
                        if s:
                            samples.append(s)
                # Simple selection: choose the longest non-empty (more comprehensive)
                summary = max(samples, key=lambda s: len(s)) if samples else None
            else:
                summary = self.call_ollama_with_retry(base_prompt, max_retries=3, timeout=300)
            
            if summary:
                logger.info("Summary generated successfully")
                return summary
            else:
                logger.error("Failed to generate summary after all retries")
                return self._generate_fallback_summary(conversations)

        except Exception as e:
            logger.error(f"Error generating summary with Ollama: {e}")
            return self._generate_fallback_summary(conversations)

    def _generate_fallback_summary(self, conversations: List[Dict]) -> str:
        """Generate a basic summary without Ollama"""
        total_messages = len(conversations)
        users = set(conv['user_name'] for conv in conversations)
        user_count = len(users)

        summary = f"""# Daily Conversation Summary

## Overview
- **Total Messages**: {total_messages}
- **Unique Users**: {user_count}
- **Users**: {', '.join(users)}

## Recent Conversations
"""

        # Show last 10 exchanges
        recent = conversations[-20:] if len(conversations) > 20 else conversations
        for conv in recent:
            timestamp_str = conv['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            role = "👤 User" if conv['role'] == 'user' else "🤖 Assistant"
            summary += f"\n**[{timestamp_str}] {role} ({conv['user_name']})**:\n{conv['message']}\n"

        return summary

    def format_html_email(self, summary: str, date_range: str, schedule_events: List[Dict],
                          schedule_changes: List[Dict], memories: List[Dict]) -> str:
        """Convert markdown summary to HTML email"""
        import re

        # Convert markdown to HTML
        html = summary
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'^# (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^\- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = html.replace('\n\n', '</p><p>')
        html = f'<p>{html}</p>'

        # Build schedule events HTML
        schedule_html = ""
        if schedule_events:
            schedule_html = '<div class="section-card schedule-section">'
            schedule_html += '<h2 class="section-title">📅 Upcoming Events (Next 7 Days)</h2>'
            schedule_html += '<div class="events-grid">'

            for event in schedule_events:
                date_str = event['event_date'].strftime('%A, %b %d')
                time_str = event['event_time'].strftime('%I:%M %p') if event['event_time'] else 'All day'
                importance = event['importance']

                # Color code by importance
                if importance >= 8:
                    badge_class = "badge-critical"
                elif importance >= 6:
                    badge_class = "badge-high"
                else:
                    badge_class = "badge-normal"

                schedule_html += f'''
                <div class="event-card">
                    <div class="event-header">
                        <span class="event-title">{event['title']}</span>
                        <span class="importance-badge {badge_class}">{importance}</span>
                    </div>
                    <div class="event-details">
                        <div class="event-date">📆 {date_str}</div>
                        <div class="event-time">🕐 {time_str}</div>
                        <div class="event-user">👤 {event['user_name']}</div>
                    </div>
                </div>
                '''

            schedule_html += '</div></div>'

        # Build schedule changes HTML
        changes_html = ""
        if schedule_changes:
            changes_html = '<div class="section-card changes-section">'
            changes_html += '<h2 class="section-title">✨ Schedule Changes (Last 24 Hours)</h2>'
            changes_html += '<ul class="changes-list">'

            for change in schedule_changes:
                date_str = change['event_date'].strftime('%a, %b %d')
                time_str = change['event_time'].strftime('%I:%M %p') if change['event_time'] else 'All day'
                changes_html += f'''
                <li class="change-item">
                    <strong>{change['title']}</strong> - {date_str} at {time_str}
                    <span class="change-meta">Added by {change['user_name']}</span>
                </li>
                '''

            changes_html += '</ul></div>'

        # Build memories HTML
        memories_html = ""
        if memories:
            memories_html = '<div class="section-card memories-section">'
            memories_html += '<h2 class="section-title">🧠 New Memories (Last 24 Hours)</h2>'
            memories_html += '<div class="memories-grid">'

            category_icons = {
                'schedule': '📅',
                'fact': '💡',
                'task': '✓',
                'preference': '❤️',
                'reminder': '⏰',
                'other': '📌'
            }
            category_colors = {
                'schedule': '#3498db',
                'fact': '#2ecc71',
                'task': '#e74c3c',
                'preference': '#e91e63',
                'reminder': '#f39c12',
                'other': '#95a5a6'
            }

            for mem in memories:
                icon = category_icons.get(mem['category'], '📌')
                color = category_colors.get(mem['category'], '#95a5a6')

                memories_html += f'''
                <div class="memory-card" style="border-left-color: {color}">
                    <div class="memory-header">
                        <span class="memory-icon">{icon}</span>
                        <span class="memory-category">{mem['category'].upper()}</span>
                        <span class="memory-importance">{mem['importance']}/10</span>
                    </div>
                    <div class="memory-content">{mem['content']}</div>
                    <div class="memory-meta">👤 {mem['user_name']}</div>
                </div>
                '''

            memories_html += '</div></div>'

        # Complete HTML email
        html_email = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .email-container {{
            max-width: 800px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.95;
            font-size: 16px;
        }}
        .content {{
            padding: 30px;
        }}
        .section-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            border: 1px solid #e9ecef;
        }}
        .section-title {{
            margin: 0 0 20px 0;
            color: #2c3e50;
            font-size: 20px;
            font-weight: 600;
        }}
        .events-grid {{
            display: grid;
            gap: 15px;
        }}
        .event-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            border-left: 4px solid #3498db;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .event-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .event-title {{
            font-weight: 600;
            color: #2c3e50;
            font-size: 16px;
        }}
        .importance-badge {{
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            color: white;
        }}
        .badge-critical {{ background: #e74c3c; }}
        .badge-high {{ background: #f39c12; }}
        .badge-normal {{ background: #3498db; }}
        .event-details {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            font-size: 14px;
            color: #7f8c8d;
        }}
        .changes-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .change-item {{
            background: white;
            padding: 12px 15px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 3px solid #2ecc71;
        }}
        .change-meta {{
            display: block;
            font-size: 13px;
            color: #7f8c8d;
            margin-top: 4px;
        }}
        .memories-grid {{
            display: grid;
            gap: 12px;
        }}
        .memory-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            border-left: 4px solid #95a5a6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .memory-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}
        .memory-icon {{
            font-size: 18px;
        }}
        .memory-category {{
            font-size: 11px;
            font-weight: 600;
            color: #7f8c8d;
            background: #ecf0f1;
            padding: 2px 8px;
            border-radius: 10px;
        }}
        .memory-importance {{
            margin-left: auto;
            font-size: 12px;
            color: #95a5a6;
            font-weight: 600;
        }}
        .memory-content {{
            color: #2c3e50;
            margin: 8px 0;
            line-height: 1.5;
        }}
        .memory-meta {{
            font-size: 12px;
            color: #7f8c8d;
        }}
        .summary-section {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .summary-section h2 {{
            color: #2c3e50;
            margin-top: 0;
        }}
        .summary-section h3 {{
            color: #34495e;
            margin-top: 20px;
        }}
        .summary-section p {{
            color: #555;
            margin: 10px 0;
        }}
        .summary-section li {{
            margin: 5px 0;
            color: #555;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 25px 30px;
            text-align: center;
            border-top: 1px solid #e9ecef;
            color: #7f8c8d;
            font-size: 14px;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }}
        @media only screen and (max-width: 600px) {{
            .email-container {{
                border-radius: 0;
            }}
            .content {{
                padding: 20px;
            }}
            .event-details {{
                flex-direction: column;
                gap: 5px;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>🤖 Mumble AI Daily Summary</h1>
            <p>{date_range}</p>
        </div>

        <div class="content">
            {schedule_html}
            {changes_html}
            {memories_html}

            <div class="summary-section">
                {html}
            </div>
        </div>

        <div class="footer">
            <p><strong>This is your automated daily summary from Mumble AI</strong></p>
            <p>Manage your settings at the <a href="http://localhost:5002">Web Control Panel</a></p>
        </div>
    </div>
</body>
</html>
'''
        return html_email

    def send_email(self, settings: Dict, subject: str, html_content: str, plain_content: str) -> bool:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = settings['from_email']
            msg['To'] = settings['recipient_email']
            msg['Date'] = formatdate(localtime=True)

            # Attach plain text and HTML versions
            part1 = MIMEText(plain_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            # Connect to SMTP server
            logger.info(f"Connecting to SMTP server {settings['smtp_host']}:{settings['smtp_port']}")

            if settings['smtp_use_ssl']:
                smtp = smtplib.SMTP_SSL(settings['smtp_host'], settings['smtp_port'], timeout=30)
            else:
                smtp = smtplib.SMTP(settings['smtp_host'], settings['smtp_port'], timeout=30)
                if settings['smtp_use_tls']:
                    smtp.starttls()

            # Login if credentials provided
            if settings['smtp_username'] and settings['smtp_password']:
                logger.info(f"Logging in as {settings['smtp_username']}")
                smtp.login(settings['smtp_username'], settings['smtp_password'])

            # Send email
            smtp.send_message(msg)
            smtp.quit()

            logger.info(f"Email sent successfully to {settings['recipient_email']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_daily_summary(self, settings: Dict):
        """Generate and send daily summary email"""
        logger.info("Starting daily summary generation...")

        # Get all data
        conversations = self.get_conversation_history(hours=24)
        schedule_events = self.get_schedule_events(days_ahead=7)
        schedule_changes = self.get_schedule_changes(hours=24)
        memories = self.get_recent_memories(hours=24)

        # Format date range
        now = datetime.now(pytz.timezone(settings['timezone']))
        yesterday = now - timedelta(days=1)
        date_range = f"{yesterday.strftime('%B %d, %Y')} - {now.strftime('%B %d, %Y')}"
        subject = f"Mumble AI Daily Summary - {now.strftime('%B %d, %Y')}"

        # Generate summary with all context
        summary = self.generate_summary_with_ollama(conversations, schedule_events, schedule_changes, memories)

        # Check if summary generation failed (using fallback)
        ollama_failed = summary.startswith("# Daily Conversation Summary")  # Fallback pattern

        # Create email content
        html_content = self.format_html_email(summary, date_range, schedule_events, schedule_changes, memories)
        plain_content = f"Mumble AI Daily Summary\n{date_range}\n\n{summary}"

        # If Ollama failed, log the failure and don't send email
        if ollama_failed and (conversations or schedule_changes or memories):
            logger.error("Ollama failed after all retries - not sending summary")
            self.log_email(
                direction='sent',
                email_type='summary',
                from_email=settings['from_email'],
                to_email=settings['recipient_email'],
                subject=subject,
                body=plain_content,
                status='error',
                error_message='Ollama API failed after 3 retry attempts - summary generation timed out. Click retry to attempt again.'
            )
            return

        # Send email
        success = self.send_email(settings, subject, html_content, plain_content)

        if success:
            # Update last_sent timestamp
            self.update_last_sent()
            logger.info("Daily summary completed successfully")

            # Log successful send
            self.log_email(
                direction='sent',
                email_type='summary',
                from_email=settings['from_email'],
                to_email=settings['recipient_email'],
                subject=subject,
                body=plain_content,
                status='success'
            )
        else:
            logger.error("Failed to send daily summary")

            # Log failed send
            self.log_email(
                direction='sent',
                email_type='summary',
                from_email=settings['from_email'],
                to_email=settings['recipient_email'],
                subject=subject,
                body=plain_content,
                status='error',
                error_message='Failed to send email via SMTP'
            )

    def send_test_email(self, settings: Dict) -> bool:
        """Send a test email"""
        logger.info("Sending test email...")

        # Get recent data for the test
        conversations = self.get_conversation_history(hours=24)
        schedule_events = self.get_schedule_events(days_ahead=7)
        schedule_changes = self.get_schedule_changes(hours=24)
        memories = self.get_recent_memories(hours=24)

        # Generate summary with all data
        if conversations or schedule_changes or memories:
            summary = self.generate_summary_with_ollama(conversations, schedule_events, schedule_changes, memories)
        else:
            summary = "This is a test email from Mumble AI.\n\nNo recent activity to display."

        date_range = datetime.now(pytz.timezone(settings['timezone'])).strftime('%B %d, %Y')
        subject = f"[TEST] Mumble AI Summary - {date_range}"
        html_content = self.format_html_email(summary, date_range, schedule_events, schedule_changes, memories)
        plain_content = f"Test Email from Mumble AI\n\n{summary}"

        success = self.send_email(settings, subject, html_content, plain_content)

        # Log test email
        self.log_email(
            direction='sent',
            email_type='test',
            from_email=settings['from_email'],
            to_email=settings['recipient_email'],
            subject=subject,
            body=plain_content,
            status='success' if success else 'error',
            error_message=None if success else 'Failed to send email via SMTP'
        )

        return success

    def update_last_checked(self):
        """Update the last_checked timestamp in database"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE email_settings
                    SET last_checked = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                """, (datetime.now(),))
            conn.commit()
            logger.debug("Updated last_checked timestamp")
        except Exception as e:
            logger.error(f"Error updating last_checked: {e}")
            conn.rollback()

    def log_email(self, direction: str, email_type: str, from_email: str, to_email: str,
                  subject: str = None, body: str = None, status: str = 'success',
                  error_message: str = None, mapped_user: str = None,
                  attachments_count: int = 0, attachments_metadata: List[Dict] = None,
                  thread_id: int = None) -> Optional[int]:
        """Log email activity to database including attachment information and thread tracking"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Create body preview (first 500 chars)
                body_preview = body[:500] if body else None

                # Convert attachments metadata to JSON
                attachments_json = json.dumps(attachments_metadata) if attachments_metadata else None

                cursor.execute("""
                    INSERT INTO email_logs (
                        direction, email_type, from_email, to_email, subject,
                        body_preview, full_body, status, error_message, mapped_user,
                        attachments_count, attachments_metadata, thread_id,
                        timestamp, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                """, (
                    direction, email_type, from_email, to_email, subject,
                    body_preview, body, status, error_message, mapped_user,
                    attachments_count, attachments_json, thread_id
                ))
                email_log_id = cursor.fetchone()[0]
            conn.commit()
            logger.debug(f"Logged {direction} email: {email_type} from {from_email} to {to_email} with {attachments_count} attachment(s) (log_id={email_log_id})")
            return email_log_id
        except Exception as e:
            logger.error(f"Error logging email activity: {e}")
            conn.rollback()
            return None

    def normalize_subject(self, subject: str) -> str:
        """Remove Re:, Fwd:, etc. from subject to identify thread"""
        if not subject:
            return ""
        # Remove Re:, RE:, re:, Fwd:, FW:, fw:, etc. (handle multiple prefixes)
        normalized = subject
        while True:
            old_normalized = normalized
            normalized = re.sub(r'^(Re|RE|re|Fwd|FW|fw):\s*', '', normalized, flags=re.IGNORECASE)
            normalized = normalized.strip()
            if normalized == old_normalized:
                break
        return normalized

    def get_or_create_thread(self, subject: str, user_email: str,
                             mapped_user: str, message_id: str) -> Optional[int]:
        """Get existing thread or create new one based on subject"""
        try:
            normalized_subject = self.normalize_subject(subject)
            if not normalized_subject:
                normalized_subject = "(No Subject)"

            conn = self.get_db_connection()
            try:
                with conn.cursor() as cursor:
                    # Try to find existing thread
                    cursor.execute("""
                        SELECT id, message_count
                        FROM email_threads
                        WHERE normalized_subject = %s AND user_email = %s
                    """, (normalized_subject, user_email))

                    row = cursor.fetchone()
                    if row:
                        thread_id, msg_count = row
                        # Update thread
                        cursor.execute("""
                            UPDATE email_threads
                            SET last_message_id = %s,
                                message_count = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (message_id, msg_count + 1, thread_id))
                        conn.commit()
                        logger.debug(f"Updated existing thread {thread_id} for subject: {normalized_subject[:50]}")
                        return thread_id
                    else:
                        # Create new thread
                        cursor.execute("""
                            INSERT INTO email_threads
                            (subject, normalized_subject, user_email, mapped_user,
                             first_message_id, last_message_id, message_count)
                            VALUES (%s, %s, %s, %s, %s, %s, 1)
                            RETURNING id
                        """, (subject, normalized_subject, user_email, mapped_user,
                              message_id, message_id))
                        thread_id = cursor.fetchone()[0]
                        conn.commit()
                        logger.info(f"Created new thread {thread_id} for subject: {normalized_subject[:50]}")
                        return thread_id
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error in get_or_create_thread: {e}")
            return None

    def get_thread_history(self, thread_id: int, limit: int = 10) -> List[Dict]:
        """Get recent conversation history for this email thread"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT role, message_content, timestamp
                        FROM email_thread_messages
                        WHERE thread_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    """, (thread_id, limit))

                    messages = []
                    for row in cursor.fetchall():
                        messages.append({
                            'role': row[0],
                            'message': row[1],
                            'timestamp': row[2]
                        })
                    return list(reversed(messages))  # Return chronological order
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error getting thread history: {e}")
            return []

    def save_thread_message(self, thread_id: int, email_log_id: int,
                            role: str, message: str):
        """Save message to thread history"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO email_thread_messages
                        (thread_id, email_log_id, role, message_content)
                        VALUES (%s, %s, %s, %s)
                    """, (thread_id, email_log_id, role, message))
                    conn.commit()
                    logger.debug(f"Saved {role} message to thread {thread_id}")
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error saving thread message: {e}")

    def get_thread_actions(self, thread_id: int, limit: int = 5) -> List[Dict]:
        """Get recent actions from this thread"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT action_type, action, intent, status, details,
                               error_message, executed_at
                        FROM email_actions
                        WHERE thread_id = %s
                        ORDER BY executed_at DESC
                        LIMIT %s
                    """, (thread_id, limit))

                    actions = []
                    for row in cursor.fetchall():
                        actions.append({
                            'action_type': row[0],
                            'action': row[1],
                            'intent': row[2],
                            'status': row[3],
                            'details': row[4],
                            'error_message': row[5],
                            'executed_at': row[6]
                        })
                    return list(reversed(actions))
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error getting thread actions: {e}")
            return []

    def log_action(self, thread_id: int, email_log_id: int, action_type: str,
                   action: str, intent: str, status: str, details: dict = None,
                   error_message: str = None):
        """Log an action attempt (memory or schedule)"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO email_actions
                        (thread_id, email_log_id, action_type, action, intent,
                         status, details, error_message)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (thread_id, email_log_id, action_type, action, intent,
                          status, json.dumps(details) if details else None, error_message))
                    conn.commit()
                    status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⏭️"
                    logger.info(f"{status_icon} Logged {action_type} action: {action} - {intent[:50]}")
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error logging action: {e}")

    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two content strings based on word overlap"""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def save_persistent_memory(self, user_name: str, category: str, content: str, session_id: str = None,
                              importance: int = 5, tags: List[str] = None, event_date: str = None,
                              event_time: str = None):
        """Save a persistent memory to the database (with deduplication)"""
        conn = None
        try:
            conn = self.get_db_connection()
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
                pass  # Email service manages its own connection

    def extract_and_save_memory(self, user_message: str, assistant_response: str, user_name: str, session_id: str = None):
        """Extract important information from conversation and save as persistent memory"""
        try:
            # Get current date for context
            from zoneinfo import ZoneInfo
            ny_tz = ZoneInfo("America/New_York")
            current_datetime = datetime.now(ny_tz)
            current_date_str = current_datetime.strftime("%Y-%m-%d (%A, %B %d, %Y)")

            # Get memory extraction model from database (use specialized model for better precision)
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'memory_extraction_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'qwen2.5:3b'
            logger.info(f"Memory extraction using model: {ollama_model}")

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
                        f"{OLLAMA_URL}/api/generate",
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

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during memory extraction: {e}")
        except Exception as e:
            logger.error(f"Error extracting memory: {e}", exc_info=True)

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
        import json
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

    def add_schedule_event(self, user_name: str, title: str, event_date: str, event_time: str = None,
                          description: str = None, importance: int = 5) -> int:
        """Add a new schedule event (with deduplication)"""
        conn = None
        try:
            conn = self.get_db_connection()
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
                pass  # Email service manages its own connection

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
                pass  # Email service manages its own connection

    def delete_schedule_event(self, event_id: int) -> bool:
        """Delete (deactivate) a schedule event"""
        conn = None
        try:
            conn = self.get_db_connection()
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
                pass  # Email service manages its own connection

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
            # Get current date for context
            from zoneinfo import ZoneInfo
            ny_tz = ZoneInfo("America/New_York")
            current_datetime = datetime.now(ny_tz)
            current_date_str = current_datetime.strftime("%Y-%m-%d (%A, %B %d, %Y)")

            # Get Ollama model from database
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'llama3.2:latest'
            logger.info(f"Schedule action extraction using model: {ollama_model}")

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
- If the user is ASKING, QUERYING, READING, or CHECKING their schedule, ALWAYS use action "NOTHING"
- DO NOT create events when the user asks "what's on my calendar", "tell me my schedule", "what do I have", "do I have anything", etc.
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
"""

            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
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

                    elif action == 'UPDATE' and result.get('event_id'):
                        # Parse the date expression if present
                        date_expression = result.get('date_expression') or result.get('date')
                        parsed_date = self.parse_date_expression(date_expression, current_datetime) if date_expression else None

                        success = self.update_schedule_event(
                            event_id=result.get('event_id'),
                            title=result.get('title'),
                            event_date=parsed_date,
                            event_time=result.get('time'),
                            description=result.get('description'),
                            importance=result.get('importance')
                        )
                        if success:
                            logger.info(f"Updated schedule event {result.get('event_id')} for {user_name}")

                    elif action == 'DELETE':
                        # Find and delete matching events
                        title_search = result.get('title', '')
                        if title_search:
                            events = self.get_schedule_events(days_ahead=365)  # Get all events for user
                            # Filter by user
                            user_events = [e for e in events if e['user_name'] == user_name]
                            for event in user_events:
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

    def extract_and_save_memory_sync(self, user_message: str, user_name: str) -> List[Dict]:
        """
        Synchronous version of extract_and_save_memory that returns results.
        Returns list of dicts with: {category, content, importance, saved, error}
        """
        results = []
        try:
            # Get current date for context
            from zoneinfo import ZoneInfo
            ny_tz = ZoneInfo("America/New_York")
            current_datetime = datetime.now(ny_tz)
            current_date_str = current_datetime.strftime("%Y-%m-%d (%A, %B %d, %Y)")

            # Get memory extraction model from database (use specialized model for better precision)
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'memory_extraction_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'qwen2.5:3b'
            logger.info(f"Memory extraction (sync) using model: {ollama_model}")

            # Same extraction prompt as extract_and_save_memory
            extraction_prompt = f"""Analyze this conversation and extract ONLY truly important information worth remembering long-term.

CURRENT DATE: {current_date_str}

User: "{user_message}"

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
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            'model': ollama_model,
                            'prompt': extraction_prompt,
                            'stream': False,
                            'options': {
                                'temperature': 0.2,
                                'num_predict': 500
                            }
                        },
                        timeout=300  # 5 minutes timeout for memory extraction
                    )
                    break  # Success, exit retry loop
                except requests.exceptions.Timeout as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"Memory extraction (sync) timeout (attempt {retry_count}/{max_retries}), retrying...")
                        time.sleep(2)  # Brief delay before retry
                    else:
                        logger.error(f"Memory extraction (sync) failed after {max_retries} attempts: {e}")
                        results.append({
                            'category': 'error',
                            'content': 'Memory extraction failed - timeout',
                            'importance': 0,
                            'saved': False,
                            'error': str(e)
                        })
                        return results
                except requests.exceptions.RequestException as e:
                    logger.error(f"Network error during memory extraction (sync): {e}")
                    results.append({
                        'category': 'error',
                        'content': 'Memory extraction failed - network error',
                        'importance': 0,
                        'saved': False,
                        'error': str(e)
                    })
                    return results

            if response and response.status_code == 200:
                result = response.json().get('response', '').strip()
                logger.debug(f"Memory extraction (sync) raw response: {result[:200]}...")

                memories = self._parse_memory_json(result)
                if memories is not None:
                    # Filter out empty memories
                    valid_memories = [mem for mem in memories
                                      if isinstance(mem, dict) and 'content' in mem
                                      and isinstance(mem.get('content'), str) and mem.get('content').strip()]

                    for memory in valid_memories:
                        if self._validate_memory(memory):
                            try:
                                # Parse date expression for schedule memories
                                event_date = None
                                event_time = memory.get('event_time')

                                if memory.get('category') == 'schedule':
                                    date_expression = memory.get('date_expression') or memory.get('event_date')
                                    if date_expression:
                                        event_date = self.parse_date_expression(date_expression)

                                    if event_date is None:
                                        logger.warning(f"Skipping schedule memory with unparseable date: '{date_expression}'")
                                        results.append({
                                            'category': memory.get('category'),
                                            'content': memory.get('content'),
                                            'importance': memory.get('importance', 5),
                                            'saved': False,
                                            'error': f"Could not parse date: {date_expression}"
                                        })
                                        continue

                                self.save_persistent_memory(
                                    user_name=user_name,
                                    category=memory.get('category', 'other'),
                                    content=memory['content'],
                                    session_id=None,
                                    importance=memory.get('importance', 5),
                                    event_date=event_date,
                                    event_time=event_time
                                )

                                results.append({
                                    'category': memory.get('category'),
                                    'content': memory.get('content'),
                                    'importance': memory.get('importance', 5),
                                    'event_date': event_date,
                                    'event_time': event_time,
                                    'saved': True,
                                    'error': None
                                })
                                logger.info(f"✅ Saved memory for {user_name}: [{memory.get('category')}] {memory['content']}")

                            except Exception as e:
                                logger.error(f"Error saving memory: {e}")
                                results.append({
                                    'category': memory.get('category'),
                                    'content': memory.get('content'),
                                    'importance': memory.get('importance', 5),
                                    'saved': False,
                                    'error': str(e)
                                })

                    if not results:
                        logger.debug(f"No important memories found for {user_name}")

        except Exception as e:
            logger.error(f"Error in extract_and_save_memory_sync: {e}", exc_info=True)
            results.append({
                'category': 'error',
                'content': 'Memory extraction failed',
                'importance': 0,
                'saved': False,
                'error': str(e)
            })

        return results

    def extract_and_manage_schedule_sync(self, user_message: str, user_name: str) -> List[Dict]:
        """
        Synchronous version of extract_and_manage_schedule that returns results.
        Returns list of dicts with: {action, title, event_date, event_time, saved, event_id, error}
        """
        results = []
        try:
            # Get current date for context
            from zoneinfo import ZoneInfo
            ny_tz = ZoneInfo("America/New_York")
            current_datetime = datetime.now(ny_tz)
            current_date_str = current_datetime.strftime("%Y-%m-%d (%A, %B %d, %Y)")

            # Get Ollama model
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'llama3.2:latest'

            extraction_prompt = f"""You are a scheduling assistant analyzing a conversation to manage calendar events.

CURRENT DATE: {current_date_str}

Conversation:
User: {user_message}

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

KEY PHRASES THAT MEAN ADD:
- "update my calendar" = ADD
- "add to my schedule" = ADD
- "put this on my calendar" = ADD
- "schedule this" = ADD
- "I have [event] on [date]" = ADD
- "add these dates" = ADD

KEY PHRASES THAT MEAN NOTHING:
- "what's on my calendar" = NOTHING
- "show me my schedule" = NOTHING
- "do I have anything" = NOTHING

When in doubt and dates are mentioned → Use "ADD"
When no specific dates/events mentioned → Use "NOTHING"

IMPORTANT: For relative dates like "next Friday", just return "next Friday" - do NOT calculate the actual date.

Respond ONLY with a JSON object (no markdown, no extra text):
{{"action": "ADD|UPDATE|DELETE|NOTHING", "title": "...", "date_expression": "next Friday", "time": "HH:MM or null", "description": "...", "importance": 5, "event_id": null}}

Examples:
User: "I have a dentist appointment tomorrow at 3pm"
{{"action": "ADD", "title": "Dentist appointment", "date_expression": "tomorrow", "time": "15:00", "description": null, "importance": 7, "event_id": null}}

User: "Update my calendar with the team meeting on Monday at 2pm"
{{"action": "ADD", "title": "Team meeting", "date_expression": "Monday", "time": "14:00", "description": null, "importance": 6, "event_id": null}}

User: "Add this to my schedule: conference call Friday 10am"
{{"action": "ADD", "title": "Conference call", "date_expression": "Friday", "time": "10:00", "description": null, "importance": 5, "event_id": null}}

User: "What's on my schedule?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Do I have any travel dates for the month of October?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Tell me about my travel plans"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}

User: "Do you know if I've got any meetings tomorrow?"
{{"action": "NOTHING", "title": null, "date_expression": null, "time": null, "description": null, "importance": 5, "event_id": null}}
"""

            # Retry logic for schedule extraction (up to 3 attempts with 5 minute timeout)
            max_retries = 3
            retry_count = 0
            response = None

            while retry_count < max_retries:
                try:
                    response = requests.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            'model': ollama_model,
                            'prompt': extraction_prompt,
                            'stream': False,
                            'temperature': 0.1
                        },
                        timeout=300  # 5 minutes timeout for schedule action extraction
                    )
                    break  # Success, exit retry loop
                except requests.exceptions.Timeout as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"Schedule extraction timeout (attempt {retry_count}/{max_retries}), retrying...")
                        time.sleep(2)  # Brief delay before retry
                    else:
                        logger.error(f"Schedule extraction failed after {max_retries} attempts: {e}")
                        results.append({
                            'action': 'error',
                            'title': 'Schedule extraction failed',
                            'event_date': None,
                            'event_time': None,
                            'saved': False,
                            'event_id': None,
                            'error': f"Timeout after {max_retries} attempts"
                        })
                        return results
                except requests.exceptions.RequestException as e:
                    logger.error(f"Network error during schedule extraction: {e}")
                    results.append({
                        'action': 'error',
                        'title': 'Schedule extraction failed',
                        'event_date': None,
                        'event_time': None,
                        'saved': False,
                        'event_id': None,
                        'error': str(e)
                    })
                    return results

            if response and response.status_code == 200:
                result_text = response.json().get('response', '').strip()

                try:
                    result = json.loads(result_text)
                    action = result.get('action', 'NOTHING')

                    if action == 'ADD':
                        date_expression = result.get('date_expression') or result.get('date')
                        parsed_date = self.parse_date_expression(date_expression, current_datetime)

                        if not parsed_date:
                            results.append({
                                'action': 'ADD',
                                'title': result.get('title', 'Untitled'),
                                'event_date': None,
                                'event_time': result.get('time'),
                                'saved': False,
                                'event_id': None,
                                'error': f"Could not parse date: {date_expression}"
                            })
                        else:
                            try:
                                event_id = self.add_schedule_event(
                                    user_name=user_name,
                                    title=result.get('title', 'Untitled Event'),
                                    event_date=parsed_date,
                                    event_time=result.get('time'),
                                    description=result.get('description'),
                                    importance=result.get('importance', 5)
                                )
                                if event_id:
                                    results.append({
                                        'action': 'ADD',
                                        'title': result.get('title'),
                                        'event_date': parsed_date,
                                        'event_time': result.get('time'),
                                        'saved': True,
                                        'event_id': event_id,
                                        'error': None
                                    })
                                    logger.info(f"✅ Added schedule event {event_id} for {user_name}: {result.get('title')} on {parsed_date}")
                                else:
                                    results.append({
                                        'action': 'ADD',
                                        'title': result.get('title'),
                                        'event_date': parsed_date,
                                        'event_time': result.get('time'),
                                        'saved': False,
                                        'event_id': None,
                                        'error': 'add_schedule_event returned None'
                                    })
                            except Exception as e:
                                results.append({
                                    'action': 'ADD',
                                    'title': result.get('title'),
                                    'event_date': parsed_date,
                                    'event_time': result.get('time'),
                                    'saved': False,
                                    'event_id': None,
                                    'error': str(e)
                                })
                                logger.error(f"Error adding schedule event: {e}")

                    elif action == 'DELETE':
                        title_search = result.get('title', '')
                        if title_search:
                            try:
                                events = self.get_schedule_events(days_ahead=365)
                                user_events = [e for e in events if e['user_name'] == user_name]
                                deleted = False
                                for event in user_events:
                                    if title_search.lower() in event['title'].lower():
                                        self.delete_schedule_event(event['id'])
                                        results.append({
                                            'action': 'DELETE',
                                            'title': event['title'],
                                            'event_date': None,
                                            'event_time': None,
                                            'saved': True,
                                            'event_id': event['id'],
                                            'error': None
                                        })
                                        logger.info(f"✅ Deleted schedule event {event['id']} for {user_name}")
                                        deleted = True
                                        break
                                if not deleted:
                                    results.append({
                                        'action': 'DELETE',
                                        'title': title_search,
                                        'event_date': None,
                                        'event_time': None,
                                        'saved': False,
                                        'event_id': None,
                                        'error': f"No matching event found for: {title_search}"
                                    })
                            except Exception as e:
                                results.append({
                                    'action': 'DELETE',
                                    'title': title_search,
                                    'event_date': None,
                                    'event_time': None,
                                    'saved': False,
                                    'event_id': None,
                                    'error': str(e)
                                })
                                logger.error(f"Error deleting schedule event: {e}")

                    elif action == 'UPDATE':
                        # Find matching event by title and/or date instead of using LLM-provided event_id
                        title_search = result.get('title', '')
                        date_expression = result.get('date_expression') or result.get('date')
                        
                        if title_search:
                            try:
                                events = self.get_schedule_events(days_ahead=365)
                                user_events = [e for e in events if e['user_name'] == user_name]
                                matching_event = None
                                
                                # Find event by title (case-insensitive partial match)
                                for event in user_events:
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
                                        results.append({
                                            'action': 'UPDATE',
                                            'title': matching_event['title'],
                                            'event_date': parsed_date,
                                            'event_time': result.get('time'),
                                            'saved': True,
                                            'event_id': matching_event['id'],
                                            'error': None
                                        })
                                        logger.info(f"✅ Updated schedule event {matching_event['id']} for {user_name}")
                                    else:
                                        results.append({
                                            'action': 'UPDATE',
                                            'title': title_search,
                                            'event_date': parsed_date,
                                            'event_time': result.get('time'),
                                            'saved': False,
                                            'event_id': matching_event['id'],
                                            'error': 'update_schedule_event returned False'
                                        })
                                else:
                                    results.append({
                                        'action': 'UPDATE',
                                        'title': title_search,
                                        'event_date': None,
                                        'event_time': None,
                                        'saved': False,
                                        'event_id': None,
                                        'error': f"No matching event found for update: {title_search}"
                                    })
                            except Exception as e:
                                results.append({
                                    'action': 'UPDATE',
                                    'title': title_search,
                                    'event_date': None,
                                    'event_time': None,
                                    'saved': False,
                                    'event_id': None,
                                    'error': str(e)
                                })
                                logger.error(f"Error updating schedule event: {e}")
                        else:
                            results.append({
                                'action': 'UPDATE',
                                'title': None,
                                'event_date': None,
                                'event_time': None,
                                'saved': False,
                                'event_id': None,
                                'error': "UPDATE action requires a title to find the event to update"
                            })

                    elif action == 'NOTHING':
                        logger.debug("Schedule extraction determined no action needed")
                        # Don't add to results if action is NOTHING

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse schedule extraction result: {result_text}")
                    results.append({
                        'action': 'error',
                        'title': 'Parse error',
                        'event_date': None,
                        'event_time': None,
                        'saved': False,
                        'event_id': None,
                        'error': f"JSON parse error: {str(e)}"
                    })

        except Exception as e:
            logger.error(f"Error in extract_and_manage_schedule_sync: {e}", exc_info=True)
            results.append({
                'action': 'error',
                'title': 'Schedule extraction failed',
                'event_date': None,
                'event_time': None,
                'saved': False,
                'event_id': None,
                'error': str(e)
            })

        return results

    def extract_attachments(self, msg) -> List[Dict]:
        """Extract attachments from email message"""
        attachments = []
        max_size = 10 * 1024 * 1024  # 10MB limit
        
        try:
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip if not an attachment
                if "attachment" not in content_disposition:
                    continue
                
                filename = part.get_filename()
                if not filename:
                    continue
                
                # Get content type and size
                content_type = part.get_content_type()
                payload = part.get_payload(decode=True)
                
                if not payload:
                    continue
                
                size = len(payload)
                
                # Skip if too large
                if size > max_size:
                    logger.warning(f"Skipping attachment {filename} - size {size} bytes exceeds {max_size} bytes limit")
                    continue
                
                attachments.append({
                    'filename': filename,
                    'content_type': content_type,
                    'size': size,
                    'payload': payload
                })
                
                logger.info(f"Extracted attachment: {filename} ({content_type}, {size} bytes)")
            
        except Exception as e:
            logger.error(f"Error extracting attachments: {e}")
        
        return attachments

    def save_attachment_temporarily(self, filename: str, payload: bytes) -> str:
        """Save attachment to temporary directory"""
        try:
            # Create temp directory with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            temp_dir = os.path.join(tempfile.gettempdir(), f'mumble-attachments/{timestamp}')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Sanitize filename
            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()
            if not safe_filename:
                safe_filename = f"attachment_{timestamp}"
            
            filepath = os.path.join(temp_dir, safe_filename)
            
            # Save file
            with open(filepath, 'wb') as f:
                f.write(payload)
            
            logger.debug(f"Saved attachment to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving attachment {filename}: {e}")
            raise

    def call_ollama_vision(self, image_base64: str, prompt: str, max_retries: int = 3, timeout: int = 300) -> Optional[str]:
        """Call Ollama vision model with retry logic"""
        try:
            # Get vision model from database
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_vision_model'")
                row = cursor.fetchone()
                vision_model = row[0] if row else 'moondream:latest'
            
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"Ollama Vision API call attempt {attempt}/{max_retries} using model {vision_model}")
                    
                    response = requests.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            'model': vision_model,
                            'prompt': prompt,
                            'images': [image_base64],
                            'stream': False,
                            'options': {
                                'temperature': 0.7,
                                'num_predict': 500
                            }
                        },
                        timeout=timeout
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        generated_text = result.get('response', '').strip()
                        logger.info(f"Ollama Vision API call succeeded on attempt {attempt}")
                        return generated_text
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        logger.warning(f"Ollama Vision request failed on attempt {attempt}: {last_error}")
                
                except Timeout as e:
                    last_error = f"Timeout after {timeout}s"
                    logger.warning(f"Ollama Vision request timed out on attempt {attempt}/{max_retries}: {e}")
                except RequestException as e:
                    last_error = f"Request error: {str(e)}"
                    logger.warning(f"Ollama Vision request failed on attempt {attempt}/{max_retries}: {e}")
                except Exception as e:
                    last_error = f"Unexpected error: {str(e)}"
                    logger.error(f"Unexpected error on Ollama Vision attempt {attempt}/{max_retries}: {e}")
                
                # Wait before retrying (exponential backoff)
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
            
            # All retries failed
            logger.error(f"All {max_retries} Ollama Vision API attempts failed. Last error: {last_error}")
            return None
            
        except Exception as e:
            logger.error(f"Error in call_ollama_vision: {e}")
            return None

    def process_image_attachment(self, filepath: str, filename: str) -> Dict:
        """Process image attachment using vision model"""
        try:
            # Open and resize image if needed
            img = Image.open(filepath)
            
            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Resize if too large (max width 800px)
            max_width = 800
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                logger.debug(f"Resized image to {max_width}x{new_height}")
            
            # Convert to base64
            import io
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Get file size
            size = os.path.getsize(filepath)
            
            # Call vision model
            prompt = "Describe this image in detail. What do you see? Include any text, objects, people, colors, and other notable features."
            analysis_text = self.call_ollama_vision(image_base64, prompt)
            
            if not analysis_text:
                analysis_text = "Unable to analyze image - vision model unavailable"
            
            return {
                'type': 'image',
                'filename': filename,
                'size': size,
                'filepath': filepath,
                'analysis_text': analysis_text
            }
            
        except Exception as e:
            logger.error(f"Error processing image {filename}: {e}")
            return {
                'type': 'image',
                'filename': filename,
                'size': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                'filepath': filepath,
                'analysis_text': f"Error processing image: {str(e)}"
            }

    def extract_text_from_pdf(self, filepath: str, filename: str) -> Dict:
        """Extract text from PDF file"""
        try:
            reader = PyPDF2.PdfReader(filepath)
            page_count = len(reader.pages)
            
            # Extract text from all pages
            text_parts = []
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
            
            extracted_text = "\n\n".join(text_parts)
            
            # Limit to first 5000 chars if too long
            if len(extracted_text) > 5000:
                extracted_text = extracted_text[:5000] + "\n\n[Text truncated - document is longer]"
            
            size = os.path.getsize(filepath)
            
            logger.info(f"Extracted {len(extracted_text)} characters from PDF with {page_count} pages")
            
            return {
                'type': 'pdf',
                'filename': filename,
                'size': size,
                'filepath': filepath,
                'extracted_text': extracted_text,
                'page_count': page_count
            }
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {filename}: {e}")
            return {
                'type': 'pdf',
                'filename': filename,
                'size': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                'filepath': filepath,
                'extracted_text': f"Error reading PDF: {str(e)}",
                'page_count': 0
            }

    def extract_text_from_docx(self, filepath: str, filename: str) -> Dict:
        """Extract text from Word document"""
        try:
            doc = Document(filepath)
            
            # Extract all paragraphs
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            extracted_text = "\n\n".join(paragraphs)
            
            # Limit to first 5000 chars if too long
            if len(extracted_text) > 5000:
                extracted_text = extracted_text[:5000] + "\n\n[Text truncated - document is longer]"
            
            size = os.path.getsize(filepath)
            
            logger.info(f"Extracted {len(extracted_text)} characters from DOCX with {len(paragraphs)} paragraphs")
            
            return {
                'type': 'docx',
                'filename': filename,
                'size': size,
                'filepath': filepath,
                'extracted_text': extracted_text
            }
            
        except Exception as e:
            logger.error(f"Error extracting text from DOCX {filename}: {e}")
            return {
                'type': 'docx',
                'filename': filename,
                'size': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                'filepath': filepath,
                'extracted_text': f"Error reading Word document: {str(e)}"
            }

    def process_attachments(self, attachments_data: List[Dict], user_question: str) -> List[Dict]:
        """Process all attachments (images, PDFs, Word docs)"""
        processed = []
        
        for attachment in attachments_data:
            filename = attachment['filename']
            content_type = attachment['content_type']
            payload = attachment['payload']
            
            try:
                # Save attachment temporarily
                filepath = self.save_attachment_temporarily(filename, payload)
                
                # Process based on type
                if content_type.startswith('image/'):
                    # Image file - use vision model
                    result = self.process_image_attachment(filepath, filename)
                    processed.append(result)
                    
                elif content_type == 'application/pdf' or filename.lower().endswith('.pdf'):
                    # PDF file - extract text
                    result = self.extract_text_from_pdf(filepath, filename)
                    processed.append(result)
                    
                elif content_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
                                      'application/msword'] or filename.lower().endswith(('.docx', '.doc')):
                    # Word document - extract text
                    result = self.extract_text_from_docx(filepath, filename)
                    processed.append(result)
                    
                else:
                    logger.warning(f"Unsupported attachment type: {content_type} for {filename}")
                    processed.append({
                        'type': 'unsupported',
                        'filename': filename,
                        'size': attachment['size'],
                        'filepath': filepath,
                        'analysis_text': f"Unsupported file type: {content_type}"
                    })
                    
            except Exception as e:
                logger.error(f"Error processing attachment {filename}: {e}")
                processed.append({
                    'type': 'error',
                    'filename': filename,
                    'size': attachment['size'],
                    'filepath': '',
                    'analysis_text': f"Error processing attachment: {str(e)}"
                })
        
        return processed

    def cleanup_attachments(self, temp_dir: str):
        """Delete temporary attachment directory"""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary attachments directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory {temp_dir}: {e}")

    def connect_imap(self, settings: Dict):
        """Connect to IMAP server"""
        try:
            if settings['imap_use_ssl']:
                imap = imaplib.IMAP4_SSL(settings['imap_host'], settings['imap_port'])
            else:
                imap = imaplib.IMAP4(settings['imap_host'], settings['imap_port'])

            imap.login(settings['imap_username'], settings['imap_password'])
            logger.info(f"Connected to IMAP server {settings['imap_host']}:{settings['imap_port']}")
            return imap
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            return None

    def get_email_body(self, msg) -> Tuple[str, str, List[Dict]]:
        """Extract plain text, HTML body, and attachments from email message"""
        plain_text = ""
        html_text = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments for body extraction (we'll get them separately)
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        plain_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
                elif content_type == "text/html":
                    try:
                        html_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                try:
                    plain_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass
            elif content_type == "text/html":
                try:
                    html_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass

        # Prefer plain text, fall back to HTML (strip tags)
        body = plain_text if plain_text else self.strip_html_tags(html_text)
        
        # Extract attachments
        attachments = self.extract_attachments(msg)
        
        return body.strip(), html_text.strip(), attachments

    def strip_html_tags(self, html: str) -> str:
        """Remove HTML tags from text"""
        if not html:
            return ""
        # Simple HTML tag removal
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def get_user_from_email(self, email_address: str) -> Optional[str]:
        """Look up the user name associated with an email address"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT user_name
                    FROM email_user_mappings
                    WHERE LOWER(email_address) = LOWER(%s)
                """, (email_address,))

                row = cursor.fetchone()
                if row:
                    user_name = row[0]
                    logger.info(f"Mapped email {email_address} to user: {user_name}")
                    return user_name
                else:
                    logger.debug(f"No mapping found for email: {email_address}")
                    return None
        except Exception as e:
            logger.error(f"Error looking up email mapping: {e}")
            return None

    def get_user_memories(self, user_name: str = None, limit: int = 10) -> List[Dict]:
        """Get persistent memories for context (user-specific or general)"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Get memories for specific user or general memories
                if user_name:
                    cursor.execute("""
                        SELECT category, content, importance, extracted_at, event_date, event_time
                        FROM persistent_memories
                        WHERE active = TRUE
                          AND (user_name = %s OR user_name = 'general')
                        ORDER BY importance DESC, extracted_at DESC
                        LIMIT %s
                    """, (user_name, limit))
                else:
                    cursor.execute("""
                        SELECT category, content, importance, extracted_at, event_date, event_time
                        FROM persistent_memories
                        WHERE active = TRUE
                        ORDER BY importance DESC, extracted_at DESC
                        LIMIT %s
                    """, (limit,))

                rows = cursor.fetchall()
                memories = []
                for row in rows:
                    memories.append({
                        'category': row[0],
                        'content': row[1],
                        'importance': row[2],
                        'extracted_at': row[3],
                        'event_date': row[4],
                        'event_time': row[5]
                    })

                logger.debug(f"Retrieved {len(memories)} memories for user '{user_name}'" if user_name else f"Retrieved {len(memories)} general memories")
                return memories
        except Exception as e:
            logger.error(f"Error getting memories: {e}")
            return []

    def get_upcoming_schedule(self, user_name: str = None, days_ahead: int = 30) -> List[Dict]:
        """Get upcoming schedule events for email context (user-specific or all)"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                if user_name:
                    cursor.execute("""
                        SELECT user_name, title, event_date, event_time, description, importance
                        FROM schedule_events
                        WHERE active = TRUE
                          AND user_name = %s
                          AND event_date >= CURRENT_DATE
                          AND event_date <= CURRENT_DATE + INTERVAL '%s days'
                        ORDER BY event_date, event_time
                    """, (user_name, days_ahead))
                else:
                    cursor.execute("""
                        SELECT user_name, title, event_date, event_time, description, importance
                        FROM schedule_events
                        WHERE active = TRUE
                          AND event_date >= CURRENT_DATE
                          AND event_date <= CURRENT_DATE + INTERVAL '%s days'
                        ORDER BY event_date, event_time
                    """, (days_ahead,))

                rows = cursor.fetchall()
                events = []
                for row in rows:
                    events.append({
                        'user_name': row[0],
                        'title': row[1],
                        'event_date': row[2],
                        'event_time': row[3],
                        'description': row[4],
                        'importance': row[5]
                    })

                logger.debug(f"Retrieved {len(events)} schedule events for user '{user_name}'" if user_name else f"Retrieved {len(events)} schedule events")
                return events
        except Exception as e:
            logger.error(f"Error getting schedule: {e}")
            return []

    def extract_and_save_entities(self, user_message: str, assistant_response: str, user_name: str):
        """Extract entities from email conversation and save to entity_mentions table"""
        try:
            # Get Ollama configuration
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
                row = cursor.fetchone()
                ollama_url = row[0] if row else OLLAMA_URL

                cursor.execute("SELECT value FROM bot_config WHERE key = 'memory_extraction_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'qwen2.5:3b'

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

                    # Get the most recent message_id for linking
                    conn = self.get_db_connection()
                    with conn.cursor() as cursor:
                        # Get most recent message ID for this user
                        cursor.execute("""
                            SELECT id FROM conversation_history
                            WHERE user_name = %s
                            ORDER BY timestamp DESC
                            LIMIT 1
                        """, (user_name,))

                        message_row = cursor.fetchone()
                        if not message_row:
                            logger.warning(f"Could not find message for entity linking: {user_name}")
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

                        logger.info(f"Saved {saved_count} entities from email conversation with {user_name}")

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

            # Get Ollama configuration
            with conn.cursor() as cursor2:
                cursor2.execute("SELECT value FROM bot_config WHERE key = 'ollama_url'")
                row = cursor2.fetchone()
                ollama_url = row[0] if row else OLLAMA_URL

                cursor2.execute("SELECT value FROM bot_config WHERE key = 'memory_extraction_model'")
                row = cursor2.fetchone()
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

    def generate_ai_reply(self, sender: str, subject: str, body: str, settings: Dict,
                          thread_id: int = None, attachments_analysis: List[Dict] = None) -> str:
        """Generate AI reply to email using Ollama with full context (thread history, memories, schedule, persona, attachments)"""
        try:
            logger.info(f"Generating AI reply for email from {sender} (thread_id={thread_id})")

            # Look up user mapping from email address
            mapped_user = self.get_user_from_email(sender)
            if mapped_user:
                logger.info(f"Using data for user: {mapped_user}")
            else:
                logger.info(f"No mapping found, using general/all data")

            # Get bot persona and model
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'bot_persona'")
                row = cursor.fetchone()
                bot_persona = row[0] if row else "a helpful AI assistant"

                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'llama3.2:latest'

            # Get advanced AI settings from database
            short_term_limit = 10  # default
            long_term_limit = 10  # default
            try:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'short_term_memory_limit'")
                row = cursor.fetchone()
                if row:
                    short_term_limit = int(row[0])
            except:
                pass

            try:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'long_term_memory_limit'")
                row = cursor.fetchone()
                if row:
                    long_term_limit = int(row[0])
            except:
                pass

            # Get memories and schedule for context (user-specific if mapped)
            # Use long_term_limit for persistent memories (long-term context)
            memories = self.get_user_memories(mapped_user, limit=long_term_limit)
            schedule_events = self.get_upcoming_schedule(mapped_user, days_ahead=30)

            # NEW: Get thread conversation history
            thread_context = ""
            if thread_id:
                thread_history = self.get_thread_history(thread_id, limit=short_term_limit)
                if thread_history:
                    thread_context = "\n📧 PREVIOUS MESSAGES IN THIS EMAIL THREAD:\n"
                    for msg in thread_history:
                        role_label = "You (AI Assistant)" if msg['role'] == 'assistant' else (mapped_user or sender)
                        # Truncate long messages
                        message_preview = msg['message'][:300] + "..." if len(msg['message']) > 300 else msg['message']
                        thread_context += f"{role_label}: {message_preview}\n"
                    thread_context += "\n"

            # NEW: Get recent actions from this thread
            actions_context = ""
            if thread_id:
                recent_actions = self.get_thread_actions(thread_id, limit=5)
                if recent_actions:
                    # Count successes and failures
                    memory_successes = sum(1 for a in recent_actions if a['action_type'] == 'memory' and a['status'] == 'success')
                    schedule_successes = sum(1 for a in recent_actions if a['action_type'] == 'schedule' and a['status'] == 'success')
                    memory_failures = sum(1 for a in recent_actions if a['action_type'] == 'memory' and a['status'] == 'failed')
                    schedule_failures = sum(1 for a in recent_actions if a['action_type'] == 'schedule' and a['status'] == 'failed')

                    # Clear summary at top
                    actions_context = "\n" + "="*80 + "\n"
                    actions_context += "📊 ACTION SUMMARY FOR THIS EMAIL:\n"
                    actions_context += f"   ✅ Successfully saved {memory_successes} memories\n"
                    actions_context += f"   ✅ Successfully added {schedule_successes} calendar events\n"
                    if memory_failures > 0:
                        actions_context += f"   ❌ Failed to save {memory_failures} memories (see errors below)\n"
                    if schedule_failures > 0:
                        actions_context += f"   ❌ Failed to add {schedule_failures} calendar events (see errors below)\n"
                    actions_context += "="*80 + "\n\n"

                    actions_context += "🔧 DETAILED ACTION LOG:\n"
                    for action in recent_actions:
                        status_icon = "✅" if action['status'] == 'success' else "❌"
                        action_desc = f"{action['action_type'].upper()}"
                        if action['action'] != 'add':
                            action_desc += f" ({action['action']})"
                        actions_context += f"{status_icon} {action_desc}: {action['intent']}\n"
                        if action['status'] == 'failed' and action['error_message']:
                            actions_context += f"   ⚠️ Error: {action['error_message']}\n"
                        elif action['status'] == 'success' and action['action_type'] == 'schedule':
                            # Show event ID for successfully created events
                            details = action.get('details')
                            if details:
                                try:
                                    details_dict = json.loads(details) if isinstance(details, str) else details
                                    if details_dict.get('event_id'):
                                        actions_context += f"   📅 Event ID: {details_dict['event_id']}\n"
                                    if details_dict.get('event_date'):
                                        actions_context += f"   📅 Date: {details_dict['event_date']}"
                                        if details_dict.get('event_time'):
                                            actions_context += f" at {details_dict['event_time']}"
                                        actions_context += "\n"
                                except:
                                    pass
                    actions_context += "\n"
                else:
                    # No actions attempted yet
                    actions_context = "\n" + "="*80 + "\n"
                    actions_context += "📊 ACTION SUMMARY: No calendar/memory actions taken yet in this email.\n"
                    actions_context += "="*80 + "\n\n"

            # Build context sections
            current_datetime = datetime.now(pytz.timezone(settings.get('timezone', 'America/New_York')))

            # Memories section (exclude schedule category - shown separately)
            memory_context = ""
            if memories:
                non_schedule_memories = [mem for mem in memories if mem['category'] != 'schedule']
                if non_schedule_memories:
                    memory_context = "\n📝 RELEVANT MEMORIES:\n"
                    category_icons = {'fact': '💡', 'task': '✓', 'preference': '❤️', 'reminder': '⏰', 'other': '📌'}
                    for mem in non_schedule_memories:
                        icon = category_icons.get(mem['category'], '📌')
                        memory_context += f"{icon} [{mem['category'].upper()}] {mem['content']}\n"
                    memory_context += "\n"

            # Schedule section with smart date filtering, keyword filtering, and event name search
            schedule_context = ""
            if schedule_events:
                # Check if this is an event name query and use search if so
                if self.is_event_name_query(body):
                    try:
                        # Use three-tier search for event name queries
                        from datetime import timedelta
                        end_date = (current_datetime + timedelta(days=30)).strftime('%Y-%m-%d')
                        search_results = self.search_schedule_by_title(
                            user_name=mapped_user or sender,
                            search_query=body,
                            start_date=current_datetime.strftime('%Y-%m-%d'),
                            end_date=end_date,
                            timeout=300,
                            max_retries=3
                        )
                        filtered_events = search_results
                        time_range = "SEARCH RESULTS"
                        logger.info(f"Event name search found {len(filtered_events)} results for '{body[:50]}...'")
                    except Exception as e:
                        logger.error(f"Event name search failed: {e}")
                        # Fallback to regular filtering
                        filtered_events = schedule_events
                        time_range = "UPCOMING"
                else:
                    # Regular date-based and keyword filtering for non-event-name queries
                    body_lower = body.lower()
                    filtered_events = schedule_events  # Default to all events
                    time_range = "UPCOMING"

                    # First: Apply keyword filtering if specific event types are mentioned
                    keyword_categories = {
                        'travel': ['travel', 'trip', 'flight', 'vacation', 'journey', 'fly', 'flying', 'depart', 'return', 'arrive', 'airport'],
                        'appointment': ['appointment', 'doctor', 'dentist', 'checkup', 'medical', 'clinic', 'hospital'],
                        'meeting': ['meeting', 'call', 'conference', 'zoom', 'presentation'],
                        'event': ['party', 'celebration', 'birthday', 'shower', 'wedding', 'anniversary'],
                    }

                    for category, keywords in keyword_categories.items():
                        if any(kw in body_lower for kw in keywords):
                            # Filter events that match these keywords
                            filtered_events = [
                                e for e in schedule_events
                                if any(kw in (e['title'] or '').lower() or kw in (e['description'] or '').lower()
                                      for kw in keywords)
                            ]
                            if filtered_events:
                                time_range = f"{category.upper()}"
                                logger.info(f"Filtered {len(filtered_events)} events by keyword category: {category}")
                                break

                    # Second: Apply month filtering if specific month is mentioned
                    month_filtered = False
                    
                    # Relative month filtering
                    if 'this month' in body_lower:
                        current_month = current_datetime.month
                        current_year = current_datetime.year
                        filtered_events = [
                            e for e in filtered_events
                            if e['event_date'].month == current_month and e['event_date'].year == current_year
                        ]
                        time_range = "THIS MONTH"
                        logger.info(f"Filtered {len(filtered_events)} events for this month")
                        month_filtered = True
                    elif 'next month' in body_lower:
                        next_month_date = current_datetime.replace(day=1) + timedelta(days=32)
                        next_month = next_month_date.month
                        next_year = next_month_date.year
                        filtered_events = [
                            e for e in filtered_events
                            if e['event_date'].month == next_month and e['event_date'].year == next_year
                        ]
                        time_range = "NEXT MONTH"
                        logger.info(f"Filtered {len(filtered_events)} events for next month")
                        month_filtered = True
                    elif 'this quarter' in body_lower:
                        current_quarter = (current_datetime.month - 1) // 3 + 1
                        quarter_start_month = (current_quarter - 1) * 3 + 1
                        quarter_end_month = current_quarter * 3
                        filtered_events = [
                            e for e in filtered_events
                            if quarter_start_month <= e['event_date'].month <= quarter_end_month
                            and e['event_date'].year == current_datetime.year
                        ]
                        time_range = f"Q{current_quarter}"
                        logger.info(f"Filtered {len(filtered_events)} events for this quarter")
                        month_filtered = True
                    
                    # Specific month filtering
                    if not month_filtered:
                        month_names = {
                            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
                        }
                        for month_name, month_num in month_names.items():
                            if month_name in body_lower:
                                # Filter events in that specific month
                                filtered_events = [
                                    e for e in filtered_events
                                    if e['event_date'].month == month_num
                                ]
                                time_range = f"{month_name.upper()}"
                                logger.info(f"Filtered {len(filtered_events)} events for month: {month_name}")
                                break

                    # Third: Apply date-based filtering (today, tomorrow, this week)
                    if 'today' in body_lower or 'tonight' in body_lower:
                        today_str = current_datetime.strftime('%Y-%m-%d')
                        filtered_events = [e for e in filtered_events if str(e['event_date']) == today_str]
                        time_range = "TODAY"
                    elif 'tomorrow' in body_lower:
                        tomorrow = current_datetime + timedelta(days=1)
                        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
                        filtered_events = [e for e in filtered_events if str(e['event_date']) == tomorrow_str]
                        time_range = "TOMORROW"
                    elif 'next week' in body_lower or 'this week' in body_lower:
                        week_end = current_datetime + timedelta(days=7)
                        filtered_events = [e for e in filtered_events if current_datetime.date() <= e['event_date'] <= week_end.date()]
                        time_range = "THIS WEEK"

                schedule_context = f"\n📅 {time_range} SCHEDULE:\n"
                if filtered_events:
                    for event in filtered_events:
                        event_date_str = event['event_date'].strftime('%A, %B %d, %Y') if hasattr(event['event_date'], 'strftime') else str(event['event_date'])
                        event_time_str = str(event['event_time']) if event['event_time'] else "All day"
                        importance_emoji = "🔴" if event['importance'] >= 9 else "🟠" if event['importance'] >= 7 else "🔵"
                        schedule_context += f"{importance_emoji} {event['title']} - {event_date_str} at {event_time_str}\n"
                        if event['description']:
                            schedule_context += f"   Details: {event['description']}\n"
                    schedule_context += "\n"
                else:
                    schedule_context = f"\n📅 SCHEDULE: No events for {time_range}\n\n"
            else:
                schedule_context = f"\n📅 SCHEDULE: No upcoming events scheduled\n\n"

            # Attachments section
            attachments_context = ""
            if attachments_analysis:
                attachments_context = "\n📎 ATTACHMENTS ANALYSIS:\n"
                type_icons = {'image': '🖼️', 'pdf': '📄', 'docx': '📝', 'unsupported': '❌', 'error': '⚠️'}
                for attach in attachments_analysis:
                    icon = type_icons.get(attach['type'], '📎')
                    size_kb = attach['size'] / 1024
                    attachments_context += f"{icon} [{attach['type'].upper()}] {attach['filename']} ({size_kb:.1f} KB):\n"
                    
                    if 'analysis_text' in attach:
                        attachments_context += f"   {attach['analysis_text']}\n\n"
                    elif 'extracted_text' in attach:
                        attachments_context += f"   {attach['extracted_text']}\n\n"
                    
                    if 'page_count' in attach:
                        attachments_context += f"   (PDF has {attach['page_count']} pages)\n\n"

            # Determine what to include in context based on email content
            # Only include schedule if user asks about it
            include_schedule = any(keyword in body.lower() for keyword in ['schedule', 'calendar', 'appointment', 'meeting', 'event', 'when'])

            # Create simple, focused prompt
            reply_prompt = f"""You are {bot_persona}.

EMAIL FROM: {mapped_user if mapped_user else sender}
SUBJECT: {subject}
MESSAGE: {body}
{attachments_context}
---
{actions_context}
🚨 CRITICAL RULES:

1. BE BRIEF AND DIRECT
   - Keep replies under 100 words
   - No formal greetings like "Dear Charles"
   - No flowery language or unnecessary explanations
   - Get straight to the point

2. REPORT ONLY WHAT ACTUALLY HAPPENED
   - Look at the ACTION SUMMARY above
   - If ✅ 1 calendar events: "Added [event] to your calendar for [date]"
   - If ✅ 0 calendar events: Don't say you added anything
   - If ❌ errors: Explain the error briefly
   - DON'T say "thank you for adding to my calendar" - YOU add to THEIR calendar, not the other way around

3. OWNERSHIP - THIS IS CRITICAL
   - The user ASKED you to add events
   - YOU (the AI) added events to THEIR calendar
   - CORRECT: "I've added the flight to your calendar"
   - WRONG: "Thank you for adding to my calendar"
   - NEVER confuse who did what

4. DON'T LIST UNRELATED EVENTS
   - If they ask about travel, ONLY mention travel
   - Don't list baby showers, haircuts, etc. unless they ask "what's on my calendar"
   - Stay focused on what they actually asked about

5. ANSWER THEIR QUESTION
   - If they sent a PDF: acknowledge it briefly
   - If they asked to add something: confirm what you added
   - If they asked a question: answer it directly
   - Don't add extra information they didn't ask for

{schedule_context if include_schedule else ""}

Your reply (brief and direct):"""

            # Use retry logic for Ollama call (5 minutes)
            reply_text = self.call_ollama_with_retry(reply_prompt, max_retries=3, timeout=300)

            if reply_text:
                # Add signature if configured
                if settings['reply_signature']:
                    reply_text += f"\n\n{settings['reply_signature']}"

                logger.info("AI reply generated successfully")
                return reply_text
            else:
                logger.error("Failed to generate AI reply after all retries")
                return None

        except Exception as e:
            logger.error(f"Error generating AI reply: {e}")
            return None

    def send_reply_email(self, settings: Dict, to_email: str, subject: str, reply_body: str,
                         in_reply_to: str = None, references: str = None, mapped_user: str = None,
                         thread_id: int = None) -> bool:
        """Send reply email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')

            # Add "Re:" prefix if not already present
            if not subject.lower().startswith('re:'):
                subject = f"Re: {subject}"

            msg['Subject'] = subject
            msg['From'] = settings['from_email']
            msg['To'] = to_email
            msg['Date'] = formatdate(localtime=True)

            # Add threading headers for proper email threading
            if in_reply_to:
                msg['In-Reply-To'] = in_reply_to
            if references:
                msg['References'] = references

            # Create plain text and HTML versions
            plain_text = reply_body
            # Convert newlines to HTML breaks for HTML version
            html_body_content = reply_body.replace('\n', '<br>')
            html_text = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            padding: 20px;
        }}
        .reply-body {{
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="reply-body">{html_body_content}</div>
</body>
</html>
"""

            # Attach plain text and HTML versions
            part1 = MIMEText(plain_text, 'plain', 'utf-8')
            part2 = MIMEText(html_text, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            # Connect to SMTP server and send
            logger.info(f"Sending reply to {to_email}")

            if settings['smtp_use_ssl']:
                smtp = smtplib.SMTP_SSL(settings['smtp_host'], settings['smtp_port'], timeout=30)
            else:
                smtp = smtplib.SMTP(settings['smtp_host'], settings['smtp_port'], timeout=30)
                if settings['smtp_use_tls']:
                    smtp.starttls()

            if settings['smtp_username'] and settings['smtp_password']:
                smtp.login(settings['smtp_username'], settings['smtp_password'])

            smtp.send_message(msg)
            smtp.quit()

            logger.info(f"Reply sent successfully to {to_email}")

            # Log successful send
            self.log_email(
                direction='sent',
                email_type='reply',
                from_email=settings['from_email'],
                to_email=to_email,
                subject=subject,
                body=reply_body,
                status='success',
                mapped_user=mapped_user,
                thread_id=thread_id
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send reply email: {e}")

            # Log failed send
            self.log_email(
                direction='sent',
                email_type='reply',
                from_email=settings['from_email'],
                to_email=to_email,
                subject=subject,
                body=reply_body,
                status='error',
                error_message=str(e),
                thread_id=thread_id,
                mapped_user=mapped_user
            )

            return False

    def get_events_needing_reminders(self) -> List[Dict]:
        """Get schedule events that need email reminders sent"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Find events where:
                # 1. reminder_enabled = TRUE
                # 2. reminder_sent = FALSE
                # 3. event is coming up in the next few hours (we'll check all and filter by time)
                # 4. event is today or in the future
                cursor.execute("""
                    SELECT id, user_name, title, event_date, event_time, description, importance,
                           reminder_enabled, reminder_minutes, recipient_email
                    FROM schedule_events
                    WHERE active = TRUE
                      AND reminder_enabled = TRUE
                      AND reminder_sent = FALSE
                      AND event_date >= CURRENT_DATE
                    ORDER BY event_date, event_time
                """)

                rows = cursor.fetchall()
                
                # Filter events that are within the reminder window
                from zoneinfo import ZoneInfo
                ny_tz = ZoneInfo("America/New_York")
                now = datetime.now(ny_tz)
                
                events_to_remind = []
                for row in rows:
                    event_date = row[3]
                    event_time = row[4]
                    reminder_minutes = row[8] or 60
                    
                    # Create datetime for the event
                    if event_time:
                        # Event has specific time
                        event_datetime = datetime.combine(event_date, event_time)
                        event_datetime = event_datetime.replace(tzinfo=ny_tz)
                    else:
                        # All-day event, set reminder for 9 AM on event date
                        event_datetime = datetime.combine(event_date, datetime.min.time().replace(hour=9))
                        event_datetime = event_datetime.replace(tzinfo=ny_tz)
                    
                    # Calculate when to send reminder
                    reminder_time = event_datetime - timedelta(minutes=reminder_minutes)
                    
                    # Check if we should send reminder now (within a 5-minute window for flexibility)
                    time_diff = (reminder_time - now).total_seconds()
                    
                    # Send if we're within the window (reminder time has passed but event hasn't)
                    if -300 <= time_diff <= 300 and now < event_datetime:  # 5-minute window
                        events_to_remind.append({
                            'id': row[0],
                            'user_name': row[1],
                            'title': row[2],
                            'event_date': row[3],
                            'event_time': row[4],
                            'description': row[5],
                            'importance': row[6],
                            'reminder_minutes': reminder_minutes,
                            'recipient_email': row[9]
                        })
                
                logger.info(f"Found {len(events_to_remind)} events needing reminders")
                return events_to_remind
                
        except Exception as e:
            logger.error(f"Error getting events needing reminders: {e}")
            return []

    def mark_reminder_sent(self, event_id: int):
        """Mark a reminder as sent for a schedule event"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE schedule_events
                    SET reminder_sent = TRUE, reminder_sent_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (event_id,))
            conn.commit()
            logger.info(f"Marked reminder as sent for event ID {event_id}")
        except Exception as e:
            logger.error(f"Error marking reminder as sent: {e}")
            if conn:
                conn.rollback()

    def generate_reminder_message(self, event: Dict, settings: Dict) -> str:
        """Generate a personalized reminder message using Ollama"""
        try:
            # Get bot persona
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM bot_config WHERE key = 'bot_persona'")
                row = cursor.fetchone()
                bot_persona = row[0] if row else "a helpful AI assistant"
                
                cursor.execute("SELECT value FROM bot_config WHERE key = 'ollama_model'")
                row = cursor.fetchone()
                ollama_model = row[0] if row else 'llama3.2:latest'
            logger.info(f"Generating response using model: {ollama_model}")

            # Format event details
            event_date_str = event['event_date'].strftime('%A, %B %d, %Y')
            event_time_str = event['event_time'].strftime('%I:%M %p') if event['event_time'] else 'All day'
            
            # Calculate time until event
            from zoneinfo import ZoneInfo
            ny_tz = ZoneInfo("America/New_York")
            now = datetime.now(ny_tz)
            
            if event['event_time']:
                event_datetime = datetime.combine(event['event_date'], event['event_time'])
                event_datetime = event_datetime.replace(tzinfo=ny_tz)
            else:
                event_datetime = datetime.combine(event['event_date'], datetime.min.time().replace(hour=9))
                event_datetime = event_datetime.replace(tzinfo=ny_tz)
            
            time_until = event_datetime - now
            minutes_until = int(time_until.total_seconds() / 60)
            
            # Create prompt for Ollama
            prompt = f"""You are {bot_persona}.

Generate a friendly, brief reminder message for an upcoming calendar event. The message should be warm, helpful, and encouraging.

EVENT DETAILS:
- Title: {event['title']}
- Date: {event_date_str}
- Time: {event_time_str}
- Minutes until event: {minutes_until}
{f"- Description: {event['description']}" if event.get('description') else ""}
- Importance: {event['importance']}/10

Generate a short, friendly reminder message (2-3 sentences max). Be conversational and supportive. Don't include formal headers or signatures.

Example tone: "Hey! Just a friendly reminder that you have [event] coming up in [time]. [Optional encouraging note based on event type]."

Your message:"""

            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    'model': ollama_model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.7,
                        'num_predict': 150
                    }
                },
                timeout=300  # 5 minutes for main response generation
            )

            if response.status_code == 200:
                result = response.json()
                message = result.get('response', '').strip()
                logger.info("Generated reminder message with Ollama")
                return message
            else:
                logger.error(f"Ollama request failed with status {response.status_code}")
                return self._generate_fallback_reminder_message(event, minutes_until)

        except Exception as e:
            logger.error(f"Error generating reminder message with Ollama: {e}")
            return self._generate_fallback_reminder_message(event, minutes_until)

    def _generate_fallback_reminder_message(self, event: Dict, minutes_until: int) -> str:
        """Generate a simple fallback reminder message"""
        time_str = f"in {minutes_until} minutes" if minutes_until > 0 else "soon"
        return f"Reminder: You have '{event['title']}' coming up {time_str}. Don't forget!"

    def send_event_reminder(self, event: Dict, settings: Dict) -> bool:
        """Send email reminder for a scheduled event"""
        try:
            logger.info(f"Sending reminder for event: {event['title']}")
            
            # Determine recipient email
            recipient = event['recipient_email'] if event['recipient_email'] else settings['recipient_email']
            
            if not recipient:
                logger.error("No recipient email configured for reminder")
                return False
            
            # Generate AI message
            ai_message = self.generate_reminder_message(event, settings)
            
            # Format event details
            event_date_str = event['event_date'].strftime('%A, %B %d, %Y')
            event_time_str = event['event_time'].strftime('%I:%M %p') if event['event_time'] else 'All day'
            
            # Importance badge
            importance = event['importance']
            if importance >= 8:
                importance_badge = '🔴 High Priority'
                importance_color = '#ef4444'
            elif importance >= 5:
                importance_badge = '🟠 Medium Priority'
                importance_color = '#f97316'
            else:
                importance_badge = '🔵 Normal'
                importance_color = '#667eea'
            
            # Create email subject
            subject = f"⏰ Reminder: {event['title']}"
            
            # Create HTML email
            html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            padding: 30px;
        }}
        .ai-message {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            font-size: 16px;
            line-height: 1.6;
        }}
        .event-card {{
            background: #ffffff;
            border: 2px solid {importance_color};
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }}
        .event-title {{
            font-size: 22px;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 15px;
        }}
        .event-detail {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 10px 0;
            font-size: 16px;
            color: #555;
        }}
        .event-detail-icon {{
            font-size: 20px;
            width: 24px;
        }}
        .importance-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            background: {importance_color};
            color: white;
            margin-top: 10px;
        }}
        .description {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            color: #666;
            font-style: italic;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            border-top: 1px solid #e9ecef;
            color: #7f8c8d;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>⏰ Event Reminder</h1>
        </div>
        
        <div class="content">
            <div class="ai-message">
                {ai_message}
            </div>
            
            <div class="event-card">
                <div class="event-title">{event['title']}</div>
                
                <div class="event-detail">
                    <span class="event-detail-icon">📅</span>
                    <span>{event_date_str}</span>
                </div>
                
                <div class="event-detail">
                    <span class="event-detail-icon">🕐</span>
                    <span>{event_time_str}</span>
                </div>
                
                <div class="event-detail">
                    <span class="event-detail-icon">👤</span>
                    <span>{event['user_name']}</span>
                </div>
                
                <div class="importance-badge">{importance_badge}</div>
                
                {f'<div class="description">{event["description"]}</div>' if event.get('description') else ''}
            </div>
        </div>
        
        <div class="footer">
            <p><strong>This reminder was sent from Mumble AI</strong></p>
            <p>Manage your schedule at the <a href="http://localhost:5002/schedule" style="color: #667eea; text-decoration: none;">Web Control Panel</a></p>
        </div>
    </div>
</body>
</html>
'''
            
            # Create plain text version
            plain_content = f"""
⏰ EVENT REMINDER

{ai_message}

EVENT DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{event['title']}

📅 Date: {event_date_str}
🕐 Time: {event_time_str}
👤 User: {event['user_name']}
{f"📝 Description: {event['description']}" if event.get('description') else ''}

Priority: {importance_badge}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This reminder was sent from Mumble AI.
Manage your schedule at http://localhost:5002/schedule
"""
            
            # Send the email
            success = self.send_email(settings, subject, html_content, plain_content)
            
            if success:
                # Mark reminder as sent
                self.mark_reminder_sent(event['id'])
                
                # Log successful reminder
                self.log_email(
                    direction='sent',
                    email_type='other',  # reminder type
                    from_email=settings['from_email'],
                    to_email=recipient,
                    subject=subject,
                    body=plain_content,
                    status='success',
                    mapped_user=event['user_name']
                )
                logger.info(f"Successfully sent reminder for event '{event['title']}' to {recipient}")
                return True
            else:
                logger.error(f"Failed to send reminder for event '{event['title']}'")
                return False
                
        except Exception as e:
            logger.error(f"Error sending event reminder: {e}", exc_info=True)
            return False

    def check_and_send_reminders(self, settings: Dict):
        """Check for events needing reminders and send them"""
        if not settings['daily_summary_enabled']:
            # Email system is disabled
            return
        
        logger.info("Checking for events needing reminders...")
        events = self.get_events_needing_reminders()
        
        if not events:
            logger.debug("No events need reminders at this time")
            return
        
        logger.info(f"Sending {len(events)} event reminder(s)")
        for event in events:
            try:
                self.send_event_reminder(event, settings)
            except Exception as e:
                logger.error(f"Error sending reminder for event {event['id']}: {e}")

    def check_and_reply_to_emails(self, settings: Dict):
        """Check for new emails and send AI-generated replies"""
        if not settings['imap_enabled']:
            return

        if not settings['auto_reply_enabled']:
            logger.debug("Auto-reply is disabled")
            return

        logger.info("Checking for new emails...")

        imap = self.connect_imap(settings)
        if not imap:
            return

        try:
            # Select mailbox
            mailbox = settings['imap_mailbox']
            imap.select(mailbox)

            # Search for unseen emails
            status, messages = imap.search(None, 'UNSEEN')

            if status != 'OK':
                logger.error("Failed to search for emails")
                return

            email_ids = messages[0].split()

            if not email_ids:
                logger.debug("No new emails found")
                self.update_last_checked()
                return

            logger.info(f"Found {len(email_ids)} new email(s)")

            for email_id in email_ids:
                try:
                    # Fetch email
                    status, msg_data = imap.fetch(email_id, '(RFC822)')

                    if status != 'OK':
                        logger.error(f"Failed to fetch email {email_id}")
                        continue

                    # Parse email
                    raw_email = msg_data[0][1]
                    msg = BytesParser(policy=policy.default).parsebytes(raw_email)

                    # Extract email details
                    from_header = msg.get('From', '')
                    sender_name, sender_email = parseaddr(from_header)
                    subject = msg.get('Subject', 'No Subject')
                    message_id = msg.get('Message-ID', '')
                    references = msg.get('References', '')

                    # Get email body and attachments
                    body, html_body, attachments_data = self.get_email_body(msg)

                    logger.info(f"Processing email from {sender_email}: {subject}")

                    # Look up user mapping for logging
                    mapped_user = self.get_user_from_email(sender_email)

                    # Process attachments if present
                    attachments_analysis = []
                    temp_dir = None
                    if attachments_data:
                        logger.info(f"Processing {len(attachments_data)} attachment(s)")
                        try:
                            attachments_analysis = self.process_attachments(attachments_data, body)
                            # Get temp directory from first processed attachment
                            if attachments_analysis and attachments_analysis[0].get('filepath'):
                                temp_dir = os.path.dirname(attachments_analysis[0]['filepath'])
                        except Exception as e:
                            logger.error(f"Error processing attachments: {e}", exc_info=True)

                    # Build attachment metadata for logging
                    attachments_metadata = []
                    if attachments_analysis:
                        for a in attachments_analysis:
                            attachments_metadata.append({
                                'filename': a['filename'],
                                'type': a['type'],
                                'size': a['size'],
                                'analysis_preview': a.get('analysis_text', a.get('extracted_text', ''))[:200]
                            })

                    # Get or create thread based on subject
                    thread_id = self.get_or_create_thread(
                        subject=subject,
                        user_email=sender_email,
                        mapped_user=mapped_user,
                        message_id=message_id
                    )

                    if not thread_id:
                        logger.error(f"Failed to create/get thread for email from {sender_email}")
                        thread_id = None  # Continue without thread tracking

                    # Log received email with attachment info and thread_id
                    email_log_id = self.log_email(
                        direction='received',
                        email_type='other',
                        from_email=sender_email,
                        to_email=settings['imap_username'],
                        subject=subject,
                        body=body,
                        status='success',
                        mapped_user=mapped_user,
                        attachments_count=len(attachments_analysis),
                        attachments_metadata=attachments_metadata,
                        thread_id=thread_id
                    )

                    # Save user message to thread history
                    if thread_id and email_log_id:
                        self.save_thread_message(
                            thread_id=thread_id,
                            email_log_id=email_log_id,
                            role='user',
                            message=body
                        )

                    # STEP 1: Extract and execute memory actions SYNCHRONOUSLY
                    if thread_id and email_log_id:
                        try:
                            logger.info("Extracting memories synchronously...")
                            memory_results = self.extract_and_save_memory_sync(
                                user_message=body,
                                user_name=mapped_user or sender_email
                            )
                            # Log each memory action
                            for result in memory_results:
                                self.log_action(
                                    thread_id=thread_id,
                                    email_log_id=email_log_id,
                                    action_type='memory',
                                    action='add',
                                    intent=result.get('content', 'Memory extraction'),
                                    status='success' if result.get('saved') else 'failed',
                                    details=result,
                                    error_message=result.get('error')
                                )
                            logger.info(f"Processed {len(memory_results)} memory extractions")
                        except Exception as e:
                            logger.error(f"Memory extraction failed: {e}", exc_info=True)
                            self.log_action(
                                thread_id=thread_id,
                                email_log_id=email_log_id,
                                action_type='memory',
                                action='add',
                                intent='Extract memories from email',
                                status='failed',
                                error_message=str(e)
                            )

                    # STEP 2: Extract and execute schedule actions SYNCHRONOUSLY
                    if thread_id and email_log_id:
                        try:
                            logger.info("Extracting schedule events synchronously...")
                            schedule_results = self.extract_and_manage_schedule_sync(
                                user_message=body,
                                user_name=mapped_user or sender_email
                            )
                            # Log each schedule action
                            for result in schedule_results:
                                self.log_action(
                                    thread_id=thread_id,
                                    email_log_id=email_log_id,
                                    action_type='schedule',
                                    action=result.get('action', 'add').lower(),
                                    intent=result.get('title', 'Schedule management'),
                                    status='success' if result.get('saved') else 'failed',
                                    details=result,
                                    error_message=result.get('error')
                                )
                            logger.info(f"Processed {len(schedule_results)} schedule actions")
                        except Exception as e:
                            logger.error(f"Schedule extraction failed: {e}", exc_info=True)
                            self.log_action(
                                thread_id=thread_id,
                                email_log_id=email_log_id,
                                action_type='schedule',
                                action='add',
                                intent='Extract schedule from email',
                                status='failed',
                                error_message=str(e)
                            )

                    # STEP 3: Generate AI reply with thread context (includes action results)
                    reply_text = self.generate_ai_reply(
                        sender_email, subject, body, settings,
                        thread_id=thread_id,
                        attachments_analysis=attachments_analysis
                    )

                    # Extract and track entities in background (non-blocking)
                    if reply_text and mapped_user:
                        threading.Thread(
                            target=self.extract_and_save_entities,
                            args=(body, reply_text, mapped_user),
                            daemon=True
                        ).start()

                    if reply_text:
                        # Send reply (will be logged inside send_reply_email)
                        success = self.send_reply_email(
                            settings,
                            sender_email,
                            subject,
                            reply_text,
                            in_reply_to=message_id,
                            references=f"{references} {message_id}".strip(),
                            mapped_user=mapped_user,
                            thread_id=thread_id
                        )

                        if success:
                            logger.info(f"✅ Successfully replied to {sender_email}")

                            # Save assistant message to thread history
                            # Note: send_reply_email returns the email_log_id, we need to modify it
                            if thread_id:
                                # For now, log without email_log_id from send_reply_email
                                # We'll enhance this by modifying send_reply_email to return log_id
                                self.save_thread_message(
                                    thread_id=thread_id,
                                    email_log_id=None,  # TODO: get from send_reply_email
                                    role='assistant',
                                    message=reply_text
                                )

                            # Cleanup temporary attachments
                            if temp_dir:
                                try:
                                    self.cleanup_attachments(temp_dir)
                                except Exception as e:
                                    logger.error(f"Error cleaning up attachments: {e}")
                        else:
                            logger.error(f"❌ Failed to send reply to {sender_email}")

                            # Cleanup temporary attachments even if reply failed
                            if temp_dir:
                                try:
                                    self.cleanup_attachments(temp_dir)
                                except Exception as e:
                                    logger.error(f"Error cleaning up attachments: {e}")
                    else:
                        logger.error(f"❌ Failed to generate reply for email from {sender_email} - Ollama timeout")

                        # Log failed reply attempt
                        self.log_email(
                            direction='sent',
                            email_type='reply',
                            from_email=settings['from_email'],
                            to_email=sender_email,
                            subject=f"Re: {subject}" if not subject.lower().startswith('re:') else subject,
                            body=f"Failed to generate reply. Original message: {body[:500]}",
                            status='error',
                            error_message='Ollama API failed after 3 retry attempts - reply generation timed out. Click retry to attempt again.',
                            mapped_user=mapped_user,
                            thread_id=thread_id
                        )

                        # Cleanup temporary attachments even after failed reply
                        if temp_dir:
                            try:
                                self.cleanup_attachments(temp_dir)
                            except Exception as e:
                                logger.error(f"Error cleaning up attachments: {e}")

                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}", exc_info=True)
                    
                    # Cleanup temporary attachments on exception
                    if 'temp_dir' in locals() and temp_dir:
                        try:
                            self.cleanup_attachments(temp_dir)
                        except Exception as cleanup_e:
                            logger.error(f"Error cleaning up attachments after exception: {cleanup_e}")

            # Update last checked timestamp
            self.update_last_checked()

        except Exception as e:
            logger.error(f"Error checking emails: {e}", exc_info=True)
        finally:
            try:
                imap.close()
                imap.logout()
            except:
                pass

    def run(self):
        """Main service loop"""
        logger.info("Email Summary Service started")
        logger.info(f"Checking every {CHECK_INTERVAL_SECONDS} seconds for scheduled emails")

        last_email_check = datetime.now()

        while True:
            try:
                # Get email settings
                settings = self.get_email_settings()

                if settings:
                    # Check if we should send daily summary
                    if self.should_send_summary(settings):
                        self.send_daily_summary(settings)
                    
                    # Check for events needing reminders and send them
                    self.check_and_send_reminders(settings)

                    # Check for incoming emails and send AI replies
                    if settings['imap_enabled'] and settings['auto_reply_enabled']:
                        # Use the configured check interval for IMAP
                        check_interval = settings['check_interval_seconds']
                        time_since_last_check = (datetime.now() - last_email_check).total_seconds()

                        if time_since_last_check >= check_interval:
                            self.check_and_reply_to_emails(settings)
                            last_email_check = datetime.now()

                # Sleep before next check
                time.sleep(CHECK_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                logger.info("Service stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(CHECK_INTERVAL_SECONDS)

        # Close database connection
        if self.db_conn:
            self.db_conn.close()
            logger.info("Database connection closed")


# Flask API for manual triggers
app = Flask(__name__)
email_service = None

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'email-summary'}), 200

@app.route('/api/send-summary', methods=['POST'])
def api_send_summary():
    """Manually trigger a daily summary send"""
    try:
        if not email_service:
            return jsonify({'error': 'Service not initialized'}), 500

        settings = email_service.get_email_settings()
        if not settings:
            return jsonify({'error': 'Email settings not configured'}), 400

        # Send summary in background thread
        def send_in_background():
            try:
                email_service.send_daily_summary(settings)
            except Exception as e:
                logger.error(f"Error sending manual summary: {e}")

        threading.Thread(target=send_in_background, daemon=True).start()

        return jsonify({'success': True, 'message': 'Summary generation started'}), 200

    except Exception as e:
        logger.error(f"Error in manual summary endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/email/retry/<int:email_log_id>', methods=['POST'])
def api_retry_email(email_log_id):
    """Retry generating and sending a failed email reply"""
    try:
        if not email_service:
            return jsonify({'error': 'Service not initialized'}), 500

        settings = email_service.get_email_settings()
        if not settings:
            return jsonify({'error': 'Email settings not configured'}), 400

        logger.info(f"Retry request received for email_log_id: {email_log_id}")

        # Get the failed email log entry
        conn = email_service.get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, thread_id, to_email, subject, from_email, mapped_user
                FROM email_logs
                WHERE id = %s AND direction = 'sent' AND status = 'error'
            """, (email_log_id,))
            failed_email = cursor.fetchone()

        if not failed_email:
            return jsonify({'error': 'Failed email not found or not in error status'}), 404

        _, thread_id, sender_email, subject, from_email, mapped_user = failed_email

        if not thread_id:
            return jsonify({'error': 'Cannot retry: email has no thread_id'}), 400

        # Get the original incoming email from the same thread
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT full_body, subject, from_email, to_email, attachments_metadata
                FROM email_logs
                WHERE thread_id = %s AND direction = 'received'
                ORDER BY timestamp DESC
                LIMIT 1
            """, (thread_id,))
            incoming_email = cursor.fetchone()

        if not incoming_email:
            return jsonify({'error': 'Cannot find original incoming email for this thread'}), 404

        original_body, original_subject, original_sender, original_recipient, attachments_metadata_json = incoming_email

        # Parse attachments metadata if present
        attachments_analysis = None
        if attachments_metadata_json:
            try:
                attachments_metadata = json.loads(attachments_metadata_json)
                # Convert metadata back to analysis format (without file paths since they're temporary)
                attachments_analysis = []
                for att in attachments_metadata:
                    attachments_analysis.append({
                        'filename': att.get('filename', 'unknown'),
                        'type': att.get('type', 'unknown'),
                        'size': att.get('size', 0),
                        'analysis_text': att.get('analysis_preview', '')
                    })
            except:
                pass

        # Retry generating the reply in background
        def retry_in_background():
            try:
                logger.info(f"Retrying email reply generation for thread_id={thread_id}")

                # Generate AI reply
                reply_text = email_service.generate_ai_reply(
                    sender=original_sender,
                    subject=original_subject,
                    body=original_body,
                    settings=settings,
                    thread_id=thread_id,
                    attachments_analysis=attachments_analysis
                )

                if reply_text:
                    # Extract and track entities in background (non-blocking)
                    if mapped_user:
                        threading.Thread(
                            target=email_service.extract_and_save_entities,
                            args=(original_body, reply_text, mapped_user),
                            daemon=True
                        ).start()

                    # Send the reply
                    success = email_service.send_reply_email(
                        settings=settings,
                        to_email=original_sender,
                        subject=original_subject,
                        reply_text=reply_text,
                        in_reply_to=None,  # We don't have message_id stored
                        references=None,
                        mapped_user=mapped_user,
                        thread_id=thread_id
                    )

                    if success:
                        logger.info(f"✅ Successfully retried and sent reply for thread_id={thread_id}")

                        # Save assistant message to thread history
                        if thread_id:
                            email_service.save_thread_message(
                                thread_id=thread_id,
                                email_log_id=None,
                                role='assistant',
                                message=reply_text
                            )

                        # Update the original failed email log to mark it as retried
                        conn = email_service.get_db_connection()
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                UPDATE email_logs
                                SET error_message = error_message || ' [Retried successfully]'
                                WHERE id = %s
                            """, (email_log_id,))
                        conn.commit()
                    else:
                        logger.error(f"❌ Retry failed: Could not send email for thread_id={thread_id}")
                else:
                    logger.error(f"❌ Retry failed: Ollama timeout for thread_id={thread_id}")

            except Exception as e:
                logger.error(f"Error in retry background task: {e}", exc_info=True)

        threading.Thread(target=retry_in_background, daemon=True).start()

        return jsonify({
            'success': True,
            'message': 'Retry started in background',
            'thread_id': thread_id,
            'email_log_id': email_log_id
        }), 200

    except Exception as e:
        logger.error(f"Error in retry endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def run_service_loop():
    """Run the email service loop in background thread"""
    email_service.run()

if __name__ == '__main__':
    # Initialize service
    email_service = EmailSummaryService()
    
    # Start service loop in background thread
    service_thread = threading.Thread(target=run_service_loop, daemon=True)
    service_thread.start()
    
    # Run Flask API
    logger.info("Starting Flask API on port 5006")
    app.run(host='0.0.0.0', port=5006, debug=False)
