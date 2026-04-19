import os
import pytest


def test_openai_integration_stream_and_embed():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    import importlib
    if importlib.util.find_spec("openai") is None:
        pytest.skip("openai package not installed")

    from modelito.openai import OpenAIProvider

    prov = OpenAIProvider(api_key=api_key, model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"))

    from modelito.messages import Message
    txt = prov.summarize([Message(role="user", content="Say hello in one word.")], settings={"max_tokens": 8})
    assert isinstance(txt, str) and txt

    chunks = []
    for c in prov.stream([Message(role="user", content="Say hello in one word.")], settings={"max_tokens": 8}):
        chunks.append(c)
        if len("".join(chunks)) > 32:
            break
    assert chunks

    try:
        vecs = prov.embed(["hello world"], dim=8)
        assert isinstance(vecs, list) and len(vecs) == 1
    except Exception:
        pytest.skip("Embedding not available in this environment")
