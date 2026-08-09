"""Provider interface for modelito.

This module defines typed Protocols for the primary provider surfaces we
intend to support in the v0.3 API. Providers may implement one or more of
these protocols; `Provider` is kept as a convenient alias for the
sync/legacy surface.
"""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    TypedDict,
    Union,
    runtime_checkable,
)

from .messages import Message, Response


class OpenAIMessageDict(TypedDict):
    """OpenAI-style chat message dict shape used by lightweight helpers."""

    role: str
    content: Any


# Convenience type alias for message inputs accepted by OpenAI-compatible providers.
# Callers may pass Message instances, plain strings, or OpenAI-style dicts.
MessageInput = Union[
    Message, str, OpenAIMessageDict, Mapping[str, Any]
]


@runtime_checkable
class SyncProvider(Protocol):
    """Synchronous provider surface (legacy-friendly).

    Implementations should provide `list_models()` and `summarize()`.
    """

    def list_models(self) -> List[str]: ...

    def summarize(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[Dict[str, Any]] = None,
    ) -> str: ...


@runtime_checkable
class AsyncProvider(Protocol):
    """Asynchronous provider surface.

    Providers implementing this protocol should provide `acomplete()` which
    mirrors `summarize()` but is awaitable.
    """

    async def acomplete(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[Dict[str, Any]] = None,
    ) -> str: ...


@runtime_checkable
class StreamingProvider(Protocol):
    """Streaming provider surface. Yields incremental text chunks."""

    def stream(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[Dict[str, Any]] = None,
    ) -> Iterable[str]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Embedding surface: produce vector embeddings for a list of texts."""

    def embed(self, texts: Iterable[str], **kwargs: Any) -> List[List[float]]: ...


@runtime_checkable
class ChatProvider(Protocol):
    """Modern provider surface returning full ``Response`` metadata.

    Prefer this protocol over :class:`SyncProvider` for new code.
    ``Client.chat()`` delegates to this interface when available.
    """

    def chat(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[Dict[str, Any]] = None,
    ) -> Response: ...


@runtime_checkable
class RawChatProvider(Protocol):
    """Raw OpenAI-chat-completions surface.

    This protocol preserves the provider's native completion payloads so HTTP
    servers and agent harnesses can forward tool calls and other metadata
    without collapsing them into plain text.
    """

    def raw_complete(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    def raw_stream(self, payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]: ...


# Keep a small alias for older code that imported `Provider`.
Provider = SyncProvider
