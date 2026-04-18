"""Compatibility shim for OpenAI provider.

Minimal `OpenAIProvider` implementation that provides safe, offline-friendly
defaults for tests and local usage without requiring network access.
"""
from __future__ import annotations

from typing import Any, List, Optional


class OpenAIProvider:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or "gpt-3.5-turbo"

    def list_models(self) -> List[str]:
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
