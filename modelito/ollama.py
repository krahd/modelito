"""Compatibility shim for Ollama provider.

Provides a lightweight `OllamaProvider` compatible with older imports
(`from modelito import OllamaProvider` and `import modelito.ollama`).

This implementation is intentionally minimal: it exposes `list_models()`
and `summarize()` with safe defaults so downstream projects that expect
the provider API during tests or local runs continue to work.
"""
from __future__ import annotations

from typing import Any, List, Optional
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

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
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
                    if isinstance(m, dict):
                        parts.append(m.get("content", ""))
                    else:
                        parts.append(str(m))
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
                # prefer sending structured messages when available
                if isinstance(messages, (list, tuple)) and messages and isinstance(messages[0], dict):
                    payload["messages"] = messages
                else:
                    payload["prompt"] = prompt

                try:
                    url = endpoint_url(self.host, self.port, "/api/generate")
                    res = json_post(url, payload, timeout=30.0)
                except Exception:
                    res = {}

                # Try to coerce common response shapes into a string result.
                if isinstance(res, dict):
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

    def stream(self, messages: Any, settings: Optional[dict] = None):
        """Streaming fallback for Ollama provider.

        Yield the completed response in character chunks. Real Ollama
        integrations can replace this with the HTTP/CLI streaming output.
        """
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
            yield text[i : i + chunk_size]

    def embed(self, texts: Any, **kwargs) -> List[List[float]]:
        """Embedding surface for tests: delegate to the embeddings helper."""
        try:
            from .embeddings import embed_texts
        except Exception:
            from modelito.embeddings import embed_texts

        texts_list = [str(t) for t in (texts or [])]
        dim = int(kwargs.get("dim", 8))
        return embed_texts(texts_list, dim=dim)
