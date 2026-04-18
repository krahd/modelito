"""Compatibility shim for Gemini provider.

This provides a minimal `GeminiProvider` with safe defaults so downstream
projects can import and use it during tests or local runs without requiring
network access or external SDKs.
"""
from __future__ import annotations

from typing import Any, List, Optional


class GeminiProvider:
    """Lightweight compatibility shim for Gemini-like providers.

    This class implements `list_models()` and `summarize()` with safe defaults
    suitable for unit tests and local runs where the external SDK is absent.
    """

    def __init__(self, host: Optional[str] = None):
        # host is informational; default is a placeholder URL
        self.host = host or "https://gemini.local"

    def list_models(self) -> List[str]:
        """Return a stubbed list of available Gemini models.

        This shim intentionally performs no network activity and returns an
        empty list to keep tests and examples offline-friendly.

        Returns:
            A list of model identifier strings (often empty in the stub).
        """
        try:
            return []
        except Exception:
            return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        """Produce a safe, deterministic summary by joining message texts.

        Args:
            messages: Iterable of message dicts or strings.
            settings: Optional provider settings (ignored by stub).

        Returns:
            Joined message contents as a string.
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
