"""
modelito.client

Unified Client interface for all providers.

- Abstract base class: Client
- Factory logic: Client(provider=..., model=...)
- Unified interface: summarize, stream, list_models, etc.
- Provider-specific features accessible via .provider
"""
from __future__ import annotations
import json
from typing import Any, Dict, Iterable, List, Optional, Type, Union, cast
from .provider_registry import get_provider, list_embedders, list_providers
from .provider import Provider
from .messages import Message, Response
from .model_metadata import get_model_metadata
from .normalization import normalize_metadata

class Client:
    """
    Unified LLM Client interface for all providers.
    Use Client(provider="openai", model="gpt-3.5-turbo") for runtime selection.
    """
    def __init__(self, provider: Union[str, Provider] = "openai", model: Optional[str] = None, **kwargs):
        if isinstance(provider, str):
            resolved_provider = get_provider(provider, model=model, **kwargs)
            if resolved_provider is None:
                raise ValueError(f"Unknown provider: {provider}")
            self.provider = resolved_provider
        else:
            self.provider = provider
        self.model = model or getattr(self.provider, "model", None)

    def list_models(self) -> List[str]:
        return self.provider.list_models()

    def summarize(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> str:
        return self.provider.summarize(messages, settings)

    def stream(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> Iterable[str]:
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
        messages: Iterable[Message],
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
        messages: Iterable[Message],
        schema: Optional[Type[Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
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
