#!/usr/bin/env python3
"""
Smart Memory Management System for Mumble AI Bot

This module provides a comprehensive memory management system that combines:
- ChromaDB for vector storage and semantic search
- Redis for fast caching and session management
- PostgreSQL for structured data storage
- Entity tracking and resolution
- Memory consolidation and summarization
- Multi-turn conversation understanding
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
from functools import wraps

import chromadb
import redis
import psycopg2
from psycopg2 import pool
import numpy as np
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def db_retry(max_retries=3, delay=1, backoff=2):
    """Decorator for database operations with exponential backoff retry"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Database operation failed after {max_retries} attempts: {e}")
            raise last_exception
        return wrapper
    return decorator


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
    canonical_id: str
    confidence: float
    context: str
    first_seen: datetime
    last_seen: datetime
    mentions: List[str]


@dataclass
class ConversationContext:
    """Represents conversation context"""
    user: str
    session_id: str
    phase: ConversationPhase
    current_topic: str
    entities: List[Entity]
    recent_messages: List[Dict]
    topic_history: deque


class VectorStore:
    """ChromaDB wrapper for vector storage and semantic search"""
    
    def __init__(self, chromadb_url: str):
        self.client = chromadb.HttpClient(host=chromadb_url.replace('http://', '').split(':')[0], 
                                        port=int(chromadb_url.split(':')[-1]))
        
        # Create or get collections
        self.conversations = self.client.get_or_create_collection(
            name="conversations",
            metadata={"description": "Raw conversation messages with embeddings"}
        )
        
        self.consolidated_memories = self.client.get_or_create_collection(
            name="consolidated_memories", 
            metadata={"description": "Summarized/compressed older memories"}
        )
        
        self.entities = self.client.get_or_create_collection(
            name="entities",
            metadata={"description": "Named entities extracted from conversations"}
        )
        
        self.facts = self.client.get_or_create_collection(
            name="facts",
            metadata={"description": "Persistent facts about users"}
        )
        
        logger.info("VectorStore initialized with ChromaDB collections")
    
    def store_conversation(self, message_id: str, user: str, message: str, 
                          embedding: List[float], metadata: Dict) -> bool:
        """Store a conversation message in ChromaDB"""
        try:
            self.conversations.add(
                ids=[message_id],
                embeddings=[embedding],
                metadatas=[{
                    'user_name': user,
                    'role': metadata.get('role', 'user'),
                    'timestamp': metadata.get('timestamp', str(datetime.now())),
                    'message_type': metadata.get('message_type', 'text'),
                    'session_id': metadata.get('session_id', ''),
                    'importance_score': metadata.get('importance_score', 0.5)
                }],
                documents=[message]
            )
            return True
        except Exception as e:
            logger.error(f"Error storing conversation in ChromaDB: {e}")
            return False
    
    def semantic_search(self, embedding: List[float], user: str, top_k: int = 10, 
                       filters: Dict = None) -> List[Dict]:
        """Perform semantic search in ChromaDB"""
        try:
            where_clause = {"user_name": user}
            if filters:
                where_clause.update(filters)
            
            results = self.conversations.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=where_clause
            )
            
            # Format results
            formatted_results = []
            if results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    formatted_results.append({
                        'id': doc_id,
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else 0
                    })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def store_consolidated_memory(self, summary_id: str, summary: str, 
                                 embedding: List[float], metadata: Dict) -> bool:
        """Store consolidated memory summary"""
        try:
            self.consolidated_memories.add(
                ids=[summary_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[summary]
            )
            return True
        except Exception as e:
            logger.error(f"Error storing consolidated memory: {e}")
            return False
    
    def store_entity(self, entity_id: str, entity_text: str, entity_type: str,
                    embedding: List[float], metadata: Dict) -> bool:
        """Store entity in ChromaDB"""
        try:
            self.entities.add(
                ids=[entity_id],
                embeddings=[embedding],
                metadatas=[{
                    'entity_text': entity_text,
                    'entity_type': entity_type,
                    'user_name': metadata.get('user_name', ''),
                    'canonical_id': metadata.get('canonical_id', entity_id),
                    'confidence': metadata.get('confidence', 1.0),
                    'context': metadata.get('context', ''),
                    'first_seen': metadata.get('first_seen', str(datetime.now())),
                    'last_seen': metadata.get('last_seen', str(datetime.now()))
                }],
                documents=[entity_text]
            )
            return True
        except Exception as e:
            logger.error(f"Error storing entity: {e}")
            return False


class CacheLayer:
    """Redis wrapper for fast caching"""
    
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.connection_pool = redis.ConnectionPool.from_url(redis_url)
        logger.info("CacheLayer initialized with Redis")
    
    def cache_session(self, user: str, session_id: str, context: Dict, ttl: int = 1800) -> bool:
        """Cache current session (30 min default TTL)"""
        try:
            key = f"session:{user}:{session_id}"
            self.redis_client.setex(key, ttl, json.dumps(context, default=str))
            return True
        except Exception as e:
            logger.error(f"Error caching session: {e}")
            return False
    
    def get_session(self, user: str, session_id: str) -> Optional[Dict]:
        """Retrieve cached session"""
        try:
            key = f"session:{user}:{session_id}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def cache_entities(self, user: str, entities: List[Entity], ttl: int = 3600) -> bool:
        """Cache recently mentioned entities (1 hour default TTL)"""
        try:
            key = f"entities:{user}"
            entities_data = [{
                'text': e.text,
                'entity_type': e.entity_type,
                'canonical_id': e.canonical_id,
                'confidence': e.confidence,
                'context': e.context,
                'first_seen': e.first_seen.isoformat(),
                'last_seen': e.last_seen.isoformat()
            } for e in entities]
            self.redis_client.setex(key, ttl, json.dumps(entities_data))
            return True
        except Exception as e:
            logger.error(f"Error caching entities: {e}")
            return False
    
    def get_entities(self, user: str) -> List[Entity]:
        """Retrieve cached entities"""
        try:
            key = f"entities:{user}"
            data = self.redis_client.get(key)
            if not data:
                return []
            
            entities_data = json.loads(data)
            return [Entity(
                text=e['text'],
                entity_type=e['entity_type'],
                canonical_id=e['canonical_id'],
                confidence=e['confidence'],
                context=e['context'],
                first_seen=datetime.fromisoformat(e['first_seen']),
                last_seen=datetime.fromisoformat(e['last_seen']),
                mentions=[]
            ) for e in entities_data]
        except Exception as e:
            logger.error(f"Error getting entities: {e}")
            return []
    
    def cache_hot_memories(self, user: str, memories: List[Dict], ttl: int = 3600) -> bool:
        """Cache frequently accessed memories"""
        try:
            key = f"hot_memories:{user}"
            self.redis_client.setex(key, ttl, json.dumps(memories, default=str))
            return True
        except Exception as e:
            logger.error(f"Error caching hot memories: {e}")
            return False
    
    def get_hot_memories(self, user: str) -> List[Dict]:
        """Retrieve cached hot memories"""
        try:
            key = f"hot_memories:{user}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else []
        except Exception as e:
            logger.error(f"Error getting hot memories: {e}")
            return []
    
    def invalidate_user_cache(self, user: str) -> bool:
        """Clear all user caches"""
        try:
            pattern = f"*:{user}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Error invalidating user cache: {e}")
            return False


