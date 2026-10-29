import io
import json
from urllib.error import URLError

import pytest

import modelito
from modelito.exceptions import (
    ModelitoBadResponseError,
    ModelitoConnectionError,
    ModelitoProviderError,
)
from modelito.ollama import OllamaProvider as BaseOllamaProvider
from modelito.ollama_strict import OllamaProvider


def test_package_root_exports_strict_aware_ollama_provider():
    assert modelito.OllamaProvider is OllamaProvider


@pytest.mark.parametrize("provider_class", [BaseOllamaProvider, OllamaProvider])
def test_default_summary_preserves_roles_settings_unicode(monkeypatch, provider_class):
    messages = [
        {"role": "system", "content": "Respondé en español."},
        {"role": "user", "content": "¿Cómo estás?"},
        {"role": "assistant", "content": "Bien, gracias."},
        {"role": "user", "content": "Resumí la conversación."},
    ]

    def post(url, payload, timeout, **kwargs):
        assert url.endswith("/api/chat")
        assert payload == {
            "model": "local-model",
            "stream": False,
            "messages": messages,
            "options": {"temperature": 0, "num_ctx": 8192},
        }
        assert timeout == 7
        return {
            "model": "local-model:latest",
            "done": True,
            "message": {"content": "Conversación en español: áéíóú ñ."},
        }

    monkeypatch.setattr("modelito.ollama.json_post", post)
    assert (
        provider_class(model="local-model", timeout=7).summarize(
            iter(messages), settings={"temperature": 0, "num_ctx": 8192, "stream": True}
        )
        == "Conversación en español: áéíóú ñ."
    )


@pytest.mark.parametrize("response", [{}, [], {"message": {"content": None}}])
def test_summary_rejects_invalid_response(monkeypatch, response):
    monkeypatch.setattr("modelito.ollama.json_post", lambda *a, **kw: response)
    with pytest.raises(ModelitoBadResponseError):
        OllamaProvider(model="local-model").summarize(["hola"])


def test_empty_summary_is_valid(monkeypatch):
    monkeypatch.setattr(
        "modelito.ollama.json_post",
        lambda *a, **kw: {"done": True, "message": {"content": ""}},
    )
    assert OllamaProvider().summarize(["hola"]) == ""


def test_default_summary_propagates_failure_without_cli(monkeypatch):
    def fail(*a, **kw):
        raise URLError("connection refused")

    monkeypatch.setattr("modelito.ollama.json_post", fail)
    monkeypatch.setattr(
        "modelito.ollama.ollama_installed", lambda: pytest.fail("must not use CLI")
    )
    with pytest.raises(ModelitoConnectionError, match="connection refused"):
        OllamaProvider().summarize(["hola"])


def test_default_stream_preserves_native_settings(monkeypatch):
    def open_stream(request, timeout):
        payload = json.loads(request.data)
        assert payload["stream"] is True
        assert payload["options"] == {"temperature": 0, "num_ctx": 8192}
        assert payload["messages"] == [{"role": "system", "content": "Español"}]
        assert timeout == 7
        return io.BytesIO(
            (
                "\n".join(
                    json.dumps(x)
                    for x in [
                        {"message": {"content": "Buen día ñ"}},
                        {"message": {"content": ""}, "done": True},
                    ]
                )
                + "\n"
            ).encode("utf-8")
        )

    monkeypatch.setattr("modelito.ollama.urlopen", open_stream)
    assert list(
        OllamaProvider(timeout=7).stream(
            [{"role": "system", "content": "Español"}],
            settings={"temperature": 0, "num_ctx": 8192},
        )
    ) == ["Buen día ñ"]


@pytest.mark.parametrize(
    "body,error",
    [
        (b"not json\n", ModelitoBadResponseError),
        (b"[]\n", ModelitoBadResponseError),
        (b'{"error":"model missing"}\n', ModelitoProviderError),
        (b'{"message":{"content":"partial"}}\n', ModelitoBadResponseError),
        (b"", ModelitoBadResponseError),
    ],
)
def test_default_stream_raises_without_replaying(monkeypatch, body, error):
    monkeypatch.setattr("modelito.ollama.urlopen", lambda *a, **kw: io.BytesIO(body))
    provider = OllamaProvider()
    monkeypatch.setattr(
        provider, "summarize", lambda *a, **kw: pytest.fail("must not replay")
    )
    with pytest.raises(error):
        list(provider.stream(["hola"]))


def test_default_stream_connection_failure(monkeypatch):
    def fail(*a, **kw):
        raise URLError("offline")

    monkeypatch.setattr("modelito.ollama.urlopen", fail)
    with pytest.raises(ModelitoConnectionError):
        list(OllamaProvider().stream(["hola"]))


def test_explicit_offline_fallback_warns(monkeypatch):
    monkeypatch.setattr("modelito.ollama.server_is_up", lambda *a: False)
    monkeypatch.setattr("modelito.ollama.ollama_installed", lambda: False)
    with pytest.warns(RuntimeWarning, match="not be model output"):
        assert (
            OllamaProvider(strict=False).summarize(["sin servidor"]) == "sin servidor"
        )
