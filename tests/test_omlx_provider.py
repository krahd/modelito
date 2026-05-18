import asyncio
import json

from modelito import OMLXProvider as ExportedOMLXProvider
from modelito.client import Client
from modelito.messages import Message
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
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **
                        _kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    p = OMLXProvider()
    out = p.summarize([Message(role="user", content="hello omlx")])

    assert "hello omlx" in out


def test_omlx_summarize_http_chat_shape(monkeypatch):
    payload = {"choices": [{"message": {"content": "omlx reply"}}]}
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **
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
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **_kwargs: _FakeResponse(lines))

    p = OMLXProvider()
    chunks = list(p.stream([Message(role="user", content="go")]))

    assert chunks == ["hello", " world"]


def test_omlx_list_models_parses_openai_compatible_models(monkeypatch):
    payload = {"data": [{"id": "omlx-1"}, {"id": "omlx-2"}]}
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **
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
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    p = OMLXProvider()
    chunks = list(p.stream([Message(role="user", content="fallback content")]))

    assert "".join(chunks) == "fallback content"


def test_omlx_stream_fallback_chunk_size(monkeypatch):
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    p = OMLXProvider()
    chunks = list(p.stream([Message(role="user", content="abcdefgh")], settings={"chunk_size": 3}))

    assert chunks == ["abc", "def", "gh"]


def test_omlx_embed_http_path(monkeypatch):
    payload = {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **_kwargs: _FakeResponse([json.dumps(payload)]))

    p = OMLXProvider()
    result = p.embed(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_omlx_embed_fallback_when_http_unavailable(monkeypatch):
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    p = OMLXProvider()
    result = p.embed(["hello"])

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], list)
    assert len(result[0]) == 8


def test_omlx_acomplete_returns_text(monkeypatch):
    payload = {"choices": [{"message": {"content": "async reply"}}]}
    monkeypatch.setattr("modelito.omlx.urlopen", lambda *_args, **_kwargs: _FakeResponse([json.dumps(payload)]))

    p = OMLXProvider()
    out = asyncio.run(p.acomplete([Message(role="user", content="hello async")]))

    assert out == "async reply"
