"""Ollama provider and local runtime helpers.

The provider exposes the standard modelito provider surface for listing models,
summarising messages, streaming text, and embeddings. It also implements raw
OpenAI-compatible chat passthrough through Ollama's `/v1/chat/completions`
endpoint so `modelito-serve` can preserve tool-call metadata and other raw
OpenAI-compatible fields.
"""

from __future__ import annotations

import json as _json
import time
import uuid
from typing import Any, Iterable, List, Optional
from urllib.request import Request, urlopen

from .exceptions import (
    ModelitoBadResponseError,
    ModelitoConnectionError,
    ModelitoProviderError,
    ModelitoTimeoutError,
)
from .messages import flatten_message_inputs
from .provider import MessageInput
from .ollama_service import (
    endpoint_url,
    server_is_up,
    json_post,
    list_local_models,
    list_remote_models,
    ollama_installed,
    run_ollama_command,
    running_model_names,
)


_OLLAMA_CHAT_TOP_LEVEL_SETTINGS = frozenset(
    {
        "format",
        "keep_alive",
        "logprobs",
        "think",
        "tools",
        "top_logprobs",
    }
)
_OLLAMA_GENERATE_TOP_LEVEL_SETTINGS = frozenset(
    {
        "format",
        "images",
        "keep_alive",
        "logprobs",
        "raw",
        "suffix",
        "system",
        "think",
        "top_logprobs",
    }
)
_OLLAMA_GENERATION_OPTIONS = frozenset(
    {
        "draft_num_predict",
        "frequency_penalty",
        "main_gpu",
        "min_p",
        "num_batch",
        "num_ctx",
        "num_gpu",
        "num_keep",
        "num_predict",
        "num_thread",
        "presence_penalty",
        "repeat_last_n",
        "repeat_penalty",
        "seed",
        "stop",
        "temperature",
        "top_k",
        "top_p",
        "typical_p",
        "use_mmap",
    }
)


def _apply_ollama_settings(
    payload: dict[str, Any],
    settings: Optional[dict[str, Any]],
    endpoint: str,
) -> None:
    """Merge recognised settings without guessing where unknown keys belong.

    ``settings["options"]`` is the explicit escape hatch for model-specific
    Ollama options that Modelito does not yet recognise.
    """
    if not isinstance(settings, dict):
        return

    if endpoint == "/api/chat":
        top_level_settings = _OLLAMA_CHAT_TOP_LEVEL_SETTINGS
    elif endpoint == "/api/generate":
        top_level_settings = _OLLAMA_GENERATE_TOP_LEVEL_SETTINGS
    else:
        top_level_settings = frozenset()
    nested_options = settings.get("options")
    options = dict(nested_options) if isinstance(nested_options, dict) else {}

    for key, value in settings.items():
        if key == "options" or key in {"chunk_size", "stream"}:
            continue
        if key in top_level_settings:
            payload[key] = value
            continue
        if key == "response_format":
            if isinstance(value, dict) and value.get("type") == "json_object":
                payload["format"] = "json"
            elif isinstance(value, dict) and value.get("type") == "json_schema":
                json_schema = value.get("json_schema")
                if isinstance(json_schema, dict) and isinstance(
                    json_schema.get("schema"), dict
                ):
                    payload["format"] = json_schema["schema"]
            continue
        if key == "max_tokens":
            if "num_predict" not in settings and "num_predict" not in options:
                options["num_predict"] = value
            continue
        if key in _OLLAMA_GENERATION_OPTIONS:
            options[key] = value

    if options:
        payload["options"] = options


