"""Regression coverage for the five upstream adversarial-audit findings."""

import io
import json
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from modelito import ollama_service as svc
from modelito.adapter import get_client
from modelito.exceptions import ModelitoBadResponseError
from modelito.ollama import OllamaProvider


@pytest.mark.parametrize("done", [None, False, 0, 1, "true"])
def test_summary_requires_explicit_completion(monkeypatch, done):
    response = {"message": {"content": "partial"}, "done": done, "model": "foo"}
    monkeypatch.setattr("modelito.ollama.json_post", lambda *a, **kw: response)
    with pytest.raises(ModelitoBadResponseError, match="incomplete"):
        OllamaProvider(model="foo").summarize(["hello"])


@pytest.mark.parametrize("actual", [None, "other", "foo:other", "namespace/foo"])
@pytest.mark.parametrize("stream", [False, True])
def test_strict_model_mismatch(monkeypatch, actual, stream):
    response = {"model": actual, "done": True, "message": {"content": "wrong"}}
    monkeypatch.setattr("modelito.ollama.json_post", lambda *a, **kw: response)
    monkeypatch.setattr(
        "modelito.ollama.urlopen",
        lambda *a, **kw: io.BytesIO((json.dumps(response) + "\n").encode()),
    )
    provider = OllamaProvider(model="foo")
    with pytest.raises(ModelitoBadResponseError, match="model"):
        if stream:
            list(provider.stream(["hello"]))
        else:
            provider.summarize(["hello"])


@pytest.mark.parametrize("stream", [False, True])
def test_timeout_override_and_latest_alias(monkeypatch, stream):
    response = {"model": "foo:latest", "done": True, "message": {"content": "ok"}}

    def post(url, payload, timeout, **kwargs):
        assert timeout == 0.25
        assert "timeout" not in payload
        return response

    def open_stream(request, timeout):
        assert timeout == 0.25
        assert "timeout" not in json.loads(request.data)
        return io.BytesIO((json.dumps(response) + "\n").encode())

    monkeypatch.setattr("modelito.ollama.json_post", post)
    monkeypatch.setattr("modelito.ollama.urlopen", open_stream)
    provider = OllamaProvider(model="foo", timeout=99)
    result = (
        "".join(provider.stream(["hello"], {"timeout": 0.25}))
        if stream
        else provider.summarize(["hello"], {"timeout": 0.25})
    )
    assert result == "ok"


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_cli_rejects_invalid_timeout_before_launch(monkeypatch, timeout):
    monkeypatch.setattr(svc, "resolve_ollama_command", lambda: pytest.fail("launched"))
    with pytest.raises(ValueError, match="finite and positive"):
        svc.run_ollama_command("list", timeout=timeout)


def test_cli_timeout_propagates(monkeypatch):
    monkeypatch.setattr(svc, "resolve_ollama_command", lambda: sys.executable)
    with pytest.raises(subprocess.TimeoutExpired):
        svc.run_ollama_command("-c", "import time; time.sleep(60)", timeout=0.1)


def test_explicit_inventory_uses_only_requested_http_endpoint(monkeypatch):
    def get(url, timeout):
        assert url == "http://127.0.0.1:12345/api/tags"
        assert timeout == 0.5
        return {"models": [{"name": "foo"}]}

    monkeypatch.setattr(svc, "json_get", get)
    monkeypatch.setattr(svc, "get_ollama_binary", lambda: pytest.fail("CLI discovery"))
    assert svc.list_local_models(host="127.0.0.1:12345", timeout=0.5) == ["foo"]


def test_cli_management_routes_endpoint_and_timeout(monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "get_ollama_binary", lambda: "ollama")

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        assert kwargs["env"]["OLLAMA_HOST"] == "http://localhost:12345"
        assert 0 < kwargs["timeout"] <= 0.5
        return subprocess.CompletedProcess(cmd, 0, '["foo"]', "")

    monkeypatch.setattr(svc.subprocess, "run", run)
    assert svc.delete_model("foo", host="localhost:12345", timeout=0.5)
    assert len(calls) == 1


