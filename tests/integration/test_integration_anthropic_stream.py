import os
import pytest


def test_anthropic_integration_basic():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    import importlib
    if importlib.util.find_spec("anthropic") is None:
        pytest.skip("anthropic package not installed")

    from modelito.claude import ClaudeProvider
    from modelito.messages import Message

    prov = ClaudeProvider(api_key=api_key)

    txt = prov.summarize([Message(role="user", content="Say hello in one word.")], settings={})
    assert isinstance(txt, str) and txt
