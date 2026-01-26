#!/usr/bin/env python3
"""
Simplified Memory Management System for Mumble AI Bot

This module provides a memory management system that combines:
- Redis for fast caching and session management
- PostgreSQL for structured data storage
- Entity tracking and resolution
- Memory consolidation and summarization
- Multi-turn conversation understanding

Note: ChromaDB integration will be added later once dependency issues are resolved.
"""

import os
import json
import time
import uuid
import hashlib
import logging
import threading
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict, deque

import redis
import psycopg2
from psycopg2 import pool
import numpy as np
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ConversationPhase(Enum):
    """Conversation state phases"""
    GREETING = "greeting"
    QUERY = "query"
    CLARIFICATION = "clarification"
    RESOLUTION = "resolution"
    IDLE = "idle"


@dataclass
class Entity:
    """Represents a named entity"""
    text: str
    entity_type: str
    canonical_id: Optional[str] = None
    confidence: float = 1.0
    context: str = ""
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


class CacheLayer:
    """Redis-based caching layer for fast access to recent data"""
    
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.connection_pool = redis.ConnectionPool.from_url(redis_url)
        
    def cache_session(self, user: str, session_id: str, context: Dict, ttl: int = 1800):
        """Cache current session data"""
        try:
            key = f"session:{user}:{session_id}"
            self.redis_client.setex(key, ttl, json.dumps(context))
        except Exception as e:
            logger.error(f"Error caching session: {e}")
    
    def get_session(self, user: str, session_id: str) -> Optional[Dict]:
        """Retrieve cached session data"""
        try:
            key = f"session:{user}:{session_id}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error retrieving session: {e}")
            return None
    
    def cache_entities(self, user: str, entities: List[Entity], ttl: int = 3600):
        """Cache recently mentioned entities"""
        try:
            key = f"entities:{user}"
            entity_data = [
                {
                    'text': e.text,
                    'type': e.entity_type,
                    'canonical_id': e.canonical_id,
                    'confidence': e.confidence,
                    'context': e.context
                }
                for e in entities
            ]
            self.redis_client.setex(key, ttl, json.dumps(entity_data))
        except Exception as e:
            logger.error(f"Error caching entities: {e}")
    
    def get_entities(self, user: str) -> List[Entity]:
        """Retrieve cached entities"""
        try:
            key = f"entities:{user}"
            data = self.redis_client.get(key)
            if data:
                entity_data = json.loads(data)
                return [
                    Entity(
                        text=e['text'],
                        entity_type=e['type'],
                        canonical_id=e.get('canonical_id'),
                        confidence=e.get('confidence', 1.0),
                        context=e.get('context', '')
                    )
                    for e in entity_data
                ]
            return []
        except Exception as e:
            logger.error(f"Error retrieving entities: {e}")
            return []
    
    def cache_hot_memories(self, user: str, memories: List[Dict], ttl: int = 3600):
        """Cache frequently accessed memories"""
        try:
            key = f"hot_memories:{user}"
            self.redis_client.setex(key, ttl, json.dumps(memories))
        except Exception as e:
            logger.error(f"Error caching hot memories: {e}")
    
    def get_hot_memories(self, user: str) -> List[Dict]:
        """Retrieve cached hot memories"""
        try:
            key = f"hot_memories:{user}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else []
        except Exception as e:
            logger.error(f"Error retrieving hot memories: {e}")
            return []
    
    def invalidate_user_cache(self, user: str):
        """Clear all user caches"""
        try:
            pattern = f"*:{user}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Error invalidating user cache: {e}")


