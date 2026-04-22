from __future__ import annotations

from typing import Iterable, List
from typing import AsyncIterable


def collect_stream(chunks: Iterable[str]) -> str:
    """Collect an iterable of text chunks into a single string.

    This helper is useful for tests and simple streaming adapters that want
    to reassemble incremental outputs into final text.
    """
    return "".join(chunks)


def collect_stream_list(chunks: Iterable[str]) -> List[str]:
    """Return list of chunks (convenience wrapper)."""
    return [c for c in chunks]


async def async_collect_stream(async_chunks: AsyncIterable[str]) -> str:
    """Collect an async iterable of text chunks into a single string."""
    parts: List[str] = []
    async for chunk in async_chunks:
        parts.append(chunk)
    return "".join(parts)
