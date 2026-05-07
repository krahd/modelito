from __future__ import annotations

from typing import Any, Iterable, List, Optional, Union, cast

from .provider import EmbeddingProvider
from .provider_registry import get_embedder, list_embedders


def embed_texts(texts: Iterable[str], dim: int = 8) -> List[List[float]]:
    """Return a deterministic (zero) embedding for each text.

    This helper is a test-friendly stub and is intended for PR scaffolding.
    Real provider adapters should implement the `EmbeddingProvider` Protocol
    defined in `modelito.provider`.
    """
    return [[0.0] * dim for _ in texts]


class StubEmbeddingProvider:
    """Simple test provider implementing the embedding surface."""

    def embed(self, texts: Iterable[str], **kwargs: Any) -> List[List[float]]:
        dim = int(kwargs.get("dim", 8))
        return embed_texts(texts, dim=dim)


class Embedder:
    """Unified embeddings client for runtime-selected embedders.

    This mirrors the small runtime-selection behavior of ``modelito.Client``
    but narrows the surface to embeddings only.
    """

    def __init__(
        self,
        provider: Union[str, EmbeddingProvider] = "openai",
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        if isinstance(provider, str):
            resolved_provider = get_embedder(provider, model=model, **kwargs)
            if resolved_provider is None:
                raise ValueError(f"Unknown embedder: {provider}")
            self.provider = resolved_provider
        else:
            self.provider = provider
        self.model = model or getattr(self.provider, "model", None)

    def embed(self, texts: Iterable[str], **kwargs: Any) -> List[List[float]]:
        return cast(Any, self.provider).embed(texts, **kwargs)

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "__class__", type(self.provider)).__name__

    @staticmethod
    def available_embedders() -> List[str]:
        return list_embedders()

    def __getattr__(self, item: str) -> Any:
        return getattr(self.provider, item)
