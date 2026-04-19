import types

from modelito.openai import OpenAIProvider


def test_stream_with_chat_completions_stream():
    class FakeCompletions:
        def stream(self, model, messages, **kwargs):
            yield {"choices": [{"delta": {"content": "Hello"}}]}
            yield {"choices": [{"delta": {"content": " "}}]}
            yield {"choices": [{"delta": {"content": "world"}}]}

    fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=FakeCompletions()))
    prov = OpenAIProvider(client=fake_client)
    out = "".join(list(prov.stream([{"role": "user", "content": "hi"}])))
    assert out == "Hello world"


def test_stream_with_chat_completions_create_stream():
    class FakeCompletions:
        def create(self, model, messages, stream=False, **kwargs):
            if stream:
                yield {"choices": [{"delta": {"content": "A"}}]}
                yield {"choices": [{"delta": {"content": "B"}}]}
            return {"choices": [{"message": {"content": "AB"}}]}

    fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=FakeCompletions()))
    prov = OpenAIProvider(client=fake_client)
    out = "".join(list(prov.stream([{"role": "user", "content": "hi"}])))
    assert out == "AB"


def test_stream_with_responses_stream_shape():
    class FakeResponses:
        def stream(self, model, input, **kwargs):
            yield {"text": "X"}
            yield {"text": "Y"}

    fake_client = types.SimpleNamespace(responses=FakeResponses())
    prov = OpenAIProvider(client=fake_client)
    out = "".join(list(prov.stream([])))
    assert out == "XY"
