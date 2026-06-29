#!/usr/bin/env python3
"""
Verification script to ensure all changes are correctly applied.
Run this to verify your setup is ready for migration.

Usage:
    python verify_setup.py
"""

import os
import sys
from pathlib import Path

def check_file_exists(file_path: str, description: str) -> bool:
    """Check if a file exists."""
    exists = Path(file_path).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {file_path}")
    return exists

def check_env_config() -> bool:
    """Check .env configuration."""
    print("\n📋 Checking .env configuration...")
    
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found. Please run: copy .env.example .env")
        return False
    
    with open(".env", "r") as f:
        content = f.read()
    
    checks = {
        "LLM_PROVIDER=nvidia": "NVIDIA provider selected" in content or "LLM_PROVIDER=nvidia" in content,
        "REQUEST_TIMEOUT": "REQUEST_TIMEOUT" in content,
        "NVIDIA_NIM_API_KEY": "NVIDIA_NIM_API_KEY" in content,
        "NVIDIA_NIM_MODEL": "NVIDIA_NIM_MODEL" in content,
    }
    
    all_good = True
    for key, found in checks.items():
        status = "✅" if found else "⚠️"
        print(f"{status} {key}: {'Found' if found else 'Not found'}")
        if not found:
            all_good = False
    
    # Check timeout value
    for line in content.split('\n'):
        if line.startswith('REQUEST_TIMEOUT='):
            timeout_val = line.split('=')[1].strip()
            try:
                timeout_int = int(timeout_val)
                if timeout_int >= 600:
                    print(f"✅ REQUEST_TIMEOUT set to {timeout_int}s (recommended: ≥600s)")
                else:
                    print(f"⚠️  REQUEST_TIMEOUT set to {timeout_int}s (recommended: ≥600s)")
            except ValueError:
                print(f"❌ REQUEST_TIMEOUT value invalid: {timeout_val}")
                all_good = False
            break
    
    return all_good

def check_python_packages() -> bool:
    """Check required Python packages."""
    print("\n📦 Checking Python packages...")
    
    required = ["openai", "pydantic", "tenacity", "dotenv"]
    all_good = True
    
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} not installed")
            all_good = False
    
    if not all_good:
        print("\n💡 Tip: Install packages with: pip install -r requirements.txt")
    
    return all_good

def check_docker_setup() -> bool:
    """Check Docker setup (if applicable)."""
    print("\n🐳 Checking Docker setup...")
    
    docker_file = Path("docker-compose.yml")
    if not docker_file.exists():
        print("⚠️  docker-compose.yml not found (Docker setup optional)")
        return True
    
    print("✅ docker-compose.yml found")
    
    # Check for .env in docker-compose
    with open("docker-compose.yml", "r") as f:
        content = f.read()
        if "env_file" in content and ".env" in content:
            print("✅ docker-compose.yml references .env file")
            return True
        else:
            print("⚠️  docker-compose.yml may not reference .env file")
            return False

def check_new_files() -> bool:
    """Check that new documentation files exist."""
    print("\n📚 Checking new documentation files...")
    
    files = {
        "QUICK_FIX.md": "Quick fix guide",
        "TROUBLESHOOTING.md": "Comprehensive troubleshooting",
        "CHANGES_SUMMARY.md": "Summary of changes",
        "test_nvidia_api.py": "Diagnostic tool",
    }
    
    all_good = True
    for file, desc in files.items():
        exists = check_file_exists(file, desc)
        all_good = all_good and exists
    
    return all_good

def main():
    """Run all verification checks."""
    print("=" * 70)
    print("  VERIFICATION CHECKLIST")
    print("=" * 70)
    
    results = {
        "Configuration": check_env_config(),
        "Python Packages": check_python_packages(),
        "Docker Setup": check_docker_setup(),
        "Documentation": check_new_files(),
    }
    
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "⚠️  CHECK"
        print(f"{status}: {check}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All checks passed! You're ready to go.")
        print("\nNext steps:")
        print("  1. Ensure REQUEST_TIMEOUT is set to at least 600 in .env")
        print("  2. Run your migration:")
        print("     - Local: python run.py input/YOUR_PROGRAM.txt")
        print("     - Docker: docker-compose run --rm migrator input/YOUR_PROGRAM.txt")
        print("\n  3. If issues occur, run: python test_nvidia_api.py")
    else:
        print("⚠️  Some checks need attention. See details above.")
        print("\nCommon fixes:")
        print("  - Missing .env file: copy .env.example .env")
        print("  - Missing packages: pip install -r requirements.txt")
        print("  - Invalid API key: Check your NVIDIA_NIM_API_KEY in .env")
    
    print("=" * 70)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