def test_catalog_can_skip_installed_discovery(monkeypatch):
    monkeypatch.setattr(svc, "list_local_models", lambda **kw: pytest.fail("inventory"))
    monkeypatch.setattr(svc, "list_remote_models", lambda **kw: ["foo:latest"])
    assert not svc.list_remote_model_catalog(include_installed=False)[0].installed


def test_effective_config_bypasses_discovery(monkeypatch):
    monkeypatch.setattr(svc, "load_llm_config", lambda *a: pytest.fail("discovery"))
    monkeypatch.setattr(svc, "ollama_installed", lambda: True)
    monkeypatch.setattr(svc, "server_is_up", lambda h, p: h == "http://localhost:12345")

    def run(*args, **kwargs):
        assert kwargs["host"] == "http://localhost:12345"
        return subprocess.CompletedProcess(args, 0, "version", "")

    monkeypatch.setattr(svc, "run_ollama_command", run)
    config = {"url": "http://localhost:12345", "port": 11434}
    assert svc.inspect_service_state(config=config)["running"]
    assert svc.start_service(config=config) == 0
    with pytest.raises(ValueError, match="not both"):
        svc.inspect_service_state("ignored", config=config)


@pytest.mark.parametrize("cancel", [False, True])
def test_download_deadline_and_iterator_close_reap_child(monkeypatch, cancel):
    original_popen = subprocess.Popen
    children = []

    def launch(*args, **kwargs):
        assert kwargs["env"]["OLLAMA_HOST"] == "http://localhost:12345"
        process = original_popen(
            [
                sys.executable,
                "-u",
                "-c",
                "import time; print('progress 10%', flush=True); time.sleep(60)",
            ],
            **kwargs,
        )
        children.append(process)
        return process

    monkeypatch.setattr(svc, "get_ollama_binary", lambda: sys.executable)
    monkeypatch.setattr(svc.subprocess, "Popen", launch)
    started = time.monotonic()
    progress = svc.download_model_progress("foo", timeout=0.5, host="localhost:12345")
    assert next(progress).phase == "downloading"
    assert next(progress).progress == 10
    if cancel:
        progress.close()
    else:
        states = list(progress)
        assert states[-1].phase == "error"
        assert "timed out" in states[-1].error
    assert time.monotonic() - started < 5
    assert len(children) == 1
    assert children[0].poll() is not None
    assert children[0].stdout.closed


@pytest.fixture
def owned_server(monkeypatch, tmp_path):
    path = tmp_path / "ownership.json"
    command = ["/usr/bin/ollama", "serve"]
    receipt = {"pid": 123, "created": 456.0, "exe": command[0], "cmdline": command}
    path.write_text(json.dumps(receipt))
    calls = []
    proc = SimpleNamespace(
        create_time=lambda: 456.0,
        exe=lambda: command[0],
        cmdline=lambda: command,
        terminate=lambda: calls.append("terminate"),
        wait=lambda **kw: calls.append("wait"),
        kill=lambda: calls.append("kill"),
    )
    psutil = SimpleNamespace(Process=lambda pid: proc, TimeoutExpired=TimeoutError)
    monkeypatch.setitem(sys.modules, "psutil", psutil)
    monkeypatch.setattr(svc, "_ownership_path", lambda host: path)
    monkeypatch.setattr(
        svc, "run_ollama_command", lambda *a, **kw: pytest.fail("unload")
    )
    monkeypatch.setattr(
        svc, "find_ollama_listener_pids", lambda *a: pytest.fail("discovery")
    )
    return path, calls, proc


def test_owned_shutdown(owned_server):
    path, calls, proc = owned_server
    assert svc.stop_service() == 0
    assert calls == ["terminate", "wait"]
    assert not path.exists()


@pytest.mark.parametrize(
    "mismatch", ["missing", "pid_reused", "executable", "command", "remote"]
)
def test_shutdown_preserves_external_or_changed_process(owned_server, mismatch):
    path, calls, proc = owned_server
    if mismatch == "missing":
        path.unlink()
    elif mismatch == "pid_reused":
        proc.create_time = lambda: 999.0
    elif mismatch == "executable":
        proc.exe = lambda: "/usr/bin/other"
    elif mismatch == "command":
        proc.cmdline = lambda: ["/usr/bin/ollama", "runner"]
    host = "http://remote.example" if mismatch == "remote" else svc.DEFAULT_URL
    assert svc.stop_service(host=host) == 1
    assert calls == []