class EntityTracker:
    """Entity extraction and tracking system"""
    
    def __init__(self, ollama_url: str):
        self.ollama_url = ollama_url
        self.entity_cache = {}
        self.canonical_entities = {}  # Maps variants to canonical forms
    
    def extract_entities(self, user_message: str, assistant_message: str, 
                        ollama_url: str) -> List[Dict]:
        """Extract named entities using Ollama"""
        try:
            extract_prompt = f"""Extract named entities from this conversation:
User: {user_message}
Assistant: {assistant_message}

Return JSON array of entities:
[{{"text": "John Smith", "type": "PERSON", "context": "user's brother"}},
 {{"text": "New York", "type": "PLACE", "context": "city they visited"}}]

Types: PERSON, PLACE, ORGANIZATION, DATE, TIME, EVENT, OTHER
Only extract entities that are clearly mentioned. Return empty array if none found."""

            response = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    'model': 'llama3.2:latest',
                    'prompt': extract_prompt,
                    'stream': False,
                    'options': {'temperature': 0.1}
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('response', '')
                
                # Extract JSON from response
                import re
                json_match = re.search(r'\[.*\]', text, re.DOTALL)
                if json_match:
                    entities = json.loads(json_match.group())
                    return entities
                    
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
        
        return []
    
    def resolve_entity(self, entity_text: str, user: str) -> str:
        """Resolve entity to canonical form"""
        # Check if we already have a canonical form
        if entity_text in self.canonical_entities:
            return self.canonical_entities[entity_text]
        
        # Use string similarity to find similar entities
        best_match = None
        best_similarity = 0.0
        
        for canonical, variants in self.canonical_entities.items():
            for variant in variants:
                similarity = SequenceMatcher(None, entity_text.lower(), variant.lower()).ratio()
                if similarity > 0.8 and similarity > best_similarity:
                    best_match = canonical
                    best_similarity = similarity
        
        if best_match:
            self.canonical_entities[entity_text] = best_match
            return best_match
        
        # Create new canonical entity
        canonical_id = str(uuid.uuid4())
        self.canonical_entities[entity_text] = canonical_id
        return canonical_id
    
    def get_entity_history(self, entity_id: str, user: str, db_pool) -> List[Dict]:
        """Get all mentions of an entity"""
        try:
            conn = db_pool.getconn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT em.entity_text, em.context_info, ch.message, ch.timestamp
                FROM entity_mentions em
                JOIN conversation_history ch ON em.message_id = ch.id
                WHERE em.canonical_id = %s AND em.user_name = %s
                ORDER BY ch.timestamp DESC
            """, (entity_id, user))
            
            results = cursor.fetchall()
            cursor.close()
            db_pool.putconn(conn)
            
            return [{
                'entity_text': row[0],
                'context': row[1],
                'message': row[2],
                'timestamp': row[3]
            } for row in results]
            
        except Exception as e:
            logger.error(f"Error getting entity history: {e}")
            return []


class MemoryConsolidator:
    """Memory consolidation and summarization system"""
    
    def __init__(self, ollama_url: str, db_pool, generate_embedding_func):
        self.ollama_url = ollama_url
        self.db_pool = db_pool
        self.generate_embedding_func = generate_embedding_func
        self.consolidation_thread = None
        self.running = False
    
    def consolidate_old_memories(self, user: str, cutoff_days: int = 7) -> Dict:
        """Consolidate old memories for a user"""
        try:
            if not self.db_pool:
                logger.error("Database pool not initialized")
                return {'messages_consolidated': 0, 'summaries_created': 0}
                
            cutoff_date = datetime.now() - timedelta(days=cutoff_days)
            
            # Get old unconsolidated messages
            conn = self.db_pool.getconn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, message, role, timestamp
                FROM conversation_history
                WHERE user_name = %s 
                  AND timestamp < %s 
                  AND consolidated_at IS NULL
                ORDER BY timestamp ASC
            """, (user, cutoff_date))
            
            old_messages = cursor.fetchall()
            cursor.close()
            self.db_pool.putconn(conn)
            
            if not old_messages:
                return {'messages_consolidated': 0, 'summaries_created': 0}
            
            # Group into chunks of 10-20 messages
            chunks = []
            current_chunk = []
            
            for msg in old_messages:
                current_chunk.append(msg)
                if len(current_chunk) >= 15:  # Chunk size
                    chunks.append(current_chunk)
                    current_chunk = []
            
            if current_chunk:
                chunks.append(current_chunk)
            
            summaries_created = 0
            messages_consolidated = 0
            
            for chunk in chunks:
                # Summarize chunk
                summary = self.summarize_conversation_chunk(chunk)
                if summary:
                    # Generate embedding for summary
                    summary_embedding = self.generate_embedding_func(summary)
                    if summary_embedding:
                        # Store in consolidated_memories
                        summary_id = str(uuid.uuid4())
                        metadata = {
                            'user': user,
                            'original_message_ids': [str(msg[0]) for msg in chunk],
                            'date_range': (chunk[0][3].isoformat(), chunk[-1][3].isoformat()),
                            'message_count': len(chunk)
                        }
                        
                        # This would be called from VectorStore
                        # vector_store.store_consolidated_memory(summary_id, summary, summary_embedding, metadata)
                        
                        # Mark originals as consolidated
                        self.mark_as_consolidated([msg[0] for msg in chunk], summary_id)
                        
                        summaries_created += 1
                        messages_consolidated += len(chunk)
            
            return {
                'messages_consolidated': messages_consolidated,
                'summaries_created': summaries_created
            }
            
        except Exception as e:
            logger.error(f"Error consolidating memories: {e}")
            return {'messages_consolidated': 0, 'summaries_created': 0}
    
    def summarize_conversation_chunk(self, messages: List[Tuple]) -> Optional[str]:
        """Create concise summary of conversation chunk"""
        try:
            # Build conversation text
            conversation_text = ""
            for msg in messages:
                role = "User" if msg[2] == 'user' else "Assistant"
                conversation_text += f"{role}: {msg[1]}\n"
            
            summarize_prompt = f"""Summarize this conversation in 2-3 sentences, focusing on key topics and outcomes:

{conversation_text}

Summary:"""

            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    'model': 'llama3.2:latest',
                    'prompt': summarize_prompt,
                    'stream': False,
                    'options': {'temperature': 0.3}
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
                
        except Exception as e:
            logger.error(f"Error summarizing conversation: {e}")
        
        return None
    
    def mark_as_consolidated(self, message_ids: List[int], summary_id: str):
        """Mark messages as consolidated in PostgreSQL"""
        try:
            if not self.db_pool:
                logger.error("Database pool not initialized")
                return
                
            conn = self.db_pool.getconn()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE conversation_history 
                SET consolidated_at = %s, consolidated_summary_id = %s
                WHERE id = ANY(%s)
            """, (datetime.now(), summary_id, message_ids))
            
            conn.commit()
            cursor.close()
            self.db_pool.putconn(conn)

        except Exception as e:
            logger.error(f"Error marking messages as consolidated: {e}")
    
    def run_consolidation_job(self):
        """Background thread for periodic consolidation"""
        self.running = True
        while self.running:
            try:
                if not self.db_pool:
                    logger.error("Database pool not initialized")
                    time.sleep(60)  # Wait before retrying
                    continue
                    
                # Get all users
                conn = self.db_pool.getconn()
                cursor = conn.cursor()
                
                cursor.execute("SELECT DISTINCT user_name FROM conversation_history")
                users = [row[0] for row in cursor.fetchall()]

                cursor.close()
                self.db_pool.putconn(conn)
                
                # Consolidate for each user
                for user in users:
                    result = self.consolidate_old_memories(user)
                    if result['messages_consolidated'] > 0:
                        logger.info(f"Consolidated {result['messages_consolidated']} messages for {user}")
                
                # Sleep for 24 hours
                time.sleep(24 * 60 * 60)
                
            except Exception as e:
                logger.error(f"Error in consolidation job: {e}")
                time.sleep(60 * 60)  # Sleep 1 hour on error


class ConversationContext:
    """Multi-turn conversation understanding"""
    
    def __init__(self):
        self.conversation_states = {}  # user -> conversation state
    
    def track_conversation_state(self, user: str, session_id: str, message: str) -> ConversationPhase:
        """Detect conversation phase"""
        message_lower = message.lower()
        
        # Simple phase detection
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return ConversationPhase.GREETING
        elif '?' in message or any(word in message_lower for word in ['what', 'how', 'when', 'where', 'why', 'who']):
            return ConversationPhase.QUERY
        elif any(word in message_lower for word in ['clarify', 'explain', 'more', 'detail']):
            return ConversationPhase.CLARIFICATION
        elif any(word in message_lower for word in ['thanks', 'thank you', 'got it', 'understood']):
            return ConversationPhase.RESOLUTION
        else:
            return ConversationPhase.IDLE
    
    def resolve_coreferences(self, message: str, context: ConversationContext) -> str:
        """Resolve pronouns using entity tracker"""
        resolved = message
        
        # Get recent entities
        recent_entities = context.entities[-5:] if context.entities else []
        
        # Simple pronoun resolution
        if "he" in message.lower() or "his" in message.lower():
            person_entities = [e for e in recent_entities if e.entity_type == "PERSON"]
            if person_entities:
                person = person_entities[0].text
                resolved = resolved.replace("his", f"{person}'s")
                resolved = resolved.replace("he", person)
        
        if "she" in message.lower() or "her" in message.lower():
            person_entities = [e for e in recent_entities if e.entity_type == "PERSON"]
            if person_entities:
                person = person_entities[0].text
                resolved = resolved.replace("her", f"{person}'s")
                resolved = resolved.replace("she", person)
        
        return resolved
    
    def detect_topic_shift(self, new_message: str, recent_context: List[str]) -> bool:
        """Detect if topic has shifted using simple heuristics"""
        if not recent_context:
            return True
        
        # Simple keyword-based topic detection
        new_words = set(new_message.lower().split())
        recent_words = set(' '.join(recent_context).lower().split())
        
        # If less than 30% word overlap, consider it a topic shift
        overlap = len(new_words & recent_words) / len(new_words | recent_words) if new_words | recent_words else 0
        return overlap < 0.3


class MemoryManager:
    """Main memory management coordinator"""
    
    def __init__(self, chromadb_url: str, redis_url: str, db_pool, ollama_url: str):
        self.vector_store = VectorStore(chromadb_url)
        self.cache_layer = CacheLayer(redis_url)
        self.entity_tracker = EntityTracker(ollama_url)
        self.memory_consolidator = MemoryConsolidator(ollama_url, db_pool, self.generate_embedding)
        self.conversation_context = ConversationContext()
        self.db_pool = db_pool
        self.ollama_url = ollama_url
        
        # Start consolidation job
        self.memory_consolidator.consolidation_thread = threading.Thread(
            target=self.memory_consolidator.run_consolidation_job,
            daemon=True
        )
        self.memory_consolidator.consolidation_thread.start()
        
        logger.info("MemoryManager initialized with all components")
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={'model': 'nomic-embed-text:latest', 'prompt': text},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('embedding', [])
                
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
        
        return None
    
    def store_message(self, user: str, message: str, role: str, session_id: str = None,
                     message_type: str = 'text', importance_score: float = 0.5, user_session: int = 0) -> bool:
        """Store message in all three layers"""
        try:
            # Generate embedding
            embedding = self.generate_embedding(message)
            if not embedding:
                logger.warning("Failed to generate embedding, storing without vector")

            # Store in PostgreSQL
            if not self.db_pool:
                logger.error("Database pool not initialized")
                return False

            conn = self.db_pool.getconn()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO conversation_history
                (user_name, user_session, message, role, message_type, embedding, importance_score, session_id, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user, user_session, message, role, message_type, embedding, importance_score, session_id, datetime.now()))
            
            message_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            db_pool.putconn(conn)
            
            # Store in ChromaDB
            if embedding:
                metadata = {
                    'role': role,
                    'message_type': message_type,
                    'session_id': session_id or '',
                    'importance_score': importance_score,
                    'timestamp': datetime.now().isoformat()
                }
                self.vector_store.store_conversation(str(message_id), user, message, embedding, metadata)
            
            # Update cache
            self._update_session_cache(user, session_id, message, role)
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            return False
    
    def get_conversation_context(self, user: str, query: str, session_id: str = None,
                                include_entities: bool = True, include_consolidated: bool = True,
                                short_term_limit: int = 10, long_term_limit: int = 10,
                                semantic_ranking: bool = True) -> Dict:
        """Build comprehensive context from all sources"""
        try:
            context = {
                'entities': [],
                'memories': [],
                'session': [],
                'consolidated': []
            }

            # Get entities from cache
            if include_entities:
                context['entities'] = self.cache_layer.get_entities(user)

            # Get recent session messages with configurable limit
            if session_id:
                context['session'] = self._get_session_messages(user, session_id, limit=short_term_limit)

            # Get relevant memories using hybrid search with configurable limit
            if semantic_ranking:
                context['memories'] = self.hybrid_search(query, user, top_k=long_term_limit)
            else:
                # Simple recent message retrieval without semantic ranking
                context['memories'] = self._get_recent_messages(user, limit=long_term_limit)

            # Get consolidated memories if requested
            if include_consolidated:
                context['consolidated'] = self._get_consolidated_memories(user, query)

            return context

        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return {'entities': [], 'memories': [], 'session': [], 'consolidated': []}
    
    def hybrid_search(self, query: str, user: str, top_k: int = 10) -> List[Dict]:
        """Hybrid search combining semantic and keyword search"""
        try:
            # Generate embedding for query
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                return []
            
            # Semantic search in ChromaDB
            semantic_results = self.vector_store.semantic_search(
                query_embedding, user, top_k=20
            )
            
            # Keyword search in PostgreSQL
            keyword_results = self._keyword_search(query, user, top_k=20)
            
            # RRF fusion
            scores = {}
            
            # Semantic results (weight 0.7)
            for rank, result in enumerate(semantic_results):
                result_id = result['id']
                scores[result_id] = scores.get(result_id, 0) + 0.7 / (rank + 60)
            
            # Keyword results (weight 0.3)
            for rank, result in enumerate(keyword_results):
                result_id = result['id']
                scores[result_id] = scores.get(result_id, 0) + 0.3 / (rank + 60)
            
            # Sort by combined score and return top-k
            sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            
            # Get full results
            final_results = []
            for result_id, score in sorted_results:
                # Find in semantic results first, then keyword
                result = next((r for r in semantic_results if r['id'] == result_id), None)
                if not result:
                    result = next((r for r in keyword_results if r['id'] == result_id), None)
                
                if result:
                    result['hybrid_score'] = score
                    final_results.append(result)
            
            return final_results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    
    def _keyword_search(self, query: str, user: str, top_k: int) -> List[Dict]:
        """Keyword search in PostgreSQL"""
        try:
            if not self.db_pool:
                logger.error("Database pool not initialized")
                return []
                
            conn = self.db_pool.getconn()
            cursor = conn.cursor()
            
            # Simple keyword search using ILIKE
            keywords = query.split()
            where_conditions = []
            params = [user]
            
            for keyword in keywords:
                where_conditions.append("message ILIKE %s")
                params.append(f"%{keyword}%")
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT id, message, role, timestamp, importance_score
                FROM conversation_history
                WHERE user_name = %s AND ({where_clause})
                ORDER BY importance_score DESC, timestamp DESC
                LIMIT %s
            """, params + [top_k])
            
            results = cursor.fetchall()
            cursor.close()
            db_pool.putconn(conn)
            
            return [{
                'id': str(row[0]),
                'content': row[1],
                'metadata': {
                    'role': row[2],
                    'timestamp': row[3].isoformat(),
                    'importance_score': row[4]
                }
            } for row in results]
            
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []
    
    def _get_session_messages(self, user: str, session_id: str, limit: int = 10) -> List[Dict]:
        """Get recent session messages"""
        try:
            if not self.db_pool:
                logger.error("Database pool not initialized")
                return []

            conn = self.db_pool.getconn()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT role, message, message_type, timestamp
                FROM conversation_history
                WHERE user_name = %s AND session_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (user, session_id, limit))

            results = cursor.fetchall()
            cursor.close()
            self.db_pool.putconn(conn)

            return [{
                'role': row[0],
                'content': row[1],
                'message_type': row[2],
                'timestamp': row[3].isoformat()
            } for row in results]

        except Exception as e:
            logger.error(f"Error getting session messages: {e}")
            return []

    @db_retry(max_retries=3, delay=1, backoff=2)
    def _get_recent_messages(self, user: str, limit: int = 10) -> List[Dict]:
        """Get recent messages without semantic ranking"""
        try:
            if not self.db_pool:
                logger.error("Database pool not initialized")
                return []

            conn = self.db_pool.getconn()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT role, message, message_type, timestamp
                FROM conversation_history
                WHERE user_name = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (user, limit))

            results = cursor.fetchall()
            cursor.close()
            self.db_pool.putconn(conn)

            return [{
                'role': row[0],
                'content': row[1],
                'message_type': row[2],
                'timestamp': row[3].isoformat()
            } for row in results]

        except Exception as e:
            logger.error(f"Error getting recent messages: {e}")
            return []

    def _get_consolidated_memories(self, user: str, query: str) -> List[Dict]:
        """Get relevant consolidated memories"""
        # This would query the consolidated_memories collection
        # For now, return empty list
        return []
    
    def _update_session_cache(self, user: str, session_id: str, message: str, role: str):
        """Update session cache"""
        if not session_id:
            return
        
        try:
            # Get current session cache
            session_data = self.cache_layer.get_session(user, session_id) or {
                'messages': [],
                'last_activity': datetime.now().isoformat()
            }
            
            # Add new message
            session_data['messages'].append({
                'role': role,
                'content': message,
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep only last 10 messages
            session_data['messages'] = session_data['messages'][-10:]
            session_data['last_activity'] = datetime.now().isoformat()
            
            # Cache updated session
            self.cache_layer.cache_session(user, session_id, session_data)
            
        except Exception as e:
            logger.error(f"Error updating session cache: {e}")
    
    def extract_and_track_entities(self, user_message: str, assistant_message: str, user: str):
        """Extract and track entities from conversation"""
        try:
            # Extract entities
            entities = self.entity_tracker.extract_entities(
                user_message, assistant_message, self.ollama_url
            )
            
            if not entities:
                return
            
            # Process each entity
            for entity_data in entities:
                entity_text = entity_data.get('text', '')
                entity_type = entity_data.get('type', 'OTHER')
                context = entity_data.get('context', '')
                
                if not entity_text:
                    continue
                
                # Resolve to canonical form
                canonical_id = self.entity_tracker.resolve_entity(entity_text, user)
                
                # Generate embedding
                embedding = self.generate_embedding(entity_text)
                if not embedding:
                    continue
                
                # Store in ChromaDB
                entity_id = str(uuid.uuid4())
                metadata = {
                    'user_name': user,
                    'canonical_id': canonical_id,
                    'confidence': 1.0,
                    'context': context,
                    'first_seen': datetime.now().isoformat(),
                    'last_seen': datetime.now().isoformat()
                }
                
                self.vector_store.store_entity(entity_id, entity_text, entity_type, embedding, metadata)
                
                # Store in PostgreSQL
                if not self.db_pool:
                    logger.error("Database pool not initialized")
                    return
                    
                conn = self.db_pool.getconn()
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO entity_mentions 
                    (user_name, entity_text, canonical_id, entity_type, confidence, context_info)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user, entity_text, canonical_id, entity_type, 1.0, context))
                
                conn.commit()
                cursor.close()
                db_pool.putconn(conn)
            
            # Update entity cache
            cached_entities = self.cache_layer.get_entities(user)
            # Add new entities to cache (simplified)
            self.cache_layer.cache_entities(user, cached_entities)
            
        except Exception as e:
            logger.error(f"Error extracting and tracking entities: {e}")
    
    def shutdown(self):
        """Shutdown memory manager"""
        self.memory_consolidator.running = False
        if self.memory_consolidator.consolidation_thread:
            self.memory_consolidator.consolidation_thread.join(timeout=5)
        logger.info("MemoryManager shutdown complete")
