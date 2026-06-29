#!/usr/bin/env python3
"""
Diagnostic script to test NVIDIA API connectivity and response times.
Run this on your EC2 instance to diagnose timeout issues.

Usage:
    python test_nvidia_api.py
"""

import os
import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from dotenv import load_dotenv

load_dotenv()

def test_api_connectivity():
    """Test connectivity to NVIDIA API endpoint."""
    import requests
    
    print("\n🔍 Testing NVIDIA API Connectivity...")
    print(f"   Base URL: {settings.llm.nvidia_base_url}")
    
    try:
        # Test basic connectivity (using health check or models endpoint if available)
        test_url = f"{settings.llm.nvidia_base_url}/models"
        print(f"   Testing: {test_url}")
        
        response = requests.get(
            test_url,
            headers={"Authorization": f"Bearer {settings.llm.nvidia_api_key}"},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"   ✅ API is reachable (Status: {response.status_code})")
            return True
        else:
            print(f"   ❌ API returned status {response.status_code}")
            print(f"      Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout connecting to API (10s)")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False


def test_simple_completion():
    """Test a simple completion request to measure response time."""
    from openai import OpenAI
    from httpx import Timeout
    
    print("\n🚀 Testing Simple Completion (30s timeout)...")
    print(f"   Model: {settings.llm.nvidia_model}")
    print(f"   Max tokens: 100")
    
    try:
        client = OpenAI(
            api_key=settings.llm.nvidia_api_key,
            base_url=settings.llm.nvidia_base_url,
            timeout=Timeout(30.0),  # 30 second timeout for this test
        )
        
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=settings.llm.nvidia_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' and nothing else."},
            ],
            max_tokens=100,
            temperature=0.2,
        )
        
        elapsed = time.time() - start_time
        
        print(f"   ✅ Success! Response time: {elapsed:.2f}s")
        print(f"      Content: {response.choices[0].message.content}")
        print(f"      Tokens used: {response.usage.total_tokens if response.usage else 'N/A'}")
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"   ❌ Failed after {elapsed:.2f}s")
        print(f"      Error: {str(e)[:300]}")
        return False


def test_large_completion():
    """Test a larger completion to simulate real workload."""
    from openai import OpenAI
    from httpx import Timeout
    
    timeout_seconds = settings.pipeline.request_timeout
    print(f"\n📊 Testing Large Completion ({timeout_seconds}s timeout)...")
    print(f"   Model: {settings.llm.nvidia_model}")
    print(f"   Max tokens: 2000")
    
    try:
        client = OpenAI(
            api_key=settings.llm.nvidia_api_key,
            base_url=settings.llm.nvidia_base_url,
            timeout=Timeout(float(timeout_seconds)),
        )
        
        start_time = time.time()
        
        large_prompt = """Provide a comprehensive analysis of the following COBOL program structure:
        
        PROGRAM-ID: TEST-PROG.
        DATA DIVISION.
        FILE SECTION.
        FD  INPUT-FILE.
        01  INPUT-RECORD           PIC X(100).
        
        WORKING-STORAGE SECTION.
        01  WS-VARIABLES.
            05  WS-COUNTER         PIC 9(5) VALUE 0.
            05  WS-FLAG            PIC X VALUE 'N'.
        
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM UNTIL WS-COUNTER > 1000
                PERFORM PROCESS-RECORD
                ADD 1 TO WS-COUNTER
            END-PERFORM.
            STOP RUN.
        
        PROCESS-RECORD.
            ACCEPT INPUT-RECORD.
            PERFORM VALIDATE-INPUT.
            IF WS-FLAG = 'Y'
                PERFORM UPDATE-DATABASE
            END-IF.
        """
        
        response = client.chat.completions.create(
            model=settings.llm.nvidia_model,
            messages=[
                {"role": "system", "content": "You are an expert COBOL to Java migration specialist."},
                {"role": "user", "content": large_prompt},
            ],
            max_tokens=2000,
            temperature=0.2,
        )
        
        elapsed = time.time() - start_time
        
        print(f"   ✅ Success! Response time: {elapsed:.2f}s")
        print(f"      Content length: {len(response.choices[0].message.content)} chars")
        print(f"      Tokens used: {response.usage.total_tokens if response.usage else 'N/A'}")
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"   ❌ Failed after {elapsed:.2f}s")
        print(f"      Error: {str(e)[:300]}")
        return False


def main():
    """Run all diagnostics."""
    print("=" * 70)
    print("  NVIDIA API Diagnostic Tool")
    print("=" * 70)
    
    # Check configuration
    print("\n📋 Configuration:")
    print(f"   LLM Provider: {settings.llm.provider}")
    print(f"   Base URL: {settings.llm.nvidia_base_url}")
    print(f"   Model: {settings.llm.nvidia_model}")
    print(f"   API Key Present: {bool(settings.llm.nvidia_api_key)}")
    print(f"   Request Timeout: {settings.pipeline.request_timeout}s")
    
    if not settings.llm.nvidia_api_key:
        print("\n❌ ERROR: NVIDIA_NIM_API_KEY not set in .env file!")
        return False
    
    results = {
        "api_connectivity": test_api_connectivity(),
        "simple_completion": test_simple_completion(),
        "large_completion": test_large_completion(),
    }
    
    # Summary
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n✅ Passed: {passed}/{total} tests")
    
    if not results["api_connectivity"]:
        print("\n💡 Recommendation: Check EC2 network connectivity:")
        print("   - Verify security group allows outbound HTTPS to NVIDIA")
        print("   - Check VPC routing and NAT gateway (if in private subnet)")
        print("   - Test: curl -I https://integrate.api.nvidia.com")
    
    if not results["simple_completion"]:
        print("\n💡 Recommendation: Check API key and authentication:")
        print("   - Verify API key is valid in NVIDIA dashboard")
        print("   - Check if API key has rate limits or quota issues")
        print("   - Try switching models (see .env.example)")
    
    if not results["large_completion"] and results["simple_completion"]:
        print("\n💡 Recommendation: Timeout during large requests:")
        print("   - Increase REQUEST_TIMEOUT in .env (currently {}s)".format(
            settings.pipeline.request_timeout))
        print("   - Try smaller max_tokens value")
        print("   - Consider using a smaller/faster model")
    
    print("\n" + "=" * 70)
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
