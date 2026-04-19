"""Provider interface for modelito.

This module defines typed Protocols for the primary provider surfaces we
intend to support in the v0.3 API. Providers may implement one or more of
these protocols; `Provider` is kept as a convenient alias for the
sync/legacy surface.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Protocol, runtime_checkable

from .messages import Message


@runtime_checkable
class SyncProvider(Protocol):
    """Synchronous provider surface (legacy-friendly).

    Implementations should provide `list_models()` and `summarize()`.
    """

    def list_models(self) -> List[str]:
        ...

    def summarize(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> str:
        ...


@runtime_checkable
class AsyncProvider(Protocol):
    """Asynchronous provider surface.

    Providers implementing this protocol should provide `acomplete()` which
    mirrors `summarize()` but is awaitable.
    """

    async def acomplete(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> str:
        ...


@runtime_checkable
class StreamingProvider(Protocol):
    """Streaming provider surface. Yields incremental text chunks.
    """

    def stream(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> Iterable[str]:
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Embedding surface: produce vector embeddings for a list of texts.
    """

    def embed(self, texts: Iterable[str], **kwargs: Any) -> List[List[float]]:
        ...


# Keep a small alias for older code that imported `Provider`.
Provider = SyncProvider
