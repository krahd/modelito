"""Compatibility shim for OpenAI provider.

Minimal `OpenAIProvider` implementation that provides safe, offline-friendly
defaults for tests and local usage without requiring network access.
"""
from __future__ import annotations

from typing import Any, List, Optional


class OpenAIProvider:
    """Minimal compatibility shim for the OpenAI provider.

    Provides `list_models()` and `summarize()` with conservative, offline-
    friendly defaults so downstream projects can import and use the API in
    tests without requiring the official SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or "gpt-3.5-turbo"

    def list_models(self) -> List[str]:
        """Return a best-effort list of available model identifiers.

        This implementation attempts a non-blocking, runtime import of the
        official ``openai`` client and inspects the client surface for a
        ``Model.list()`` API. When the real client is unavailable or the
        call fails, an empty list is returned to keep the shim offline-
        friendly and safe for unit tests.

        Returns:
            A list of model identifier strings, or an empty list on failure.
        """
        try:
            # best-effort: attempt to import the official client and list models
            import importlib

            openai = importlib.import_module("openai")
            try:
                # Newer clients expose Model.list()
                models = getattr(openai, "Model", None)
                if models is not None and hasattr(models, "list"):
                    res = models.list()
                    # try to coerce into a list of names
                    return [getattr(m, "id", str(m)) for m in getattr(res, "data", [])]
            except Exception:
                pass
        except Exception:
            pass
        return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        """Produce a simple, deterministic summary from ``messages``.

        This shim concatenates message contents in order and is intended to
        be safe for offline unit tests and examples where a real model
        invocation is not possible.

        Args:
            messages: Iterable of message dicts (with ``content``) or strings.
            settings: Optional provider-specific settings (ignored by stub).

        Returns:
            A single string containing the joined message contents.
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
