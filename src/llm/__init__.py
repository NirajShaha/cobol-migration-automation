"""LLM provider factory."""

from .base import BaseLLMProvider
from .openai_provider import OpenAIProvider
from .azure_provider import AzureOpenAIProvider
from .anthropic_provider import AnthropicProvider
from .nvidia_nim_provider import NvidiaNimProvider


def create_llm_provider(provider_type: str, **kwargs) -> BaseLLMProvider:
    """Factory function to create the appropriate LLM provider.
    
    Args:
        provider_type: One of 'openai', 'azure', 'anthropic', 'nvidia'
        **kwargs: Provider-specific configuration
    
    Returns:
        Configured LLM provider instance
    """
    providers = {
        "openai": lambda: OpenAIProvider(
            api_key=kwargs["api_key"],
            model=kwargs.get("model", "gpt-4o"),
        ),
        "azure": lambda: AzureOpenAIProvider(
            api_key=kwargs["api_key"],
            endpoint=kwargs["endpoint"],
            deployment=kwargs["deployment"],
            api_version=kwargs.get("api_version", "2024-02-01"),
        ),
        "anthropic": lambda: AnthropicProvider(
            api_key=kwargs["api_key"],
            model=kwargs.get("model", "claude-sonnet-4-20250514"),
        ),
        "nvidia": lambda: NvidiaNimProvider(
            api_key=kwargs["api_key"],
            model=kwargs.get("model", "meta/llama-3.1-405b-instruct"),
            base_url=kwargs.get("base_url", "https://integrate.api.nvidia.com/v1"),
        ),
    }

    if provider_type not in providers:
        raise ValueError(
            f"Unknown provider: {provider_type}. "
            f"Supported: {list(providers.keys())}"
        )

    return providers[provider_type]()


__all__ = [
    "BaseLLMProvider",
    "OpenAIProvider",
    "AzureOpenAIProvider",
    "AnthropicProvider",
    "NvidiaNimProvider",
    "create_llm_provider",
]
