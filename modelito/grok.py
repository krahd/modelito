"""Compatibility shim for Grok provider.

Minimal `GrokProvider` implementation with safe defaults for local testing
and import compatibility.
"""
from __future__ import annotations

from typing import Any, List, Optional


class GrokProvider:
    def __init__(self, host: Optional[str] = None):
        self.host = host or "https://grok.local"

    def list_models(self) -> List[str]:
        try:
            return []
        except Exception:
            return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
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
