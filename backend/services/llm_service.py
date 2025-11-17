"""
LLM Service - Abstraction layer for DeepSeek and Claude APIs.
Provides unified interface for chat completions.
"""

from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import time
import httpx
from anthropic import Anthropic

from config.settings import get_settings
from models.schemas import LLMResponse


settings = get_settings()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate a chat completion."""
        pass


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.deepseek.com/v1"

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate a chat completion using DeepSeek."""
        start_time = time.time()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    timeout=30.0
                )
                response.raise_for_status()

                data = response.json()
                processing_time = int((time.time() - start_time) * 1000)

                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model_used=self.model,
                    tokens_used=data.get("usage", {}).get("total_tokens"),
                    processing_time_ms=processing_time,
                    finish_reason=data["choices"][0].get("finish_reason")
                )

            except httpx.HTTPError as e:
                raise Exception(f"DeepSeek API error: {str(e)}")


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate a chat completion using Claude."""
        start_time = time.time()

        # Claude expects system message separately
        system_message = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                chat_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message if system_message else "",
                messages=chat_messages
            )

            processing_time = int((time.time() - start_time) * 1000)

            return LLMResponse(
                content=response.content[0].text,
                model_used=self.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                processing_time_ms=processing_time,
                finish_reason=response.stop_reason
            )

        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")


class LLMService:
    """
    Unified LLM service that routes requests to appropriate providers.
    """

    def __init__(self):
        # Initialize providers
        self.deepseek = DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model
        )

        self.claude = ClaudeProvider(
            api_key=settings.anthropic_api_key,
            model=settings.claude_model
        )

        # Set default provider
        self.primary_provider = (
            self.deepseek if settings.primary_llm == "deepseek" else self.claude
        )

        self.risk_provider = (
            self.claude if settings.risk_detection_llm == "claude" else self.deepseek
        )

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        provider: Optional[str] = None
    ) -> LLMResponse:
        """
        Generate a response using the specified or default provider.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            provider: 'deepseek', 'claude', or None (uses primary)

        Returns:
            LLMResponse with content and metadata
        """
        if provider == "deepseek":
            selected_provider = self.deepseek
        elif provider == "claude":
            selected_provider = self.claude
        else:
            selected_provider = self.primary_provider

        return await selected_provider.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def risk_detection_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,  # Lower temp for more consistent risk detection
        max_tokens: int = 500
    ) -> LLMResponse:
        """
        Generate a response specifically for risk detection.
        Uses the configured risk detection provider (usually Claude for safety).
        """
        return await self.risk_provider.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )


# Global service instance
llm_service = LLMService()


def get_llm_service() -> LLMService:
    """Get LLM service instance."""
    return llm_service
