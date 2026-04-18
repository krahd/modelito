"""Compatibility shim for Claude (Anthropic) provider.

Provides a minimal `ClaudeProvider` wrapper that is safe for tests and
local usage without the actual Anthropic SDK.
"""
from __future__ import annotations

from typing import Any, List, Optional


class ClaudeProvider:
    """Compatibility shim for Anthropic/Claude providers.

    Implements a minimal `list_models()` and `summarize()` surface so code can
    import and use `ClaudeProvider` in tests without the real SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or "claude-2.1"

    def list_models(self) -> List[str]:
        """Return a best-effort list of available Claude model identifiers.

        Attempts a runtime import of the ``anthropic`` package and calls a
        discovery helper if present. Returns an empty list when the SDK is
        unavailable or the call fails.

        Returns:
            A list of model identifier strings or an empty list on failure.
        """
        try:
            import importlib

            anthropic = importlib.import_module("anthropic")
            # best-effort: try to introspect available models
            if hasattr(anthropic, "list_models"):
                try:
                    return list(anthropic.list_models())
                except Exception:
                    pass
        except Exception:
            pass
        return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        """Return a simple concatenation of message contents.

        This stub is intentionally minimal and deterministic so it remains
        safe for unit tests and examples when the real Anthropic client is
        not available.

        Args:
            messages: Iterable of message dicts or strings.
            settings: Optional settings (ignored by stub).

        Returns:
            Concatenated message contents as a string.
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
