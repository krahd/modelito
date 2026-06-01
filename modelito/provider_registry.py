"""Provider and embedder registry helpers for Modelito."""

from inspect import signature, Parameter
from typing import Any, Dict, List, Optional, Type
from .provider import EmbeddingProvider, SyncProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .omlx import OMLXProvider

# Registry of provider classes
from .mock_provider import MockProvider

PROVIDER_REGISTRY: Dict[str, Type] = {
    "openai": OpenAIProvider,
    "anthropic": ClaudeProvider,
    "claude": ClaudeProvider,
    "google": GeminiProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "omlx": OMLXProvider,
    "om": OMLXProvider,
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
        try:
            params = signature(cls.__init__).parameters
            accepts_var_kwargs = any(
                param.kind == Parameter.VAR_KEYWORD for param in params.values()
            )
            if accepts_var_kwargs:
                return cls(**kwargs)
            filtered = {
                key: value
                for key, value in kwargs.items()
                if key in params and key != "self"
            }
            return cls(**filtered)
        except Exception:
            return cls(**kwargs)
    return None


def get_embedder(name: str, **kwargs: Any) -> Optional[EmbeddingProvider]:
    """Factory to instantiate an embedder by name."""
    cls = EMBEDDER_REGISTRY.get(name.lower())
    if cls is not None:
        try:
            params = signature(cls.__init__).parameters
            accepts_var_kwargs = any(
                param.kind == Parameter.VAR_KEYWORD for param in params.values()
            )
            if accepts_var_kwargs:
                return cls(**kwargs)
            filtered = {
                key: value
                for key, value in kwargs.items()
                if key in params and key != "self"
            }
            return cls(**filtered)
        except Exception:
            return cls(**kwargs)
    return None


def list_providers() -> List[str]:
    """Return a list of available provider names."""
    return list(PROVIDER_REGISTRY.keys())


def list_embedders() -> List[str]:
    """Return a list of available embedder names."""
    return list(EMBEDDER_REGISTRY.keys())
