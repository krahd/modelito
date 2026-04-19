"""Anthropic/Claude provider that prefers the `anthropic` SDK when available.

This module detects common Anthropic client shapes at runtime and attempts
to call the SDK for completions. When the SDK is unavailable or the call
fails, it falls back to a deterministic join of message contents for
offline-friendly behavior.
"""
from __future__ import annotations
import importlib

from typing import Any, List, Optional
from .messages import Message
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
                    if isinstance(m, Message):
                        parts.append(m.content)
                    elif isinstance(m, str):
                        parts.append(m)
                    else:
                        raise TypeError(
                            "ClaudeProvider.summarize requires modelito.messages.Message instances; dicts are not supported")
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

    def stream(self, messages: Any, settings: Optional[dict] = None):
        """SDK-aware streaming for Claude.

        Try several common client shapes for streaming completions and
        yield incremental text chunks. Falls back to deterministic
        chunking via `summarize()` when streaming isn't available.
        """
        def _flatten(msgs: Any) -> str:
            try:
                parts = []
                for m in (msgs or []):
                    if isinstance(m, Message):
                        parts.append(m.content)
                    elif isinstance(m, str):
                        parts.append(m)
                    else:
                        raise TypeError(
                            "ClaudeProvider.stream requires modelito.messages.Message instances; dicts are not supported")
                return "\n".join(p for p in parts if p)
            except Exception:
                return ""

        prompt = _flatten(messages)

        import json

        def _extract_delta_text(evt: Any) -> str:
            if not evt:
                return ""
            if isinstance(evt, str):
                s = evt.strip()
                if s.startswith("data: "):
                    s = s[6:]
                try:
                    evt = json.loads(s)
                except Exception:
                    return s
            if isinstance(evt, dict):
                for k in ("text", "completion", "content", "output"):
                    if k in evt and isinstance(evt.get(k), str):
                        return evt.get(k) or ""
                choices = evt.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    if isinstance(first, dict):
                        delta = first.get("delta") or first.get("message") or {}
                        if isinstance(delta, dict) and "content" in delta:
                            return str(delta.get("content") or "")
                        if "text" in first:
                            return str(first.get("text") or "")
                    else:
                        return str(first)
            try:
                # object-like
                choices = getattr(evt, "choices", None)
                if choices:
                    first = choices[0]
                    delta = getattr(first, "delta", None)
                    if delta:
                        if isinstance(delta, dict) and "content" in delta:
                            return str(delta.get("content") or "")
                        return str(delta)
                    msg = getattr(first, "message", None)
                    if msg:
                        return str(getattr(msg, "content", "") or "")
                for attr in ("text", "completion", "content", "output"):
                    val = getattr(evt, attr, None)
                    if val:
                        return str(val)
            except Exception:
                pass
            return ""

        client = self._client or self._anthropic
        if client is not None:
            try:
                # Try modern streaming: client.completions.stream(...)
                comps = getattr(client, "completions", None)
                if comps is not None and hasattr(comps, "stream"):
                    for e in comps.stream(model=self.model, prompt=prompt, **(settings or {})):
                        txt = _extract_delta_text(e)
                        if txt:
                            yield txt
                    return

                # Try create(..., stream=True)
                if comps is not None and hasattr(comps, "create"):
                    try:
                        for e in comps.create(model=self.model, prompt=prompt, stream=True, **(settings or {})):
                            txt = _extract_delta_text(e)
                            if txt:
                                yield txt
                        return
                    except TypeError:
                        pass

                # Try alternate client shape
                if hasattr(client, "create_completion"):
                    try:
                        for e in client.create_completion(model=self.model, prompt=prompt, stream=True, **(settings or {})):
                            txt = _extract_delta_text(e)
                            if txt:
                                yield txt
                        return
                    except Exception:
                        pass
            except Exception:
                pass

        # Fallback deterministic chunking
        text = self.summarize(messages, settings=settings)
        if not text:
            return
        chunk_size = 64
        try:
            if isinstance(settings, dict) and "chunk_size" in settings:
                chunk_size = int(settings.get("chunk_size", chunk_size) or chunk_size)
        except Exception:
            pass
        for i in range(0, len(text), chunk_size):
            yield text[i: i + chunk_size]

    def embed(self, texts: Any, **kwargs) -> List[List[float]]:
        """Embedding surface for tests: delegate to the embeddings helper."""
        try:
            from .embeddings import embed_texts
        except Exception:
            from modelito.embeddings import embed_texts

        texts_list = [str(t) for t in (texts or [])]
        dim = int(kwargs.get("dim", 8))
        return embed_texts(texts_list, dim=dim)
