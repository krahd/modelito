import pytest

from modelito.ollama import OllamaProvider


def _force_offline(monkeypatch):
    monkeypatch.setattr("modelito.ollama.server_is_up", lambda *_args, **_kwargs: False)
    monkeypatch.setattr("modelito.ollama.ollama_installed", lambda: False)


def test_ollama_summarize_dict_message_input_falls_back_to_text(monkeypatch):
    _force_offline(monkeypatch)
    provider = OllamaProvider()

    out = provider.summarize([{"role": "user", "content": "hello"}])

    assert out == "hello"


def test_ollama_summarize_string_message_input_falls_back_to_text(monkeypatch):
    _force_offline(monkeypatch)
    provider = OllamaProvider()

    out = provider.summarize(["hello"])

    assert out == "hello"


def test_ollama_stream_dict_message_input_falls_back_without_raising(monkeypatch):
    _force_offline(monkeypatch)

    def _raise_urlopen(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr("urllib.request.urlopen", _raise_urlopen)
    provider = OllamaProvider()

    chunks = list(provider.stream([{"role": "user", "content": "hello"}]))

    assert "".join(chunks) == "hello"


def test_ollama_invalid_message_type_raises(monkeypatch):
    _force_offline(monkeypatch)
    provider = OllamaProvider()

    with pytest.raises(TypeError):
        provider.summarize([object()])

    with pytest.raises(TypeError):
        list(provider.stream([object()]))