class EntityTracker:
    """Entity extraction and tracking system"""
    
    def __init__(self, db_pool, ollama_url: str):
        self.db_pool = db_pool
        self.ollama_url = ollama_url
    
    def extract_entities(self, text: str, ollama_url: str) -> List[Entity]:
        """Extract entities from text using Ollama"""
        try:
            prompt = f"""Extract named entities from this text:
"{text}"

Return JSON array of entities:
[{{"text": "John Smith", "type": "PERSON", "context": "user's brother"}},
 {{"text": "New York", "type": "PLACE", "context": "city they visited"}}]

Types: PERSON, PLACE, ORGANIZATION, DATE, TIME, EVENT, OTHER
Only return the JSON array, nothing else."""

            response = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                entities_text = result.get('response', '').strip()
                
                # Try to parse JSON
                try:
                    entities_data = json.loads(entities_text)
                    entities = []
                    for entity_data in entities_data:
                        entity = Entity(
                            text=entity_data.get('text', ''),
                            entity_type=entity_data.get('type', 'OTHER'),
                            context=entity_data.get('context', ''),
                            confidence=0.8
                        )
                        entities.append(entity)
                    return entities
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse entity JSON: {entities_text}")
                    return []
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    def resolve_entity(self, entity_text: str, user: str) -> Optional[str]:
        """Resolve entity to canonical ID"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cur:
                    # Look for similar entities
                    cur.execute("""
                        SELECT canonical_id, entity_text, confidence
                        FROM entity_mentions 
                        WHERE user_name = %s AND entity_text ILIKE %s
                        ORDER BY confidence DESC
                        LIMIT 1
                    """, (user, f"%{entity_text}%"))
                    
                    result = cur.fetchone()
                    if result:
                        canonical_id, existing_text, confidence = result
                        # Check similarity
                        similarity = SequenceMatcher(None, entity_text.lower(), existing_text.lower()).ratio()
                        if similarity > 0.8:
                            return canonical_id
                    
                    # Create new canonical ID
                    canonical_id = str(uuid.uuid4())
                    return canonical_id
                    
        except Exception as e:
            logger.error(f"Error resolving entity: {e}")
            return None
    
    def store_entity(self, entity: Entity, user: str, message_id: int):
        """Store entity in database"""
        try:
            canonical_id = self.resolve_entity(entity.text, user)
            if not canonical_id:
                canonical_id = str(uuid.uuid4())
            
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO entity_mentions 
                        (user_name, entity_text, canonical_id, entity_type, message_id, confidence, context_info)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user, entity.text, canonical_id, entity.entity_type,
                        message_id, entity.confidence, entity.context
                    ))
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Error storing entity: {e}")
    
    def get_entity_history(self, canonical_id: str, user: str) -> List[Dict]:
        """Get all mentions of an entity"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT em.entity_text, em.entity_type, em.context_info, em.created_at,
                               ch.message, ch.role
                        FROM entity_mentions em
                        JOIN conversation_history ch ON em.message_id = ch.id
                        WHERE em.canonical_id = %s AND em.user_name = %s
                        ORDER BY em.created_at DESC
                        LIMIT 10
                    """, (canonical_id, user))
                    
                    results = cur.fetchall()
                    return [
                        {
                            'text': row[0],
                            'type': row[1],
                            'context': row[2],
                            'timestamp': row[3],
                            'message': row[4],
                            'role': row[5]
                        }
                        for row in results
                    ]
                    
        except Exception as e:
            logger.error(f"Error getting entity history: {e}")
            return []


class MemoryConsolidator:
    """Memory consolidation and summarization system"""
    
    def __init__(self, db_pool, ollama_url: str):
        self.db_pool = db_pool
        self.ollama_url = ollama_url
    
    def consolidate_old_memories(self, user: str, cutoff_days: int = 7):
        """Consolidate old memories into summaries"""
        try:
            cutoff_date = datetime.now() - timedelta(days=cutoff_days)
            
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cur:
                    # Get old unconsolidated messages
                    cur.execute("""
                        SELECT id, message, role, timestamp
                        FROM conversation_history
                        WHERE user_name = %s AND timestamp < %s 
                        AND consolidated_at IS NULL
                        ORDER BY timestamp
                        LIMIT 50
                    """, (user, cutoff_date))
                    
                    old_messages = cur.fetchall()
                    
                    if len(old_messages) < 10:
                        return  # Not enough messages to consolidate
                    
                    # Group into chunks of 15 messages
                    chunks = [old_messages[i:i+15] for i in range(0, len(old_messages), 15)]
                    
                    for chunk in chunks:
                        summary = self.summarize_conversation_chunk(chunk)
                        if summary:
                            # Store summary
                            summary_id = str(uuid.uuid4())
                            cur.execute("""
                                INSERT INTO memory_consolidation_log
                                (user_name, messages_consolidated, summaries_created, tokens_saved_estimate, cutoff_date)
                                VALUES (%s, %s, 1, %s, %s)
                            """, (user, len(chunk), len(summary) * 2, cutoff_date.date()))
                            
                            # Mark messages as consolidated
                            message_ids = [msg[0] for msg in chunk]
                            cur.execute("""
                                UPDATE conversation_history
                                SET consolidated_at = %s, consolidated_summary_id = %s
                                WHERE id = ANY(%s)
                            """, (datetime.now(), summary_id, message_ids))
                            
                            conn.commit()
                            logger.info(f"Consolidated {len(chunk)} messages for user {user}")
                            
        except Exception as e:
            logger.error(f"Error consolidating memories: {e}")
    
    def summarize_conversation_chunk(self, messages: List[Tuple]) -> Optional[str]:
        """Summarize a chunk of conversation messages"""
        try:
            # Format messages for summarization
            conversation_text = ""
            for msg_id, message, role, timestamp in messages:
                conversation_text += f"{role}: {message}\n"
            
            prompt = f"""Summarize this conversation in 2-3 sentences, focusing on key topics and decisions:

