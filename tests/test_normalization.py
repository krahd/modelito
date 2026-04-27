from dataclasses import dataclass
from types import SimpleNamespace

import modelito
from modelito.normalization import normalize_metadata, normalize_models


@dataclass
class ModelInfo:
    id: str
    owned_by: str


def test_normalize_models_accepts_llmr_inline_shapes():
    raw = [
        "gpt-4.1-mini",
        {"model": "claude-3-sonnet", "provider": "anthropic"},
        {"name": "llama3:latest", "size": 123},
    ]

    assert normalize_models(raw) == [
        {"id": "gpt-4.1-mini"},
        {"model": "claude-3-sonnet", "provider": "anthropic", "id": "claude-3-sonnet"},
        {"name": "llama3:latest", "size": 123, "id": "llama3:latest"},
    ]


def test_normalize_models_accepts_wrapped_and_object_responses():
    response = SimpleNamespace(data=[ModelInfo(id="gpt-4o-mini", owned_by="openai")])

    assert normalize_models(response) == [{"id": "gpt-4o-mini", "owned_by": "openai"}]
    assert normalize_models({"models": [{"name": "mistral", "details": {"family": "llama"}}]}) == [
        {"name": "mistral", "details": {"family": "llama"}, "id": "mistral"}
    ]


def test_normalize_models_accepts_mapping_by_model_id():
    raw = {
        "llama3": {"size": 1},
        "gemma": {"name": "gemma:latest", "size": 2},
    }

    assert normalize_models(raw) == [
        {"size": 1, "id": "llama3"},
        {"name": "gemma:latest", "size": 2, "id": "gemma"},
    ]


def test_normalize_metadata_wraps_scalars_and_copies_common_aliases():
    assert normalize_metadata("unavailable") == {"value": "unavailable"}
    assert normalize_metadata({"ctx": 128000, "supports_tools": True}) == {
        "ctx": 128000,
        "supports_tools": True,
        "context_window": 128000,
        "tools": True,
    }


def test_normalize_metadata_accepts_objects_and_nested_metadata():
    raw = SimpleNamespace(model="dummy", metadata=SimpleNamespace(ctx=4096))

    assert normalize_metadata(raw) == {
        "model": "dummy",
        "metadata": {"ctx": 4096, "context_window": 4096},
    }


def test_normalizers_are_exported_at_package_level():
    assert modelito.normalize_models(["x"]) == [{"id": "x"}]
    assert modelito.normalize_metadata(None) == {}
