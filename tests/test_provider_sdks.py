from types import SimpleNamespace
import sys


from modelito.openai import OpenAIProvider
from modelito.claude import ClaudeProvider
from modelito import gemini as gemini_mod
from modelito import ollama as ollama_mod


def test_openai_modern_client(monkeypatch):
    # Simulate an installed `openai` module and pass a modern client object
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace())

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda model, messages, **kwargs: {
                    "choices": [{"message": {"content": "sdk reply"}}]}
            )
        )
    )

    p = OpenAIProvider(client=client)
    out = p.summarize([{"role": "user", "content": "hi"}], settings={})
    assert isinstance(out, str)
    assert out == "sdk reply"


def test_openai_legacy_chatcompletion(monkeypatch):
    # Simulate legacy ChatCompletion surface on the `openai` module
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(
        ChatCompletion=SimpleNamespace(
            create=lambda model, messages, **kwargs: {
                "choices": [{"message": {"content": "legacy reply"}}]}
        )
    ))

    p = OpenAIProvider()
    out = p.summarize([{"role": "user", "content": "hello"}], settings={})
    assert "legacy reply" in out


def test_claude_modern_client(monkeypatch):
    # Ensure `anthropic` module is present and client.completions.create is used
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace())

    client = SimpleNamespace(
        completions=SimpleNamespace(
            create=lambda model, prompt, **kwargs: {"text": "anthropic reply"}
        )
    )

    p = ClaudeProvider(client=client)
    out = p.summarize([{"role": "user", "content": "ok"}], settings={})
    assert isinstance(out, str)
    assert out == "anthropic reply"


def test_claude_legacy_create_completion(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace())

    client = SimpleNamespace(
        create_completion=lambda model, prompt, **kwargs: {"completion": "legacy anthropic"}
    )

    p = ClaudeProvider(client=client)
    out = p.summarize([{"role": "user", "content": "ok"}], settings={})
    assert "legacy anthropic" in out


def test_gemini_generate_text(monkeypatch):
    # Install a fake google.generativeai module with generate_text
    fake = SimpleNamespace(
        generate_text=lambda model, prompt, **kwargs: {"candidates": [{"content": "gen reply"}]}
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)

    p = gemini_mod.GeminiProvider()
    out = p.summarize([{"role": "user", "content": "hi"}], settings={})
    assert isinstance(out, str)
    assert "gen reply" in out


def test_ollama_server_response(monkeypatch):
    # Force the ollama helpers imported into the `modelito.ollama` module
    monkeypatch.setattr("modelito.ollama.server_is_up", lambda host, port: True)
    monkeypatch.setattr("modelito.ollama.json_post", lambda url,
                        payload, timeout=None: {"text": "ollama reply"})

    p = ollama_mod.OllamaProvider()
    out = p.summarize([{"role": "user", "content": "hello"}], settings={})
    assert out == "ollama reply"
