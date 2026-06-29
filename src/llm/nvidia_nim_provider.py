"""NVIDIA NIM LLM provider implementation.

NVIDIA NIM uses an OpenAI-compatible API endpoint, so we leverage the OpenAI client
with a custom base_url pointing to NVIDIA's inference API.
"""

from openai import OpenAI
from config.settings import settings
from .base import BaseLLMProvider, LLMResponse


# Available models on NVIDIA NIM (common ones for code generation)
NVIDIA_NIM_MODELS = {
    "meta/llama-3.1-405b-instruct": "Llama 3.1 405B (best for code)",
    "meta/llama-3.1-70b-instruct": "Llama 3.1 70B",
    "meta/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "nvidia/llama-3.1-nemotron-70b-instruct": "Nemotron 70B",
    "qwen/qwen2.5-coder-32b-instruct": "Qwen 2.5 Coder 32B",
    "deepseek-ai/deepseek-coder-6.7b-instruct": "DeepSeek Coder 6.7B",
    "microsoft/phi-3-medium-128k-instruct": "Phi-3 Medium 128K",
    "google/gemma-2-27b-it": "Gemma 2 27B",
}

NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaNimProvider(BaseLLMProvider):
    """NVIDIA NIM API provider (OpenAI-compatible endpoint)."""

    def __init__(
        self,
        api_key: str,
        model: str = "meta/llama-3.1-405b-instruct",
        base_url: str = NVIDIA_NIM_BASE_URL,
        timeout: float = None,
    ):
        # Use configured timeout from settings, or explicit value, or default to 600s
        timeout_seconds = timeout or settings.pipeline.request_timeout or 600
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
        )
        
        self.model = model
        self.base_url = base_url
        self.timeout = timeout_seconds

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model or self.model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "unknown",
        )

    def generate_with_context(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        response = self.client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model or self.model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "unknown",
        )

    def get_model_name(self) -> str:
        return f"nvidia/{self.model}"

    def estimate_tokens(self, text: str) -> int:
        # Approximate: ~4 chars per token for most models
        return len(text) // 4

    @staticmethod
    def list_available_models() -> dict[str, str]:
        """Return dict of available NVIDIA NIM models."""
        return NVIDIA_NIM_MODELS.copy()
