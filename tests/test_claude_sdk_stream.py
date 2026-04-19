import types

from modelito.claude import ClaudeProvider
from modelito.messages import Message


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
