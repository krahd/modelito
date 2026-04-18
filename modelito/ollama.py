"""Compatibility shim for Ollama provider.

Provides a lightweight `OllamaProvider` compatible with older imports
(`from modelito import OllamaProvider` and `import modelito.ollama`).

This implementation is intentionally minimal: it exposes `list_models()`
and `summarize()` with safe defaults so downstream projects that expect
the provider API during tests or local runs continue to work.
"""
from __future__ import annotations

from typing import Any, List, Optional
from .ollama_service import endpoint_url, server_is_up


class OllamaProvider:
    """Minimal compatibility shim for Ollama-style providers.

    Provides `list_models()` and `summarize()` with safe defaults for local
    testing and compatibility with older imports.
    """

    def __init__(self, host: Optional[str] = None):
        self.host = host or endpoint_url('127.0.0.1', 11434)

    def list_models(self) -> List[str]:
        """Return a best-effort list of locally available Ollama models.

        This shim avoids making heavy network calls and instead returns an
        empty list when a local server is reachable or the check fails.

        Returns:
            A list of model identifiers (often empty for the compatibility shim).
        """
        try:
            if server_is_up('127.0.0.1', 11434):
                return []
        except Exception:
            pass
        return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        """Produce a deterministic summary by concatenating message contents.

        This minimal implementation is intended for local testing and
        compatibility; it does not contact a model service.

        Args:
            messages: Iterable of message dicts (containing ``content``) or
                plain strings.
            settings: Optional settings passed through by callers (ignored).

        Returns:
            A string containing the joined message contents.
        """
        try:
            parts = []
            for m in (messages or []):
                if isinstance(m, dict):
                    parts.append(m.get('content', ''))
                else:
                    parts.append(str(m))
            return "\n".join(p for p in parts if p)
        except Exception:
            return ""
