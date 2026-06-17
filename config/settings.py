"""Configuration settings for the COBOL/Telon migration automation."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "nvidia")  # nvidia | openai | azure | anthropic

# NVIDIA NIM
NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY", "")
NVIDIA_NIM_MODEL = os.getenv("NVIDIA_NIM_MODEL", "meta/llama-3.1-405b-instruct")
NVIDIA_NIM_BASE_URL = os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Azure OpenAI
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Migration Settings
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
TARGET_ACCURACY = float(os.getenv("TARGET_ACCURACY", "95"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

# Accuracy Weights (must sum to 1.0)
ACCURACY_WEIGHTS = {
    "business_logic": 0.25,
    "error_handling": 0.15,
    "schema_mapping": 0.20,
    "field_validation": 0.15,
    "ui_fields": 0.15,
    "error_messages": 0.10,
}
