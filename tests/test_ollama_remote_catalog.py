"""Remote discovery uses the public library, independently of local Ollama."""

import io
from urllib.error import URLError

import pytest

from modelito import ollama_service as svc
from modelito.adapter import get_client
from modelito.errors import ProviderError
from modelito.ollama_api import api_list_remote, api_list_remote_envelope

LIBRARY = b"""<!doctype html><html><body>
<a href="/library/llama3.2">Llama <span>description</span></a>
<a href="/library/llama3.2">duplicate</a>
<a href="https://ollama.com/library/qwen2.5">Qwen</a>
<a href="/library/qwen2.5/tags">not a model link</a>
<a href="https://other.example/library/false">foreign</a>
<a href="//other.example/library/false">foreign</a>
<a href="/download">download</a>
<a href="/library/not%20valid">invalid</a>
</body></html>"""


def test_library_discovery_needs_no_cli_or_daemon(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("must not inspect CLI, daemon or local models")

    monkeypatch.setattr(svc, "get_ollama_binary", fail)
    monkeypatch.setattr(svc, "server_is_up", fail)
    monkeypatch.setattr(svc, "list_local_models", fail)
    monkeypatch.setattr(svc.subprocess, "run", fail)

    def open_library(request, timeout):
        assert request.full_url == "https://ollama.com/library"
        assert timeout in (0.5, 30.0)
        return io.BytesIO(LIBRARY)

    monkeypatch.setattr(svc, "urlopen", open_library)
    assert svc.list_remote_models(host="http://unreachable:12345", timeout=0.5) == [
        "llama3.2",
        "qwen2.5",
    ]
    assert get_client("http://unreachable:12345").list_remote() == [
        "llama3.2",
        "qwen2.5",
    ]


@pytest.mark.parametrize(
    "body",
    [b"", b"<html>Service unavailable</html>", b"\xff", b"x" * (4 * 1024 * 1024 + 1)],
    ids=["empty", "unrecognised-html", "invalid-utf8", "oversized"],
)
def test_unrecognised_library_is_an_error(monkeypatch, body):
    monkeypatch.setattr(svc, "urlopen", lambda *a, **kw: io.BytesIO(body))
    with pytest.raises(ProviderError):
        svc.list_remote_models()


def test_fetch_failure_is_not_an_empty_catalogue(monkeypatch):
    def fail(*a, **kw):
        raise URLError("offline")

    monkeypatch.setattr(svc, "urlopen", fail)
    for discover in [svc.list_remote_models, get_client().list_remote, api_list_remote]:
        with pytest.raises(ProviderError, match="offline"):
            discover()
    result = api_list_remote_envelope()
    assert result.ok is False
    assert result.error is not None


def test_catalogue_installed_latest_alias_and_explicit_endpoint(monkeypatch):
    monkeypatch.setattr(svc, "urlopen", lambda *a, **kw: io.BytesIO(LIBRARY))

    def installed(**kwargs):
        assert kwargs["host"] == "http://localhost:12345"
        return ["llama3.2:latest"]

    monkeypatch.setattr(svc, "list_local_models", installed)
    entries = svc.list_remote_model_catalog(host="http://localhost:12345")
    assert [(x.name, x.installed) for x in entries] == [
        ("llama3.2", True),
        ("qwen2.5", False),
    ]
    assert [
        x.name
        for x in svc.list_remote_model_catalog(query="qwen", include_installed=False)
    ] == ["qwen2.5"]


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_library_validates_timeout_before_fetch(monkeypatch, timeout):
    monkeypatch.setattr(svc, "urlopen", lambda *a, **kw: pytest.fail("fetched"))
    with pytest.raises(ValueError):
        svc.list_remote_models(timeout=timeout)
