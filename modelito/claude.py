"""Anthropic/Claude provider that prefers the `anthropic` SDK when available.

This module detects common Anthropic client shapes at runtime and attempts
to call the SDK for completions. When the SDK is unavailable or the call
fails, it falls back to a deterministic join of message contents for
offline-friendly behavior.
"""
from __future__ import annotations
import importlib

from typing import Any, List, Optional
from types import ModuleType

def _extract_text_from_response(res: Any) -> str:
    try:
        if not res:
            return ""
        if isinstance(res, dict):
            # common dict shapes
            if "completion" in res:
                return str(res.get("completion") or "")
            if "text" in res:
                return str(res.get("text") or "")
            if "choices" in res and isinstance(res["choices"], list) and res["choices"]:
                first = res["choices"][0]
                if isinstance(first, dict):
                    return str(first.get("text") or first.get("completion") or "")
                return str(first)
        # object-like response
        text = getattr(res, "text", None)
        if text:
            return str(text)
        completion = getattr(res, "completion", None)
        if completion:
            return str(completion)
    except Exception:
        pass
    return ""


class ClaudeProvider:
    """Provider for Anthropic/Claude that uses the SDK when present.

    The provider attempts multiple client shapes (modern `anthropic` client
    surfaces and common compatibility functions) and gracefully falls back
    to an offline stub when calls fail.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, client: Any = None):
        self.api_key = api_key
        self.model = model or "claude-2.1"
        self._client = client
        self._anthropic: Optional[ModuleType] = None
        try:
            self._anthropic = importlib.import_module("anthropic")
        except Exception:
            self._anthropic = None

        if self._client is None and self._anthropic is not None:
            try:
                if hasattr(self._anthropic, "Anthropic"):
                    try:
                        self._client = self._anthropic.Anthropic(
                            api_key=api_key) if api_key else self._anthropic.Anthropic()
                    except Exception:
                        self._client = None
                elif hasattr(self._anthropic, "Client"):
                    try:
                        self._client = self._anthropic.Client(
                            api_key=api_key) if api_key else self._anthropic.Client()
                    except Exception:
                        self._client = None
            except Exception:
                self._client = None

    def list_models(self) -> List[str]:
        try:
            if self._anthropic is not None:
                if hasattr(self._anthropic, "list_models"):
                    try:
                        return list(self._anthropic.list_models())
                    except Exception:
                        pass
        except Exception:
            pass
        return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        def _flatten(msgs: Any) -> str:
            try:
                parts = []
                for m in (msgs or []):
                    if isinstance(m, dict):
                        parts.append(m.get("content", ""))
                    else:
                        parts.append(str(m))
                return "\n".join(p for p in parts if p)
            except Exception:
                return ""

        prompt = _flatten(messages)

        if self._anthropic is not None and self._client is not None:
            try:
                client = self._client
                # modern: client.completions.create
                if hasattr(client, "completions") and hasattr(client.completions, "create"):
                    try:
                        res = client.completions.create(
                            model=self.model, prompt=prompt, **(settings or {}))
                        text = _extract_text_from_response(res)
                        if text:
                            return text
                    except Exception:
                        pass
                # alternate: client.create_completion
                if hasattr(client, "create_completion"):
                    try:
                        res = client.create_completion(
                            model=self.model, prompt=prompt, **(settings or {}))
                        text = _extract_text_from_response(res)
                        if text:
                            return text
                    except Exception:
                        pass
            except Exception:
                pass

        # deterministic fallback
        try:
            return prompt
        except Exception:
            return ""
