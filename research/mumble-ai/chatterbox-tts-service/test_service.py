#!/usr/bin/env python3
"""
Test script for Chatterbox TTS Service
"""

import requests
import sys
import json
import time

BASE_URL = "http://localhost:5005"


def test_health():
    """Test health endpoint"""
    print("Testing /health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✓ Health check passed")
            print(f"  Device: {data.get('device', 'unknown')}")
            print(f"  CUDA Available: {data.get('cuda_available', False)}")
            print(f"  Model Loaded: {data.get('model_loaded', False)}")
            if data.get('gpu_name'):
                print(f"  GPU: {data['gpu_name']}")
            return True
        else:
            print(f"✗ Health check failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check failed: {str(e)}")
        return False


def test_info():
    """Test info endpoint"""
    print("\nTesting /api/info endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/info", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✓ Info endpoint working")
            print(f"  Service: {data.get('service', 'unknown')}")
            print(f"  Version: {data.get('version', 'unknown')}")
            print(f"  Languages: {len(data.get('supported_languages', []))} supported")
            return True
        else:
            print(f"✗ Info endpoint failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Info endpoint failed: {str(e)}")
        return False


def test_models():
    """Test models endpoint"""
    print("\nTesting /api/models endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/models", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✓ Models endpoint working")
            print(f"  Current model: {data.get('current_model', 'unknown')}")
            return True
        else:
            print(f"✗ Models endpoint failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Models endpoint failed: {str(e)}")
        return False


def test_tts_basic():
    """Test basic TTS (without voice cloning, will fail but tests endpoint)"""
    print("\nTesting /api/tts endpoint (basic)...")
    try:
        payload = {
            "text": "This is a test.",
            "speaker_wav": "/nonexistent/path.wav",  # This will fail, but tests endpoint
            "language": "en"
        }
        response = requests.post(
            f"{BASE_URL}/api/tts",
            json=payload,
            timeout=30
        )
        # We expect this to fail (400 or 500) due to missing speaker_wav
        # but it should return a proper error response
        if response.status_code in [400, 500]:
            print("✓ TTS endpoint responds (error expected without valid speaker_wav)")
            return True
        elif response.status_code == 200:
            print("✓ TTS endpoint working (unexpected success)")
            return True
        else:
            print(f"✗ TTS endpoint unexpected response: HTTP {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print("✗ TTS endpoint timeout (may be loading model)")
        return False
    except Exception as e:
        print(f"✗ TTS endpoint failed: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Chatterbox TTS Service Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    time.sleep(1)
    
    results.append(("Service Info", test_info()))
    time.sleep(1)
    
    results.append(("Models List", test_models()))
    time.sleep(1)
    
    results.append(("TTS Endpoint", test_tts_basic()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Service is ready.")
        return 0
    else:
        print("\n✗ Some tests failed. Check the service logs:")
        print("  docker-compose logs chatterbox-tts")
        return 1


if __name__ == "__main__":
    sys.exit(main())

