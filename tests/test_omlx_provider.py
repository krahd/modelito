import asyncio
import json

import pytest

from modelito import OMLXProvider as ExportedOMLXProvider
from modelito.client import Client
from modelito.exceptions import (
    LLMProviderError,
    ModelitoConnectionError,
)
from modelito.messages import Message, Response
from modelito.openai_compat import OpenAICompatibleHTTPProvider
from modelito.omlx import OMLXProvider
from modelito.provider_registry import get_provider, list_providers


class _FakeResponse:
    def __init__(self, lines):
        self._lines = [item if isinstance(item, bytes) else item.encode("utf-8") for item in lines]
        self._idx = 0

    def read(self):
        return b"".join(self._lines)

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


def test_omlx_summarize_fallback_contains_input_when_http_unavailable(monkeypatch):
    monkeypatch.setattr("modelito.openai_compat.urlopen", lambda *_args, **
                        _kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    p = OMLXProvider()
    out = p.summarize([Message(role="user", content="hello omlx")])

    assert "hello omlx" in out


def test_omlx_summarize_http_chat_shape(monkeypatch):
    payload = {"choices": [{"message": {"content": "omlx reply"}}]}
    monkeypatch.setattr("modelito.openai_compat.urlopen", lambda *_args, **
                        _kwargs: _FakeResponse([json.dumps(payload)]))

    p = OMLXProvider(base_url="http://localhost:7777/v1", model="omlx-chat")
    out = p.summarize([Message(role="user", content="ping")])

    assert out == "omlx reply"


def test_omlx_stream_parses_sse_delta_events(monkeypatch):
    lines = [
        "data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}\n",
        "data: {\"choices\":[{\"delta\":{\"content\":\" world\"}}]}\n",
        "data: [DONE]\n",
    ]
    monkeypatch.setattr("modelito.openai_compat.urlopen",
                        lambda *_args, **_kwargs: _FakeResponse(lines))

    p = OMLXProvider()
    chunks = list(p.stream([Message(role="user", content="go")]))

    assert chunks == ["hello", " world"]


def test_omlx_list_models_parses_openai_compatible_models(monkeypatch):
    payload = {"data": [{"id": "omlx-1"}, {"id": "omlx-2"}]}
    monkeypatch.setattr("modelito.openai_compat.urlopen", lambda *_args, **
                        _kwargs: _FakeResponse([json.dumps(payload)]))

    p = OMLXProvider()

    assert p.list_models() == ["omlx-1", "omlx-2"]


def test_provider_registry_and_client_support_omlx_aliases():
    assert "omlx" in list_providers()
    assert get_provider("om") is not None

    client = Client(provider="omlx")
    out = client.summarize([Message(role="user", content="hi")])

    assert "hi" in out


def test_package_root_exports_omlx_provider():
    assert ExportedOMLXProvider is OMLXProvider


def test_omlx_stream_fallback_when_http_unavailable(monkeypatch):
    monkeypatch.setattr("modelito.openai_compat.urlopen", lambda *_args, **
                        _kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    p = OMLXProvider()
    chunks = list(p.stream([Message(role="user", content="fallback content")]))

    assert "".join(chunks) == "fallback content"


def test_omlx_stream_fallback_chunk_size(monkeypatch):
    monkeypatch.setattr("modelito.openai_compat.urlopen", lambda *_args, **
                        _kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    p = OMLXProvider()
    chunks = list(p.stream([Message(role="user", content="abcdefgh")], settings={"chunk_size": 3}))

    assert chunks == ["abc", "def", "gh"]


def test_omlx_embed_http_path(monkeypatch):
    payload = {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
    monkeypatch.setattr("modelito.openai_compat.urlopen", lambda *_args,
                        **_kwargs: _FakeResponse([json.dumps(payload)]))

    p = OMLXProvider()
    result = p.embed(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_omlx_embed_fallback_when_http_unavailable(monkeypatch):
    monkeypatch.setattr("modelito.openai_compat.urlopen", lambda *_args, **
                        _kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    p = OMLXProvider()
    result = p.embed(["hello"])

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], list)
    assert len(result[0]) == 8


def test_omlx_acomplete_returns_text(monkeypatch):
    payload = {"choices": [{"message": {"content": "async reply"}}]}
    monkeypatch.setattr("modelito.openai_compat.urlopen", lambda *_args,
                        **_kwargs: _FakeResponse([json.dumps(payload)]))

    p = OMLXProvider()
    out = asyncio.run(p.acomplete([Message(role="user", content="hello async")]))

    assert out == "async reply"


# ------------------------------------------------------------------
# Strict mode
# ------------------------------------------------------------------


def test_omlx_strict_mode_raises_on_failure(monkeypatch):
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("refused")),
    )
    p = OMLXProvider(strict=True)
    with pytest.raises(LLMProviderError):
        p.summarize([Message(role="user", content="hello")])


def test_omlx_strict_mode_raises_connection_error_for_url_error(monkeypatch):
    import urllib.error

    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            urllib.error.URLError("Connection refused")
        ),
    )
    p = OMLXProvider(strict=True)
    with pytest.raises(ModelitoConnectionError):
        p.summarize([Message(role="user", content="ping")])


