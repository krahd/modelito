"""OpenAI-compatible HTTP provider base class.

Shared HTTP, streaming, embeddings, timeout, and error handling for all
OpenAI-compatible local runtime providers (oMLX, llama.cpp, LM Studio,
vLLM, etc.).

Subclass ``OpenAICompatibleHTTPProvider`` and set default ``base_url`` and
``model`` in your ``__init__`` to create a new provider profile without
duplicating request logic.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional
from urllib.request import Request, urlopen

from .exceptions import (
    LLMProviderError,
    ModelitoBadResponseError,
    ModelitoConnectionError,
    ModelitoModelNotFoundError,
    ModelitoProviderError,
    ModelitoTimeoutError,
)
from .messages import Message, Response


def _extract_chat_text(payload: Any) -> str:
    """Extract the assistant text from an OpenAI-style chat completion payload."""
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


def _extract_stream_text(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    choices = event.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            delta = first.get("delta")
            if isinstance(delta, dict):
                content = delta.get("content")
                if isinstance(content, str):
                    return content
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
            text = first.get("text")
            if isinstance(text, str):
                return text
    return ""


def _fallback_chat_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    messages = payload.get("messages")
    parts: List[str] = []
    if isinstance(messages, list):
        for item in messages:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str) and content:
                    parts.append(content)
            elif isinstance(item, str):
                parts.append(item)
    prompt = payload.get("prompt")
    if isinstance(prompt, str) and prompt:
        parts.append(prompt)
    text = "\n".join(parts)
    created = int(time.time())
    return {
        "id": f"chatcmpl-modelito-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": created,
        "model": None,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": None,
            }
        ],
        "usage": {
            "prompt_tokens": payload.get("prompt_tokens", 0) or 0,
            "completion_tokens": payload.get("completion_tokens", 0) or 0,
            "total_tokens": (payload.get("prompt_tokens", 0) or 0) + (payload.get("completion_tokens", 0) or 0),
        },
    }


class OpenAICompatibleHTTPProvider:
    """Base class for providers that speak OpenAI-compatible HTTP APIs.

    Implements ``list_models``, ``chat``, ``summarize``, ``stream``,
    ``acomplete``, and ``embed`` using standard-library HTTP only.

    Args:
        base_url: Root URL of the OpenAI-compatible API (no trailing slash).
        model: Default model name to use in requests.
        api_key: Optional bearer token for secured endpoints.
        timeout: HTTP request timeout in seconds.
        strict: When ``True``, raise typed Modelito exceptions instead of
            falling back to deterministic offline behaviour.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 20.0,
        strict: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = float(timeout)
        self.strict = strict

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _flatten_messages(self, messages: Iterable[Any]) -> List[Dict[str, str]]:
        """Convert messages to OpenAI-style dicts.

        Accepts :class:`~modelito.messages.Message` instances, plain strings
        (treated as ``role="user"``), and dicts with ``role``/``content`` keys.
        """
        out: List[Dict[str, str]] = []
        for m in messages or []:
            if isinstance(m, Message):
                out.append({"role": m.role, "content": m.content})
            elif isinstance(m, str):
                out.append({"role": "user", "content": m})
            elif isinstance(m, dict):
                out.append(
                    {
                        "role": str(m.get("role", "user")),
                        "content": str(m.get("content", "")),
                    }
                )
            else:
                raise TypeError(
                    f"Messages must be Message, str, or dict with role/content; "
                    f"got {type(m).__name__}"
                )
        return out

    def _classify_error(self, exc: Exception) -> LLMProviderError:
        """Convert a raw exception into a typed Modelito error."""
        import socket
        import urllib.error

        if isinstance(exc, urllib.error.HTTPError):
            if exc.code == 404:
                return ModelitoModelNotFoundError(str(exc))
            return ModelitoProviderError(f"HTTP {exc.code}: {exc}")
        if isinstance(exc, urllib.error.URLError):
            reason = str(getattr(exc, "reason", exc)).lower()
            if "timed out" in reason or "timeout" in reason:
                return ModelitoTimeoutError(str(exc))
            return ModelitoConnectionError(str(exc))
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return ModelitoTimeoutError(str(exc))
        if isinstance(exc, (json.JSONDecodeError, ValueError)):
            return ModelitoBadResponseError(str(exc))
        return ModelitoProviderError(str(exc))

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Any:
        req = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8")
        return json.loads(body)

    def _fallback_stream_events(self, payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        response = _fallback_chat_response(payload)
        created = response.get("created") or int(time.time())
        model = response.get("model") or self.model
        chunk_size = 64
        if isinstance(payload, dict) and "chunk_size" in payload:
            try:
                chunk_size = max(1, int(payload.get("chunk_size") or chunk_size))
            except Exception:
                chunk_size = 64
        yield {
            "id": response["id"],
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }
            ],
        }
        text = _extract_chat_text(response)
        for start in range(0, len(text), chunk_size):
            chunk = text[start: start + chunk_size]
            if not chunk:
                continue
            yield {
                "id": response["id"],
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None,
                    }
                ],
            }
        yield {
            "id": response["id"],
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }

    def _strict_raise(self, exc: Exception) -> None:
        """Raise a typed Modelito error if ``strict=True``; otherwise no-op."""
        if self.strict:
            raise self._classify_error(exc) from exc

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def list_models(self) -> List[str]:
        """Return available model IDs.

        In non-strict mode falls back to ``[self.model]`` on any failure.
        In strict mode raises a typed Modelito error on connection or parse
        failure, and raises ``ModelitoBadResponseError`` when the server
        returns valid JSON but no usable model IDs.
        """
        try:
            req = Request(
                f"{self.base_url}/models",
                headers=self._headers(),
                method="GET",
            )
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            models = data.get("data") if isinstance(data, dict) else None
            if isinstance(models, list):
                out: List[str] = [
                    item["id"]
                    for item in models
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                ]
                if out:
                    return out
            if self.strict:
                raise ModelitoBadResponseError(
                    "list_models: server returned valid JSON but no usable model IDs"
                )
        except LLMProviderError:
            raise
        except Exception as exc:
            self._strict_raise(exc)
        return [self.model]

    def raw_complete(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request_payload = dict(payload or {})
        request_payload.setdefault("model", self.model)
        try:
            data = self._post_json("/chat/completions", request_payload)
            if isinstance(data, dict):
                if self.strict and "choices" not in data:
                    raise ModelitoBadResponseError(
                        "raw_complete: server returned valid JSON but no choices"
                    )
                return data
            if self.strict:
                raise ModelitoBadResponseError(
                    "raw_complete: server returned a non-dict JSON response"
                )
        except LLMProviderError:
            raise
        except Exception as exc:
            if self.strict:
                raise self._classify_error(exc) from exc
        return _fallback_chat_response(request_payload)

    def raw_stream(self, payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        request_payload = dict(payload or {})
        request_payload.setdefault("model", self.model)
        request_payload["stream"] = True
        try:
            req = Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(request_payload).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            with urlopen(req, timeout=self.timeout) as resp:
                while True:
                    raw_line = resp.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[5:].lstrip()
                    if line == "[DONE]":
                        break
                    try:
                        event = json.loads(line)
                    except Exception:
                        if self.strict:
                            raise ModelitoBadResponseError(
                                f"raw_stream: unable to parse stream event: {line!r}"
                            )
                        continue
                    if isinstance(event, dict):
                        yield event
                return
        except LLMProviderError:
            raise
        except Exception as exc:
            if self.strict:
                raise self._classify_error(exc) from exc
        yield from self._fallback_stream_events(request_payload)

    def chat(
        self,
        messages: Iterable[Any],
        settings: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Send messages and return a full :class:`~modelito.messages.Response`.

        Populates ``text``, ``raw``, ``model``, ``finish_reason``,
        ``tokens_in``, and ``tokens_out`` from the provider response.

        In ``strict=False`` mode (default), falls back to a deterministic
        :class:`~modelito.messages.Response` whose ``text`` is the
        concatenation of the input messages if the HTTP call fails.

        In ``strict=True`` mode, raises a typed Modelito exception on failure.
        """
        flat = self._flatten_messages(messages)
        payload: Dict[str, Any] = {"model": self.model, "messages": flat, "stream": False}
        if isinstance(settings, dict):
            payload.update(settings)

        try:
            data = self.raw_complete(payload)
            text = _extract_chat_text(data)

            model_name: Optional[str] = None
            finish_reason: Optional[str] = None
            tokens_in: Optional[int] = None
            tokens_out: Optional[int] = None

            if isinstance(data, dict):
                mn = data.get("model")
                if isinstance(mn, str):
                    model_name = mn
                choices = data.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    if isinstance(first, dict):
                        fr = first.get("finish_reason")
                        if isinstance(fr, str):
                            finish_reason = fr
                usage = data.get("usage")
                if isinstance(usage, dict):
                    ti = usage.get("prompt_tokens")
                    to_ = usage.get("completion_tokens")
                    tokens_in = int(ti) if ti is not None else None
                    tokens_out = int(to_) if to_ is not None else None

            if not text and self.strict:
                raise ModelitoBadResponseError(
                    "chat: server returned a valid response but no text content"
                )

            return Response(
                text=text,
                raw=data,
                model=model_name,
                finish_reason=finish_reason,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            self._strict_raise(exc)

        # Non-strict deterministic fallback.
        fallback_text = "\n".join(
            m.get("content", "") for m in flat if m.get("content")
        )
        return Response(text=fallback_text)

    def summarize(
        self,
        messages: Iterable[Any],
        settings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Return the assistant text from ``chat()``."""
        return self.chat(messages, settings).text

    def stream(
        self,
        messages: Iterable[Any],
        settings: Optional[Dict[str, Any]] = None,
    ) -> Iterable[str]:
        """Yield text chunks from a streaming chat completion.

        Falls back to chunked deterministic output in non-strict mode when the
        endpoint is unavailable.  In strict mode, raises a typed Modelito
        exception on connection or protocol failure.
        """
        flat = self._flatten_messages(messages)
        payload: Dict[str, Any] = {"model": self.model, "messages": flat, "stream": True}
        if isinstance(settings, dict):
            payload.update(settings)

        try:
            for event in self.raw_stream(payload):
                text = _extract_stream_text(event)
                if text:
                    yield text
            return
        except LLMProviderError:
            raise
        except Exception as exc:
            if self.strict:
                raise self._classify_error(exc) from exc

        # Non-strict deterministic stream fallback.
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

    async def acomplete(
        self,
        messages: Iterable[Any],
        settings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Async wrapper around ``summarize`` using a thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.summarize(messages, settings=settings)
        )

    def embed(self, texts: Iterable[str], **kwargs: Any) -> List[List[float]]:
        """Return embeddings for *texts*.

        Falls back to a deterministic stub in non-strict mode when the
        endpoint is unavailable.
        """
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
                if self.strict and len(out) != len(inputs):
                    raise ModelitoBadResponseError(
                        f"embed: expected {len(inputs)} embeddings, got {len(out)}"
                    )
                return out
            # Server responded with valid JSON but no usable embeddings.
            if self.strict:
                raise ModelitoBadResponseError(
                    "embed: server returned valid JSON but no usable embeddings"
                )
        except LLMProviderError:
            raise
        except Exception as exc:
            self._strict_raise(exc)

        from .embeddings import embed_texts

        return embed_texts(inputs, dim=int(kwargs.get("dim", 8)))
