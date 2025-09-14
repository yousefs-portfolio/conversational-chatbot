"""LLM service for multi-provider language model integration."""

import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
from enum import Enum
import openai
import anthropic
import google.generativeai as genai
from openai import OpenAI, AsyncOpenAI
from anthropic import Anthropic, AsyncAnthropic

from .config import settings


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


@dataclass
class LLMMessage:
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    tool_calls: Optional[List[Dict]] = None


@dataclass
class LLMStreamChunk:
    content: str
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def generate_response(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    async def stream_response(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream a response from the LLM."""
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)
        self.sync_client = OpenAI(api_key=api_key)

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict]:
        """Convert LLMMessage to OpenAI format."""
        openai_messages = []
        for msg in messages:
            message = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                message["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                message["tool_call_id"] = msg.tool_call_id
            openai_messages.append(message)
        return openai_messages

    async def generate_response(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
    ) -> LLMResponse:
        """Generate response using OpenAI API."""
        try:
            kwargs = {
                "model": model,
                "messages": self._convert_messages(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"] = tools

            response = await self.client.chat.completions.create(**kwargs)

            message = response.choices[0].message
            return LLMResponse(
                content=message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=response.choices[0].finish_reason,
                tool_calls=message.tool_calls if hasattr(message, 'tool_calls') else None,
            )
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    async def stream_response(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream response using OpenAI API."""
        try:
            kwargs = {
                "model": model,
                "messages": self._convert_messages(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            async for chunk in await self.client.chat.completions.create(**kwargs):
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    yield LLMStreamChunk(
                        content=delta.content or "",
                        finish_reason=chunk.choices[0].finish_reason,
                        tool_calls=delta.tool_calls if hasattr(delta, 'tool_calls') else None,
                    )
        except Exception as e:
            raise Exception(f"OpenAI streaming error: {str(e)}")

    def get_available_models(self) -> List[str]:
        """Get available OpenAI models."""
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]


class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider implementation."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict]:
        """Convert LLMMessage to Anthropic format."""
        anthropic_messages = []
        for msg in messages:
            if msg.role != "system":  # System messages handled separately
                message = {"role": msg.role, "content": msg.content}
                anthropic_messages.append(message)
        return anthropic_messages

    async def generate_response(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
    ) -> LLMResponse:
        """Generate response using Anthropic API."""
        try:
            system_message = None
            user_messages = []

            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    user_messages.append(msg)

            kwargs = {
                "model": model,
                "messages": self._convert_messages(user_messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system_message:
                kwargs["system"] = system_message
            if tools:
                kwargs["tools"] = tools

            response = await self.client.messages.create(**kwargs)

            return LLMResponse(
                content=response.content[0].text if response.content else "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
            )
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    async def stream_response(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream response using Anthropic API."""
        try:
            system_message = None
            user_messages = []

            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    user_messages.append(msg)

            kwargs = {
                "model": model,
                "messages": self._convert_messages(user_messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if system_message:
                kwargs["system"] = system_message
            if tools:
                kwargs["tools"] = tools

            async with self.client.messages.stream(**kwargs) as stream:
                async for chunk in stream:
                    if chunk.type == "content_block_delta":
                        yield LLMStreamChunk(
                            content=chunk.delta.text if hasattr(chunk.delta, 'text') else "",
                        )
                    elif chunk.type == "message_stop":
                        yield LLMStreamChunk(
                            content="",
                            finish_reason="stop",
                        )
        except Exception as e:
            raise Exception(f"Anthropic streaming error: {str(e)}")

    def get_available_models(self) -> List[str]:
        """Get available Anthropic models."""
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]


class LLMService:
    """Main service for managing multiple LLM providers."""

    def __init__(self):
        self.providers: Dict[LLMProvider, BaseLLMProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available LLM providers."""
        if settings.OPENAI_API_KEY:
            self.providers[LLMProvider.OPENAI] = OpenAIProvider(settings.OPENAI_API_KEY)

        if settings.ANTHROPIC_API_KEY:
            self.providers[LLMProvider.ANTHROPIC] = AnthropicProvider(settings.ANTHROPIC_API_KEY)

        # Add Google provider when available
        # if settings.GOOGLE_API_KEY:
        #     self.providers[LLMProvider.GOOGLE] = GoogleProvider(settings.GOOGLE_API_KEY)

    def get_provider(self, provider: LLMProvider) -> BaseLLMProvider:
        """Get provider instance."""
        if provider not in self.providers:
            raise ValueError(f"Provider {provider.value} not available")
        return self.providers[provider]

    def get_default_model_for_provider(self, provider: LLMProvider) -> str:
        """Get default model for provider."""
        defaults = {
            LLMProvider.OPENAI: "gpt-4o-mini",
            LLMProvider.ANTHROPIC: "claude-3-5-haiku-20241022",
            LLMProvider.GOOGLE: "gemini-pro",
        }
        return defaults.get(provider, "gpt-3.5-turbo")

    def parse_model_string(self, model: str) -> tuple[LLMProvider, str]:
        """Parse model string to provider and model name."""
        if model.startswith("gpt-"):
            return LLMProvider.OPENAI, model
        elif model.startswith("claude-"):
            return LLMProvider.ANTHROPIC, model
        elif model.startswith("gemini-"):
            return LLMProvider.GOOGLE, model
        else:
            # Default to OpenAI
            return LLMProvider.OPENAI, model

    async def generate_response(
        self,
        messages: List[LLMMessage],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
    ) -> LLMResponse:
        """Generate response using appropriate provider."""
        provider_type, model_name = self.parse_model_string(model)
        provider = self.get_provider(provider_type)
        return await provider.generate_response(messages, model_name, temperature, max_tokens, tools)

    async def stream_response(
        self,
        messages: List[LLMMessage],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream response using appropriate provider."""
        provider_type, model_name = self.parse_model_string(model)
        provider = self.get_provider(provider_type)
        async for chunk in provider.stream_response(messages, model_name, temperature, max_tokens, tools):
            yield chunk

    def get_available_models(self) -> Dict[str, List[str]]:
        """Get all available models grouped by provider."""
        models = {}
        for provider_type, provider in self.providers.items():
            models[provider_type.value] = provider.get_available_models()
        return models


# Global LLM service instance
llm_service = LLMService()