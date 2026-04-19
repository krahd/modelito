"""Compatibility shim for OpenAI provider.

Minimal `OpenAIProvider` implementation that provides safe, offline-friendly
defaults for tests and local usage without requiring network access.
"""
from __future__ import annotations
import importlib

from typing import Any, List, Optional
from types import ModuleType


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
        self._openai: Optional[ModuleType] = None
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

    def stream(self, messages: Any, settings: Optional[dict] = None):
        """Streaming provider surface attempting SDK streaming first.

        Tries several common client shapes (modern and legacy). Falls back
        to chunked deterministic output when streaming is unavailable.
        """

        def _flatten_msgs(msgs: Any) -> List[dict]:
            if not msgs:
                return []
            if isinstance(msgs, (list, tuple)):
                out: List[dict] = []
                for m in msgs:
                    if isinstance(m, dict):
                        out.append({"role": m.get("role", "user"),
                                   "content": m.get("content", str(m))})
                    else:
                        # dataclass-like or plain string
                        role = getattr(m, "role", "user") if hasattr(m, "role") else "user"
                        content = getattr(m, "content", str(m)) if hasattr(m, "content") else str(m)
                        out.append({"role": role, "content": content})
                return out
            return [{"role": "user", "content": str(msgs)}]

        msgs = _flatten_msgs(messages)

        import json

        def _extract_delta_text(event: Any) -> str:
            if not event:
                return ""
            # string payloads may be newline/json-prefixed
            if isinstance(event, str):
                s = event.strip()
                if s.startswith("data: "):
                    s = s[6:]
                try:
                    event = json.loads(s)
                except Exception:
                    return s

            # dict-like
            if isinstance(event, dict):
                for k in ("text", "content", "output"):
                    if k in event and isinstance(event.get(k), str):
                        return event.get(k) or ""
                choices = event.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    if isinstance(first, dict):
                        delta = first.get("delta") or first.get("message") or {}
                        if isinstance(delta, dict):
                            if "content" in delta:
                                c = delta.get("content") or ""
                                if isinstance(c, str):
                                    return c
                                if isinstance(c, list):
                                    return "".join(str(x) for x in c)
                        if "message" in first and isinstance(first["message"], dict):
                            return str(first["message"].get("content") or "")
                        if "text" in first:
                            return str(first.get("text") or "")
                    else:
                        return str(first)

            # object-like
            try:
                choices = getattr(event, "choices", None)
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
                for attr in ("text", "content", "output"):
                    val = getattr(event, attr, None)
                    if val:
                        return str(val)
            except Exception:
                pass
            return ""

        client = self._client or self._openai
        if client is not None:
            try:
                # Preferred modern shape: client.chat.completions.stream(...)
                chat = getattr(client, "chat", None)
                if chat is not None:
                    comps = getattr(chat, "completions", None)
                    if comps is not None:
                        if hasattr(comps, "stream"):
                            for evt in comps.stream(model=self.model, messages=msgs, **(settings or {})):
                                txt = _extract_delta_text(evt)
                                if txt:
                                    yield txt
                            return
                        if hasattr(comps, "create"):
                            try:
                                for evt in comps.create(model=self.model, messages=msgs, stream=True, **(settings or {})):
                                    txt = _extract_delta_text(evt)
                                    if txt:
                                        yield txt
                                return
                            except TypeError:
                                # create() may not accept stream param
                                pass

                # legacy module-level ChatCompletion.create(..., stream=True)
                if hasattr(self._openai, "ChatCompletion") and hasattr(self._openai.ChatCompletion, "create"):
                    try:
                        for evt in self._openai.ChatCompletion.create(model=self.model, messages=msgs, stream=True, **(settings or {})):
                            txt = _extract_delta_text(evt)
                            if txt:
                                yield txt
                        return
                    except Exception:
                        pass

                # Newer "responses" streaming API
                if hasattr(client, "responses") and hasattr(client.responses, "stream"):
                    try:
                        for evt in client.responses.stream(model=self.model, input=msgs, **(settings or {})):
                            txt = _extract_delta_text(evt)
                            if txt:
                                yield txt
                        return
                    except Exception:
                        pass
            except Exception:
                pass

        # Fallback: deterministic chunked output
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

    async def acomplete(self, messages: Any, settings: Optional[dict] = None) -> str:
        """Async wrapper for `summarize()` using a threadpool executor."""
        try:
            import asyncio

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: self.summarize(messages, settings=settings))
        except Exception:
            return self.summarize(messages, settings=settings)

    def embed(self, texts: Any, **kwargs) -> List[List[float]]:
        """Attempt to use provider SDK for embeddings, fallback to stub.

        Supports common client shapes (modern and legacy). Returns a list
        of vectors for each input text.
        """
        try:
            client = self._client or self._openai
            if client is not None:
                # modern client: client.embeddings.create(input=[...])
                emb_api = getattr(client, "embeddings", None)
                if emb_api is not None and hasattr(emb_api, "create"):
                    res = emb_api.create(input=list(texts or []), **kwargs)
                    data = getattr(res, "data", None) if not isinstance(
                        res, dict) else res.get("data")
                    out: List[List[float]] = []
                    for item in (data or []):
                        if isinstance(item, dict) and "embedding" in item:
                            out.append(list(item.get("embedding") or []))
                        else:
                            out.append(list(getattr(item, "embedding", [])))
                    if out:
                        return out

                # older shape: client.Embedding.create(input=[...])
                if hasattr(client, "Embedding") and hasattr(client.Embedding, "create"):
                    res = client.Embedding.create(input=list(texts or []), **kwargs)
                    data = getattr(res, "data", None) if not isinstance(
                        res, dict) else res.get("data")
                    out = []
                    for item in (data or []):
                        if isinstance(item, dict) and "embedding" in item:
                            out.append(list(item.get("embedding") or []))
                        else:
                            out.append(list(getattr(item, "embedding", [])))
                    if out:
                        return out
        except Exception:
            pass

        # Fallback to test stub
        try:
            from .embeddings import embed_texts
        except Exception:
            from modelito.embeddings import embed_texts

        dim = int(kwargs.get("dim", 8))
        return embed_texts(texts or [], dim=dim)
