"""Compatibility shim for Ollama provider.

Provides a lightweight `OllamaProvider` compatible with older imports
(`from modelito import OllamaProvider` and `import modelito.ollama`).

This implementation is intentionally minimal: it exposes `list_models()`
and `summarize()` with safe defaults so downstream projects that expect
the provider API during tests or local runs continue to work.
"""
from __future__ import annotations

from typing import Any, List, Optional
from .ollama_service import endpoint_url, server_is_up, json_post, list_local_models


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
                # prefer the helper that probes CLI/installed models; it's a
                # best-effort enumeration and will return an empty list when
                # the CLI is not present or fails.
                return list_local_models()
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
        try:
            if server_is_up(self.host, self.port):
                payload = {}
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
            # best-effort; fall through to deterministic fallback
            pass

        return prompt
