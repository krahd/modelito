import subprocess

import pytest

from modelito.adapter import get_client
from modelito.messages import Message


def test_client_basic_methods_exist():
    c = get_client()
    assert hasattr(c, "version")
    assert hasattr(c, "ps")
    assert hasattr(c, "pull")
    assert hasattr(c, "generate")


def test_generate_fallback_chunks(monkeypatch):
    # Ensure server_is_up reports False so we exercise the deterministic fallback
    monkeypatch.setattr("modelito.ollama_service.server_is_up", lambda *_a, **_k: False)

    c = get_client()
    messages = ["hello", "world"]
    parts = list(c.generate(messages, stream=True))
    # The fallback flattens with a newline; chunk size is 64 so expect single chunk
    assert parts == ["hello\nworld"]


def test_pull_uses_cli(monkeypatch):
    called = {}

    def fake_run(*args, **kwargs):
        called['args'] = args
        # emulate subprocess.CompletedProcess
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("modelito.ollama_service.run_ollama_command", fake_run)

    c = get_client()
    assert c.pull("some-model") is True
    assert 'args' in called
