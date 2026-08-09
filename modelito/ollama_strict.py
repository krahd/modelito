"""Strict-aware Ollama provider surface.

The historical :mod:`modelito.ollama` provider intentionally keeps deterministic
fallbacks for offline-friendly use. Local-runtime profiles have a stronger
contract: when ``strict=True`` a failed local model request must fail rather than
silently returning the prompt. This subclass preserves the legacy non-strict
behaviour while routing strict chat through Ollama's OpenAI-compatible raw
surfaces, which already classify and raise transport/provider errors.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .exceptions import ModelitoBadResponseError
from .messages import flatten_message_inputs
from .ollama import OllamaProvider as _LegacyOllamaProvider
from .provider import MessageInput


class OllamaProvider(_LegacyOllamaProvider):
    """Ollama provider that enforces ``strict=True`` for summary and streaming."""

    @staticmethod
    def _strict_messages(messages: Iterable[MessageInput]) -> list[dict[str, Any]]:
        return flatten_message_inputs(messages)

    def summarize(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[dict[str, Any]] = None,
    ) -> str:
        if not self.strict:
            return super().summarize(messages, settings=settings)

        payload: dict[str, Any] = {"messages": self._strict_messages(messages)}
        if settings:
            payload.update(settings)
        response = self.raw_complete(payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelitoBadResponseError(
                "Ollama strict summarize returned no completion choices"
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise ModelitoBadResponseError(
                "Ollama strict summarize returned an invalid completion choice"
            )
        message = first.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return str(message["content"])
        if isinstance(first.get("text"), str):
            return str(first["text"])
        raise ModelitoBadResponseError(
            "Ollama strict summarize returned no textual completion"
        )

    def stream(
        self,
        messages: Iterable[MessageInput],
        settings: Optional[dict[str, Any]] = None,
    ) -> Iterable[str]:
        if not self.strict:
            yield from super().stream(messages, settings=settings)
            return

        payload: dict[str, Any] = {"messages": self._strict_messages(messages)}
        if settings:
            payload.update(settings)
        for event in self.raw_stream(payload):
            choices = event.get("choices") if isinstance(event, dict) else None
            if not isinstance(choices, list) or not choices:
                continue
            first = choices[0]
            if not isinstance(first, dict):
                continue
            delta = first.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                content = str(delta["content"])
                if content:
                    yield content
                continue
            text = first.get("text")
            if isinstance(text, str) and text:
                yield text
