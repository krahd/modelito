"""Tokenizer wrapper for optional high-accuracy token counting.

This module provides `count_tokens(text)` which uses `tiktoken` when
available and falls back to a conservative heuristic otherwise.
"""

from __future__ import annotations


def count_tokens(text: str) -> int:
    """Return an estimated token count for ``text``.

    The function prefers the high-accuracy ``tiktoken`` encoder when the
    package is available. If ``tiktoken`` cannot be imported, a conservative
    heuristic (approx. 1 token per 4 characters) is used to avoid a hard
    dependency for consumers of the package.

    Args:
        text: Input string to estimate tokens for.

    Returns:
        Estimated number of tokens as an ``int``.

    Example:
        >>> count_tokens("Hello world")
        2
    """
    if not text:
        return 0
    try:
        import importlib

        tiktoken = importlib.import_module("tiktoken")
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # heuristic: 4 characters per token on average (conservative)
        return max(1, len(text) // 4)
