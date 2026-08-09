"""Provider and embedder registry helpers for Modelito."""

from inspect import Parameter, signature
from typing import Any, Dict, List, Optional, Type

from .basert import BaseRTProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .mock_provider import MockProvider
from .ollama_strict import OllamaProvider
from .omlx import OMLXProvider
from .openai import OpenAIProvider
from .provider import EmbeddingProvider, SyncProvider
from .vllm_mlx import VLLMMLXProvider


PROVIDER_REGISTRY: Dict[str, Type] = {
    "openai": OpenAIProvider,
    "anthropic": ClaudeProvider,
    "claude": ClaudeProvider,
    "google": GeminiProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "omlx": OMLXProvider,
    "om": OMLXProvider,
    "basert": BaseRTProvider,
    "vllm-mlx": VLLMMLXProvider,
    "vllm_mlx": VLLMMLXProvider,
    "mock": MockProvider,
}

EMBEDDER_REGISTRY: Dict[str, Type] = dict(PROVIDER_REGISTRY)


def get_provider(name: str, **kwargs: Any) -> Optional[SyncProvider]:
    """Instantiate a provider by name, or return ``None`` when unknown."""
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
    """Instantiate an embedder by name, or return ``None`` when unknown."""
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
    """Return the available provider names."""
    return list(PROVIDER_REGISTRY.keys())


def list_embedders() -> List[str]:
    """Return the available embedder names."""
    return list(EMBEDDER_REGISTRY.keys())
