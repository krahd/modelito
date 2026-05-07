import json

from modelito.ollama_api import (
    api_health_envelope,
    api_list_local_envelope,
    api_ensure_model_loaded_envelope,
)
from modelito.ollama_service import ensure_model_loaded, json_get
from modelito.plumbing import TransportPolicy


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_json_get_retries_on_transient_network_error(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(url, timeout=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("first timeout")
        return _FakeResponse({"ok": True})

    monkeypatch.setattr("modelito.ollama_service.urlopen", fake_urlopen)

    payload = json_get(
        "http://127.0.0.1:11434/api/version",
        timeout=0.1,
        policy=TransportPolicy(timeout=0.1, max_attempts=2, base_delay=0.0, max_delay=0.0),
    )

    assert payload["ok"] is True
    assert calls["n"] == 2


def test_ensure_model_loaded_is_alias_for_ready(monkeypatch):
    monkeypatch.setattr("modelito.ollama_service.ensure_model_ready", lambda *args, **kwargs: True)
    assert ensure_model_loaded("llama3.1:8b") is True


def test_api_health_envelope_success(monkeypatch):
    monkeypatch.setattr("modelito.ollama_api.api_health", lambda **kwargs: {"ready": True})
    env = api_health_envelope()
    assert env.ok is True
    assert env.data == {"ready": True}


def test_api_list_local_envelope_normalizes_error(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("socket down")

    monkeypatch.setattr("modelito.ollama_api.api_list_local", boom)
    env = api_list_local_envelope()
    assert env.ok is False
    assert env.error is not None
    assert env.error.code in {"network_os_error", "connection_error", "network_unknown"}


def test_api_ensure_model_loaded_envelope(monkeypatch):
    monkeypatch.setattr("modelito.ollama_api.api_ensure_model_loaded", lambda **kwargs: True)
    env = api_ensure_model_loaded_envelope("llama3.1:8b")
    assert env.ok is True
    assert env.data is True
