"""Azure OpenAI LLM provider implementation."""

from openai import AzureOpenAI
import tiktoken
from .base import BaseLLMProvider, LLMResponse


class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI API provider."""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str = "2024-02-01",
    ):
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self.deployment = deployment
        try:
            self.encoding = tiktoken.encoding_for_model("gpt-4o")
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.deployment,
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
            model=self.deployment,
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
            model=self.deployment,
            messages=all_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=self.deployment,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "unknown",
        )

    def get_model_name(self) -> str:
        return f"azure/{self.deployment}"

    def estimate_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
