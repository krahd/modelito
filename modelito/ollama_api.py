"""Thin Ollama HTTP API wrappers (Phase A helpers).

These helpers wrap the `adapter` client and provide a small stable
surface for common actions like version, ps, tags, pull and generate.
"""
from __future__ import annotations

from typing import Any, Callable, Generator, Iterable, List, Optional, Union

from .messages import Message
from .adapter import get_client
from .plumbing import (
    ErrorEnvelope,
    ResponseEnvelope,
    TransportPolicy,
    envelope_error,
    envelope_ok,
    normalize_network_error,
)


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


def api_pull_progress(model: str, timeout: float = 600.0):
    from .ollama_service import download_model_progress

    yield from download_model_progress(model, timeout=timeout)


def api_remote_catalog(query: Optional[str] = None):
    from .ollama_service import list_remote_model_catalog

    return list_remote_model_catalog(query=query)


def api_model_state(model: str):
    from .ollama_service import get_model_lifecycle_state

    return get_model_lifecycle_state(model)


def api_health(
    host: Optional[str] = None,
    port: int = 11434,
    timeout: float = 2.0,
    policy: Optional[TransportPolicy] = None,
):
    from .ollama_service import DEFAULT_URL, ollama_health_check

    return ollama_health_check(host=host or DEFAULT_URL, port=port, timeout=timeout, policy=policy)


def api_readiness(
    host: Optional[str] = None,
    port: int = 11434,
    timeout: float = 2.0,
    policy: Optional[TransportPolicy] = None,
) -> bool:
    from .ollama_service import DEFAULT_URL, ollama_readiness_probe

    return ollama_readiness_probe(host=host or DEFAULT_URL, port=port, timeout=timeout, policy=policy)


def api_ensure_model_loaded(
    model: str,
    host: Optional[str] = None,
    port: int = 11434,
    auto_start: bool = False,
    allow_download: bool = False,
    timeout: float = 120.0,
) -> bool:
    from .ollama_service import DEFAULT_URL, ensure_model_loaded

    return ensure_model_loaded(
        model_name=model,
        host=host or DEFAULT_URL,
        port=port,
        auto_start=auto_start,
        allow_download=allow_download,
        timeout=timeout,
    )


def _enveloped(operation: str, fn: Callable[[], Any]) -> ResponseEnvelope:
    try:
        data = fn()
        return envelope_ok("ollama", operation, data)
    except Exception as exc:
        error: ErrorEnvelope = normalize_network_error(exc, provider="ollama", operation=operation)
        return envelope_error("ollama", operation, error)


def api_health_envelope(
    host: Optional[str] = None,
    port: int = 11434,
    timeout: float = 2.0,
    policy: Optional[TransportPolicy] = None,
) -> ResponseEnvelope:
    return _enveloped("health", lambda: api_health(host=host, port=port, timeout=timeout, policy=policy))


def api_readiness_envelope(
    host: Optional[str] = None,
    port: int = 11434,
    timeout: float = 2.0,
    policy: Optional[TransportPolicy] = None,
) -> ResponseEnvelope:
    return _enveloped("readiness", lambda: api_readiness(host=host, port=port, timeout=timeout, policy=policy))


def api_list_local_envelope(host: Optional[str] = None, port: int = 11434) -> ResponseEnvelope:
    return _enveloped("list_local", lambda: api_list_local(host=host, port=port))


def api_list_remote_envelope(host: Optional[str] = None, port: int = 11434) -> ResponseEnvelope:
    return _enveloped("list_remote", lambda: api_list_remote(host=host, port=port))


def api_running_models_envelope(host: Optional[str] = None, port: int = 11434) -> ResponseEnvelope:
    return _enveloped("running_models", lambda: api_ps(host=host, port=port))


def api_pull_envelope(model: str, host: Optional[str] = None, port: int = 11434, timeout: float = 600.0) -> ResponseEnvelope:
    return _enveloped("pull", lambda: api_pull(model=model, host=host, port=port, timeout=timeout))


def api_delete_model_envelope(model: str, host: Optional[str] = None, port: int = 11434) -> ResponseEnvelope:
    return _enveloped("delete_model", lambda: api_delete_model(model=model, host=host, port=port))


def api_ensure_model_loaded_envelope(
    model: str,
    host: Optional[str] = None,
    port: int = 11434,
    auto_start: bool = False,
    allow_download: bool = False,
    timeout: float = 120.0,
) -> ResponseEnvelope:
    return _enveloped(
        "ensure_model_loaded",
        lambda: api_ensure_model_loaded(
            model=model,
            host=host,
            port=port,
            auto_start=auto_start,
            allow_download=allow_download,
            timeout=timeout,
        ),
    )

__all__.extend([
    "api_list_local",
    "api_list_remote",
    "api_delete_model",
    "api_pull_stream",
    "api_pull_progress",
    "api_remote_catalog",
    "api_model_state",
    "api_health",
    "api_readiness",
    "api_ensure_model_loaded",
    "api_health_envelope",
    "api_readiness_envelope",
    "api_list_local_envelope",
    "api_list_remote_envelope",
    "api_running_models_envelope",
    "api_pull_envelope",
    "api_delete_model_envelope",
    "api_ensure_model_loaded_envelope",
])
