from modelito import timeout


def test_timeout_estimator_basic():
    t = timeout.estimate_remote_timeout("llama3.2:latest", input_tokens=512, concurrency=1)
    assert isinstance(t, int)
    t2 = timeout.estimate_remote_timeout("smollm_v1", input_tokens=256, concurrency=1)
    assert isinstance(t2, int)
    # smollm is expected to be smaller multiplier than llama
    assert t2 <= t
