"""Compatibility shim for Grok provider.

Minimal `GrokProvider` implementation with safe defaults for local testing
and import compatibility.
"""
from __future__ import annotations

from typing import Any, List, Optional


class GrokProvider:
    """Minimal compatibility shim for Grok providers used in tests.

    Offers `list_models()` and `summarize()` methods with conservative behavior
    so the package can be imported without external dependencies.
    """

    def __init__(self, host: Optional[str] = None):
        self.host = host or "https://grok.local"

    def list_models(self) -> List[str]:
        """Return a best-effort (stubbed) list of available Grok models.

        The shim does not perform network calls and returns an empty list by
        default to remain safe for unit testing and local use.

        Returns:
            A list of model identifier strings or an empty list.
        """
        try:
            return []
        except Exception:
            return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        """Return a deterministic join of message contents for tests.

        Args:
            messages: Iterable of message dicts or strings.
            settings: Optional settings (ignored by this stub).

        Returns:
            Joined message text as a single string.
        """
        try:
            parts = []
            for m in (messages or []):
                if isinstance(m, dict):
                    parts.append(m.get("content", ""))
                else:
                    parts.append(str(m))
            return "\n".join(p for p in parts if p)
        except Exception:
            return ""

    def stream(self, messages: Any, settings: Optional[dict] = None):
        """Streaming fallback for Grok provider.

        Yields the joined message text in sequential chunks.
        """
        text = self.summarize(messages, settings=settings)
        if not text:
            return
        chunk_size = 64
        try:
            if isinstance(settings, dict) and "chunk_size" in settings:
                chunk_size = int(settings.get("chunk_size", chunk_size) or chunk_size)
        except Exception:
            pass
        for i in range(0, len(text), chunk_size):
            yield text[i: i + chunk_size]

    def embed(self, texts: Any, **kwargs) -> List[List[float]]:
        """Embedding surface for tests: delegate to the embeddings helper."""
        try:
            from .embeddings import embed_texts
        except Exception:
            from modelito.embeddings import embed_texts

        texts_list = [str(t) for t in (texts or [])]
        dim = int(kwargs.get("dim", 8))
        return embed_texts(texts_list, dim=dim)