def test_adapter_pull_forwards_timeout(monkeypatch):
    def run(*args, **kwargs):
        assert kwargs["timeout"] == 0.5
        assert kwargs["host"] == "http://localhost:12345"
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(svc, "run_ollama_command", run)
    assert get_client("http://localhost:12345").pull("foo", timeout=0.5)


def test_launch_records_process_identity(monkeypatch, tmp_path):
    path = tmp_path / "receipt.json"
    process = SimpleNamespace(pid=321, poll=lambda: None)
    proc = SimpleNamespace(
        pid=321,
        create_time=lambda: 123.5,
        exe=lambda: "/usr/bin/ollama",
        cmdline=lambda: ["/usr/bin/ollama", "serve"],
    )
    monkeypatch.setitem(
        sys.modules, "psutil", SimpleNamespace(Process=lambda pid: proc)
    )
    monkeypatch.setattr(svc, "_ownership_path", lambda host: path)
    monkeypatch.setattr(svc, "resolve_ollama_command", lambda: "/usr/bin/ollama")

    def launch(cmd, **kwargs):
        assert cmd == ["/usr/bin/ollama", "serve"]
        assert kwargs["env"]["OLLAMA_HOST"] == "localhost:12345"
        return process

    monkeypatch.setattr(svc.subprocess, "Popen", launch)
    assert svc.start_detached_ollama_serve("localhost:12345") is process
    assert json.loads(path.read_text()) == {
        "pid": 321,
        "created": 123.5,
        "exe": "/usr/bin/ollama",
        "cmdline": ["/usr/bin/ollama", "serve"],
    }


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
@pytest.mark.parametrize("stream", [False, True])
def test_provider_invalid_timeout_does_not_send(monkeypatch, timeout, stream):
    monkeypatch.setattr(
        "modelito.ollama.json_post", lambda *a, **kw: pytest.fail("sent")
    )
    monkeypatch.setattr("modelito.ollama.urlopen", lambda *a, **kw: pytest.fail("sent"))
    provider = OllamaProvider()
    with pytest.raises(ValueError, match="finite and positive"):
        if stream:
            list(provider.stream(["hello"], {"timeout": timeout}))
        else:
            provider.summarize(["hello"], {"timeout": timeout})


@pytest.mark.parametrize("delay", [False, True])
def test_native_http_contract(monkeypatch, delay):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from modelito.exceptions import ModelitoTimeoutError

    captured = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append((self.path, payload))
            if delay:
                time.sleep(0.2)
            response = {
                "model": "foo:latest",
                "done": True,
                "message": {"content": "áéíóú ñ"},
            }
            body = json.dumps(response).encode()
            try:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = OllamaProvider(
            host="127.0.0.1", port=server.server_port, model="foo", timeout=10
        )
        if delay:
            with pytest.raises(ModelitoTimeoutError):
                provider.summarize(
                    [{"role": "system", "content": "Español"}], {"timeout": 0.03}
                )
        else:
            assert (
                provider.summarize(
                    [{"role": "system", "content": "Español"}],
                    {"timeout": 0.5, "temperature": 0},
                )
                == "áéíóú ñ"
            )
        assert len(captured) == 1
        assert captured[0][0] == "/api/chat"
        assert captured[0][1]["stream"] is False
        assert captured[0][1]["messages"] == [{"role": "system", "content": "Español"}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_adapter_closes_progress_on_cancellation(monkeypatch):
    closed = []

    def progress(*args, **kwargs):
        try:
            yield svc.ModelLifecycleState("foo", "downloading", message="progress")
        finally:
            closed.append(True)

    monkeypatch.setattr(svc, "download_model_progress", progress)
    iterator = get_client().download_stream("foo")
    assert next(iterator) == "progress"
    iterator.close()
    assert closed == [True]
