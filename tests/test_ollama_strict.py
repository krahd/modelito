import pytest

import modelito
from modelito.exceptions import ModelitoBadResponseError, ModelitoConnectionError
from modelito.ollama_strict import OllamaProvider


def test_package_root_exports_strict_aware_ollama_provider():
    assert modelito.OllamaProvider is OllamaProvider


def test_strict_summarize_uses_raw_completion(monkeypatch):
    provider = OllamaProvider(model="local-model", strict=True)
    seen = {}

    def raw_complete(payload):
        seen.update(payload)
        return {"choices": [{"message": {"content": "respuesta local"}}]}

    monkeypatch.setattr(provider, "raw_complete", raw_complete)

    result = provider.summarize([{"role": "user", "content": "hola"}])

    assert result == "respuesta local"
    assert seen["messages"] == [{"role": "user", "content": "hola"}]


def test_strict_summarize_propagates_runtime_failure(monkeypatch):
    provider = OllamaProvider(model="local-model", strict=True)

    def fail(_payload):
        raise ModelitoConnectionError("Ollama disappeared")

    monkeypatch.setattr(provider, "raw_complete", fail)

    with pytest.raises(ModelitoConnectionError, match="Ollama disappeared"):
        provider.summarize([{"role": "user", "content": "hola"}])


def test_strict_summarize_rejects_non_text_completion(monkeypatch):
    provider = OllamaProvider(model="local-model", strict=True)
    monkeypatch.setattr(
        provider,
        "raw_complete",
        lambda _payload: {"choices": [{"message": {"content": None}}]},
    )

    with pytest.raises(ModelitoBadResponseError, match="no textual completion"):
        provider.summarize([{"role": "user", "content": "hola"}])


def test_strict_stream_propagates_runtime_failure(monkeypatch):
    provider = OllamaProvider(model="local-model", strict=True)

    def fail(_payload):
        raise ModelitoConnectionError("stream failed")
        yield  # pragma: no cover

    monkeypatch.setattr(provider, "raw_stream", fail)

    with pytest.raises(ModelitoConnectionError, match="stream failed"):
        list(provider.stream([{"role": "user", "content": "hola"}]))


def test_strict_stream_yields_only_text(monkeypatch):
    provider = OllamaProvider(model="local-model", strict=True)

    def events(_payload):
        yield {"choices": [{"delta": {"role": "assistant"}}]}
        yield {"choices": [{"delta": {"content": "Buen"}}]}
        yield {"choices": [{"delta": {"content": " día"}}]}
        yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}

    monkeypatch.setattr(provider, "raw_stream", events)

    assert list(provider.stream([{"role": "user", "content": "hola"}])) == [
        "Buen",
        " día",
    ]


def test_non_strict_summarize_preserves_legacy_fallback(monkeypatch):
    provider = OllamaProvider(model="local-model", strict=False)
    monkeypatch.setattr("modelito.ollama.server_is_up", lambda *_args: False)
    monkeypatch.setattr("modelito.ollama.ollama_installed", lambda: False)

    assert provider.summarize([{"role": "user", "content": "sin servidor"}]) == (
        "sin servidor"
    )
