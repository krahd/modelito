"""Local runtime selection helpers.

Profiles express deployment intent without claiming that one local backend is
universally fastest. ``portable`` uses Ollama as the common cross-platform
path. ``mac-performance`` uses Apple-Silicon-oriented backends before Ollama.
Applications should benchmark representative workloads and may override the
candidate order with ``prefer=``.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
from typing import Any, List, Literal, Mapping, Optional, Sequence

from .probes import (
    ProviderStatus,
    probe_basert_status,
    probe_ollama_status,
    probe_omlx_status,
    probe_vllm_mlx_status,
)

LOCAL_PROFILE_AUTO = "auto"
LOCAL_PROFILE_PORTABLE = "portable"
LOCAL_PROFILE_MAC_PERFORMANCE = "mac-performance"
LOCAL_PROFILES = (
    LOCAL_PROFILE_AUTO,
    LOCAL_PROFILE_PORTABLE,
    LOCAL_PROFILE_MAC_PERFORMANCE,
)
LOCAL_PROVIDERS = ("basert", "vllm-mlx", "omlx", "ollama")

CapabilityState = Literal["yes", "no", "conditional", "unknown"]

_ALIASES = {
    "mac": LOCAL_PROFILE_MAC_PERFORMANCE,
    "macos": LOCAL_PROFILE_MAC_PERFORMANCE,
    "apple": LOCAL_PROFILE_MAC_PERFORMANCE,
    "apple-silicon": LOCAL_PROFILE_MAC_PERFORMANCE,
    "apple_silicon": LOCAL_PROFILE_MAC_PERFORMANCE,
    "cross-platform": LOCAL_PROFILE_PORTABLE,
    "cross_platform": LOCAL_PROFILE_PORTABLE,
}

_PROVIDER_ALIASES = {
    "om": "omlx",
    "vllm_mlx": "vllm-mlx",
    "vllmmlx": "vllm-mlx",
}


@dataclass(frozen=True)
class LocalRuntimeSelection:
    """Resolved local runtime and model."""

    profile: str
    provider: str
    model: Optional[str]
    endpoint: Optional[str] = None


@dataclass(frozen=True)
class LocalRuntimeCapabilities:
    """Coarse upstream capabilities relevant to local runtime selection.

    Values describe the runtime family, not every model/configuration. A
    ``conditional`` capability depends on model, parser, packaging, or runtime
    configuration. ``unknown`` means Modelito deliberately does not claim the
    capability from the upstream evidence currently recorded in the project.
    """

    streaming: CapabilityState
    prefix_cache: CapabilityState
    cancellation: CapabilityState
    structured_output: CapabilityState
    tool_calls: CapabilityState
    model_discovery: CapabilityState
    notes: str = ""


_LOCAL_RUNTIME_CAPABILITIES = {
    "basert": LocalRuntimeCapabilities(
        streaming="yes",
        prefix_cache="yes",
        cancellation="unknown",
        structured_output="unknown",
        tool_calls="yes",
        model_discovery="yes",
        notes="Native Metal runtime; exact features depend on the served model and BaseRT release.",
    ),
    "vllm-mlx": LocalRuntimeCapabilities(
        streaming="yes",
        prefix_cache="yes",
        cancellation="yes",
        structured_output="yes",
        tool_calls="conditional",
        model_discovery="yes",
        notes="Tool calling depends on model support and server parser/configuration.",
    ),
    "omlx": LocalRuntimeCapabilities(
        streaming="yes",
        prefix_cache="yes",
        cancellation="yes",
        structured_output="conditional",
        tool_calls="conditional",
        model_discovery="yes",
        notes="Structured output and tool calling can depend on installation and model/chat-template support.",
    ),
    "ollama": LocalRuntimeCapabilities(
        streaming="yes",
        prefix_cache="yes",
        cancellation="unknown",
        structured_output="yes",
        tool_calls="conditional",
        model_discovery="yes",
        notes="Model support and engine choice vary by Ollama release and model format.",
    ),
}


def is_macos_apple_silicon() -> bool:
    """Return whether the current host is macOS on Apple Silicon."""

    try:
        return platform.system() == "Darwin" and platform.machine().lower() in {
            "arm64",
            "aarch64",
        }
    except Exception:
        return False


def normalize_local_profile(profile: Optional[str]) -> str:
    """Return the canonical local-runtime profile name.

    ``None`` resolves from ``MODELITO_LOCAL_PROFILE`` and then to ``auto``.
    Unknown names fail explicitly rather than silently changing provider
    selection behaviour.
    """

    raw = profile if profile is not None else os.getenv("MODELITO_LOCAL_PROFILE")
    value = str(raw or LOCAL_PROFILE_AUTO).strip().lower()
    value = _ALIASES.get(value, value)
    if value not in LOCAL_PROFILES:
        allowed = ", ".join(LOCAL_PROFILES)
        raise ValueError(
            f"Unknown local runtime profile: {profile!r}. Expected one of: {allowed}"
        )
    return value


def local_provider_candidates(
    profile: Optional[str], *, is_macos_apple_silicon: bool
) -> List[str]:
    """Return the ordered local providers for *profile*.

    ``mac-performance`` is intentionally restricted to Apple Silicon. The
    order is a starting policy, not a benchmark result for an arbitrary model,
    machine, or workload. Use ``prefer=`` after measuring the target workload.
    """

    normalized = normalize_local_profile(profile)
    if normalized == LOCAL_PROFILE_AUTO:
        normalized = (
            LOCAL_PROFILE_MAC_PERFORMANCE
            if is_macos_apple_silicon
            else LOCAL_PROFILE_PORTABLE
        )

    if normalized == LOCAL_PROFILE_PORTABLE:
        return ["ollama"]

    if not is_macos_apple_silicon:
        raise ValueError(
            "The mac-performance local runtime profile requires macOS on Apple Silicon. "
            "Use profile='portable' on other platforms."
        )
    return ["basert", "vllm-mlx", "omlx", "ollama"]


def _normalize_provider(name: str) -> str:
    value = str(name or "").strip().lower()
    return _PROVIDER_ALIASES.get(value, value)


def local_runtime_capabilities(provider: str) -> LocalRuntimeCapabilities:
    """Return coarse capability metadata for a supported local runtime.

    The metadata is intentionally conservative and does not replace a runtime
    probe or an application-specific feature test.
    """

    normalized = _normalize_provider(provider)
    try:
        return _LOCAL_RUNTIME_CAPABILITIES[normalized]
    except KeyError as exc:
        allowed = ", ".join(LOCAL_PROVIDERS)
        raise ValueError(
            f"Unknown local runtime provider: {provider!r}. Expected one of: {allowed}"
        ) from exc


def _ordered_candidates(
    profile: str,
    prefer: Optional[Sequence[str]],
    *,
    on_macos_apple_silicon: bool,
) -> List[str]:
    defaults: List[str] = local_provider_candidates(
        profile, is_macos_apple_silicon=on_macos_apple_silicon
    )
    requested: List[str] = [_normalize_provider(x) for x in (prefer or [])]
    unknown = [x for x in requested if x not in LOCAL_PROVIDERS]
    if unknown:
        raise ValueError(
            "Local runtime preference can only contain basert, vllm-mlx, omlx or "
            "ollama; got: " + ", ".join(unknown)
        )
    apple_only = [x for x in requested if x in {"basert", "vllm-mlx", "omlx"}]
    if not on_macos_apple_silicon and apple_only:
        raise ValueError("BaseRT, vllm-mlx and oMLX require macOS on Apple Silicon")

    ordered: List[str] = []
    for candidate in requested + defaults:
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def _model_for_provider(
    provider: str,
    model: Optional[str],
    models: Optional[Mapping[str, str]],
) -> Optional[str]:
    if not models:
        return model
    normalized = {_normalize_provider(k): v for k, v in models.items()}
    return normalized.get(provider, model)


def _mapped_value(
    provider: str,
    default: Optional[str],
    mapping: Optional[Mapping[str, str]],
) -> Optional[str]:
    if not mapping:
        return default
    normalized = {_normalize_provider(k): v for k, v in mapping.items()}
    return normalized.get(provider, default)


def _probe_local_provider(
    provider: str,
    model: Optional[str],
    *,
    host: Optional[str],
    port: Optional[int],
    base_url: Optional[str],
    api_key: Optional[str],
    probe_timeout: float,
) -> ProviderStatus:
    if provider == "basert":
        return probe_basert_status(model, base_url, api_key, probe_timeout)
    if provider == "vllm-mlx":
        return probe_vllm_mlx_status(model, base_url, api_key, probe_timeout)
    if provider == "omlx":
        return probe_omlx_status(model, base_url, api_key, probe_timeout)
    if provider == "ollama":
        return probe_ollama_status(model, host, port, probe_timeout)
    raise ValueError(f"Unsupported local provider: {provider}")


def select_local_runtime(
    model: Optional[str] = None,
    *,
    models: Optional[Mapping[str, str]] = None,
    profile: Optional[str] = None,
    prefer: Optional[Sequence[str]] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    base_url: Optional[str] = None,
    base_urls: Optional[Mapping[str, str]] = None,
    api_key: Optional[str] = None,
    api_keys: Optional[Mapping[str, str]] = None,
    probe_timeout: float = 1.5,
    _is_macos_apple_silicon: Optional[bool] = None,
) -> LocalRuntimeSelection:
    """Select a ready local runtime without falling back to a hosted provider.

    ``models`` may map provider names to provider-specific model identifiers.
    ``base_urls`` and ``api_keys`` provide the same per-provider distinction for
    OpenAI-compatible local servers. When no model is requested, the selector
    binds to the first model reported by a ready local server; a server with no
    loaded models is not considered usable.
    """

    resolved_profile = normalize_local_profile(profile)
    on_mac = (
        is_macos_apple_silicon()
        if _is_macos_apple_silicon is None
        else bool(_is_macos_apple_silicon)
    )
    candidates: List[str] = _ordered_candidates(
        resolved_profile, prefer, on_macos_apple_silicon=on_mac
    )
    diagnostics: List[str] = []

    for provider in candidates:
        candidate_model = _model_for_provider(provider, model, models)
        candidate_base_url = _mapped_value(provider, base_url, base_urls)
        candidate_api_key = _mapped_value(provider, api_key, api_keys)
        status = _probe_local_provider(
            provider,
            candidate_model,
            host=host,
            port=port,
            base_url=candidate_base_url,
            api_key=candidate_api_key,
            probe_timeout=probe_timeout,
        )
        if status.ready:
            resolved_model = candidate_model
            if not resolved_model:
                resolved_model = status.models[0] if status.models else None
            if resolved_model:
                return LocalRuntimeSelection(
                    profile=resolved_profile,
                    provider=provider,
                    model=resolved_model,
                    endpoint=status.endpoint,
                )
            diagnostics.append(
                f"{provider} at {status.endpoint or 'unknown endpoint'}: no loaded models"
            )
            continue
        reason = status.reason or "not ready"
        endpoint = status.endpoint or "unknown endpoint"
        diagnostics.append(f"{provider} at {endpoint}: {reason}")

    detail = "; ".join(diagnostics) if diagnostics else "no local providers probed"
    raise ValueError(
        f"No ready local runtime for profile '{resolved_profile}'. {detail}. "
        "Start a local backend and ensure its requested model is available."
    )


def local_client(
    model: Optional[str] = None,
    *,
    models: Optional[Mapping[str, str]] = None,
    profile: Optional[str] = None,
    prefer: Optional[Sequence[str]] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    base_url: Optional[str] = None,
    base_urls: Optional[Mapping[str, str]] = None,
    api_key: Optional[str] = None,
    api_keys: Optional[Mapping[str, str]] = None,
    probe_timeout: float = 1.5,
    **provider_kwargs: Any,
):
    """Return a :class:`modelito.Client` bound to a ready local runtime.

    The returned provider is strict by default so a runtime failure is not
    silently replaced by Modelito's deterministic offline fallback.
    """

    selection = select_local_runtime(
        model,
        models=models,
        profile=profile,
        prefer=prefer,
        host=host,
        port=port,
        base_url=base_url,
        base_urls=base_urls,
        api_key=api_key,
        api_keys=api_keys,
        probe_timeout=probe_timeout,
    )

    from .client import Client

    kwargs = dict(provider_kwargs)
    kwargs.setdefault("strict", True)
    if selection.provider in {"basert", "vllm-mlx", "omlx"}:
        selected_base_url = _mapped_value(selection.provider, base_url, base_urls)
        selected_api_key = _mapped_value(selection.provider, api_key, api_keys)
        if selected_base_url is not None:
            kwargs["base_url"] = selected_base_url
        if selected_api_key is not None:
            kwargs["api_key"] = selected_api_key
    else:
        if host is not None:
            kwargs["host"] = host
        if port is not None:
            kwargs["port"] = port

    return Client(provider=selection.provider, model=selection.model, **kwargs)
