import types

from modelito.claude import ClaudeProvider
from modelito.messages import Message, Response


def test_claude_completions_stream():
    class FakeCompletions:
        def stream(self, model, prompt, **kwargs):
            yield {"choices": [{"delta": {"content": "Hi"}}]}
            yield {"choices": [{"delta": {"content": " there"}}]}

    fake_client = types.SimpleNamespace(completions=FakeCompletions())
    prov = ClaudeProvider(client=fake_client)
    out = "".join(list(prov.stream([Message(role="user", content="hi")])))
    assert out == "Hi there"


def test_claude_completions_create_stream():
    class FakeCompletions:
        def create(self, model, prompt, stream=False, **kwargs):
            if stream:
                yield {"choices": [{"delta": {"content": "A"}}]}
                yield {"choices": [{"delta": {"content": "B"}}]}
            return {"choices": [{"message": {"content": "AB"}}]}

    fake_client = types.SimpleNamespace(completions=FakeCompletions())
    prov = ClaudeProvider(client=fake_client)
    out = "".join(list(prov.stream([Message(role="user", content="hi")])))
    assert out == "AB"


def test_claude_chat_returns_response():
    prov = ClaudeProvider()
    msgs = [Message(role="user", content="hello")]
    resp = prov.chat(msgs)
    assert isinstance(resp, Response)
    assert "hello" in resp.text
    assert resp.model == prov.model


def test_claude_chat_with_sdk_client():
    class FakeCompletions:
        def create(self, model, prompt, **kwargs):
            return {"choices": [{"message": {"content": "sdk reply"}}]}

    fake_client = types.SimpleNamespace(completions=FakeCompletions())
    prov = ClaudeProvider(client=fake_client)
    resp = prov.chat([Message(role="user", content="hi")])
    assert isinstance(resp, Response)
    assert resp.model == prov.model
