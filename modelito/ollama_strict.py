"""Strict-aware Ollama provider surface.

The historical :mod:`modelito.ollama` provider intentionally keeps deterministic
fallbacks for offline-friendly use. Local-runtime profiles have a stronger
contract: when ``strict=True`` a failed local model request must fail rather than
silently returning the prompt. The base provider now enforces that distinction
directly. This subclass remains as the stable package-root and registry export
for compatibility.
"""

from __future__ import annotations

from .ollama import OllamaProvider as _LegacyOllamaProvider


class OllamaProvider(_LegacyOllamaProvider):
    """Compatibility export for the strict-aware base Ollama provider."""
