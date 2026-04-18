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
