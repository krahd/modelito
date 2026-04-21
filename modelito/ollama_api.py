"""Thin Ollama HTTP API wrappers (Phase A helpers).

These helpers wrap the `adapter` client and provide a small stable
surface for common actions like version, ps, tags, pull and generate.
"""
from __future__ import annotations

from typing import Generator, Iterable, List, Optional, Union

from .messages import Message
from .adapter import get_client


def api_version(host: Optional[str] = None, port: int = 11434) -> str:
    """Return the Ollama version string (HTTP then CLI fallback)."""
    client = get_client(host, port)
    return client.version()


def api_ps(host: Optional[str] = None, port: int = 11434) -> List[str]:
    """Return a list of running models (best-effort)."""
    client = get_client(host, port)
    return client.ps()


def api_tags(host: Optional[str] = None, port: int = 11434) -> List[str]:
    """Return available tags/models from the HTTP endpoint when present.

    Falls back to an empty list when the HTTP API is unavailable.
    """
    client = get_client(host, port)
    try:
        # Try the HTTP endpoint first (best-effort)
        from .ollama_service import endpoint_url, json_get, server_is_up

        if server_is_up(client.host, client.port):
            url = endpoint_url(client.host, client.port, "/api/tags")
            try:
                data = json_get(url, timeout=3.0)
                if isinstance(data, list):
                    return [str(x) for x in data]
                if isinstance(data, dict):
                    items = data.get("tags") or data.get("models") or []
                    if isinstance(items, list):
                        return [str(x) for x in items]
            except Exception:
                pass
    except Exception:
        pass
    return []


def api_pull(model: str, host: Optional[str] = None, port: int = 11434, timeout: float = 600.0) -> bool:
    """Pull a remote model into the local cache (CLI-backed)."""
    client = get_client(host, port)
    return client.pull(model, timeout=timeout)


def api_generate(
    messages: Iterable[Union[str, Message]] | str,
    host: Optional[str] = None,
    port: int = 11434,
    model: Optional[str] = None,
    stream: bool = False,
    timeout: float = 60.0,
) -> Union[str, Generator[str, None, None]]:
    """Generate text from the given `messages`.

    When `stream` is True return a generator that yields incremental pieces.
    When `stream` is False return the complete string result.
    """
    client = get_client(host, port)
    gen = client.generate(messages, model=model, stream=stream, timeout=timeout)
    if stream:
        return gen
    # materialize and join
    parts = list(gen)
    return "".join(parts)


__all__ = ["api_version", "api_ps", "api_tags", "api_pull", "api_generate"]

def api_list_local(host: Optional[str] = None, port: int = 11434) -> List[str]:
    client = get_client(host, port)
    try:
        return client.list_local()
    except Exception:
        return []


def api_list_remote(host: Optional[str] = None, port: int = 11434) -> List[str]:
    client = get_client(host, port)
    try:
        return client.list_remote()
    except Exception:
        return []


def api_delete_model(model: str, host: Optional[str] = None, port: int = 11434) -> bool:
    client = get_client(host, port)
    try:
        return client.delete_model(model)
    except Exception:
        return False


def api_pull_stream(model: str, host: Optional[str] = None, port: int = 11434, timeout: float = 600.0) -> Generator[str, None, None]:
    client = get_client(host, port)
    try:
        for line in client.download_stream(model, timeout=timeout):
            yield line
    except Exception:
        return

__all__.extend(["api_list_local", "api_list_remote", "api_delete_model", "api_pull_stream"])
