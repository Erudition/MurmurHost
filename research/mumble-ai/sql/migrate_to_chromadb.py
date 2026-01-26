#!/usr/bin/env python3
"""
Migrate existing conversation_history to ChromaDB

This script migrates all existing conversation history from PostgreSQL
to ChromaDB for the new smart memory system.
"""

import os
import sys
import psycopg2
import chromadb
import requests
import json
from datetime import datetime
from typing import List, Optional

# Add parent directory to path to import memory_manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'mumble_ai'),
            user=os.getenv('DB_USER', 'mumbleai'),
            password=os.getenv('DB_PASSWORD', 'mumbleai123')
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def generate_embedding(text: str, ollama_url: str) -> Optional[List[float]]:
    """Generate embedding using Ollama"""
    try:
        response = requests.post(
            f"{ollama_url}/api/embeddings",
            json={'model': 'nomic-embed-text:latest', 'prompt': text},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json().get('embedding', [])
        else:
            print(f"Error generating embedding: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def migrate_conversations():
    """Migrate conversation history to ChromaDB"""
    print("Starting migration of conversation history to ChromaDB...")
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    # Connect to ChromaDB
    try:
        chromadb_url = os.getenv('CHROMADB_URL', 'http://localhost:8000')
        host = chromadb_url.replace('http://', '').split(':')[0]
        port = int(chromadb_url.split(':')[-1])
        
        client = chromadb.HttpClient(host=host, port=port)
        collection = client.get_or_create_collection(
            name="conversations",
            metadata={"description": "Raw conversation messages with embeddings"}
        )
        print(f"Connected to ChromaDB at {host}:{port}")
    except Exception as e:
        print(f"Error connecting to ChromaDB: {e}")
        return False
    
    # Get Ollama URL
    ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    
    try:
        cursor = conn.cursor()
        
        # Get all messages that don't have embeddings yet
        cursor.execute("""
            SELECT id, user_name, message, role, message_type, timestamp, 
                   importance_score, session_id, embedding
            FROM conversation_history 
            WHERE embedding IS NULL
            ORDER BY id
        """)
        
        messages = cursor.fetchall()
        total_messages = len(messages)
        
        if total_messages == 0:
            print("No messages need migration (all already have embeddings)")
            return True
        
        print(f"Found {total_messages} messages to migrate")
        
        # Process messages in batches
        batch_size = 50
        processed = 0
        failed = 0
        
        for i in range(0, total_messages, batch_size):
            batch = messages[i:i + batch_size]
            batch_ids = []
            batch_embeddings = []
            batch_metadatas = []
            batch_documents = []
            
            print(f"Processing batch {i//batch_size + 1}/{(total_messages + batch_size - 1)//batch_size}...")
            
            for msg in batch:
                msg_id, user_name, message, role, message_type, timestamp, importance_score, session_id, existing_embedding = msg
                
                # Skip if already has embedding
                if existing_embedding:
                    continue
                
                # Generate embedding
                embedding = generate_embedding(message, ollama_url)
                if not embedding:
                    print(f"Failed to generate embedding for message {msg_id}")
                    failed += 1
                    continue
                
                # Prepare data for ChromaDB
                batch_ids.append(str(msg_id))
                batch_embeddings.append(embedding)
                batch_metadatas.append({
                    'user_name': user_name,
                    'role': role,
                    'message_type': message_type or 'text',
                    'timestamp': timestamp.isoformat() if timestamp else datetime.now().isoformat(),
                    'importance_score': importance_score or 0.5,
                    'session_id': session_id or ''
                })
                batch_documents.append(message)
            
            # Store batch in ChromaDB
            if batch_ids:
                try:
                    collection.add(
                        ids=batch_ids,
                        embeddings=batch_embeddings,
                        metadatas=batch_metadatas,
                        documents=batch_documents
                    )
                    processed += len(batch_ids)
                    print(f"  Stored {len(batch_ids)} messages in ChromaDB")
                except Exception as e:
                    print(f"  Error storing batch in ChromaDB: {e}")
                    failed += len(batch_ids)
            
            # Update PostgreSQL with embeddings
            for j, msg in enumerate(batch):
                msg_id = msg[0]
                if j < len(batch_embeddings):
                    try:
                        cursor.execute("""
                            UPDATE conversation_history 
                            SET embedding = %s 
                            WHERE id = %s
                        """, (batch_embeddings[j], msg_id))
                    except Exception as e:
                        print(f"  Error updating PostgreSQL for message {msg_id}: {e}")
            
            # Commit batch
            conn.commit()
        
        cursor.close()
        conn.close()
        
        print(f"\nMigration complete!")
        print(f"  Processed: {processed} messages")
        print(f"  Failed: {failed} messages")
        print(f"  Total: {total_messages} messages")
        
        return failed == 0
        
    except Exception as e:
        print(f"Error during migration: {e}")
        if conn:
            conn.close()
        return False

def verify_migration():
    """Verify the migration was successful"""
    print("\nVerifying migration...")
    
    # Check PostgreSQL
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Count messages with embeddings
        cursor.execute("SELECT COUNT(*) FROM conversation_history WHERE embedding IS NOT NULL")
        with_embeddings = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversation_history")
        total_messages = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print(f"PostgreSQL: {with_embeddings}/{total_messages} messages have embeddings")
        
        # Check ChromaDB
        chromadb_url = os.getenv('CHROMADB_URL', 'http://localhost:8000')
        host = chromadb_url.replace('http://', '').split(':')[0]
        port = int(chromadb_url.split(':')[-1])
        
        client = chromadb.HttpClient(host=host, port=port)
        collection = client.get_collection("conversations")
        
        count = collection.count()
        print(f"ChromaDB: {count} messages stored")
        
        if with_embeddings == count:
            print("✓ Migration verification successful!")
            return True
        else:
            print("✗ Migration verification failed - counts don't match")
            return False
            
    except Exception as e:
        print(f"Error during verification: {e}")
        return False

def main():
    """Main migration function"""
    print("ChromaDB Migration Script")
    print("=" * 50)
    
    # Check if ChromaDB is running
    chromadb_url = os.getenv('CHROMADB_URL', 'http://localhost:8000')
    try:
        response = requests.get(f"{chromadb_url}/api/v1/heartbeat", timeout=5)
        if response.status_code != 200:
            print(f"ChromaDB is not responding at {chromadb_url}")
            return False
    except Exception as e:
        print(f"Cannot connect to ChromaDB at {chromadb_url}: {e}")
        return False
    
    # Check if Ollama is running
    ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code != 200:
            print(f"Ollama is not responding at {ollama_url}")
            return False
    except Exception as e:
        print(f"Cannot connect to Ollama at {ollama_url}: {e}")
        return False
    
    # Run migration
    success = migrate_conversations()
    
    if success:
        # Verify migration
        verify_migration()
        print("\nMigration completed successfully!")
    else:
        print("\nMigration failed!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

