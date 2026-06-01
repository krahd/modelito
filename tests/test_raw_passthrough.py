import json
import pytest

from modelito import OMLXProvider as ExportedOMLXProvider, RawChatProvider
from modelito.exceptions import ModelitoProviderError
from modelito.openai import OpenAIProvider
from modelito.openai_compat import OpenAICompatibleHTTPProvider
from modelito.omlx import OMLXProvider


class _FakeResponse:
    def __init__(self, lines):
        self._lines = [
            item if isinstance(item, bytes) else item.encode("utf-8") for item in lines
        ]
        self._idx = 0

    def read(self):
        return b"".join(self._lines)

    def __iter__(self):
        return iter(self._lines)

    def readline(self):
        if self._idx >= len(self._lines):
            return b""
        item = self._lines[self._idx]
        self._idx += 1
        return item

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_raw_chat_provider_is_exported_and_runtime_checkable():
    class FakeRawProvider:
        def raw_complete(self, payload):
            return payload

        def raw_stream(self, payload):
            yield payload

    assert isinstance(FakeRawProvider(), RawChatProvider)


def test_openai_compatible_raw_complete_preserves_payload(monkeypatch):
    captured = {}
    payload = {
        "messages": [{"role": "user", "content": "call tool"}],
        "tools": [{"type": "function", "function": {"name": "lookup"}}],
        "tool_choice": "auto",
        "response_format": {"type": "json_object"},
        "unknown_field": "preserve-me",
    }
    response_payload = {
        "id": "chatcmpl-raw-1",
        "object": "chat.completion",
        "created": 0,
        "model": "omlx",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "lookup", "arguments": "{}"},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }

    def fake_urlopen(req, timeout=0):
        captured["request"] = req
        return _FakeResponse([json.dumps(response_payload)])

    monkeypatch.setattr("modelito.openai_compat.urlopen", fake_urlopen)

    provider = OpenAICompatibleHTTPProvider(
        base_url="http://example.test/v1", model="omlx", strict=True
    )
    raw = provider.raw_complete(payload)

    sent_payload = json.loads(captured["request"].data.decode("utf-8"))
    assert sent_payload["model"] == "omlx"
    assert sent_payload["tools"][0]["function"]["name"] == "lookup"
    assert sent_payload["tool_choice"] == "auto"
    assert sent_payload["response_format"] == {"type": "json_object"}
    assert sent_payload["unknown_field"] == "preserve-me"
    assert raw == response_payload


def test_openai_compatible_raw_stream_preserves_chunks(monkeypatch):
    captured = {}
    payload = {
        "messages": [{"role": "user", "content": "call tool"}],
        "tools": [{"type": "function", "function": {"name": "lookup"}}],
    }
    lines = [
        'data: {"id":"chunk-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}'
        + "\n",
        'data: {"id":"chunk-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"tool_calls":[{"id":"call_1","type":"function","function":{"name":"lookup","arguments":"{}"}}]},"finish_reason":null}]}'
        + "\n",
        'data: {"id":"chunk-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"done"},"finish_reason":null}]}'
        + "\n",
        "data: [DONE]\n",
    ]

    def fake_urlopen(req, timeout=0):
        captured["request"] = req
        return _FakeResponse(lines)

    monkeypatch.setattr("modelito.openai_compat.urlopen", fake_urlopen)

    provider = OpenAICompatibleHTTPProvider(
        base_url="http://example.test/v1", model="omlx", strict=True
    )
    events = list(provider.raw_stream(payload))

    sent_payload = json.loads(captured["request"].data.decode("utf-8"))
    assert sent_payload["stream"] is True
    assert sent_payload["model"] == "omlx"
    assert (
        events[1]["choices"][0]["delta"]["tool_calls"][0]["function"]["name"]
        == "lookup"
    )
    assert events[2]["choices"][0]["delta"]["content"] == "done"


def test_omlx_inherits_raw_passthrough(monkeypatch):
    assert hasattr(OMLXProvider, "raw_complete")
    assert hasattr(OMLXProvider, "raw_stream")
    assert OMLXProvider.raw_complete is OpenAICompatibleHTTPProvider.raw_complete
    assert OMLXProvider.raw_stream is OpenAICompatibleHTTPProvider.raw_stream
    assert isinstance(OMLXProvider(), RawChatProvider)
    assert ExportedOMLXProvider is OMLXProvider


def test_openai_provider_accepts_dict_messages_and_raw_tool_calls():
    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return {
                        "id": "chatcmpl-openai-1",
                        "object": "chat.completion",
                        "created": 0,
                        "model": kwargs["model"],
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "tool_call_1",
                                            "type": "function",
                                            "function": {
                                                "name": "lookup",
                                                "arguments": "{}",
                                            },
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                    }

    provider = OpenAIProvider(client=FakeClient(), model="gpt-test", strict=True)
    assert "hello" in provider.summarize([{"role": "user", "content": "hello"}])

    raw = provider.raw_complete(
        {
            "messages": [{"role": "user", "content": "call tool"}],
            "tools": [{"type": "function", "function": {"name": "lookup"}}],
            "tool_choice": "auto",
        }
    )

    assert raw["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "lookup"


def test_openai_provider_raw_stream_with_create_receives_stream_payload():
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
                                "delta": {"content": "hello"},
                                "finish_reason": None,
                            }
                        ],
                    }
                ]
            )

    class FakeClient:
        class chat:
            completions = FakeCompletions()

    provider = OpenAIProvider(client=FakeClient(), model="gpt-test", strict=True)
    chunks = list(
        provider.raw_stream(
            {
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 0.2,
            }
        )
    )

    assert captured["kwargs"]["stream"] is True
    assert captured["kwargs"]["temperature"] == 0.2
    assert chunks[0]["choices"][0]["delta"]["content"] == "hello"


def test_openai_provider_raw_stream_strict_mode_wraps_errors():
    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("boom")

    class FakeClient:
        class chat:
            completions = FakeCompletions()

    provider = OpenAIProvider(client=FakeClient(), model="gpt-test", strict=True)
    with pytest.raises(ModelitoProviderError):
        list(provider.raw_stream({"messages": [{"role": "user", "content": "hello"}]}))
