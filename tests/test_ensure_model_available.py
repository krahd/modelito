from modelito.ollama_service import ensure_model_available


def test_ensure_model_available_no_download():
    # Use a likely-nonexistent model name; without allow_download this should be False
    assert ensure_model_available("__definitely_not_a_real_model__", allow_download=False) is False
