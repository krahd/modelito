from __future__ import annotations

from typing import Iterable, List


def collect_stream(chunks: Iterable[str]) -> str:
    """Collect an iterable of text chunks into a single string.

    This helper is useful for tests and simple streaming adapters that want
    to reassemble incremental outputs into final text.
    """
    return "".join(chunks)


def collect_stream_list(chunks: Iterable[str]) -> List[str]:
    """Return list of chunks (convenience wrapper)."""
    return [c for c in chunks]
