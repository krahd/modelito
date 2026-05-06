"""Normalization helpers for model and metadata payloads.

Provider SDKs expose model lists and metadata in a few common shapes:
strings, dictionaries, wrapper objects with ``data`` or ``models`` members,
and SDK objects with attributes.  These helpers keep downstream adapters from
having to duplicate that shape handling.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

_MODEL_COLLECTION_KEYS = ("models", "data", "items", "llms", "tags", "running")
_MODEL_ID_KEYS = ("id", "model", "name", "model_id", "slug", "value")
_RESPONSE_METADATA_KEYS = {
    "object",
    "has_more",
    "first_id",
    "last_id",
    "total",
    "total_count",
}

_CONTEXT_KEYS = (
    "context_window",
    "context_length",
    "max_context_length",
    "max_context",
    "ctx",
    "n_ctx",
    "num_ctx",
)
_FUNCTION_KEYS = (
    "functions",
    "supports_functions",
    "function_calling",
    "supports_function_calling",
)
_TOOL_KEYS = ("tools", "supports_tools", "tool_use", "tool_calling", "tools_supported")


def normalize_models(raw: Any) -> list[dict[str, Any]]:
    """Return model payloads as ``{"id": ...}`` dictionaries.

    Args:
        raw: A provider model listing. Supported inputs include a single model
            string or object, a list/tuple/generator of model entries, a dict
            wrapper such as ``{"models": [...]}`` or ``{"data": [...]}``, and
            SDK objects exposing similar attributes.

    Returns:
        A list of dictionaries. Each dictionary has a non-empty string ``id``
        and preserves any other fields found on the source item.
    """
    models: list[dict[str, Any]] = []
    for item in _iter_model_items(raw):
        normalized = _normalize_model_item(item)
        if normalized is not None:
            models.append(normalized)
    return models


def normalize_metadata(raw: Any) -> dict[str, Any]:
    """Return model metadata as a dictionary.

    Non-mapping scalar metadata is wrapped as ``{"value": raw}``. Mapping and
    SDK-object metadata is copied into a plain dictionary. Common aliases such
    as ``ctx`` or ``context_length`` also populate ``context_window`` when that
    canonical key is missing.
    """
    if raw is None:
        return {}

    data = _coerce_mapping(raw)
    if data is None:
        return {"value": raw}

    normalized = {str(key): value for key, value in data.items()}
    if "metadata" in normalized:
        normalized["metadata"] = normalize_metadata(normalized["metadata"])

    _copy_first_present(normalized, "context_window", _CONTEXT_KEYS)
    _copy_first_present(normalized, "functions", _FUNCTION_KEYS)
    _copy_first_present(normalized, "tools", _TOOL_KEYS)
    return normalized


def _iter_model_items(raw: Any) -> Iterable[Any]:
    if raw is None:
        return ()

    if isinstance(raw, (str, bytes)):
        return (raw,)

    data = _coerce_mapping(raw)
    if data is not None:
        for key in _MODEL_COLLECTION_KEYS:
            if key in data and data[key] is not None:
                return _iter_collection(data[key])
        if _has_model_id(data):
            return (data,)
        return _iter_model_mapping(data)

    for key in _MODEL_COLLECTION_KEYS:
        try:
            value = getattr(raw, key)
        except Exception:
            continue
        if value is not None:
            return _iter_collection(value)

    if isinstance(raw, Iterable):
        return raw

    return (raw,)


def _iter_collection(value: Any) -> Iterable[Any]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)

    data = _coerce_mapping(value)
    if data is not None:
        if _has_model_id(data):
            return (data,)
        return _iter_model_mapping(data)

    if isinstance(value, Iterable):
        return value

    return (value,)


def _iter_model_mapping(data: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, value in data.items():
        key_str = str(key)
        if key_str in _RESPONSE_METADATA_KEYS:
            continue

        payload = _coerce_mapping(value)
        if payload is None:
            items.append({"id": key_str, "value": value})
            continue

        normalized = {str(payload_key): payload_value for payload_key,
                      payload_value in payload.items()}
        normalized.setdefault("id", key_str)
        items.append(normalized)
    return items


def _normalize_model_item(item: Any) -> dict[str, Any] | None:
    if item is None:
        return None

    if isinstance(item, bytes):
        item = item.decode("utf-8", errors="replace")

    if isinstance(item, str):
        model_id_str = item.strip()
        return {"id": model_id_str} if model_id_str else None

    data = _coerce_mapping(item)
    if data is None:
        model_id_str = str(item).strip()
        return {"id": model_id_str} if model_id_str else None

    payload = {str(key): value for key, value in data.items()}
    model_id = _first_present(payload, _MODEL_ID_KEYS)
    if model_id is None:
        return None

    model_id_str = str(model_id).strip()
    if not model_id_str:
        return None

    payload["id"] = model_id_str
    return payload


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)

    try:
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
    except Exception:
        pass

    for method_name in ("model_dump", "dict", "to_dict"):
        method = getattr(value, method_name, None)
        if not callable(method):
            continue
        try:
            result = method()
        except Exception:
            continue
        if isinstance(result, Mapping):
            return dict(result)

    asdict_method = getattr(value, "_asdict", None)
    if callable(asdict_method):
        try:
            result = asdict_method()
        except Exception:
            result = None
        if isinstance(result, Mapping):
            return dict(result)

    try:
        raw_attrs = vars(value)
    except TypeError:
        return None

    attrs = {
        key: attr_value
        for key, attr_value in raw_attrs.items()
        if not key.startswith("_") and not callable(attr_value)
    }
    return attrs or None


def _has_model_id(data: Mapping[str, Any]) -> bool:
    return _first_present(data, _MODEL_ID_KEYS) is not None


def _first_present(data: Mapping[str, Any], keys: Iterable[str]) -> Any | None:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _copy_first_present(data: dict[str, Any], target: str, keys: Iterable[str]) -> None:
    existing = data.get(target)
    if existing is not None and str(existing).strip():
        return
    value = _first_present(data, keys)
    if value is not None:
        data[target] = value


__all__ = ["normalize_models", "normalize_metadata"]
