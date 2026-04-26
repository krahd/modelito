from modelito.mock_provider import MockProvider
from modelito.messages import Message

def test_mockprovider_summarize():
    provider = MockProvider()
    msgs = [Message(role="user", content="hello"), Message(role="assistant", content="world")]
    out = provider.summarize(msgs)
    assert out.startswith("[MOCK]")
    assert "hello" in out and "world" in out

def test_mockprovider_stream():
    provider = MockProvider()
    msgs = [Message(role="user", content="streaming test")]
    chunks = list(provider.stream(msgs))
    assert all(isinstance(c, str) for c in chunks)
    assert "[MOCK]" in "".join(chunks)

def test_mockprovider_embed():
    provider = MockProvider()
    texts = ["foo", "barbaz"]
    embs = provider.embed(texts)
    assert isinstance(embs, list)
    assert all(isinstance(vec, list) for vec in embs)
    assert all(len(vec) == 8 for vec in embs)
