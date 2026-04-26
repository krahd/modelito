from modelito.model_metadata import get_model_metadata

def test_get_model_metadata():
    meta = get_model_metadata("gpt-3.5-turbo")
    assert isinstance(meta, dict)
    assert meta["context_window"] == 4096
    assert meta["functions"] is True
    assert meta["tools"] is True
    # Unknown model returns empty dict
    assert get_model_metadata("unknown-model") == {}
