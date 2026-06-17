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

# Per-Dimension Minimum Thresholds
# 95% target means EACH dimension must individually score >= 95%
DIMENSION_THRESHOLDS = {
    "business_logic": float(os.getenv("MIN_BUSINESS_LOGIC", "95")),
    "error_handling": float(os.getenv("MIN_ERROR_HANDLING", "95")),
    "schema_mapping": float(os.getenv("MIN_SCHEMA_MAPPING", "95")),
    "field_validation": float(os.getenv("MIN_FIELD_VALIDATION", "95")),
    "ui_fields": float(os.getenv("MIN_UI_FIELDS", "95")),
    "error_messages": float(os.getenv("MIN_ERROR_MESSAGES", "95")),
}
