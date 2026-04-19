"""Compatibility shim for OpenAI provider.

Minimal `OpenAIProvider` implementation that provides safe, offline-friendly
defaults for tests and local usage without requiring network access.
"""
from __future__ import annotations
import importlib

from typing import Any, List, Optional


"""OpenAI provider that prefers the official SDK when available.

This implementation will attempt to use the installed `openai` package
(modern and legacy client surfaces are both supported via runtime
introspection). When the SDK is unavailable or a call fails, the provider
falls back to a deterministic, offline-friendly summarizer used by tests.
"""



def _extract_text_from_response(res: Any) -> str:
    if not res:
        return ""
    # dict-like responses
    try:
        if isinstance(res, dict):
            if "text" in res:
                return str(res.get("text") or "")
            if "output" in res:
                out = res.get("output")
                if isinstance(out, list) and out:
                    first = out[0]
                    if isinstance(first, dict):
                        return str(first.get("content") or first)
                    return str(first)
                return str(out or "")
            choices = res.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    msg = first.get("message") or {}
                    return str(msg.get("content") or first.get("text") or "")
                return str(first)
        # object-like responses
        choices = getattr(res, "choices", None)
        if choices:
            first = choices[0]
            message = getattr(first, "message", None)
            if message is not None:
                return str(getattr(message, "content", "") or "")
            return str(getattr(first, "text", "") or str(first))
    except Exception:
        pass
    return ""


class OpenAIProvider:
    """OpenAI provider using the official SDK when available.

    Methods provided:
    - `list_models()` — best-effort model enumeration using `openai.Model.list()`.
    - `summarize(messages, settings)` — attempts a chat completion via the
      SDK and falls back to a deterministic join of message contents.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, client: Any = None):
        self.api_key = api_key
        self.model = model or "gpt-3.5-turbo"
        self._client = client
        try:
            self._openai = importlib.import_module("openai")
        except Exception:
            self._openai = None

        # Try to construct a modern client if none was provided.
        if self._client is None and self._openai is not None:
            try:
                if hasattr(self._openai, "OpenAI"):
                    try:
                        self._client = self._openai.OpenAI(
                            api_key=api_key) if api_key else self._openai.OpenAI()
                    except Exception:
                        self._client = None
            except Exception:
                self._client = None

    def list_models(self) -> List[str]:
        try:
            if self._openai is not None:
                client = self._client or self._openai
                if hasattr(client, "Model") and hasattr(client.Model, "list"):
                    try:
                        res = client.Model.list()
                        data = getattr(res, "data", None) or res
                        return [getattr(m, "id", str(m)) for m in (data or [])]
                    except Exception:
                        pass
                if hasattr(self._openai, "Model") and hasattr(self._openai.Model, "list"):
                    try:
                        res = self._openai.Model.list()
                        return [getattr(m, "id", str(m)) for m in getattr(res, "data", [])]
                    except Exception:
                        pass
        except Exception:
            pass
        return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        def _flatten(msgs: Any) -> List[dict]:
            if not msgs:
                return []
            if isinstance(msgs, (list, tuple)):
                out = []
                for m in msgs:
                    if isinstance(m, dict):
                        out.append({"role": m.get("role", "user"),
                                   "content": m.get("content", str(m))})
                    else:
                        out.append({"role": "user", "content": str(m)})
                return out
            return [{"role": "user", "content": str(msgs)}]

        msgs = _flatten(messages)

        # Try SDK-backed chat completion (modern and legacy APIs).
        if self._openai is not None:
            try:
                client = self._client
                if client and hasattr(client, "chat") and hasattr(client.chat, "completions") and hasattr(client.chat.completions, "create"):
                    res = client.chat.completions.create(
                        model=self.model, messages=msgs, **(settings or {}))
                    text = _extract_text_from_response(res)
                    if text:
                        return text

                if hasattr(self._openai, "ChatCompletion") and hasattr(self._openai.ChatCompletion, "create"):
                    res = self._openai.ChatCompletion.create(
                        model=self.model, messages=msgs, **(settings or {}))
                    text = _extract_text_from_response(res)
                    if text:
                        return text
            except Exception:
                pass

        # Deterministic fallback
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
