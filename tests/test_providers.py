from modelito import gemini, grok


def test_gemini_provider_basic():
    p = gemini.GeminiProvider()
    assert isinstance(p.list_models(), list)
    resp = p.summarize([{"role": "user", "content": "hello"}], settings={})
    assert isinstance(resp, str)
    assert "hello" in resp


def test_grok_provider_basic():
    p = grok.GrokProvider()
    assert isinstance(p.list_models(), list)
    resp = p.summarize([{"role": "assistant", "content": "ok"}], settings={})
    assert isinstance(resp, str)
    assert "ok" in resp