def test_omlx_non_strict_mode_falls_back_silently(monkeypatch):
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("refused")),
    )
    p = OMLXProvider(strict=False)
    out = p.summarize([Message(role="user", content="fallback test")])
    assert "fallback test" in out


def test_omlx_strict_stream_raises(monkeypatch):
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("refused")),
    )
    p = OMLXProvider(strict=True)
    with pytest.raises(LLMProviderError):
        list(p.stream([Message(role="user", content="hi")]))


# ------------------------------------------------------------------
# chat() — full Response with metadata
# ------------------------------------------------------------------


def test_omlx_chat_returns_response_with_metadata(monkeypatch):
    payload = {
        "model": "omlx-7b",
        "choices": [
            {"message": {"content": "hello back"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: _FakeResponse([json.dumps(payload)]),
    )
    p = OMLXProvider()
    r = p.chat([Message(role="user", content="hello")])

    assert isinstance(r, Response)
    assert r.text == "hello back"
    assert r.model == "omlx-7b"
    assert r.finish_reason == "stop"
    assert r.tokens_in == 5
    assert r.tokens_out == 3
    assert isinstance(r.raw, dict)


def test_omlx_chat_fallback_returns_response(monkeypatch):
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("down")),
    )
    p = OMLXProvider()
    r = p.chat([Message(role="user", content="offline")])

    assert isinstance(r, Response)
    assert "offline" in r.text
    assert r.model is None
    assert r.finish_reason is None


# ------------------------------------------------------------------
# Dict message support
# ------------------------------------------------------------------


def test_omlx_accepts_dict_messages(monkeypatch):
    payload = {"choices": [{"message": {"content": "dict ok"}}]}
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: _FakeResponse([json.dumps(payload)]),
    )
    p = OMLXProvider()
    out = p.summarize([{"role": "user", "content": "hi from dict"}])
    assert out == "dict ok"


def test_omlx_dict_messages_fallback(monkeypatch):
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("down")),
    )
    p = OMLXProvider()
    out = p.summarize([{"role": "user", "content": "dict fallback"}])
    assert "dict fallback" in out


def test_omlx_rejects_invalid_message_type():
    p = OMLXProvider()
    with pytest.raises(TypeError):
        p.summarize([42])  # type: ignore[list-item]


# ------------------------------------------------------------------
# OpenAICompatibleHTTPProvider base class
# ------------------------------------------------------------------


def test_openai_compat_base_class_is_exported():
    from modelito import OpenAICompatibleHTTPProvider as Exported

    assert Exported is OpenAICompatibleHTTPProvider


def test_omlx_provider_is_subclass_of_base():
    assert issubclass(OMLXProvider, OpenAICompatibleHTTPProvider)


# ------------------------------------------------------------------
# Client.chat_json()
# ------------------------------------------------------------------


def test_client_chat_json_parses_structured_output(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": '{"action": "move", "source": "a.pdf", "confidence": 0.9}'
                },
                "finish_reason": "stop",
            }
        ]
    }
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: _FakeResponse([json.dumps(payload)]),
    )
    client = Client(provider="omlx")
    result = client.chat_json([Message(role="user", content="plan")])

    assert result["action"] == "move"
    assert result["source"] == "a.pdf"
    assert result["confidence"] == pytest.approx(0.9)


def test_client_chat_json_raises_on_non_json_response(monkeypatch):
    payload = {"choices": [{"message": {"content": "not json"}}]}
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: _FakeResponse([json.dumps(payload)]),
    )
    client = Client(provider="omlx")
    with pytest.raises(ValueError, match="valid JSON"):
        client.chat_json([Message(role="user", content="plan")])


def test_client_chat_json_validates_schema(monkeypatch):
    from typing import TypedDict

    class MovePlan(TypedDict):
        action: str
        source: str

    # Missing "source" key
    payload = {"choices": [{"message": {"content": '{"action": "move"}'}}]}
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: _FakeResponse([json.dumps(payload)]),
    )
    client = Client(provider="omlx")
    with pytest.raises(ValueError, match="missing required keys"):
        client.chat_json([Message(role="user", content="plan")], schema=MovePlan)


def test_client_chat_returns_response_object(monkeypatch):
    payload = {
        "model": "omlx-test",
        "choices": [{"message": {"content": "response"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1},
    }
    monkeypatch.setattr(
        "modelito.openai_compat.urlopen",
        lambda *_a, **_kw: _FakeResponse([json.dumps(payload)]),
    )
    client = Client(provider="omlx")
    r = client.chat([Message(role="user", content="hi")])

    assert isinstance(r, Response)
    assert r.text == "response"
    assert r.model == "omlx-test"
