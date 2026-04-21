from modelito import timeout


def test_timeout_estimator_basic():
    t = timeout.estimate_remote_timeout("llama3.2:latest", input_tokens=512, concurrency=1)
    assert isinstance(t, int)
    t2 = timeout.estimate_remote_timeout("smollm_v1", input_tokens=256, concurrency=1)
    assert isinstance(t2, int)
    # smollm is expected to be smaller multiplier than llama
    assert t2 <= t


def test_timeout_with_source():
    # Ensure we can request source details and that model overrides are respected
    t, src = timeout.estimate_remote_timeout("llama-2-70b", input_tokens=1000, concurrency=1, with_source=True)
    assert isinstance(t, int)
    assert isinstance(src, dict)
    # The bundled catalog contains a model override for llama-2-70b -> 3.2
    assert src.get("matched_model_override") == 3.2
    # base band for 1000 tokens is the 2048 band (timeout_seconds 30)
    assert src.get("base_timeout") == 30
    assert t == int(30 * 3.2)
