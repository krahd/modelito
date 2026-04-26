"""
modelito.client

Unified Client interface for all providers.

- Abstract base class: Client
- Factory logic: Client(provider=..., model=...)
- Unified interface: summarize, stream, list_models, etc.
- Provider-specific features accessible via .provider
"""
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Union
from .provider_registry import get_provider, list_providers
from .provider import Provider
from .messages import Message

class Client:
    """
    Unified LLM Client interface for all providers.
    Use Client(provider="openai", model="gpt-3.5-turbo") for runtime selection.
    """
    def __init__(self, provider: Union[str, Provider] = "openai", model: Optional[str] = None, **kwargs):
        if isinstance(provider, str):
            self.provider = get_provider(provider, model=model, **kwargs)
            if self.provider is None:
                raise ValueError(f"Unknown provider: {provider}")
        else:
            self.provider = provider
        self.model = model or getattr(self.provider, "model", None)

    def list_models(self) -> List[str]:
        return self.provider.list_models()

    def summarize(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> str:
        return self.provider.summarize(messages, settings)

    def stream(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> Iterable[str]:
        if hasattr(self.provider, "stream"):
            return self.provider.stream(messages, settings)
        # Fallback: yield the full result as one chunk
        yield self.summarize(messages, settings)

    def embed(self, texts: Iterable[str], **kwargs) -> List[List[float]]:
        if hasattr(self.provider, "embed"):
            return self.provider.embed(texts, **kwargs)
        raise NotImplementedError("This provider does not support embeddings.")

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "__class__", type(self.provider)).__name__

    @staticmethod
    def available_providers() -> List[str]:
        return list_providers()

    # Expose provider-specific features if needed
    def __getattr__(self, item):
        # Allow access to provider-specific methods/attributes
        return getattr(self.provider, item)
