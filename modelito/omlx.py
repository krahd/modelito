"""oMLX provider with HTTP-first local runtime integration.

The oMLX provider targets OpenAI-compatible HTTP endpoints exposed by local
oMLX runtimes. It keeps dependencies optional by using standard-library HTTP
clients and falls back to deterministic behaviour when a runtime is not
reachable.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Iterable, List, Optional
from urllib.request import Request, urlopen

from .messages import Message


def _extract_text_from_chat_response(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str):
                    return content
            text = first.get("text")
            if isinstance(text, str):
                return text
    return ""


class OMLXProvider:
    """Provider for oMLX-compatible HTTP runtimes.

    Args:
        base_url: Base URL for an OpenAI-compatible oMLX endpoint.
        model: Default model name.
        api_key: Optional bearer token for secured endpoints.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 20.0,
    ):
        self.base_url = (base_url or "http://127.0.0.1:11435/v1").rstrip("/")
        self.model = model or "omlx"
        self.api_key = api_key
        self.timeout = float(timeout)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _flatten_messages(self, messages: Iterable[Message | str]) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for m in (messages or []):
            if isinstance(m, Message):
                out.append({"role": m.role, "content": m.content})
            elif isinstance(m, str):
                out.append({"role": "user", "content": m})
            else:
                raise TypeError(
                    "OMLXProvider requires modelito.messages.Message instances; dicts are not supported"
                )
        return out

    def list_models(self) -> List[str]:
        try:
            req = Request(f"{self.base_url}/models", headers=self._headers(), method="GET")
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            models = data.get("data") if isinstance(data, dict) else None
            if isinstance(models, list):
                out: List[str] = []
                for item in models:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        out.append(item["id"])
                if out:
                    return out
        except Exception:
            pass
        return [self.model]

    def summarize(self, messages: Iterable[Message | str], settings: Optional[Dict[str, Any]] = None) -> str:
        flat = self._flatten_messages(messages)
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": flat,
            "stream": False,
        }
        if isinstance(settings, dict):
            payload.update(settings)

        try:
            req = Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            text = _extract_text_from_chat_response(data)
            if text:
                return text
        except Exception:
            pass

        # Deterministic fallback for offline tests.
        return "\n".join(m.get("content", "") for m in flat if m.get("content"))

    def stream(self, messages: Iterable[Message | str], settings: Optional[Dict[str, Any]] = None) -> Iterable[str]:
        flat = self._flatten_messages(messages)
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": flat,
            "stream": True,
        }
        if isinstance(settings, dict):
            payload.update(settings)

        try:
            req = Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            with urlopen(req, timeout=self.timeout) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    raw = line.decode("utf-8", errors="ignore").strip()
                    if not raw:
                        continue
                    if raw.startswith("data: "):
                        raw = raw[6:]
                    if raw == "[DONE]":
                        break
                    try:
                        evt = json.loads(raw)
                    except Exception:
                        continue
                    if isinstance(evt, dict):
                        choices = evt.get("choices")
                        if isinstance(choices, list) and choices:
                            first = choices[0]
                            if isinstance(first, dict):
                                delta = first.get("delta")
                                if isinstance(delta, dict):
                                    content = delta.get("content")
                                    if isinstance(content, str) and content:
                                        yield content
                                        continue
                                text = first.get("text")
                                if isinstance(text, str) and text:
                                    yield text
                return
        except Exception:
            pass

        text = "\n".join(m.get("content", "") for m in flat if m.get("content"))
        if not text:
            return
        chunk_size = 64
        if isinstance(settings, dict) and "chunk_size" in settings:
            try:
                chunk_size = int(settings.get("chunk_size") or chunk_size)
            except Exception:
                pass
        for i in range(0, len(text), chunk_size):
            yield text[i: i + chunk_size]

    async def acomplete(self, messages: Iterable[Message | str], settings: Optional[Dict[str, Any]] = None) -> str:
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: self.summarize(messages, settings=settings))
        except Exception:
            return self.summarize(messages, settings=settings)

    def embed(self, texts: Iterable[str], **kwargs: Any) -> List[List[float]]:
        inputs = [str(t) for t in (texts or [])]
        payload: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "input": inputs,
        }
        try:
            req = Request(
                f"{self.base_url}/embeddings",
                data=json.dumps(payload).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            items = data.get("data") if isinstance(data, dict) else None
            out: List[List[float]] = []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        emb = item.get("embedding")
                        if isinstance(emb, list):
                            out.append([float(v) for v in emb])
            if out:
                return out
        except Exception:
            pass

        from .embeddings import embed_texts

        return embed_texts(inputs, dim=int(kwargs.get("dim", 8)))
