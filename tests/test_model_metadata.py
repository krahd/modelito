from modelito.model_metadata import get_model_info, get_model_metadata


def test_get_model_metadata_unknown_returns_empty_dict():
    assert get_model_metadata("unknown-model") == {}


def test_get_model_metadata_known_openai_entry_has_expected_fields():
    meta = get_model_metadata("gpt-4o-mini")
    assert isinstance(meta, dict)
    assert meta["provider"] == "openai"
    assert meta["supports_tools"] is True
    assert meta["supports_streaming"] is True
    assert meta["tools"] is True
    assert meta["functions"] is True


def test_get_model_info_known_claude_entry_exists():
    info = get_model_info("claude-3-5-sonnet-latest", infer=False)
    assert info is not None
    assert info.provider == "anthropic"
    assert info.supports_streaming is True


def test_get_model_info_known_gemini_entry_exists():
    info = get_model_info("gemini-1.5-pro", infer=False)
    assert info is not None
    assert info.provider == "google"
    assert info.supports_streaming is True


def test_infer_claude_provider_for_unknown_claude_model():
    meta = get_model_metadata("claude-something-new", infer=True)
    assert meta["provider"] == "anthropic"
    assert meta["supports_streaming"] is True


def test_infer_gemini_provider_for_unknown_gemini_model():
    meta = get_model_metadata("gemini-something-new", infer=True)
    assert meta["provider"] == "google"
    assert meta["supports_streaming"] is True


def test_unknown_context_window_remains_none_for_inferred_model():
    meta = get_model_metadata("claude-something-new", infer=True)
    assert meta["context_window"] is None


def test_backward_compatible_dict_return_shape_contains_legacy_aliases():
    meta = get_model_metadata("gpt-4o-mini")
    assert "tools" in meta
    assert "functions" in meta


def test_infer_openai_reasoning_o_models():
    assert get_model_metadata("o1", infer=True)["provider"] == "openai"
    assert get_model_metadata("o3-mini", infer=True)["provider"] == "openai"
    assert get_model_metadata("o4-mini", infer=True)["provider"] == "openai"


def test_infer_does_not_map_arbitrary_o_names_to_openai():
    assert get_model_metadata("orca-mini", infer=True) == {}
    assert get_model_metadata("openhermes", infer=True) == {}
    assert get_model_metadata("ollama-local", infer=True) == {}


def test_root_exports_include_model_metadata_helpers():
    from modelito import ModelMetadata, get_model_metadata, infer_model_metadata

    assert get_model_metadata("gpt-4o-mini")["provider"] == "openai"
    inferred = infer_model_metadata("o3-mini")
    assert isinstance(inferred, ModelMetadata)
    assert inferred.provider == "openai"
