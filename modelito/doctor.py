"""Provider readiness diagnostics and CLI helpers.

The readiness API is intentionally read-only: it diagnoses whether a provider
looks usable, reports the endpoint and discovered models when applicable, and
returns actionable setup hints without installing or modifying anything.
"""

from __future__ import annotations

import argparse
import json
import platform
from typing import List, Optional, Sequence

from . import probes
from .openai import OpenAIProvider
from .provider_registry import get_provider

ProviderStatus = probes.ProviderStatus


def _normalize_provider_name(provider: str) -> str:
    name = str(provider or "").strip().lower()
    if name == "om":
        return "omlx"
    return name


def _probe_omlx(
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    probe_timeout: float,
) -> ProviderStatus:
    return probes.probe_omlx_status(model, base_url, api_key, probe_timeout)


def _probe_ollama(
    model: Optional[str],
    host: Optional[str],
    port: Optional[int],
    probe_timeout: float,
) -> ProviderStatus:
    return probes.probe_ollama_status(model, host, port, probe_timeout)


def _probe_openai(
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
) -> ProviderStatus:
    try:
        provider = OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
        models = provider.list_models()
        ready = probes.model_is_available(model, models)
        endpoint = (
            base_url
            or getattr(provider, "base_url", None)
            or "https://api.openai.com/v1"
        )
        return probes.build_status(
            "openai",
            ready,
            endpoint=endpoint,
            models=models,
            reason="" if ready else "requested model not found or API unavailable",
            setup_hint="Set OPENAI_API_KEY and optional OPENAI_BASE_URL if you are targeting a hosted OpenAI-compatible API.",
        )
    except Exception as exc:
        return probes.build_status(
            "openai",
            False,
            endpoint=base_url or "https://api.openai.com/v1",
            models=[],
            reason="OpenAI provider unavailable",
            setup_hint="Set OPENAI_API_KEY and optional OPENAI_BASE_URL if you are targeting a hosted OpenAI-compatible API.",
            details={"error": str(exc)},
        )


def _probe_generic_provider(provider: str, model: Optional[str]) -> ProviderStatus:
    try:
        resolved = get_provider(provider, model=model)
        if resolved is None:
            return probes.build_status(
                provider,
                False,
                reason=f"Unknown provider: {provider}",
                setup_hint="Pick one of the built-in providers or configure a valid provider profile.",
            )
        models = []
        try:
            models = list(resolved.list_models())
        except Exception as exc:
            return probes.build_status(
                provider,
                False,
                models=[],
                reason="Provider failed while listing models",
                setup_hint="Check provider configuration and API credentials.",
                details={"error": str(exc)},
            )
        ready = probes.model_is_available(model, models)
        endpoint = getattr(resolved, "base_url", None) or getattr(
            resolved, "host", None
        )
        return probes.build_status(
            provider,
            ready,
            endpoint=str(endpoint) if endpoint is not None else None,
            models=models,
            reason="" if ready else "requested model not found",
            setup_hint="Check provider configuration and API credentials.",
        )
    except Exception as exc:
        return probes.build_status(
            provider,
            False,
            reason="Provider probe failed",
            setup_hint="Check provider configuration and API credentials.",
            details={"error": str(exc)},
        )


def check_provider_ready(
    provider: str,
    model: Optional[str] = None,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    prefer: Optional[Sequence[str]] = None,
    probe_timeout: float = 1.5,
) -> ProviderStatus:
    """Diagnose whether a provider looks ready to use.

    The helper is read-only: it does not install, download, or mutate state.
    """
    normalized = _normalize_provider_name(provider)
    if normalized == "auto":
        default_prefer: List[str] = list(
            prefer or (["omlx", "ollama"] if _is_macos_apple_silicon() else ["ollama"])
        )
        for candidate in default_prefer:
            candidate_name = _normalize_provider_name(candidate)
            if candidate_name == "omlx":
                status = _probe_omlx(model, base_url, api_key, probe_timeout)
            elif candidate_name == "ollama":
                status = _probe_ollama(model, host, port, probe_timeout)
            else:
                status = _probe_generic_provider(candidate_name, model)
            if status.ready:
                return status
        if _is_macos_apple_silicon():
            return probes.build_status(
                "auto",
                False,
                reason="No local backend was ready on macOS Apple Silicon",
                setup_hint=(
                    "Start oMLX at http://localhost:8000/v1 or Ollama at http://127.0.0.1:11434, then ensure the requested model is available."
                ),
            )
        return probes.build_status(
            "auto",
            False,
            reason="No suitable provider was ready",
            setup_hint="Configure a provider profile, environment override, or a local backend.",
        )

    if normalized == "omlx":
        return _probe_omlx(model, base_url, api_key, probe_timeout)
    if normalized == "ollama":
        return _probe_ollama(model, host, port, probe_timeout)
    if normalized == "openai":
        return _probe_openai(model, base_url, api_key)

    return _probe_generic_provider(normalized, model)


def format_provider_status(status: ProviderStatus) -> str:
    """Render a provider status as a human-readable multi-line string."""
    lines = [
        f"provider: {status.provider}",
        f"ready: {status.ready}",
    ]
    if status.endpoint:
        lines.append(f"endpoint: {status.endpoint}")
    if status.models:
        lines.append(f"models: {', '.join(status.models)}")
    if status.reason:
        lines.append(f"reason: {status.reason}")
    if status.setup_hint:
        lines.append(f"setup_hint: {status.setup_hint}")
    if status.details:
        lines.append(f"details: {json.dumps(status.details, sort_keys=True)}")
    return "\n".join(lines)


def _is_macos_apple_silicon() -> bool:
    try:
        return platform.system() == "Darwin" and platform.machine().lower() in {
            "arm64",
            "aarch64",
        }
    except Exception:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelito", description="Provider readiness diagnostics"
    )
    subparsers = parser.add_subparsers(dest="cmd")

    doctor = subparsers.add_parser(
        "doctor", help="Check whether a provider looks ready"
    )
    doctor.add_argument(
        "--provider", default="auto", help="Provider name to probe (default: auto)"
    )
    doctor.add_argument("--model", default=None, help="Requested model name")
    doctor.add_argument("--host", default=None, help="Provider host override")
    doctor.add_argument("--port", type=int, default=None, help="Provider port override")
    doctor.add_argument(
        "--base-url", default=None, help="OpenAI/oMLX-compatible base URL override"
    )
    doctor.add_argument("--api-key", default=None, help="Optional API key override")
    doctor.add_argument(
        "--probe-timeout",
        type=float,
        default=1.5,
        help="Short probe timeout in seconds",
    )
    doctor.add_argument("--json", action="store_true", help="Print JSON output")
    doctor.add_argument(
        "--prefer", nargs="*", default=None, help="Preferred providers for auto mode"
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "cmd", None) != "doctor":
        parser.print_help()
        return 2

    status = check_provider_ready(
        args.provider,
        model=args.model,
        host=args.host,
        port=args.port,
        base_url=args.base_url,
        api_key=args.api_key,
        prefer=args.prefer,
        probe_timeout=args.probe_timeout,
    )
    if args.json:
        print(json.dumps(status.__dict__, indent=2, sort_keys=True))
    else:
        print(format_provider_status(status))
    return 0 if status.ready else 1


__all__ = [
    "ProviderStatus",
    "check_provider_ready",
    "format_provider_status",
    "build_parser",
    "main",
]
