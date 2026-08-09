"""BaseRT provider with OpenAI-compatible local runtime integration.

BaseRT exposes an OpenAI-compatible HTTP server on Apple Silicon. This provider
reuses Modelito's shared OpenAI-compatible transport and only supplies BaseRT
specific defaults.
"""

from __future__ import annotations

from typing import Optional

from .openai_compat import OpenAICompatibleHTTPProvider


class BaseRTProvider(OpenAICompatibleHTTPProvider):
    """Provider for a local ``basert serve`` endpoint.

    Args:
        base_url: Base URL of the BaseRT OpenAI-compatible endpoint.
            Defaults to ``http://127.0.0.1:8080/v1``.
        model: Loaded BaseRT model identifier.
        api_key: Optional bearer token matching ``basert serve --api-key``.
        timeout: HTTP timeout in seconds.
        strict: When ``True``, raise typed Modelito errors instead of falling
            back to deterministic offline behaviour.
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
            base_url=base_url or "http://127.0.0.1:8080/v1",
            model=model or "basert",
            api_key=api_key,
            timeout=timeout,
            strict=strict,
        )
