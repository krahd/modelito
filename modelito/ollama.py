"""Compatibility shim for Ollama provider.

Provides a lightweight `OllamaProvider` compatible with older imports
(`from modelito import OllamaProvider` and `import modelito.ollama`).

This implementation is intentionally minimal: it exposes `list_models()`
and `summarize()` with safe defaults so downstream projects that expect
the provider API during tests or local runs continue to work.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional
from .messages import Message
from .ollama_service import endpoint_url, server_is_up, json_post, list_local_models, list_remote_models, ollama_installed, run_ollama_command, running_model_names


class OllamaProvider:
    """Minimal compatibility shim for Ollama-style providers.

    Provides `list_models()` and `summarize()` with safe defaults for local
    testing and compatibility with older imports.
    """

    def __init__(self, host: Optional[str] = None, port: int = 11434, model: Optional[str] = None):
        """Initialize the provider.

        When an Ollama HTTP API is reachable at ``host:port`` the provider
        will attempt to use it for `list_models()` and `summarize()` calls.
        Otherwise it falls back to a deterministic offline-friendly shim.
        """
        # Accept host with or without scheme; endpoint_url will normalize it.
        self.host = host or "http://127.0.0.1"
        self.port = int(port or 11434)
        self.model = model

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
                    running = running_model_names(self.host.replace(
                        "http://", "").replace("https://", ""))
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

    def summarize(self, messages: Iterable[Message | str], settings: Optional[dict[str, Any]] = None) -> str:
        """Produce a deterministic summary by concatenating message contents.

        This minimal implementation is intended for local testing and
        compatibility; it does not contact a model service.

        Args:
            messages: Iterable of message dicts (containing ``content``) or
                plain strings.
            settings: Optional settings passed through by callers (ignored).

        Returns:
            A string containing the joined message contents.
        """
        # Helper to flatten messages into a single prompt string.
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
                            "OllamaProvider.summarize requires modelito.messages.Message instances; dicts are not supported")
                return "\n".join(p for p in parts if p)
            except Exception:
                return ""

        prompt = _flatten(messages)

        # If an Ollama HTTP API is available try to call it and return the
        # service output. Use the bundled `json_post` helper to avoid adding
        # extra runtime dependencies. Fall back to the deterministic join
        # behavior when the service is not reachable or the call fails.
        # First attempt: HTTP API
        try:
            if server_is_up(self.host, self.port):
                payload: dict[str, Any] = {}
                if self.model:
                    payload["model"] = self.model
                # Determine if we have structured messages or a prompt
                has_messages = isinstance(messages, (list, tuple)
                                          ) and messages and isinstance(messages[0], Message)
                if has_messages:
                    payload["messages"] = [
                        {"role": m.role, "content": m.content}
                        for m in messages
                        if isinstance(m, Message)
                    ]
                    endpoint = "/api/chat"
                else:
                    payload["prompt"] = prompt
                    endpoint = "/api/generate"

                try:
                    url = endpoint_url(self.host, self.port, endpoint)
                    res = json_post(url, payload, timeout=30.0)
                except Exception:
                    res = {}

                # Extract response based on which endpoint was used
                if isinstance(res, dict):
                    # /api/chat returns message.content
                    if has_messages and "message" in res and isinstance(res["message"], dict):
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
                    choices = res.get("choices") if isinstance(res.get("choices"), list) else None
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
                    cmd_variants = [["run", self.model, "--prompt", prompt], ["generate", self.model,
                                                                              "--prompt", prompt], ["run", self.model, prompt], ["generate", self.model, prompt]]
                else:
                    cmd_variants = [["run", "--prompt", prompt], ["generate",
                                                                  "--prompt", prompt], ["run", prompt], ["generate", prompt]]

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
                                        return str(first.get("text") or first.get("content") or "")
                                    return str(first)
                            return str(parsed)
                        except Exception:
                            return out
        except Exception:
            pass

        # deterministic fallback
        return prompt

    def stream(self, messages: Iterable[Message | str], settings: Optional[dict[str, Any]] = None) -> Iterable[str]:
        """Streaming implementation for Ollama via the local HTTP API.

        Attempts to call the Ollama `/api/chat` endpoint for structured messages
        or `/api/generate` endpoint for prompts, yielding incremental text pieces
        as they arrive. Falls back to the deterministic `summarize()` chunking
        when streaming isn't available.
        """
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
        payload: dict[str, Any] = {}
        if self.model:
            payload["model"] = self.model

        has_messages = isinstance(messages, (list, tuple)
                                  ) and messages and isinstance(messages[0], Message)
        if has_messages:
            payload["messages"] = [
                {"role": m.role, "content": m.content}
                for m in messages
                if isinstance(m, Message)
            ]
            endpoint = "/api/chat"
        else:
            # flatten
            try:
                parts = []
                for m in (messages or []):
                    if isinstance(m, Message):
                        parts.append(m.content)
                    elif isinstance(m, str):
                        parts.append(m)
                    else:
                        raise TypeError(
                            "OllamaProvider.stream requires modelito.messages.Message instances; dicts are not supported")
                payload["prompt"] = "\n".join(p for p in parts if p)
            except Exception:
                payload["prompt"] = str(messages or "")
            endpoint = "/api/generate"

        url = endpoint_url(self.host, self.port, endpoint)

        req = Request(url, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
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
                        if has_messages and "message" in obj and isinstance(obj["message"], dict):
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
                                    yield str(first.get("content") or first.get("text") or "")
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
