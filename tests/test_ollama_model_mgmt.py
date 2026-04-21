import subprocess

import pytest

from modelito.ollama_api import api_list_local, api_list_remote, api_delete_model, api_pull_stream


def test_api_list_local(monkeypatch):
    monkeypatch.setattr("modelito.ollama_service.list_local_models", lambda: ["a", "b"])
    res = api_list_local()
    assert res == ["a", "b"]


def test_api_list_remote(monkeypatch):
    monkeypatch.setattr("modelito.ollama_service.list_remote_models", lambda: ["r1", "r2"])
    res = api_list_remote()
    assert res == ["r1", "r2"]


def test_api_delete_model(monkeypatch):
    monkeypatch.setattr("modelito.ollama_service.delete_model", lambda m: True)
    assert api_delete_model("foo") is True


def test_api_pull_stream(monkeypatch):
    # Patch the adapter's download_stream to yield sample lines
    from modelito.adapter import OllamaHTTPClient

    def fake_stream(self, model, timeout=600.0):
        yield "progress 10%"
        yield "progress 50%"
        yield "done"

    monkeypatch.setattr(OllamaHTTPClient, "download_stream", fake_stream)

    parts = list(api_pull_stream("some-model"))
    assert parts == ["progress 10%", "progress 50%", "done"]
