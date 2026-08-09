"""vllm-mlx provider with OpenAI-compatible local runtime integration.

vllm-mlx exposes an OpenAI-compatible HTTP server on Apple Silicon. This
provider reuses Modelito's shared OpenAI-compatible transport and only supplies
vllm-mlx-specific defaults.
"""

from __future__ import annotations

from typing import Optional

from .openai_compat import OpenAICompatibleHTTPProvider


class VLLMMLXProvider(OpenAICompatibleHTTPProvider):
    """Provider for a local ``vllm-mlx serve`` endpoint.

    Args:
        base_url: Base URL of the vllm-mlx OpenAI-compatible endpoint.
            Defaults to ``http://localhost:8000/v1``.
        model: Served model identifier. ``"default"`` is used only when a
            caller constructs the provider directly without specifying one;
            runtime selection discovers the actual model through ``/models``.
        api_key: Optional bearer token matching ``vllm-mlx serve --api-key``.
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
            base_url=base_url or "http://localhost:8000/v1",
            model=model or "default",
            api_key=api_key,
            timeout=timeout,
            strict=strict,
        )
