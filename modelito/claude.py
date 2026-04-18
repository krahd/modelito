"""Compatibility shim for Claude (Anthropic) provider.

Provides a minimal `ClaudeProvider` wrapper that is safe for tests and
local usage without the actual Anthropic SDK.
"""
from __future__ import annotations

from typing import Any, List, Optional


class ClaudeProvider:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or "claude-2.1"

    def list_models(self) -> List[str]:
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
