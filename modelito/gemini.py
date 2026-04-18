"""Compatibility shim for Gemini provider.

This provides a minimal `GeminiProvider` with safe defaults so downstream
projects can import and use it during tests or local runs without requiring
network access or external SDKs.
"""
from __future__ import annotations

from typing import Any, List, Optional


class GeminiProvider:
    def __init__(self, host: Optional[str] = None):
        # host is informational; default is a placeholder URL
        self.host = host or "https://gemini.local"

    def list_models(self) -> List[str]:
        # Best-effort stub: no network calls here.
        try:
            return []
        except Exception:
            return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        # Minimal safe summarizer: join message contents
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
