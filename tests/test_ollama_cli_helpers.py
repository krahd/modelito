import subprocess

import pytest

from modelito import ollama_service as osvc


def test_ollama_cli_helpers_smoke():
    candidates = osvc.ollama_binary_candidates()
    assert isinstance(candidates, list)

    installed = osvc.ollama_installed()
    assert isinstance(installed, bool)

    # resolve_ollama_command either returns a path or raises FileNotFoundError
    try:
        cmd = osvc.resolve_ollama_command()
        assert isinstance(cmd, str)
    except FileNotFoundError:
        pass

    if not installed:
        with pytest.raises(FileNotFoundError):
            osvc.run_ollama_command("--version")
    else:
        proc = osvc.run_ollama_command("--version")
        assert isinstance(proc, subprocess.CompletedProcess)

    # running model names should be a list even when not installed
    assert isinstance(osvc.running_model_names("127.0.0.1:11434"), list)


def test_cli_uses_utf8_for_accented_output(monkeypatch):
    monkeypatch.setattr(osvc, "resolve_ollama_command", lambda: "ollama")

    def run(args, **kwargs):
        assert kwargs["encoding"] == "utf-8"
        assert args == ["ollama", "run", "model", "¿Cómo estás?"]
        return subprocess.CompletedProcess(args, 0, "¡Bien! ñ áéíóú", "")

    monkeypatch.setattr(osvc.subprocess, "run", run)
    assert (
        osvc.run_ollama_command("run", "model", "¿Cómo estás?").stdout
        == "¡Bien! ñ áéíóú"
    )


def test_cli_decodes_real_utf8_subprocess(monkeypatch):
    import sys

    monkeypatch.setattr(osvc, "resolve_ollama_command", lambda: sys.executable)
    result = osvc.run_ollama_command(
        "-c", "import sys; sys.stdout.buffer.write('áéíóú ñ ¿Hola?'.encode('utf-8'))"
    )
    assert result.returncode == 0
    assert result.stdout == "áéíóú ñ ¿Hola?"
