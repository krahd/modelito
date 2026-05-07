"""Provider and embedder registry helpers for Modelito."""
from typing import Any, Dict, List, Optional, Type
from .provider import EmbeddingProvider, SyncProvider
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

EMBEDDER_REGISTRY: Dict[str, Type] = dict(PROVIDER_REGISTRY)

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


def get_embedder(name: str, **kwargs: Any) -> Optional[EmbeddingProvider]:
    """Factory to instantiate an embedder by name."""
    cls = EMBEDDER_REGISTRY.get(name.lower())
    if cls is not None:
        return cls(**kwargs)
    return None


def list_providers() -> List[str]:
    """Return a list of available provider names."""
    return list(PROVIDER_REGISTRY.keys())


def list_embedders() -> List[str]:
    """Return a list of available embedder names."""
    return list(EMBEDDER_REGISTRY.keys())
