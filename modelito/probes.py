"""Shared provider readiness probes.

These helpers are used by both the client auto-selection path and the doctor
diagnostics so readiness behaviour stays aligned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .basert import BaseRTProvider
from .ollama_service import DEFAULT_PORT, DEFAULT_URL, list_local_models, server_is_up
from .omlx import OMLXProvider
from .vllm_mlx import VLLMMLXProvider


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    ready: bool
    endpoint: Optional[str] = None
    models: List[str] = field(default_factory=list)
    reason: str = ""
    setup_hint: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


def _normalise_model_listing_item(item: str) -> str:
    """Return the model identifier from either a bare name or a CLI table row."""
    text = str(item or "").strip()
    return text.split()[0] if text else ""


def model_is_available(model: Optional[str], models: Iterable[str]) -> bool:
    if not model:
        return True
    names = {_normalise_model_listing_item(item) for item in models}
    names.discard("")
    return model in names


# Back-compat alias used internally
_model_is_available = model_is_available


def build_status(
    provider: str,
    ready: bool,
    *,
    endpoint: Optional[str] = None,
    models: Optional[Iterable[str]] = None,
    reason: str = "",
    setup_hint: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> ProviderStatus:
    return ProviderStatus(
        provider=provider,
        ready=ready,
        endpoint=endpoint,
        models=list(models or []),
        reason=reason,
        setup_hint=setup_hint,
        details=dict(details or {}),
    )


# Internal alias used within this module
_build_status = build_status


def probe_basert_status(
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    probe_timeout: float,
) -> ProviderStatus:
    endpoint = base_url or "http://127.0.0.1:8080/v1"
    try:
        provider = BaseRTProvider(
            base_url=endpoint,
            model=model,
            api_key=api_key,
            timeout=probe_timeout,
            strict=True,
        )
        models = provider.list_models()
        ready = _model_is_available(model, models)
        return _build_status(
            "basert",
            ready,
            endpoint=getattr(provider, "base_url", endpoint),
            models=models,
            reason="" if ready else "requested model not found",
            setup_hint=(
                "Start BaseRT with `basert serve <model> --port 8080` and use the "
                "same API key in Modelito if `--api-key` is enabled."
            ),
        )
    except Exception as exc:
        return _build_status(
            "basert",
            False,
            endpoint=endpoint,
            models=[],
            reason="BaseRT server not reachable",
            setup_hint=(
                "Start BaseRT with `basert serve <model> --port 8080` and use the "
                "same API key in Modelito if `--api-key` is enabled."
            ),
            details={"error": str(exc)},
        )


def probe_vllm_mlx_status(
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    probe_timeout: float,
) -> ProviderStatus:
    endpoint = base_url or "http://localhost:8000/v1"
    try:
        provider = VLLMMLXProvider(
            base_url=endpoint,
            model=model,
            api_key=api_key,
            timeout=probe_timeout,
            strict=True,
        )
        models = provider.list_models()
        ready = _model_is_available(model, models)
        return _build_status(
            "vllm-mlx",
            ready,
            endpoint=getattr(provider, "base_url", endpoint),
            models=models,
            reason="" if ready else "requested model not found",
            setup_hint=(
                "Start vllm-mlx with `vllm-mlx serve <model> --port 8000` and use "
                "the same API key in Modelito if `--api-key` is enabled."
            ),
        )
    except Exception as exc:
        return _build_status(
            "vllm-mlx",
            False,
            endpoint=endpoint,
            models=[],
            reason="vllm-mlx server not reachable",
            setup_hint=(
                "Start vllm-mlx with `vllm-mlx serve <model> --port 8000` and use "
                "the same API key in Modelito if `--api-key` is enabled."
            ),
            details={"error": str(exc)},
        )


def probe_omlx_status(
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    probe_timeout: float,
) -> ProviderStatus:
    endpoint = base_url or "http://localhost:8000/v1"
    try:
        provider = OMLXProvider(
            base_url=endpoint,
            model=model,
            api_key=api_key,
            timeout=probe_timeout,
            strict=True,
        )
        models = provider.list_models()
        ready = _model_is_available(model, models)
        return _build_status(
            "omlx",
            ready,
            endpoint=getattr(provider, "base_url", endpoint),
            models=models,
            reason="" if ready else "requested model not found",
            setup_hint="Start oMLX and make the requested model available to the server.",
        )
    except Exception as exc:
        return _build_status(
            "omlx",
            False,
            endpoint=endpoint,
            models=[],
            reason="oMLX server not reachable",
            setup_hint="Start oMLX and make the requested model available to the server.",
            details={"error": str(exc)},
        )


def probe_ollama_status(
    model: Optional[str],
    host: Optional[str],
    port: Optional[int],
    probe_timeout: float,
) -> ProviderStatus:
    _ = probe_timeout
    host_value = host or DEFAULT_URL
    port_value = int(port or DEFAULT_PORT)
    endpoint = f"{host_value}:{port_value}"
    try:
        if not server_is_up(host_value, port_value):
            return _build_status(
                "ollama",
                False,
                endpoint=endpoint,
                models=[],
                reason="Ollama server not reachable",
                setup_hint=(
                    "Start Ollama and pull the requested model with "
                    "`ollama pull <model>`."
                ),
            )

        models = list_local_models()
        ready = _model_is_available(model, models)
        return _build_status(
            "ollama",
            ready,
            endpoint=endpoint,
            models=models,
            reason="" if ready else "requested model not found",
            setup_hint="Pull the requested model with `ollama pull <model>`.",
        )
    except Exception as exc:
        return _build_status(
            "ollama",
            False,
            endpoint=endpoint,
            models=[],
            reason="Ollama probe failed",
            setup_hint=(
                "Start Ollama and pull the requested model with "
                "`ollama pull <model>`."
            ),
            details={"error": str(exc)},
        )
