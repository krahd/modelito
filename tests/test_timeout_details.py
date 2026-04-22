from modelito.timeout import estimate_remote_timeout_details


def test_timeout_details_structure():
    timeout, details = estimate_remote_timeout_details(
        "llama-2-13b", input_tokens=1000, concurrency=2)
    assert isinstance(timeout, int)
    assert isinstance(details, dict)
    assert details.get("base_timeout") is not None
    assert details.get("estimated_timeout") == timeout
