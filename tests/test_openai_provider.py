from types import SimpleNamespace

import pytest

from modelito.exceptions import ModelitoProviderError
from modelito.messages import Response
from modelito.openai import OpenAIProvider


def test_openai_provider_chat_returns_response_metadata():
    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": "gpt-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello back"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    provider = OpenAIProvider(client=fake_client, model="gpt-test", strict=True)

    result = provider.chat([{"role": "user", "content": "hello"}])

    assert isinstance(result, Response)
    assert result.text == "hello back"
    assert isinstance(result.raw, dict)
    assert result.model == "gpt-test"
    assert result.finish_reason == "stop"
    assert result.tokens_in == 11
    assert result.tokens_out == 7


def test_openai_provider_raw_complete_strict_wraps_errors():
    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("boom")

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    provider = OpenAIProvider(client=fake_client, model="gpt-test", strict=True)

    with pytest.raises(ModelitoProviderError):
        provider.raw_complete({"messages": [{"role": "user", "content": "hello"}]})


def test_openai_provider_raw_stream_strict_wraps_errors():
    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("boom")

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    provider = OpenAIProvider(client=fake_client, model="gpt-test", strict=True)

    with pytest.raises(ModelitoProviderError):
        list(provider.raw_stream({"messages": [{"role": "user", "content": "hello"}]}))


def test_openai_provider_raw_complete_non_strict_returns_fallback():
    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("boom")

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    provider = OpenAIProvider(client=fake_client, model="gpt-test", strict=False)

    result = provider.raw_complete({"messages": [{"role": "user", "content": "hello"}]})

    assert result["object"] == "chat.completion"
    assert result["choices"][0]["message"]["content"] == "hello"
    assert result["model"] == "gpt-test"


def test_openai_provider_raw_complete_non_strict_fallback_does_not_call_summarize():
    class FakeCompletions:
        create_calls = 0

        @staticmethod
        def create(**kwargs):
            FakeCompletions.create_calls += 1
            raise RuntimeError("boom")

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    provider = OpenAIProvider(client=fake_client, model="gpt-test", strict=False)
    provider.summarize = lambda *_args, **_kwargs: (_ for _ in ()
                                                    ).throw(AssertionError("summarize should not be called"))

    result = provider.raw_complete(
        {
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"type": "function", "function": {"name": "lookup"}}],
        }
    )

    assert FakeCompletions.create_calls == 1
    assert result["choices"][0]["message"]["content"] == "hello"


def test_openai_provider_raw_stream_with_create_stream_true_payload():
    captured = {}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            captured["kwargs"] = dict(kwargs)
            return iter(
                [
                    {
                        "id": "chunk-1",
                        "object": "chat.completion.chunk",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": "alpha"},
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chunk-1",
                        "object": "chat.completion.chunk",
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    },
                ]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    provider = OpenAIProvider(client=fake_client, model="gpt-test", strict=True)

    chunks = list(provider.raw_stream({"messages": [{"role": "user", "content": "hello"}]}))

    assert captured["kwargs"]["stream"] is True
    assert chunks[0]["choices"][0]["delta"]["content"] == "alpha"
