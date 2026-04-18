from modelito.ollama_service import ensure_ollama_running_verbose


def test_ensure_ollama_running_verbose_no_server():
    # Pick a port that is very unlikely to be used during tests
    ok, msg = ensure_ollama_running_verbose('http://127.0.0.1', 65000, auto_start=False)
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    assert not ok
