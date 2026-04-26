from modelito.streaming import collect_stream
from modelito.openai import OpenAIProvider
from modelito.mock_provider import MockProvider
from modelito.messages import Message

class DummyStreamingProvider:
    def stream(self, messages, settings=None):
        # simulate chunked output
        yield "Hello"
        yield " "
        yield "world"


def test_collect_stream_from_provider():
    prov = DummyStreamingProvider()
    chunks = prov.stream([])
    text = collect_stream(chunks)
    assert text == "Hello world"


def test_openai_stream_fallback(monkeypatch):
    # Simulate OpenAIProvider with no SDK, fallback to chunked output
    p = OpenAIProvider(client=None)
    out = list(p.stream([Message(role="user", content="stream test")]))
    assert any("stream test" in chunk for chunk in out)


def test_mockprovider_stream():
    p = MockProvider()
    msgs = [Message(role="user", content="streaming test")]
    chunks = list(p.stream(msgs))
    assert "[MOCK]" in "".join(chunks)
