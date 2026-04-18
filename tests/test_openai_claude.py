from modelito.openai import OpenAIProvider
from modelito.claude import ClaudeProvider


def test_openai_provider_basic():
    p = OpenAIProvider()
    assert isinstance(p.list_models(), list)
    resp = p.summarize([{"role": "user", "content": "hello"}], settings={})
    assert isinstance(resp, str)
    assert "hello" in resp


def test_claude_provider_basic():
    p = ClaudeProvider()
    assert isinstance(p.list_models(), list)
    resp = p.summarize([{"role": "assistant", "content": "ok"}], settings={})
    assert isinstance(resp, str)
    assert "ok" in resp
