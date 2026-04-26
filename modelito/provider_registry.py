"""
Provider registry and factory for Modelito.
Allows runtime selection and instantiation of providers by name.
"""
from typing import Any, Dict, Optional, Type
from .provider import SyncProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider

# Registry of provider classes
from .mock_provider import MockProvider

PROVIDER_REGISTRY: Dict[str, Type] = {
    "openai": OpenAIProvider,
    "anthropic": ClaudeProvider,
    "claude": ClaudeProvider,
    "google": GeminiProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "mock": MockProvider,
}

def get_provider(name: str, **kwargs: Any) -> Optional[SyncProvider]:
    """
    Factory to instantiate a provider by name.
    Args:
        name: Provider name (e.g., 'openai', 'claude', 'gemini', 'ollama')
        kwargs: Passed to provider constructor
    Returns:
        Provider instance or None if not found
    """
    cls = PROVIDER_REGISTRY.get(name.lower())
    if cls is not None:
        return cls(**kwargs)
    return None

def list_providers() -> list:
    """Return a list of available provider names."""
    return list(PROVIDER_REGISTRY.keys())
