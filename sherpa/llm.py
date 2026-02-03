#!/usr/bin/env python3
"""
Unified LLM client supporting multiple providers.
Provides a consistent interface across Anthropic, OpenAI, and Google Gemini.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Generator, Dict, Any, List

from .config import load_config, get_config_value


@dataclass
class LLMResponse:
    """Unified response from any LLM provider"""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    @abstractmethod
    def create(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Create a completion"""
        pass

    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]:
        """Stream a completion token by token"""
        pass


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client"""

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str, model: str = None):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)
        self.model = model or self.DEFAULT_MODEL
        self.provider = "anthropic"

    def create(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return LLMResponse(
            content=response.content[0].text,
            model=self.model,
            provider=self.provider,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        )

    def stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client"""

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: str, model: str = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model or self.DEFAULT_MODEL
        self.provider = "openai"

    def create(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=self.model,
            provider=self.provider,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            } if response.usage else None
        )

    def stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]:
        stream = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GeminiClient(BaseLLMClient):
    """Google Gemini client"""

    DEFAULT_MODEL = "gemini-1.5-pro"

    def __init__(self, api_key: str, model: str = None):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model_name = model or self.DEFAULT_MODEL
        self.model = genai.GenerativeModel(self.model_name)
        self.provider = "gemini"

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict]:
        """Convert standard messages to Gemini format"""
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({
                "role": role,
                "parts": [msg["content"]]
            })
        return gemini_messages

    def create(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        # Gemini uses a different conversation format
        gemini_messages = self._convert_messages(messages)

        # For single message, use generate_content directly
        if len(gemini_messages) == 1:
            response = self.model.generate_content(
                messages[0]["content"],
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
        else:
            # For multi-turn, start a chat
            chat = self.model.start_chat(history=gemini_messages[:-1])
            response = chat.send_message(
                gemini_messages[-1]["parts"][0],
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                }
            )

        return LLMResponse(
            content=response.text,
            model=self.model_name,
            provider=self.provider,
        )

    def stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]:
        gemini_messages = self._convert_messages(messages)

        if len(gemini_messages) == 1:
            response = self.model.generate_content(
                messages[0]["content"],
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
                stream=True,
            )
        else:
            chat = self.model.start_chat(history=gemini_messages[:-1])
            response = chat.send_message(
                gemini_messages[-1]["parts"][0],
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
                stream=True,
            )

        for chunk in response:
            if chunk.text:
                yield chunk.text


# Provider registry
PROVIDERS = {
    "anthropic": {
        "client_class": AnthropicClient,
        "env_var": "ANTHROPIC_API_KEY",
        "config_key": "anthropic_api_key",
        "key_prefix": "sk-ant-",
        "display_name": "Anthropic (Claude)",
        "url": "https://console.anthropic.com/settings/keys",
    },
    "openai": {
        "client_class": OpenAIClient,
        "env_var": "OPENAI_API_KEY",
        "config_key": "openai_api_key",
        "key_prefix": "sk-",
        "display_name": "OpenAI (GPT-4)",
        "url": "https://platform.openai.com/api-keys",
    },
    "gemini": {
        "client_class": GeminiClient,
        "env_var": "GOOGLE_API_KEY",
        "config_key": "gemini_api_key",
        "key_prefix": "AI",
        "display_name": "Google (Gemini)",
        "url": "https://aistudio.google.com/app/apikey",
    },
}


def get_available_providers() -> List[str]:
    """Get list of providers with configured API keys"""
    available = []
    for provider, info in PROVIDERS.items():
        # Check environment variable
        if os.getenv(info["env_var"]):
            available.append(provider)
            continue
        # Check config file
        config = load_config()
        if config.get(info["config_key"]):
            available.append(provider)
    return available


def get_api_key_for_provider(provider: str) -> Optional[str]:
    """Get API key for a specific provider"""
    if provider not in PROVIDERS:
        return None

    info = PROVIDERS[provider]

    # Check environment variable first
    api_key = os.getenv(info["env_var"])
    if api_key:
        return api_key

    # Check config file
    config = load_config()
    return config.get(info["config_key"])


def get_preferred_provider() -> Optional[str]:
    """Get the user's preferred provider from config, or first available"""
    config = load_config()
    preferred = config.get("preferred_provider")

    if preferred and get_api_key_for_provider(preferred):
        return preferred

    # Fall back to first available
    available = get_available_providers()
    return available[0] if available else None


def create_llm_client(
    provider: str = None,
    model: str = None,
) -> Optional[BaseLLMClient]:
    """
    Create an LLM client for the specified or preferred provider.

    Args:
        provider: Provider name (anthropic, openai, gemini). If None, uses preferred.
        model: Model name override. If None, uses provider default.

    Returns:
        LLM client instance or None if no provider available.
    """
    if provider is None:
        provider = get_preferred_provider()

    if provider is None or provider not in PROVIDERS:
        return None

    api_key = get_api_key_for_provider(provider)
    if not api_key:
        return None

    info = PROVIDERS[provider]
    client_class = info["client_class"]

    try:
        return client_class(api_key=api_key, model=model)
    except ImportError as e:
        print(f"Warning: {provider} SDK not installed. Run: pip install {_get_package_name(provider)}")
        return None
    except Exception as e:
        print(f"Warning: Failed to initialize {provider} client: {e}")
        return None


def _get_package_name(provider: str) -> str:
    """Get pip package name for a provider"""
    packages = {
        "anthropic": "anthropic",
        "openai": "openai",
        "gemini": "google-generativeai",
    }
    return packages.get(provider, provider)


class UnifiedLLMClient:
    """
    Wrapper that provides backwards-compatible interface.
    Can be used as a drop-in replacement for direct Anthropic client usage.
    """

    def __init__(self, provider: str = None, model: str = None):
        self.client = create_llm_client(provider, model)
        self.provider = provider or get_preferred_provider()
        self._messages_api = _MessagesAPI(self.client) if self.client else None

    @property
    def messages(self):
        """Provides .messages.create() and .messages.stream() interface"""
        return self._messages_api

    def is_available(self) -> bool:
        """Check if client is available"""
        return self.client is not None


class _MessagesAPI:
    """Mimics Anthropic's messages API for compatibility"""

    def __init__(self, client: BaseLLMClient):
        self.client = client

    def create(
        self,
        model: str = None,
        max_tokens: int = 2000,
        messages: List[Dict[str, str]] = None,
        **kwargs
    ):
        """Create completion (mimics Anthropic API)"""
        response = self.client.create(messages=messages, max_tokens=max_tokens)
        # Return object with .content[0].text for compatibility
        return _CompatResponse(response)

    def stream(
        self,
        model: str = None,
        max_tokens: int = 2000,
        messages: List[Dict[str, str]] = None,
        **kwargs
    ):
        """Stream completion (mimics Anthropic API)"""
        return _CompatStreamContext(self.client, messages, max_tokens)


class _CompatResponse:
    """Compatibility wrapper for response"""

    def __init__(self, response: LLMResponse):
        self.response = response
        self.content = [_ContentBlock(response.content)]


class _ContentBlock:
    """Mimics Anthropic content block"""

    def __init__(self, text: str):
        self.text = text


class _CompatStreamContext:
    """Context manager for streaming that mimics Anthropic's API"""

    def __init__(self, client: BaseLLMClient, messages: List, max_tokens: int):
        self.client = client
        self.messages = messages
        self.max_tokens = max_tokens
        self._stream = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    @property
    def text_stream(self):
        """Yields text chunks"""
        return self.client.stream(messages=self.messages, max_tokens=self.max_tokens)