class OllamaProvider:
    """Provider for local Ollama runtimes.

    `OllamaProvider` supports the standard modelito provider methods, local Ollama
    HTTP/CLI fallbacks, embeddings, and raw OpenAI-compatible chat passthrough via
    Ollama's `/v1/chat/completions` endpoint.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 11434,
        model: Optional[str] = None,
        timeout: float = 20.0,
        strict: bool = False,
        **_: Any,
    ):
        """Initialize the provider.

        When an Ollama HTTP API is reachable at ``host:port`` the provider
        will attempt to use it for `list_models()` and `summarize()` calls.
        With ``strict=False``, failures may fall back through the Ollama CLI to
        a deterministic offline-friendly shim. With ``strict=True``, summary
        and streaming calls use the direct OpenAI-compatible HTTP transport and
        propagate failures without changing transport.
        """
        # Accept host with or without scheme; endpoint_url will normalize it.
        self.host = host or "http://127.0.0.1"
        self.port = int(port or 11434)
        self.model = model
        self.timeout = float(timeout)
        self.strict = bool(strict)

    def list_models(self) -> List[str]:
        """Return a best-effort list of locally available Ollama models.

        This shim avoids making heavy network calls and instead returns an
        empty list when a local server is reachable or the check fails.

        Returns:
            A list of model identifiers (often empty for the compatibility shim).
        """
        try:
            if server_is_up(self.host, self.port):
                # Prefer local enumeration via the CLI helper when the HTTP
                # API is available — this will return a best-effort list and
                # is resilient when the CLI is missing.
                models = list_local_models()
                if models:
                    return models
                # if nothing local, try running names reported by `ollama ps`
                try:
                    running = running_model_names(
                        self.host.replace("http://", "").replace("https://", "")
                    )
                    if running:
                        return running
                except Exception:
                    pass
        except Exception:
            pass

        # If the HTTP API isn't reachable try probing the CLI directly
        try:
            if ollama_installed():
                models = list_local_models()
                if models:
                    return models
                remote = list_remote_models()
                if remote:
                    return remote
        except Exception:
            pass

        return []

    @staticmethod
    def _strict_messages(
        messages: Iterable[MessageInput],
    ) -> list[dict[str, Any]]:
        return flatten_message_inputs(messages)

    def _strict_summarize(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[dict[str, Any]],
    ) -> str:
        payload: dict[str, Any] = {"messages": self._strict_messages(messages)}
        if settings:
            payload.update(settings)
        response = self.raw_complete(payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelitoBadResponseError(
                "Ollama strict summarize returned no completion choices"
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise ModelitoBadResponseError(
                "Ollama strict summarize returned an invalid completion choice"
            )
        message = first.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return str(message["content"])
        if isinstance(first.get("text"), str):
            return str(first["text"])
        raise ModelitoBadResponseError(
            "Ollama strict summarize returned no textual completion"
        )

    def _strict_stream(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[dict[str, Any]],
    ) -> Iterable[str]:
        payload: dict[str, Any] = {"messages": self._strict_messages(messages)}
        if settings:
            payload.update(settings)
        for event in self.raw_stream(payload):
            choices = event.get("choices") if isinstance(event, dict) else None
            if not isinstance(choices, list) or not choices:
                continue
            first = choices[0]
            if not isinstance(first, dict):
                continue
            delta = first.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                content = str(delta["content"])
                if content:
                    yield content
                continue
            text = first.get("text")
            if isinstance(text, str) and text:
                yield text

    def summarize(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[dict[str, Any]] = None,
    ) -> str:
        """Return assistant text from Ollama or the configured fallback path.

        Strict mode uses direct HTTP and propagates failures. Non-strict mode
        retains the legacy HTTP, CLI, and deterministic fallback chain.

        Args:
            messages: Iterable of message dicts (containing ``content``) or
                plain strings.
            settings: Optional generation settings. Ollama model parameters are
                sent in the native API's ``options`` object; request controls
                such as ``format`` and ``keep_alive`` remain top-level.

        Returns:
            A string containing the joined message contents.
        """
        if self.strict:
            return self._strict_summarize(messages, settings)

        flattened = flatten_message_inputs(messages)
        prompt = "\n".join(
            str(item.get("content") or "")
            for item in flattened
            if isinstance(item, dict)
        )

        # If an Ollama HTTP API is available try to call it and return the
        # service output. Use the bundled `json_post` helper to avoid adding
        # extra runtime dependencies. Fall back to the deterministic join
        # behavior when the service is not reachable or the call fails.
        # First attempt: HTTP API
        try:
            if server_is_up(self.host, self.port):
                payload: dict[str, Any] = {"stream": False}
                if self.model:
                    payload["model"] = self.model
                # Determine if we have structured messages or a prompt
                has_messages = bool(flattened)
                if has_messages:
                    payload["messages"] = flattened
                    endpoint = "/api/chat"
                else:
                    payload["prompt"] = prompt
                    endpoint = "/api/generate"
                _apply_ollama_settings(payload, settings, endpoint)

                try:
                    url = endpoint_url(self.host, self.port, endpoint)
                    res = json_post(url, payload, timeout=30.0)
                except Exception:
                    res = {}

                # Extract response based on which endpoint was used
                if isinstance(res, dict):
                    # /api/chat returns message.content
                    if (
                        has_messages
                        and "message" in res
                        and isinstance(res["message"], dict)
                    ):
                        content = res["message"].get("content")
                        if content:
                            return str(content)
                    # /api/generate returns response field
                    if "response" in res:
                        return str(res.get("response") or "")
                    # Fallback to common alternative field names
                    if "text" in res:
                        return str(res.get("text") or "")
                    if "output" in res:
                        return str(res.get("output") or "")
                    if "result" in res:
                        return str(res.get("result") or "")
                    choices = (
                        res.get("choices")
                        if isinstance(res.get("choices"), list)
                        else None
                    )
                    if choices:
                        first = choices[0]
                        if isinstance(first, dict) and "text" in first:
                            return str(first.get("text") or "")
                        return str(first)
        except Exception:
            # best-effort; fall through to CLI and deterministic fallback
            pass

        # Second attempt: invoke Ollama CLI (best-effort). Try several
        # command shapes and return the first successful textual result.
        try:
            host_env = f"{self.host.replace('http://', '').replace('https://', '')}:{self.port}"
            if ollama_installed():
                cmd_variants = []
                if self.model:
                    cmd_variants = [
                        ["run", self.model, "--prompt", prompt],
                        ["generate", self.model, "--prompt", prompt],
                        ["run", self.model, prompt],
                        ["generate", self.model, prompt],
                    ]
                else:
                    cmd_variants = [
                        ["run", "--prompt", prompt],
                        ["generate", "--prompt", prompt],
                        ["run", prompt],
                        ["generate", prompt],
                    ]

                for cmd in cmd_variants:
                    try:
                        proc = run_ollama_command(*cmd, host=host_env)
                    except FileNotFoundError:
                        break
                    except Exception:
                        continue

                    if proc and proc.returncode == 0:
                        out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
                        if not out:
                            continue
                        # attempt to parse JSON first
                        try:
                            import json as _json

                            parsed = _json.loads(out)
                            if isinstance(parsed, dict):
                                for k in ("text", "output", "result"):
                                    if k in parsed:
                                        return str(parsed.get(k) or "")
                                if "choices" in parsed and parsed["choices"]:
                                    first = parsed["choices"][0]
                                    if isinstance(first, dict):
                                        return str(
                                            first.get("text")
                                            or first.get("content")
                                            or ""
                                        )
                                    return str(first)
                            return str(parsed)
                        except Exception:
                            return out
        except Exception:
            pass

        # deterministic fallback
        return prompt

    def stream(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[dict[str, Any]] = None,
    ) -> Iterable[str]:
        """Streaming implementation for Ollama via the local HTTP API.

        Attempts to call the Ollama `/api/chat` endpoint for structured messages
        or `/api/generate` endpoint for prompts, yielding incremental text pieces
        as they arrive. Falls back to the deterministic `summarize()` chunking
        when streaming isn't available.
        """
        if self.strict:
            yield from self._strict_stream(messages, settings)
            return

        try:
            import json
            from urllib.request import Request, urlopen
        except Exception:
            # best-effort fallback
            text = self.summarize(messages, settings=settings)
            if not text:
                return
            for i in range(0, len(text), 64):
                yield text[i: i + 64]
            return

        # Build payload and determine endpoint
        payload: dict[str, Any] = {"stream": True}
        if self.model:
            payload["model"] = self.model

        flattened = flatten_message_inputs(messages)
        has_messages = bool(flattened)
        if has_messages:
            payload["messages"] = flattened
            endpoint = "/api/chat"
        else:
            # flatten
            payload["prompt"] = "\n".join(
                str(item.get("content") or "")
                for item in flattened
                if isinstance(item, dict)
            )
            endpoint = "/api/generate"
        _apply_ollama_settings(payload, settings, endpoint)

        url = endpoint_url(self.host, self.port, endpoint)

        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=60) as resp:
                # iterate lines as they arrive
                while True:
                    chunk = resp.readline()
                    if not chunk:
                        break
                    try:
                        s = chunk.decode("utf-8").strip()
                    except Exception:
                        try:
                            s = str(chunk)
                        except Exception:
                            continue
                    if not s:
                        continue
                    # Some servers prefix SSE lines with 'data: '
                    if s.startswith("data: "):
                        s2 = s[6:]
                    else:
                        s2 = s
                    # Try JSON parse
                    try:
                        obj = json.loads(s2)
                    except Exception:
                        yield s2
                        continue
                    # Extract plausible text fields based on endpoint
                    if isinstance(obj, dict):
                        # /api/chat returns message.content in streaming mode
                        if (
                            has_messages
                            and "message" in obj
                            and isinstance(obj["message"], dict)
                        ):
                            content = obj["message"].get("content")
                            if content:
                                yield str(content)
                                continue
                        # common shapes for /api/generate and other endpoints
                        if "token" in obj and isinstance(obj.get("token"), str):
                            yield str(obj.get("token") or "")
                            continue
                        if "text" in obj and isinstance(obj.get("text"), str):
                            yield str(obj.get("text") or "")
                            continue
                        if "output" in obj:
                            out = obj.get("output")
                            if isinstance(out, str):
                                yield out
                                continue
                            if isinstance(out, list) and out:
                                first = out[0]
                                if isinstance(first, dict):
                                    yield str(
                                        first.get("content") or first.get("text") or ""
                                    )
                                    continue
                                yield str(first)
                                continue
                        choices = obj.get("choices")
                        if isinstance(choices, list) and choices:
                            first = choices[0]
                            if isinstance(first, dict):
                                delta = first.get("delta") or first.get("message") or {}
                                if isinstance(delta, dict) and "content" in delta:
                                    yield str(delta.get("content") or "")
                                    continue
                                if "text" in first:
                                    yield str(first.get("text") or "")
                                    continue
                    # Fallback: yield the raw string
                    yield s2
                return
        except Exception:
            # fallback deterministic chunked output
            text = self.summarize(messages, settings=settings)
            if not text:
                return
            for i in range(0, len(text), 64):
                yield text[i: i + 64]
            return

    def embed(self, texts: Iterable[str], **kwargs: Any) -> List[List[float]]:
        """Embedding surface for tests: delegate to the embeddings helper."""
        try:
            from .embeddings import embed_texts
        except Exception:
            from modelito.embeddings import embed_texts

        texts_list = [str(t) for t in (texts or [])]
        dim = int(kwargs.get("dim", 8))
        return embed_texts(texts_list, dim=dim)

    def _fallback_raw_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate a deterministic OpenAI-compatible fallback completion."""
        created = int(time.time())
        model = payload.get("model", self.model or "unknown")
        messages = payload.get("messages", [])
        parts: List[str] = []
        if isinstance(messages, list):
            for item in messages:
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, str) and content:
                        parts.append(content)
                elif isinstance(item, str):
                    parts.append(item)
        text = "\n".join(parts) or "fallback"
        return {
            "id": f"chatcmpl-modelito-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    def raw_complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send raw OpenAI-compatible chat completion payload to Ollama's /v1/chat/completions.

        Args:
            payload: OpenAI-compatible chat completion request payload.

        Returns:
            The parsed JSON response as a dict, preserving all fields.
            In non-strict mode, returns a deterministic fallback on errors.

        Raises:
            ModelitoBadResponseError: In strict mode, if response parsing fails.
            ModelitoConnectionError: In strict mode, if the endpoint is unreachable.
            ModelitoTimeoutError: In strict mode, if the request times out.
            ModelitoProviderError: In strict mode, for other provider errors.
        """
        # Shallow copy only: raw_complete only adds/overrides top-level transport
        # keys ("model").  Nested OpenAI-compatible structures such as messages,
        # tools, tool_choice, and response_format are intentionally not deep-copied
        # so callers can pass large payloads without unnecessary allocation.
        request_payload = dict(payload or {})

        # Set model if absent, but don't overwrite an explicit model.
        if "model" not in request_payload and self.model:
            request_payload["model"] = self.model

        try:
            url = endpoint_url(self.host, self.port, "/v1/chat/completions")
            data = json_post(url, request_payload, timeout=self.timeout)

            if isinstance(data, dict):
                if self.strict and "choices" not in data:
                    raise ModelitoBadResponseError(
                        "raw_complete: server returned valid JSON but no choices"
                    )
                return data

            # Non-dict response in strict mode is an error.
            if self.strict:
                raise ModelitoBadResponseError(
                    "raw_complete: server returned a non-dict JSON response"
                )
        except ModelitoBadResponseError:
            if self.strict:
                raise
        except ModelitoConnectionError:
            if self.strict:
                raise
        except ModelitoTimeoutError:
            if self.strict:
                raise
        except ModelitoProviderError:
            if self.strict:
                raise
        except Exception as exc:
            # Classify unknown exceptions.
            if self.strict:
                import socket
                import urllib.error

                if isinstance(exc, urllib.error.HTTPError):
                    raise ModelitoProviderError(f"HTTP {exc.code}: {exc}") from exc
                if isinstance(exc, urllib.error.URLError):
                    reason = str(getattr(exc, "reason", exc)).lower()
                    if "timed out" in reason or "timeout" in reason:
                        raise ModelitoTimeoutError(str(exc)) from exc
                    raise ModelitoConnectionError(str(exc)) from exc
                if isinstance(exc, (TimeoutError, socket.timeout)):
                    raise ModelitoTimeoutError(str(exc)) from exc
                if isinstance(exc, _json.JSONDecodeError):
                    raise ModelitoBadResponseError(str(exc)) from exc
                raise ModelitoProviderError(str(exc)) from exc

        # Non-strict fallback.
        return self._fallback_raw_response(request_payload)

    def raw_stream(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        """Stream raw OpenAI-compatible chat completion events from Ollama's /v1/chat/completions.

        Args:
            payload: OpenAI-compatible chat completion request payload.

        Yields:
            Parsed JSON dictionaries from Server-Sent Events, one per event.
            Does not yield the [DONE] marker.

        Raises:
            ModelitoBadResponseError: In strict mode, if event parsing fails.
            ModelitoConnectionError: In strict mode, if the endpoint is unreachable.
            ModelitoTimeoutError: In strict mode, if the request times out.
            ModelitoProviderError: In strict mode, for other provider errors.
        """
        # Shallow copy only: raw_stream only adds/overrides top-level transport
        # keys ("model", "stream").  Nested OpenAI-compatible structures such as
        # messages, tools, tool_choice, and response_format are intentionally not
        # deep-copied so callers can pass large payloads without unnecessary
        # allocation.
        request_payload = dict(payload or {})

        # Set model if absent, but don't overwrite an explicit model.
        if "model" not in request_payload and self.model:
            request_payload["model"] = self.model

        # Force streaming.
        request_payload["stream"] = True

        # raw_stream uses urlopen directly instead of json_post because it needs
        # access to the response iterator to parse SSE data: frames incrementally.
        # json_post reads the full response body before returning, which is
        # incompatible with a streaming response.
        try:
            url = endpoint_url(self.host, self.port, "/v1/chat/completions")
            req = Request(
                url,
                data=_json.dumps(request_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
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

                    # Strip SSE "data: " prefix if present.
                    if line.startswith("data:"):
                        line = line[5:].lstrip()

                    # Stop on [DONE] marker.
                    if line == "[DONE]":
                        break

                    # Parse the event JSON.
                    try:
                        event = _json.loads(line)
                    except _json.JSONDecodeError as exc:
                        if self.strict:
                            raise ModelitoBadResponseError(
                                f"raw_stream: unable to parse stream event: {line!r}"
                            ) from exc
                        continue

                    if not isinstance(event, dict):
                        if self.strict:
                            raise ModelitoBadResponseError(
                                "raw_stream: expected JSON object event, "
                                f"got {type(event).__name__}"
                            )
                        continue

                    # Yield the parsed event dict.
                    yield event

            return

        except ModelitoBadResponseError:
            if self.strict:
                raise
        except ModelitoConnectionError:
            if self.strict:
                raise
        except ModelitoTimeoutError:
            if self.strict:
                raise
        except ModelitoProviderError:
            if self.strict:
                raise
        except Exception as exc:
            # Classify unknown exceptions.
            if self.strict:
                import socket
                import urllib.error

                if isinstance(exc, urllib.error.HTTPError):
                    raise ModelitoProviderError(f"HTTP {exc.code}: {exc}") from exc
                if isinstance(exc, urllib.error.URLError):
                    reason = str(getattr(exc, "reason", exc)).lower()
                    if "timed out" in reason or "timeout" in reason:
                        raise ModelitoTimeoutError(str(exc)) from exc
                    raise ModelitoConnectionError(str(exc)) from exc
                if isinstance(exc, (TimeoutError, socket.timeout)):
                    raise ModelitoTimeoutError(str(exc)) from exc
                raise ModelitoProviderError(str(exc)) from exc

        # Non-strict fallback: yield deterministic stream events.
        created = int(time.time())
        model = request_payload.get("model", self.model or "unknown")
        event_id = f"chatcmpl-modelito-{uuid.uuid4().hex}"

        # Initial role chunk
        yield {
            "id": event_id,
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

        # Content chunk(s)
        messages = request_payload.get("messages", [])
        parts: List[str] = []
        if isinstance(messages, list):
            for item in messages:
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, str) and content:
                        parts.append(content)
                elif isinstance(item, str):
                    parts.append(item)

        text = "\n".join(parts) or "fallback"
        chunk_size = 64
        if isinstance(request_payload, dict) and "chunk_size" in request_payload:
            try:
                chunk_size = max(
                    1, int(request_payload.get("chunk_size") or chunk_size)
                )
            except Exception:
                chunk_size = 64

        for start in range(0, len(text), chunk_size):
            chunk = text[start: start + chunk_size]
            if not chunk:
                continue

            yield {
                "id": event_id,
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

        # Final stop chunk
        yield {
            "id": event_id,
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
