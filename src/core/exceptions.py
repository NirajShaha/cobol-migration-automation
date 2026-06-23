"""Custom exception hierarchy for the migration pipeline.

Follows industry-standard patterns:
- Base exception class for the application
- Specific subclasses for different failure modes
- Rich context in exceptions for debugging
"""

from typing import Optional


class MigrationError(Exception):
    """Base exception for all migration pipeline errors."""

    def __init__(self, message: str, context: Optional[dict] = None):
        self.context = context or {}
        super().__init__(message)

    def __str__(self):
        base = super().__str__()
        if self.context:
            details = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base} [{details}]"
        return base


class LLMProviderError(MigrationError):
    """Error communicating with LLM provider."""

    def __init__(self, message: str, provider: str = "", model: str = "", **kwargs):
        super().__init__(message, context={"provider": provider, "model": model, **kwargs})
        self.provider = provider
        self.model = model


class LLMRateLimitError(LLMProviderError):
    """Rate limit exceeded — should trigger backoff retry."""

    def __init__(self, provider: str, retry_after: Optional[float] = None):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for {provider}",
            provider=provider,
            retry_after=str(retry_after) if retry_after else "unknown",
        )


class LLMContextOverflowError(LLMProviderError):
    """Input exceeds model's context window."""

    def __init__(self, provider: str, tokens_sent: int, max_tokens: int):
        self.tokens_sent = tokens_sent
        self.max_tokens = max_tokens
        super().__init__(
            f"Context overflow: {tokens_sent} tokens sent, max is {max_tokens}",
            provider=provider,
            tokens_sent=str(tokens_sent),
            max_tokens=str(max_tokens),
        )


class LLMResponseParseError(MigrationError):
    """Failed to parse LLM response into expected format."""

    def __init__(self, message: str, raw_response: str = ""):
        self.raw_response = raw_response[:500]  # Keep first 500 chars for debugging
        super().__init__(message, context={"response_preview": self.raw_response[:100]})


class ConversionError(MigrationError):
    """Error during code conversion phase."""

    def __init__(self, message: str, layer: str = "", iteration: int = 0):
        super().__init__(message, context={"layer": layer, "iteration": str(iteration)})
        self.layer = layer
        self.iteration = iteration


class AnalysisError(MigrationError):
    """Error during accuracy analysis phase."""
    pass


class PipelineError(MigrationError):
    """Error in the pipeline orchestration logic."""
    pass
