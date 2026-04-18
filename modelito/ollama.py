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
    def __init__(self, host: Optional[str] = None):
        self.host = host or endpoint_url('127.0.0.1', 11434)

    def list_models(self) -> List[str]:
        # Best-effort: if server is up, return empty list (no network calls here).
        try:
            if server_is_up('127.0.0.1', 11434):
                return []
        except Exception:
            pass
        return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        # Minimal safe summarizer: join user/assistant message text.
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
