"""Best-effort model metadata fallback registry.

This module exposes conservative metadata defaults for known model IDs and
model families. Provider APIs remain the source of truth. Unknown fields are
represented as ``None`` and entries should be updated conservatively.

Do not use this registry as the sole source for safety-critical routing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ModelMetadata:
    id: str
    provider: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_tools: bool | None = None
    supports_functions: bool | None = None
    supports_vision: bool | None = None
    supports_embeddings: bool | None = None
    supports_streaming: bool | None = None
    notes: str | None = None


MODEL_METADATA: dict[str, ModelMetadata] = {
    "gpt-4o-mini": ModelMetadata(
        id="gpt-4o-mini",
        provider="openai",
        supports_tools=True,
        supports_functions=True,
        supports_streaming=True,
    ),
    "gpt-4o": ModelMetadata(
        id="gpt-4o",
        provider="openai",
        supports_tools=True,
        supports_functions=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    "claude-3-5-sonnet-latest": ModelMetadata(
        id="claude-3-5-sonnet-latest",
        provider="anthropic",
        supports_tools=True,
        supports_streaming=True,
    ),
    "gemini-1.5-pro": ModelMetadata(
        id="gemini-1.5-pro",
        provider="google",
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    "gemini-2.0-flash": ModelMetadata(
        id="gemini-2.0-flash",
        provider="google",
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
}


def infer_model_metadata(model_name: str) -> ModelMetadata:
    """Infer conservative model metadata from a model identifier.

    Inference intentionally avoids guessed token limits and only sets fields
    that are reasonably clear from the model name/family.
    """
    normalized = str(model_name or "").strip().lower()
    metadata = ModelMetadata(id=str(model_name or "").strip() or "unknown")

    if normalized.startswith("gpt-") or normalized.startswith("o"):
        metadata = _replace(metadata, provider="openai", supports_streaming=True)
    elif normalized.startswith("claude-"):
        metadata = _replace(metadata, provider="anthropic", supports_streaming=True)
    elif normalized.startswith("gemini-"):
        metadata = _replace(metadata, provider="google", supports_streaming=True)

    if "nomic-embed" in normalized or "text-embedding" in normalized:
        metadata = _replace(metadata, supports_embeddings=True)

    return metadata


def get_model_info(model_name: str, infer: bool = True) -> Optional[ModelMetadata]:
    """Return typed model metadata for an exact ID or inferred family match."""
    key = str(model_name or "").strip()
    if not key:
        return None

    exact = MODEL_METADATA.get(key)
    if exact is not None:
        return exact

    if not infer:
        return None

    inferred = infer_model_metadata(key)
    if inferred.provider is None and inferred.supports_embeddings is None:
        return None
    return inferred


def get_model_metadata(model_name: str, infer: bool = False) -> Dict[str, Any]:
    """Return metadata dictionary for a model name.

    Unknown models return ``{}`` by default for backward compatibility.
    Set ``infer=True`` to return conservative family-based metadata.
    """
    info = get_model_info(model_name, infer=infer)
    if info is None:
        return {}

    data = asdict(info)
    # Keep legacy aliases for callers that expect the older shape.
    data["tools"] = info.supports_tools
    data["functions"] = info.supports_functions
    return data


def _replace(metadata: ModelMetadata, **updates: Any) -> ModelMetadata:
    values = asdict(metadata)
    values.update(updates)
    return ModelMetadata(**values)
