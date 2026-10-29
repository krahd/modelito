"""Bounded regressions for the BatLLM consumer contract."""

import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess

import pytest

from modelito import ollama_service as svc
from modelito.errors import ProviderError
from modelito.exceptions import (
    ModelitoBadResponseError,
    ModelitoProviderError,
    ModelitoTimeoutError,
)
from modelito.ollama import OllamaProvider


@pytest.mark.parametrize(
    "response",
    [
        [],
        {},
        {"error": "failed"},
        {"done": False},
        {"model": "wrong", "done": True},
        {"model": "foo", "done": True, "response": 42},
    ],
)
def test_warmup_rejects_failed_responses(monkeypatch, response):
    monkeypatch.setattr(svc, "json_post", lambda *a, **kw: response)
    with pytest.raises((ModelitoBadResponseError, ModelitoProviderError)):
        svc.preload_model("localhost", 11434, "foo")


def test_warmup_empty_text_and_single_attempt(monkeypatch):
    calls = []

    def open_request(*a, **kw):
        calls.append(1)
        raise TimeoutError("expired")

    monkeypatch.setattr(svc, "urlopen", open_request)
    with pytest.raises(ProviderError):
        svc.preload_model("localhost", 11434, "foo", timeout=0.02)
    assert calls == [1]
    monkeypatch.setattr(
        svc,
        "json_post",
        lambda *a, **kw: {"model": "foo:latest", "done": True, "response": ""},
    )
    svc.preload_model("localhost", 11434, "foo")


@pytest.mark.parametrize(
    "fields",
    [
        {"message": {"content": 42}},
        {"message": None},
        {"message": {"content": None}},
        {"response": 42},
        {"message": []},
    ],
)
def test_malformed_terminal_event_after_text(monkeypatch, fields):
    events = [
        {"model": "foo", "message": {"content": "ok"}},
        {"model": "foo", "done": True, **fields},
    ]
    monkeypatch.setattr(
        "modelito.ollama.urlopen",
        lambda *a, **kw: io.BytesIO(
            b"\n".join(json.dumps(event).encode() for event in events)
        ),
    )
    with pytest.raises(ModelitoBadResponseError):
        list(OllamaProvider(model="foo").stream(["hello"]))


def test_terminal_event_can_omit_text(monkeypatch):
    monkeypatch.setattr(
        "modelito.ollama.urlopen",
        lambda *a, **kw: io.BytesIO(b'{"model":"foo","done":true}\n'),
    )
    assert list(OllamaProvider(model="foo").stream(["hello"])) == []


@pytest.mark.parametrize(
    "response",
    [{}, {"version": ""}, {"version": 1}, {"error": "failed", "version": "1"}],
)
def test_readiness_rejects_liveness_and_clamps_budget(monkeypatch, response):
    budgets = []

    def get(*a, **kw):
        budgets.append(kw["policy"].timeout)
        assert kw["policy"].max_attempts == 1
        return response

    monkeypatch.setattr(svc, "json_get", get)
    monkeypatch.setattr(svc, "server_is_up", lambda *a: pytest.fail("liveness probe"))
    started = time.monotonic()
    with pytest.raises(RuntimeError):
        svc.wait_until_ready("localhost", 11434, 0.03)
    assert time.monotonic() - started < 0.15
    assert all(0 < budget <= 0.03 for budget in budgets)


def test_ready_version_response(monkeypatch):
    monkeypatch.setattr(svc, "json_get", lambda *a, **kw: {"version": "0.12.0"})
    svc.wait_until_ready("localhost", 11434, 0.1)


def test_startup_never_pulls(monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "server_is_up", lambda *a: True)

    def run(*args, **kw):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "version", "")

    monkeypatch.setattr(svc, "run_ollama_command", run)
    monkeypatch.setattr(svc, "preload_model", lambda *a, **kw: None)
    assert (
        svc.start_service(config={"url": "localhost", "port": 11434, "model": "foo"})
        == 0
    )
    assert calls == [("--version",)]


@pytest.mark.parametrize("phase", ["headers", "body", "stream"])
def test_total_deadline_interrupts_trickling_bytes(phase, monkeypatch):
    # A test-owned loopback endpoint must not use host proxy configuration.
    monkeypatch.setattr("modelito._http_deadline._PROXIES", {})
    disconnected = threading.Event()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            requests.append(self.rfile.read(int(self.headers["Content-Length"])))

            def observe_disconnect():
                # Read the client's FIN directly. Windows may buffer successful
                # writes after peer shutdown, so write errors are not a reliable
                # measure of when the client closed its socket.
                try:
                    if self.connection.recv(1) == b"":
                        disconnected.set()
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    disconnected.set()

            threading.Thread(target=observe_disconnect, daemon=True).start()
            body = (
                json.dumps(
                    {"model": "foo", "message": {"content": "ok"}, "done": True}
                ).encode()
                + b"\n"
            )
            try:
                if phase == "headers":
                    data = (
                        b"HTTP/1.1 200 OK\r\nX-Slow: " + b"a" * 100 + b"\r\n\r\n" + body
                    )
                else:
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    data = body
                for byte in data:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.01)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                disconnected.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        provider = OllamaProvider(
            host="127.0.0.1", port=server.server_port, model="foo", timeout=0.1
        )
        started = time.monotonic()
        with pytest.raises(ModelitoTimeoutError) as failure:
            if phase == "stream":
                list(provider.stream(["hello"]))
            else:
                provider.summarize(["hello"])
        assert time.monotonic() - started < 0.3
        assert len(requests) == 1, str(failure.value)
        assert disconnected.wait(1.0)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_dns_resolution_cannot_exceed_request_budget(monkeypatch):
    from modelito._http_deadline import urlopen
    import socket

    release = threading.Event()
    finished = threading.Event()

    def resolve(*args, **kwargs):
        try:
            release.wait(2)
            return []
        finally:
            finished.set()

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            with urlopen("http://unresolved.invalid/api/version", timeout=0.03):
                pytest.fail("resolved")
        assert time.monotonic() - started < 0.2
    finally:
        release.set()
        assert finished.wait(1)
