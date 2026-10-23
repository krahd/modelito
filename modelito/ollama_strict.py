"""Strict-aware Ollama provider surface.

The base provider defaults to strict native HTTP requests. Legacy offline
fallbacks require explicit ``strict=False`` and warn about degraded semantics.
This subclass remains as the stable package-root and registry export
for compatibility.
"""

from __future__ import annotations

from .ollama import OllamaProvider as _LegacyOllamaProvider


class OllamaProvider(_LegacyOllamaProvider):
    """Compatibility export for the strict-aware base Ollama provider."""
