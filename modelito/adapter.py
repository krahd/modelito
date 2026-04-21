"""Simple Ollama HTTP adapter and fallback client (Phase A scaffolding).

This module provides a lightweight HTTP client that centralizes calls to
the local Ollama HTTP API and falls back to CLI/deterministic behavior
when the HTTP service is not available. It intentionally avoids adding a
hard dependency on `httpx` and will use it only when present for streaming
reads.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, Iterable, List, Optional

from .messages import Message

logger = logging.getLogger(__name__)


def get_client(host: Optional[str] = None, port: int = 11434) -> "OllamaHTTPClient":
    return OllamaHTTPClient(host or "http://127.0.0.1", int(port or 11434))


class OllamaHTTPClient:
    """Minimal HTTP client that mirrors a small subset of Ollama actions.

    Methods implemented here are intentionally conservative and serve as a
    stable surface for higher-level helpers and tests during Phase A.
    """

    def __init__(self, host: str, port: int = 11434) -> None:
        if not host.startswith("http://") and not host.startswith("https://"):
            host = f"http://{host}"
        self.host = host.rstrip("/")
        self.port = int(port)

    def _host_env(self) -> str:
        return f"{self.host.replace('http://', '').replace('https://', '')}:{self.port}"

    def version(self) -> str:
        try:
            from .ollama_service import endpoint_url, json_get, ollama_version_text, server_is_up

            if server_is_up(self.host, self.port):
                url = endpoint_url(self.host, self.port, "/api/version")
                try:
                    data = json_get(url, timeout=3.0)
                    if isinstance(data, dict):
                        return str(data.get("version") or data.get("ollama_version") or "")
                except Exception:
                    logger.debug("version: json_get failed", exc_info=True)
            return ollama_version_text(host=self._host_env())
        except Exception:
            return ""

    def ps(self) -> List[str]:
        try:
            from .ollama_service import endpoint_url, json_get, running_model_names, server_is_up

            if server_is_up(self.host, self.port):
                url = endpoint_url(self.host, self.port, "/api/ps")
                try:
                    data = json_get(url, timeout=3.0)
                    if isinstance(data, dict):
                        models = data.get("models") or data.get("running") or []
                        if isinstance(models, list):
                            return [str(m) for m in models]
                    if isinstance(data, list):
                        return [str(m) for m in data]
                except Exception:
                    logger.debug("ps: json_get failed", exc_info=True)
            # Fallback to CLI probing
            return running_model_names(self._host_env())
        except Exception:
            return []

    def pull(self, model: str, timeout: float = 600.0) -> bool:
        try:
            from .ollama_service import run_ollama_command

            proc = run_ollama_command("pull", model, host=self._host_env())
            return bool(proc and proc.returncode == 0)
        except FileNotFoundError:
            return False
        except Exception:
            logger.debug("pull: run_ollama_command failed", exc_info=True)
            return False

    def generate(self, messages: Iterable[Message | str] | str, model: Optional[str] = None, stream: bool = False, timeout: float = 60.0) -> Generator[str, None, None]:
        """Generate text from messages.

        When `stream` is True attempt an HTTP streaming read (SSE-like) and
        yield incremental pieces. When the HTTP API is unavailable fall back
        to a deterministic chunked prompt derived from the provided messages.
        """
        # Build payload mirroring the compatibility shim
        payload: Dict[str, Any] = {}
        if model:
            payload["model"] = model

        # Support Message instances or plain strings
        if isinstance(messages, (list, tuple)) and messages:
            first = next(iter(messages))
            if isinstance(first, Message):
                payload["messages"] = [{"role": m.role, "content": m.content}
                                       for m in messages]  # type: ignore[arg-type]
            else:
                parts: List[str] = [str(m) for m in messages]  # type: ignore[arg-type]
                payload["prompt"] = "\n".join(p for p in parts if p)
        else:
            # single-string prompt
            payload["prompt"] = str(messages or "")

        try:
            from .ollama_service import endpoint_url, json_post, server_is_up

            url = endpoint_url(self.host, self.port, "/api/generate")
            if not server_is_up(self.host, self.port):
                raise RuntimeError("server not available")

            # Non-streaming request: POST and coerce common shapes
            if not stream:
                try:
                    res = json_post(url, payload, timeout=timeout)
                except Exception:
                    res = {}

                if isinstance(res, dict):
                    for k in ("text", "output", "result"):
                        if k in res:
                            yield str(res.get(k) or "")
                            return
                    choices = res.get("choices") if isinstance(res.get("choices"), list) else None
                    if choices:
                        first = choices[0]
                        if isinstance(first, dict) and "text" in first:
                            yield str(first.get("text") or "")
                            return
                        yield str(first)
                        return
                else:
                    yield str(res)
                    return

            # Streaming path: prefer httpx when available for robust iter_lines
            try:
                import httpx  # type: ignore
            except Exception:
                httpx = None

            if stream and httpx:
                try:
                    with httpx.Client(timeout=timeout) as client:
                        with client.stream("POST", url, json=payload) as r:
                            for raw in r.iter_lines():
                                if not raw:
                                    continue
                                s = raw.decode("utf-8") if isinstance(raw,
                                                                      (bytes, bytearray)) else str(raw)
                                s = s.strip()
                                if not s:
                                    continue
                                if s.startswith("data: "):
                                    s2 = s[6:]
                                else:
                                    s2 = s
                                try:
                                    obj = json.loads(s2)
                                except Exception:
                                    yield s2
                                    continue
                                # common shapes
                                if isinstance(obj, dict):
                                    if "token" in obj and isinstance(obj.get("token"), str):
                                        yield str(obj.get("token") or "")
                                        continue
                                    if "text" in obj and isinstance(obj.get("text"), str):
                                        yield str(obj.get("text") or "")
                                        continue
                                yield s2
                            return
                except Exception:
                    logger.debug("stream via httpx failed, falling back", exc_info=True)

            # HTTP fallback streaming using urlopen/readline (matches existing shim)
            try:
                from urllib.request import Request, urlopen

                req = Request(url, data=json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(req, timeout=timeout) as resp:
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
                        if s.startswith("data: "):
                            s2 = s[6:]
                        else:
                            s2 = s
                        try:
                            obj = json.loads(s2)
                        except Exception:
                            yield s2
                            continue
                        if isinstance(obj, dict):
                            if "token" in obj and isinstance(obj.get("token"), str):
                                yield str(obj.get("token") or "")
                                continue
                            if "text" in obj and isinstance(obj.get("text"), str):
                                yield str(obj.get("text") or "")
                                continue
                        yield s2
                    return
            except Exception:
                logger.debug("stream fallback urlopen failed", exc_info=True)

        except Exception:
            # server not available or other transient error — fall through
            pass

        # Final deterministic fallback: flatten prompt and yield fixed-size chunks
        prompt = ""
        if "prompt" in payload:
            prompt = str(payload.get("prompt") or "")
        elif "messages" in payload:
            try:
                parts: List[str] = []
                for m in payload.get("messages", []):
                    if isinstance(m, dict) and "content" in m:
                        parts.append(str(m.get("content") or ""))
                    else:
                        parts.append(str(m))
                prompt = "\n".join(p for p in parts if p)
            except Exception:
                prompt = ""

        if not prompt:
            return

        chunk_size = 64
        for i in range(0, len(prompt), chunk_size):
            yield prompt[i: i + chunk_size]
