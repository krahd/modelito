import subprocess

import pytest

from modelito.ollama_api import api_generate, api_version, api_ps, api_pull, api_tags


def test_api_generate_nonstream_fallback(monkeypatch):
    # Force HTTP unavailability to trigger deterministic fallback
    monkeypatch.setattr("modelito.ollama_service.server_is_up", lambda *_a, **_k: False)

    out = api_generate(["hello", "world"], stream=False)
    assert out == "hello\nworld"


def test_api_generate_stream_fallback(monkeypatch):
    monkeypatch.setattr("modelito.ollama_service.server_is_up", lambda *_a, **_k: False)

    gen = api_generate(["hello", "world"], stream=True)
    parts = list(gen)
    assert parts == ["hello\nworld"]


def test_api_version_cli_fallback(monkeypatch):
    # Force HTTP down and emulate CLI --version
    monkeypatch.setattr("modelito.ollama_service.server_is_up", lambda *_a, **_k: False)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ollama 0.9.0\n", stderr="")

    monkeypatch.setattr("modelito.ollama_service.run_ollama_command", fake_run)
    v = api_version()
    assert "ollama" in v


def test_api_ps_cli_fallback(monkeypatch):
    monkeypatch.setattr("modelito.ollama_service.server_is_up", lambda *_a, **_k: False)
    monkeypatch.setattr("modelito.ollama_service.running_model_names",
                        lambda *_a, **_k: ["m1", "m2"])
    ps = api_ps()
    assert ps == ["m1", "m2"]


def test_api_pull_cli_fallback(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("modelito.ollama_service.run_ollama_command", fake_run)
    ok = api_pull("some-model")
    assert ok is True


def test_api_tags_http(monkeypatch):
    # Emulate HTTP tags endpoint returning a list
    monkeypatch.setattr("modelito.ollama_service.server_is_up", lambda *_a, **_k: True)
    monkeypatch.setattr("modelito.ollama_service.json_get",
                        lambda url, timeout=3.0: ["tag1", "tag2"])
    tags = api_tags()
    assert tags == ["tag1", "tag2"]
