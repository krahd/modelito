from __future__ import annotations

from typing import Iterable, List


def embed_texts(texts: Iterable[str], dim: int = 8) -> List[List[float]]:
    """Return a deterministic (zero) embedding for each text.

    This helper is a test-friendly stub and is intended for PR scaffolding.
    Real provider adapters should implement the `EmbeddingProvider` Protocol
    defined in `modelito.provider`.
    """
    return [[0.0] * dim for _ in texts]


class StubEmbeddingProvider:
    """Simple test provider implementing the embedding surface."""

    def embed(self, texts: Iterable[str], **kwargs) -> List[List[float]]:
        dim = int(kwargs.get("dim", 8))
        return embed_texts(texts, dim=dim)
