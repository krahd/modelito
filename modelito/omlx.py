"""oMLX provider with HTTP-first local runtime integration.

The oMLX provider targets OpenAI-compatible HTTP endpoints exposed by local
oMLX runtimes.  It delegates all HTTP, streaming, and error logic to
:class:`~modelito.openai_compat.OpenAICompatibleHTTPProvider` and only sets
oMLX-specific defaults.
"""
from __future__ import annotations

from typing import Optional

from .openai_compat import OpenAICompatibleHTTPProvider


class OMLXProvider(OpenAICompatibleHTTPProvider):
    """Provider for oMLX-compatible HTTP runtimes.

    Args:
        base_url: Base URL of an OpenAI-compatible oMLX endpoint.
            Defaults to ``http://127.0.0.1:11435/v1``.
        model: Default model name.  Defaults to ``"omlx"``.
        api_key: Optional bearer token for secured endpoints.
        timeout: HTTP timeout in seconds.
        strict: When ``True``, raise typed Modelito errors instead of
            falling back to deterministic offline behaviour.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 20.0,
        strict: bool = False,
    ) -> None:
        super().__init__(
            base_url=base_url or "http://127.0.0.1:11435/v1",
            model=model or "omlx",
            api_key=api_key,
            timeout=timeout,
            strict=strict,
        )
