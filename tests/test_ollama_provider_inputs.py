import json

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


def test_ollama_summarize_preserves_roles_and_applies_settings(monkeypatch):
    monkeypatch.setattr("modelito.ollama.server_is_up", lambda *_args: True)
    captured = {}

    def fake_json_post(url, payload, timeout):
        captured.update({"url": url, "payload": payload, "timeout": timeout})
        return {"message": {"role": "assistant", "content": "summary"}}

    monkeypatch.setattr("modelito.ollama.json_post", fake_json_post)
    provider = OllamaProvider(model="llama3.2")
    messages = [
        {"role": "system", "content": "Keep this instruction."},
        {"role": "user", "content": "Summarise this."},
    ]

    out = provider.summarize(
        messages,
        settings={
            "temperature": 0,
            "seed": 7,
            "num_predict": 64,
            "options": {"top_p": 0.8},
            "keep_alive": "10m",
            "truncate": True,
            "timeout": 1,
            "future_setting": "must not be guessed",
        },
    )

    assert out == "summary"
    assert captured["payload"] == {
        "stream": False,
        "model": "llama3.2",
        "messages": messages,
        "keep_alive": "10m",
        "truncate": True,
        "options": {
            "top_p": 0.8,
            "temperature": 0,
            "seed": 7,
            "num_predict": 64,
        },
    }
    assert "timeout" not in captured["payload"]
    assert "future_setting" not in captured["payload"]
    assert "timeout" not in captured["payload"]["options"]
    assert "future_setting" not in captured["payload"]["options"]


def test_ollama_summarize_maps_common_json_and_token_settings(monkeypatch):
    monkeypatch.setattr("modelito.ollama.server_is_up", lambda *_args: True)
    captured_payload = {}

    def fake_json_post(_url, payload, timeout):
        captured_payload.update(payload)
        return {"message": {"content": "{}"}}

    monkeypatch.setattr("modelito.ollama.json_post", fake_json_post)

    out = OllamaProvider(model="llama3.2").summarize(
        [{"role": "user", "content": "Return JSON."}],
        settings={
            "max_tokens": 32,
            "response_format": {"type": "json_object"},
        },
    )

    assert out == "{}"
    assert captured_payload["format"] == "json"
    assert captured_payload["options"]["num_predict"] == 32


def test_ollama_stream_dict_message_input_falls_back_without_raising(monkeypatch):
    _force_offline(monkeypatch)

    def _raise_urlopen(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr("urllib.request.urlopen", _raise_urlopen)
    provider = OllamaProvider()

    chunks = list(provider.stream([{"role": "user", "content": "hello"}]))

    assert "".join(chunks) == "hello"


def test_ollama_stream_applies_settings_to_native_options(monkeypatch):
    captured_payload = {}

    class FakeResponse:
        def __init__(self):
            self.lines = iter(
                [b'{"message":{"content":"done"},"done":false}\n', b""]
            )

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def readline(self):
            return next(self.lines)

    def fake_urlopen(request, timeout):
        captured_payload.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaProvider(model="llama3.2")

    chunks = list(
        provider.stream(
            [{"role": "system", "content": "Be brief."}],
            settings={"temperature": 0, "seed": 9, "num_predict": 12},
        )
    )

    assert chunks == ["done"]
    assert captured_payload["stream"] is True
    assert captured_payload["messages"] == [
        {"role": "system", "content": "Be brief."}
    ]
    assert captured_payload["options"] == {
        "temperature": 0,
        "seed": 9,
        "num_predict": 12,
    }


def test_ollama_invalid_message_type_raises(monkeypatch):
    _force_offline(monkeypatch)
    provider = OllamaProvider()

    with pytest.raises(TypeError):
        provider.summarize([object()])

    with pytest.raises(TypeError):
        list(provider.stream([object()]))