{conversation_text}

Summary:"""

            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error summarizing conversation: {e}")
            return None


class MemoryManager:
    """Main memory management coordinator"""
    
    def __init__(self, chromadb_url: str, redis_url: str, db_pool, ollama_url: str):
        self.redis_url = redis_url
        self.db_pool = db_pool
        self.ollama_url = ollama_url
        
        # Initialize components
        self.cache = CacheLayer(redis_url)
        self.entity_tracker = EntityTracker(db_pool, ollama_url)
        self.consolidator = MemoryConsolidator(db_pool, ollama_url)
        
        logger.info("MemoryManager initialized (simplified version without ChromaDB)")
    
    def store_message(self, user: str, message: str, role: str, session_id: str = None, message_type: str = "text"):
        """Store a message in the database"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO conversation_history 
                        (user_name, user_session, message_type, role, message, session_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (user, session_id or str(uuid.uuid4()), message_type, role, message, session_id))
                    
                    message_id = cur.fetchone()[0]
                    conn.commit()
                    
                    # Cache in Redis
                    session_data = {
                        'last_message': message,
                        'last_role': role,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.cache.cache_session(user, session_id or "default", session_data)
                    
                    return message_id
                    
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            return None
    
    def get_conversation_context(self, user: str, query: str, session_id: str = None, 
                                include_entities: bool = True, include_consolidated: bool = True) -> Dict:
        """Get comprehensive conversation context"""
        try:
            context = {
                'memories': [],
                'entities': [],
                'session': [],
                'consolidated': []
            }
            
            # Get recent messages from database
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cur:
                    # Recent messages (last 10)
                    cur.execute("""
                        SELECT message, role, timestamp
                        FROM conversation_history
                        WHERE user_name = %s
                        ORDER BY timestamp DESC
                        LIMIT 10
                    """, (user,))
                    
                    recent_messages = cur.fetchall()
                    context['memories'] = [
                        {
                            'content': msg[0],
                            'metadata': {'role': msg[1], 'timestamp': msg[2].isoformat()}
                        }
                        for msg in recent_messages
                    ]
                    
                    # Get entities if requested
                    if include_entities:
                        cur.execute("""
                            SELECT DISTINCT entity_text, entity_type, context_info
                            FROM entity_mentions
                            WHERE user_name = %s
                            ORDER BY created_at DESC
                            LIMIT 20
                        """, (user,))
                        
                        entity_data = cur.fetchall()
                        context['entities'] = [
                            Entity(
                                text=row[0],
                                entity_type=row[1],
                                context=row[2] or ''
                            )
                            for row in entity_data
                        ]
            
            # Get cached session data
            if session_id:
                session_data = self.cache.get_session(user, session_id)
                if session_data:
                    context['session'] = [session_data]
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return {'memories': [], 'entities': [], 'session': [], 'consolidated': []}
    
    def extract_and_track_entities(self, user_message: str, bot_response: str, user: str):
        """Extract and track entities from conversation"""
        try:
            # Extract entities from both messages
            combined_text = f"{user_message} {bot_response}"
            entities = self.entity_tracker.extract_entities(combined_text, self.ollama_url)
            
            if entities:
                # Get the latest message ID for this user
                with self.db_pool.getconn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id FROM conversation_history
                            WHERE user_name = %s
                            ORDER BY timestamp DESC
                            LIMIT 1
                        """, (user,))
                        
                        result = cur.fetchone()
                        if result:
                            message_id = result[0]
                            
                            # Store entities
                            for entity in entities:
                                self.entity_tracker.store_entity(entity, user, message_id)
                            
                            # Cache entities
                            self.cache.cache_entities(user, entities)
                            
        except Exception as e:
            logger.error(f"Error extracting and tracking entities: {e}")
    
    def run_consolidation_job(self):
        """Run memory consolidation in background"""
        try:
            # Get all users
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT user_name FROM conversation_history")
                    users = [row[0] for row in cur.fetchall()]
            
            # Consolidate for each user
            for user in users:
                self.consolidator.consolidate_old_memories(user)
                
        except Exception as e:
            logger.error(f"Error running consolidation job: {e}")

