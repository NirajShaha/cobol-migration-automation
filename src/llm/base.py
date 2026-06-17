"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Standard response from any LLM provider."""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str


class BaseLLMProvider(ABC):
    """Abstract LLM provider interface. Implement this for any AI backend."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def generate_with_context(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Generate a response with conversation history."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        pass

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string."""
        pass
