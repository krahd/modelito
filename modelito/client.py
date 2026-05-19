"""
modelito.client

Unified Client interface for all providers.

- Abstract base class: Client
- Factory logic: Client(provider=..., model=...)
- Unified interface: summarize, stream, list_models, etc.
- Provider-specific features accessible via .provider
"""
from __future__ import annotations
from dataclasses import is_dataclass
import json
import os
import platform
from typing import Any, Dict, Iterable, List, Optional, Sequence, Type, Union, cast
from .config import load_config
from .ollama_service import server_is_up
from .omlx import OMLXProvider
from .ollama import OllamaProvider
from .provider_registry import get_provider, list_embedders, list_providers
from .provider import MessageInput, Provider
from .messages import Response
from .model_metadata import get_model_metadata
from .normalization import normalize_metadata

class Client:
    """
    Unified LLM Client interface for all providers.
    Use Client(provider="openai", model="gpt-3.5-turbo") for runtime selection.
    """
    def __init__(
        self,
        provider: Union[str, Provider] = "openai",
        model: Optional[str] = None,
        prefer: Optional[Iterable[str]] = None,
        **kwargs,
    ):
        profile_path = kwargs.pop("profile_path", None)
        provider_env_var = str(kwargs.pop("provider_env_var", "MODELITO_PROVIDER"))
        remote_provider_env_var = str(
            kwargs.pop("remote_provider_env_var", "MODELITO_REMOTE_PROVIDER")
        )
        default_provider = str(kwargs.pop("default_provider", "openai"))
        auto_probe_timeout = float(kwargs.pop("auto_probe_timeout", 1.5))
        prefer_list = list(prefer or [])

        if isinstance(provider, str):
            provider_name = self._resolve_provider_name(
                provider=provider,
                model=model,
                prefer=prefer_list,
                profile_path=profile_path,
                provider_env_var=provider_env_var,
                remote_provider_env_var=remote_provider_env_var,
                default_provider=default_provider,
                auto_probe_timeout=auto_probe_timeout,
                provider_kwargs=kwargs,
            )
            resolved_provider = get_provider(provider_name, model=model, **kwargs)
            if resolved_provider is None:
                raise ValueError(f"Unknown provider: {provider_name}")
            self.provider = resolved_provider
        else:
            self.provider = provider
        self.model = model or getattr(self.provider, "model", None)

    @staticmethod
    def _normalize_provider_name(name: str) -> str:
        value = str(name or "").strip().lower()
        if value == "om":
            return "omlx"
        return value

    @classmethod
    def _ensure_known_provider(cls, name: str, source: str) -> str:
        normalized = cls._normalize_provider_name(name)
        if normalized not in set(list_providers()) and normalized != "auto":
            raise ValueError(f"Unknown provider in {source}: {name}")
        return normalized

    @staticmethod
    def _extract_provider_from_profile(config: Dict[str, Any]) -> Optional[str]:
        if not isinstance(config, dict):
            return None
        provider = config.get("provider")
        if isinstance(provider, str) and provider.strip():
            return provider.strip()
        profile = config.get("profile")
        if isinstance(profile, dict):
            provider = profile.get("provider")
            if isinstance(provider, str) and provider.strip():
                return provider.strip()
        modelito = config.get("modelito")
        if isinstance(modelito, dict):
            provider = modelito.get("provider")
            if isinstance(provider, str) and provider.strip():
                return provider.strip()
        return None

    @classmethod
    def _provider_from_project_profile(cls, profile_path: Optional[str] = None) -> Optional[str]:
        candidates: List[str] = []
        if profile_path:
            candidates.append(str(profile_path))
        env_profile = os.getenv("MODELITO_PROFILE")
        if env_profile:
            candidates.append(env_profile)
        candidates.extend([".modelito.json", ".modelito.yaml", ".modelito.yml"])

        for path in candidates:
            config = load_config(path)
            if not config:
                continue
            found = cls._extract_provider_from_profile(config)
            if isinstance(found, str) and found.strip():
                return cls._ensure_known_provider(found, f"project profile {path}")
        return None

    @staticmethod
    def _is_macos_apple_silicon() -> bool:
        return platform.system() == "Darwin" and platform.machine().lower() in {
            "arm64",
            "aarch64",
        }

    @staticmethod
    def _omlx_probe(
        model: Optional[str], provider_kwargs: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"strict": True}
        kwargs["timeout"] = timeout
        if model:
            kwargs["model"] = model
        if "base_url" in provider_kwargs:
            kwargs["base_url"] = provider_kwargs["base_url"]
        if "api_key" in provider_kwargs:
            kwargs["api_key"] = provider_kwargs["api_key"]
        if "timeout" in provider_kwargs:
            kwargs["timeout"] = provider_kwargs["timeout"]
        try:
            provider = OMLXProvider(**kwargs)
            models = provider.list_models()
            available = model in set(models) if model else True
            return {
                "provider": "omlx",
                "available": available,
                "models": models,
                "endpoint": getattr(provider, "base_url", "http://localhost:8000/v1"),
                "reason": None if available else "requested model not found",
                "setup_hint": "Start oMLX and download an MLX model via the admin dashboard.",
            }
        except Exception:
            return {
                "provider": "omlx",
                "available": False,
                "models": [],
                "endpoint": "http://localhost:8000/v1",
                "reason": "oMLX server not reachable",
                "setup_hint": "Start oMLX and download an MLX model via the admin dashboard.",
            }

    @staticmethod
    def _ollama_probe(
        model: Optional[str], provider_kwargs: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        host = str(provider_kwargs.get("host") or "http://127.0.0.1")
        port = int(provider_kwargs.get("port") or 11434)
        try:
            if not server_is_up(host, port):
                return {
                    "provider": "ollama",
                    "available": False,
                    "models": [],
                    "endpoint": f"{host}:{port}",
                    "reason": "Ollama server not reachable",
                    "setup_hint": "Start Ollama and pull the requested model with `ollama pull <model>`.",
                }
        except Exception:
            return {
                "provider": "ollama",
                "available": False,
                "models": [],
                "endpoint": f"{host}:{port}",
                "reason": "Ollama server not reachable",
                "setup_hint": "Start Ollama and pull the requested model with `ollama pull <model>`.",
            }

        kwargs: Dict[str, Any] = {"host": host, "port": port}
        if model:
            kwargs["model"] = model
        try:
            provider = OllamaProvider(**kwargs)
            models = provider.list_models()
            available = model in set(models) if model else True
            return {
                "provider": "ollama",
                "available": available,
                "models": models,
                "endpoint": f"{host}:{port}",
                "reason": None if available else "requested model not found",
                "setup_hint": "Pull the requested model with `ollama pull <model>`.",
            }
        except Exception:
            return {
                "provider": "ollama",
                "available": False,
                "models": [],
                "endpoint": f"{host}:{port}",
                "reason": "Ollama probe failed",
                "setup_hint": "Start Ollama and pull the requested model with `ollama pull <model>`.",
            }

    @staticmethod
    def _probe_summary(probe: Dict[str, Any]) -> str:
        status = "ready" if probe.get("available") else "not ready"
        endpoint = probe.get("endpoint") or "unknown endpoint"
        reason = probe.get("reason") or "ok"
        models = probe.get("models") or []
        model_part = f", models={models}" if models else ""
        return f"{probe.get('provider')}: {status} at {endpoint} ({reason}{model_part})"

    @classmethod
    def _auto_select_provider(
        cls,
        model: Optional[str],
        provider_kwargs: Dict[str, Any],
        remote_provider_env_var: str,
        prefer: Sequence[str],
        auto_probe_timeout: float,
    ) -> Optional[str]:
        probes: List[Dict[str, Any]] = []

        def try_preferred(name: str) -> Optional[str]:
            normalized = cls._normalize_provider_name(name)
            if normalized == "omlx":
                probe = cls._omlx_probe(model, provider_kwargs, auto_probe_timeout)
                probes.append(probe)
                return "omlx" if probe.get("available") else None
            if normalized == "ollama":
                probe = cls._ollama_probe(model, provider_kwargs, auto_probe_timeout)
                probes.append(probe)
                return "ollama" if probe.get("available") else None
            if normalized in set(list_providers()):
                return normalized
            return None

        for candidate in prefer:
            selected = try_preferred(candidate)
            if selected:
                return selected

        if cls._is_macos_apple_silicon():
            omx_probe = cls._omlx_probe(model, provider_kwargs, auto_probe_timeout)
            probes.append(omx_probe)
            if omx_probe.get("available"):
                return "omlx"
            ollama_probe = cls._ollama_probe(model, provider_kwargs, auto_probe_timeout)
            probes.append(ollama_probe)
            if ollama_probe.get("available"):
                return "ollama"
            raise ValueError(
                "Auto provider could not find a usable local backend on macOS "
                "Apple Silicon. "
                + "; ".join(cls._probe_summary(probe) for probe in probes)
                + ". Install/start one backend and ensure the requested model is "
                "available (for Ollama: `ollama pull <model>`)."
            )

        ollama_probe = cls._ollama_probe(model, provider_kwargs, auto_probe_timeout)
        probes.append(ollama_probe)
        if ollama_probe.get("available"):
            return "ollama"

        remote_provider = os.getenv(remote_provider_env_var)
        if isinstance(remote_provider, str) and remote_provider.strip():
            normalized = cls._ensure_known_provider(
                remote_provider, remote_provider_env_var
            )
            if normalized != "auto":
                return normalized

        return None

    @classmethod
    def _resolve_provider_name(
        cls,
        provider: str,
        model: Optional[str],
        prefer: Sequence[str],
        profile_path: Optional[str],
        provider_env_var: str,
        remote_provider_env_var: str,
        default_provider: str,
        auto_probe_timeout: float,
        provider_kwargs: Dict[str, Any],
    ) -> str:
        requested = cls._ensure_known_provider(provider, "provider argument")

        # 1) Explicit provider argument wins unless it's explicit auto mode.
        if requested != "auto":
            return requested

        # 2) Project profile provider.
        profile_provider = cls._provider_from_project_profile(profile_path)
        if profile_provider:
            if profile_provider != "auto":
                return profile_provider

        # 3) Environment provider.
        env_provider = os.getenv(provider_env_var)
        if isinstance(env_provider, str) and env_provider.strip():
            normalized_env = cls._ensure_known_provider(env_provider, provider_env_var)
            if normalized_env != "auto":
                return normalized_env

        # 4) Auto detection.
        auto_name = cls._auto_select_provider(
            model=model,
            provider_kwargs=provider_kwargs,
            remote_provider_env_var=remote_provider_env_var,
            prefer=prefer,
            auto_probe_timeout=auto_probe_timeout,
        )
        if auto_name:
            return auto_name

        # 5) Old/default provider fallback.
        return cls._ensure_known_provider(default_provider, "default provider")

    def chat_parsed(
        self,
        messages: Iterable[MessageInput],
        schema: Type[Any],
        settings: Optional[Dict[str, Any]] = None,
        strict_schema: bool = True,
    ) -> Any:
        """Return a parsed structured object instead of the raw JSON dict."""
        result = self.chat_json(
            messages,
            schema=schema,
            settings=settings,
            strict_schema=strict_schema,
        )

        annotations = getattr(schema, "__annotations__", None)
        if is_dataclass(schema):
            return cast(Any, schema)(**result)
        if callable(getattr(schema, "model_validate", None)):
            return cast(Any, schema).model_validate(result)
        if callable(getattr(schema, "parse_obj", None)):
            return cast(Any, schema).parse_obj(result)
        if annotations:
            return result
        return result

    def list_models(self) -> List[str]:
        return self.provider.list_models()

    def summarize(self, messages: Iterable[MessageInput], settings: Optional[Dict[str, Any]] = None) -> str:
        return self.provider.summarize(messages, settings)

    def stream(self, messages: Iterable[MessageInput], settings: Optional[Dict[str, Any]] = None) -> Iterable[str]:
        if hasattr(self.provider, "stream"):
            yield from cast(Any, self.provider).stream(messages, settings)
            return
        # Fallback: yield the full result as one chunk
        yield self.summarize(messages, settings)

    def model_metadata(self, model: Optional[str] = None) -> Dict[str, Any]:
        target_model = model or self.model
        if hasattr(self.provider, "model_metadata"):
            raw_metadata = cast(Any, self.provider).model_metadata(target_model)
            return normalize_metadata(raw_metadata)
        if target_model is None:
            return {}
        return get_model_metadata(target_model)

    def embed(self, texts: Iterable[str], **kwargs) -> List[List[float]]:
        if hasattr(self.provider, "embed"):
            return cast(Any, self.provider).embed(texts, **kwargs)
        raise NotImplementedError("This provider does not support embeddings.")

    def chat(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Return a full :class:`~modelito.messages.Response` with metadata.

        Delegates to ``provider.chat()`` when available; otherwise wraps
        ``summarize()`` in a minimal ``Response``.
        """
        if hasattr(self.provider, "chat"):
            return cast(Any, self.provider).chat(messages, settings)
        text = self.summarize(messages, settings)
        return Response(text=text)

    def chat_json(
        self,
        messages: Iterable[MessageInput],
        schema: Optional[Type[Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        strict_schema: bool = False,
    ) -> dict:
        """Request structured JSON output from the provider.

        Injects ``response_format={"type": "json_object"}`` into *settings*
        and returns the parsed JSON dict.

        Args:
            messages: Conversation messages.
            schema: Optional TypedDict or dataclass whose ``__annotations__``
                are used to verify that all declared keys are present.
            settings: Extra provider settings merged with
                ``response_format``.
            strict_schema: When ``True``, performs stronger runtime validation
                when possible: dataclass construction and Pydantic-style
                ``model_validate``/``parse_obj`` hooks.

        Returns:
            Parsed JSON dict from the provider response.

        Raises:
            ValueError: If the provider response is not valid JSON, or if
                *schema* is given and required keys are missing.
        """
        merged: Dict[str, Any] = dict(settings or {})
        merged["response_format"] = {"type": "json_object"}

        if hasattr(self.provider, "chat"):
            response = cast(Any, self.provider).chat(messages, merged)
            text = response.text
        else:
            text = self.summarize(messages, merged)

        try:
            result: dict = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Provider did not return valid JSON: {text!r}"
            ) from exc

        if schema is not None:
            annotations = getattr(schema, "__annotations__", None)
            if annotations:
                missing = [k for k in annotations if k not in result]
                if missing:
                    raise ValueError(
                        f"JSON response missing required keys: {missing}"
                    )

        if strict_schema and schema is not None:
            if is_dataclass(schema):
                try:
                    cast(Any, schema)(**result)
                except Exception as exc:
                    raise ValueError(
                        f"JSON response failed dataclass validation: {exc}"
                    ) from exc
            elif callable(getattr(schema, "model_validate", None)):
                try:
                    cast(Any, schema).model_validate(result)
                except Exception as exc:
                    raise ValueError(
                        f"JSON response failed model validation: {exc}"
                    ) from exc
            elif callable(getattr(schema, "parse_obj", None)):
                try:
                    cast(Any, schema).parse_obj(result)
                except Exception as exc:
                    raise ValueError(
                        f"JSON response failed model validation: {exc}"
                    ) from exc

        return result

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "__class__", type(self.provider)).__name__

    @staticmethod
    def available_providers() -> List[str]:
        return list_providers()

    @staticmethod
    def available_embedders() -> List[str]:
        return list_embedders()

    # Expose provider-specific features if needed
    def __getattr__(self, item):
        # Allow access to provider-specific methods/attributes
        return getattr(self.provider, item)
