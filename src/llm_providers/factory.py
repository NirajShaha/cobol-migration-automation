"""Factory for creating LangChain-based LLM providers."""

from langchain_core.language_models import BaseChatModel

from .provider import LLMProvider
from ..core.exceptions import LLMProviderError
from ..core.logging import get_logger
from config.settings import settings

logger = get_logger("llm_factory")


def create_provider(
    provider_type: str = None,
    api_key: str = None,
    model: str = None,
    **kwargs,
) -> LLMProvider:
    """Create a configured LLMProvider instance.
    
    Args:
        provider_type: One of 'nvidia', 'openai', 'azure', 'anthropic'
        api_key: API key override
        model: Model name override
        **kwargs: Additional provider-specific configuration
        
    Returns:
        Configured LLMProvider with resilience features
        
    Raises:
        LLMProviderError: If provider cannot be created
    """
    provider_type = provider_type or settings.llm.provider
    
    try:
        chat_model, resolved_model = _create_chat_model(
            provider_type, api_key, model, **kwargs
        )
    except ImportError as e:
        raise LLMProviderError(
            f"Missing dependency for provider '{provider_type}': {e}",
            provider=provider_type,
        )
    except Exception as e:
        raise LLMProviderError(
            f"Failed to create provider '{provider_type}': {e}",
            provider=provider_type,
        )

    logger.info(
        "provider_created",
        provider=provider_type,
        model=resolved_model,
    )

    return LLMProvider(
        chat_model=chat_model,
        provider_name=provider_type,
        model_name=resolved_model,
    )


def _create_chat_model(
    provider_type: str,
    api_key: str = None,
    model: str = None,
    **kwargs,
) -> tuple[BaseChatModel, str]:
    """Create the underlying LangChain ChatModel."""
    
    if provider_type == "nvidia":
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
        
        resolved_key = api_key or settings.llm.nvidia_api_key
        resolved_model = model or settings.llm.nvidia_model
        base_url = kwargs.get("base_url", settings.llm.nvidia_base_url)
        
        if not resolved_key:
            raise LLMProviderError("NVIDIA API key not configured", provider="nvidia")
        
        chat_model = ChatNVIDIA(
            model=resolved_model,
            api_key=resolved_key,
            base_url=base_url,
            timeout=settings.pipeline.request_timeout,
        )
        return chat_model, resolved_model

    elif provider_type == "openai":
        from langchain_openai import ChatOpenAI
        
        resolved_key = api_key or settings.llm.openai_api_key
        resolved_model = model or settings.llm.openai_model
        
        if not resolved_key:
            raise LLMProviderError("OpenAI API key not configured", provider="openai")
        
        chat_model = ChatOpenAI(
            model=resolved_model,
            api_key=resolved_key,
            timeout=settings.pipeline.request_timeout,
        )
        return chat_model, resolved_model

    elif provider_type == "azure":
        from langchain_openai import AzureChatOpenAI
        
        resolved_key = api_key or settings.llm.azure_api_key
        endpoint = kwargs.get("endpoint", settings.llm.azure_endpoint)
        deployment = kwargs.get("deployment", settings.llm.azure_deployment)
        api_version = kwargs.get("api_version", settings.llm.azure_api_version)
        
        if not resolved_key:
            raise LLMProviderError("Azure OpenAI API key not configured", provider="azure")
        
        chat_model = AzureChatOpenAI(
            azure_deployment=deployment,
            api_key=resolved_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            timeout=settings.pipeline.request_timeout,
        )
        return chat_model, deployment

    elif provider_type == "anthropic":
        from langchain_anthropic import ChatAnthropic
        
        resolved_key = api_key or settings.llm.anthropic_api_key
        resolved_model = model or settings.llm.anthropic_model
        
        if not resolved_key:
            raise LLMProviderError("Anthropic API key not configured", provider="anthropic")
        
        chat_model = ChatAnthropic(
            model=resolved_model,
            api_key=resolved_key,
            timeout=settings.pipeline.request_timeout,
        )
        return chat_model, resolved_model

    else:
        raise LLMProviderError(
            f"Unknown provider: {provider_type}. Supported: nvidia, openai, azure, anthropic",
            provider=provider_type,
        )
