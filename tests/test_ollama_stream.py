import json

from modelito.ollama import OllamaProvider


class _FakeResp:
    def __init__(self, lines):
        self._lines = [l.encode("utf-8") for l in lines]
        self._i = 0

    def readline(self):
        if self._i < len(self._lines):
            v = self._lines[self._i]
            self._i += 1
            return v
        return b""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ollama_stream_monkeypatch(monkeypatch):
    # Simulate SSE/line-delimited JSON tokens
    lines = [json.dumps({"token": "Hello"}) + "\n", json.dumps({"token": " "}) + "\n", json.dumps({"token": "world"}) + "\n"]

    def _fake_urlopen(req, timeout=60):
        return _FakeResp(lines)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    prov = OllamaProvider(host="http://127.0.0.1", port=11434)
    out = "".join(list(prov.stream([{"role": "user", "content": "hi"}])))
    assert out == "Hello world"
