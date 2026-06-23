"""Unified LLM provider wrapping LangChain ChatModels with resilience."""

import time
from dataclasses import dataclass
from typing import Optional

import tiktoken
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

from ..core.exceptions import (
    LLMProviderError,
    LLMRateLimitError,
    LLMContextOverflowError,
    LLMResponseParseError,
)
from ..core.resilience import with_retries, CircuitBreaker
from ..core.logging import get_logger
from config.settings import settings

logger = get_logger("llm_provider")


@dataclass
class LLMResult:
    """Standardized result from an LLM call."""
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: float
    finish_reason: str = "stop"


class LLMProvider:
    """Production-ready LLM provider with retries, circuit breaker, and token tracking.
    
    Wraps a LangChain BaseChatModel with:
    - Exponential backoff retries on transient failures
    - Circuit breaker to prevent cascading failures
    - Token counting and budget awareness
    - Structured logging of all calls
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        provider_name: str,
        model_name: str,
        max_retries: int = None,
    ):
        self.chat_model = chat_model
        self.provider_name = provider_name
        self.model_name = model_name
        self._max_retries = max_retries or settings.pipeline.max_retries
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            cooldown_seconds=60.0,
        )
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_count = 0

        # Token encoder for estimation
        try:
            self._encoder = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            self._encoder = tiktoken.get_encoding("cl100k_base")

    @property
    def total_tokens_used(self) -> int:
        return self._total_input_tokens + self._total_output_tokens

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string."""
        try:
            return len(self._encoder.encode(text))
        except Exception:
            return len(text) // 4

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = None,
        temperature: float = None,
    ) -> LLMResult:
        """Generate a response with full resilience (retries + circuit breaker).
        
        Raises:
            LLMProviderError: On non-retryable provider errors
            LLMRateLimitError: After all retries exhausted on rate limits
            LLMContextOverflowError: When input exceeds context window
        """
        if not self._circuit_breaker.can_execute():
            raise LLMProviderError(
                "Circuit breaker is OPEN — too many recent failures",
                provider=self.provider_name,
                model=self.model_name,
            )

        max_tok = max_tokens or settings.llm.max_tokens
        temp = temperature if temperature is not None else settings.llm.temperature

        return self._invoke_with_retries(system_prompt, user_prompt, max_tok, temp)

    @with_retries(
        max_attempts=3,
        base_delay=1.0,
        max_delay=60.0,
    )
    def _invoke_with_retries(
        self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
    ) -> LLMResult:
        """Internal method decorated with retry logic."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        start = time.time()
        self._call_count += 1

        try:
            # Bind generation params
            bound_model = self.chat_model.bind(
                max_tokens=max_tokens,
                temperature=temperature,
            )
            response = bound_model.invoke(messages)
        except Exception as e:
            self._circuit_breaker.record_failure()
            error_msg = str(e).lower()

            if "rate" in error_msg and "limit" in error_msg:
                raise LLMRateLimitError(provider=self.provider_name)
            elif "context" in error_msg or "token" in error_msg and "maximum" in error_msg:
                estimated = self.estimate_tokens(system_prompt + user_prompt)
                raise LLMContextOverflowError(
                    provider=self.provider_name,
                    tokens_sent=estimated,
                    max_tokens=max_tokens,
                )
            else:
                raise LLMProviderError(
                    f"LLM call failed: {e}",
                    provider=self.provider_name,
                    model=self.model_name,
                )

        latency_ms = (time.time() - start) * 1000
        self._circuit_breaker.record_success()

        # Extract token usage
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)
        elif hasattr(response, "response_metadata"):
            meta = response.response_metadata or {}
            token_usage = meta.get("token_usage", {})
            input_tokens = token_usage.get("prompt_tokens", 0)
            output_tokens = token_usage.get("completion_tokens", 0)

        # Fallback estimation
        if input_tokens == 0:
            input_tokens = self.estimate_tokens(system_prompt + user_prompt)
        if output_tokens == 0:
            output_tokens = self.estimate_tokens(response.content or "")

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        content = response.content or ""

        logger.debug(
            "llm_call_complete",
            provider=self.provider_name,
            model=self.model_name,
            call_number=self._call_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms),
            content_length=len(content),
        )

        return LLMResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model_name,
            latency_ms=latency_ms,
        )
