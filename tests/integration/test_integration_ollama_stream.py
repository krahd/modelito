import os
import pytest

pytestmark = pytest.mark.integration


def test_ollama_integration_streaming():
    from modelito.ollama_service import server_is_up

    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1")
    port = int(os.environ.get("OLLAMA_PORT", "11434"))

    if not server_is_up(host, port):
        pytest.skip("Ollama server not reachable on host/port")

    from modelito.ollama import OllamaProvider

    prov = OllamaProvider(host=host, port=port, model=os.environ.get("OLLAMA_MODEL"))

    from modelito.messages import Message
    out = prov.summarize([Message(role="user", content="Hello world")], settings={})
    assert isinstance(out, str) and out

    parts = []
    for p in prov.stream([Message(role="user", content="Hello world")], settings={}):
        parts.append(p)
        if len("".join(parts)) > 32:
            break
    assert parts
