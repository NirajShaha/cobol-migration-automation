"""Configuration settings for the COBOL/Telon migration automation.

Uses pydantic-settings for validated configuration with environment variable support.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class LLMSettings(BaseSettings):
    """LLM provider configuration."""
    provider: str = Field(default="nvidia", alias="LLM_PROVIDER")
    max_tokens: int = Field(default=16384, alias="MAX_TOKENS")
    temperature: float = Field(default=0.2, alias="TEMPERATURE")
    
    # NVIDIA NIM
    nvidia_api_key: str = Field(default="", alias="NVIDIA_NIM_API_KEY")
    nvidia_model: str = Field(default="meta/llama-3.1-405b-instruct", alias="NVIDIA_NIM_MODEL")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", alias="NVIDIA_NIM_BASE_URL")
    
    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    
    # Azure OpenAI
    azure_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    azure_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    azure_deployment: str = Field(default="gpt-4o", alias="AZURE_OPENAI_DEPLOYMENT")
    azure_api_version: str = Field(default="2024-02-01", alias="AZURE_OPENAI_API_VERSION")
    
    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-20250514", alias="ANTHROPIC_MODEL")

    class Config:
        env_file = ".env"
        extra = "ignore"


class PipelineSettings(BaseSettings):
    """Pipeline execution configuration."""
    max_iterations: int = Field(default=10, alias="MAX_ITERATIONS")
    target_accuracy: float = Field(default=95.0, alias="TARGET_ACCURACY")
    
    # Parallelism
    max_parallel_calls: int = Field(default=3, alias="MAX_PARALLEL_CALLS")
    
    # Resilience
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    retry_base_delay: float = Field(default=1.0, alias="RETRY_BASE_DELAY")
    retry_max_delay: float = Field(default=60.0, alias="RETRY_MAX_DELAY")
    request_timeout: int = Field(default=300, alias="REQUEST_TIMEOUT")
    
    # Token budget
    large_source_threshold: int = Field(default=12000, alias="LARGE_SOURCE_THRESHOLD")
    max_context_chars: int = Field(default=90000, alias="MAX_CONTEXT_CHARS")
    
    # Per-Dimension Minimum Thresholds
    min_business_logic: float = Field(default=95.0, alias="MIN_BUSINESS_LOGIC")
    min_error_handling: float = Field(default=95.0, alias="MIN_ERROR_HANDLING")
    min_schema_mapping: float = Field(default=95.0, alias="MIN_SCHEMA_MAPPING")
    min_field_validation: float = Field(default=95.0, alias="MIN_FIELD_VALIDATION")
    min_ui_fields: float = Field(default=95.0, alias="MIN_UI_FIELDS")
    min_error_messages: float = Field(default=95.0, alias="MIN_ERROR_MESSAGES")

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def dimension_thresholds(self) -> dict[str, float]:
        return {
            "business_logic": self.min_business_logic,
            "error_handling": self.min_error_handling,
            "schema_mapping": self.min_schema_mapping,
            "field_validation": self.min_field_validation,
            "ui_fields": self.min_ui_fields,
            "error_messages": self.min_error_messages,
        }


class AppSettings(BaseSettings):
    """Top-level application settings."""
    base_dir: Path = Path(__file__).parent.parent
    input_dir: Path = Path(__file__).parent.parent / "input"
    output_dir: Path = Path(__file__).parent.parent / "output"
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    llm: LLMSettings = Field(default_factory=LLMSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)

    class Config:
        env_file = ".env"
        extra = "ignore"


# Singleton instances
settings = AppSettings()

# Backward-compatible flat access
BASE_DIR = settings.base_dir
INPUT_DIR = settings.input_dir
OUTPUT_DIR = settings.output_dir
LLM_PROVIDER = settings.llm.provider
MAX_ITERATIONS = settings.pipeline.max_iterations
TARGET_ACCURACY = settings.pipeline.target_accuracy
MAX_TOKENS = settings.llm.max_tokens
TEMPERATURE = settings.llm.temperature
DIMENSION_THRESHOLDS = settings.pipeline.dimension_thresholds

# Provider keys (backward compat)
NVIDIA_NIM_API_KEY = settings.llm.nvidia_api_key
NVIDIA_NIM_MODEL = settings.llm.nvidia_model
NVIDIA_NIM_BASE_URL = settings.llm.nvidia_base_url
OPENAI_API_KEY = settings.llm.openai_api_key
OPENAI_MODEL = settings.llm.openai_model
AZURE_OPENAI_API_KEY = settings.llm.azure_api_key
AZURE_OPENAI_ENDPOINT = settings.llm.azure_endpoint
AZURE_OPENAI_DEPLOYMENT = settings.llm.azure_deployment
AZURE_OPENAI_API_VERSION = settings.llm.azure_api_version
ANTHROPIC_API_KEY = settings.llm.anthropic_api_key
ANTHROPIC_MODEL = settings.llm.anthropic_model
