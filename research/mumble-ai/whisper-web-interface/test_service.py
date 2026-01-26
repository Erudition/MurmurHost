#!/usr/bin/env python3
"""
Test script for Whisper Web Interface service
"""

import requests
import json
import time
import os

# Configuration
BASE_URL = "http://localhost:5008"
TEST_AUDIO_FILE = "test_audio.wav"  # You'll need to provide this

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_upload():
    """Test file upload"""
    print("Testing file upload...")
    
    # Create a simple test audio file (1 second of silence)
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine
        
        # Generate 1 second of 440Hz tone
        tone = Sine(440).to_audio_segment(duration=1000)
        tone.export(TEST_AUDIO_FILE, format="wav")
        print(f"Created test audio file: {TEST_AUDIO_FILE}")
    except ImportError:
        print("❌ pydub not available for test audio generation")
        return False
    except Exception as e:
        print(f"❌ Error creating test audio: {e}")
        return False
    
    try:
        with open(TEST_AUDIO_FILE, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{BASE_URL}/api/upload", files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Upload successful")
            print(f"   Filename: {data.get('filename')}")
            print(f"   Size: {data.get('file_size_bytes')} bytes")
            print(f"   Duration: {data.get('duration_seconds')} seconds")
            return data
        else:
            print(f"❌ Upload failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return None

def test_transcribe(upload_data):
    """Test transcription"""
    print("Testing transcription...")
    
    if not upload_data or 'temp_path' not in upload_data:
        print("❌ No upload data available for transcription")
        return None
    
    try:
        response = requests.post(f"{BASE_URL}/api/transcribe", 
                               json=upload_data, 
                               timeout=300)  # 5 minutes timeout
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Transcription successful")
            print(f"   Language: {data.get('language')}")
            print(f"   Confidence: {data.get('language_probability', 0):.2%}")
            print(f"   Processing time: {data.get('processing_time_seconds', 0):.1f}s")
            print(f"   Text preview: {data.get('transcription_text', '')[:100]}...")
            return data
        else:
            print(f"❌ Transcription failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return None

def test_summarize(transcription_data):
    """Test summarization"""
    print("Testing summarization...")
    
    if not transcription_data:
        print("❌ No transcription data available for summarization")
        return None
    
    try:
        payload = {
            'transcription_id': transcription_data.get('transcription_id'),
            'transcription_text': transcription_data.get('transcription_text')
        }
        
        response = requests.post(f"{BASE_URL}/api/summarize", 
                               json=payload, 
                               timeout=120)  # 2 minutes timeout
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Summarization successful")
            print(f"   Model: {data.get('summary_model')}")
            print(f"   Summary preview: {data.get('summary_text', '')[:100]}...")
            return data
        else:
            print(f"❌ Summarization failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Summarization error: {e}")
        return None

def test_list_transcriptions():
    """Test listing transcriptions"""
    print("Testing transcription list...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/transcriptions", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ List transcriptions successful")
            print(f"   Found {len(data.get('transcriptions', []))} transcriptions")
            print(f"   Pagination: page {data.get('pagination', {}).get('page', 1)} of {data.get('pagination', {}).get('pages', 1)}")
            return data
        else:
            print(f"❌ List transcriptions failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ List transcriptions error: {e}")
        return None

def cleanup():
    """Clean up test files"""
    try:
        if os.path.exists(TEST_AUDIO_FILE):
            os.remove(TEST_AUDIO_FILE)
            print(f"Cleaned up {TEST_AUDIO_FILE}")
    except Exception as e:
        print(f"Warning: Could not clean up test file: {e}")

def main():
    """Run all tests"""
    print("🧪 Whisper Web Interface Test Suite")
    print("=" * 50)
    
    # Test health
    if not test_health():
        print("\n❌ Service is not healthy. Please check if it's running.")
        return
    
    print()
    
    # Test upload
    upload_data = test_upload()
    if not upload_data:
        print("\n❌ Upload test failed. Stopping tests.")
        cleanup()
        return
    
    print()
    
    # Test transcription
    transcription_data = test_transcribe(upload_data)
    if not transcription_data:
        print("\n❌ Transcription test failed. Stopping tests.")
        cleanup()
        return
    
    print()
    
    # Test summarization (optional - may fail if Ollama not available)
    print("Note: Summarization test may fail if Ollama is not running locally")
    summarize_data = test_summarize(transcription_data)
    if summarize_data:
        print("✅ Summarization test passed")
    else:
        print("⚠️  Summarization test failed (this is expected if Ollama is not running)")
    
    print()
    
    # Test list transcriptions
    list_data = test_list_transcriptions()
    if list_data:
        print("✅ List transcriptions test passed")
    else:
        print("❌ List transcriptions test failed")
    
    print()
    print("=" * 50)
    print("🎉 Test suite completed!")
    
    # Cleanup
    cleanup()

if __name__ == "__main__":
    main()
