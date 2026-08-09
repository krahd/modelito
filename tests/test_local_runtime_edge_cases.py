import pytest

from modelito.local_runtime import select_local_runtime
from modelito.probes import ProviderStatus


def test_selector_uses_first_loaded_model_when_none_requested(monkeypatch):
    monkeypatch.setattr(
        "modelito.local_runtime.probe_ollama_status",
        lambda model, host, port, timeout: ProviderStatus(
            provider="ollama",
            ready=True,
            endpoint="http://127.0.0.1:11434",
            models=["loaded-model"],
        ),
    )

    selection = select_local_runtime(
        profile="portable",
        _is_macos_apple_silicon=False,
    )

    assert selection.model == "loaded-model"


def test_selector_rejects_reachable_server_without_loaded_model(monkeypatch):
    monkeypatch.setattr(
        "modelito.local_runtime.probe_ollama_status",
        lambda model, host, port, timeout: ProviderStatus(
            provider="ollama",
            ready=True,
            endpoint="http://127.0.0.1:11434",
            models=[],
        ),
    )

    with pytest.raises(ValueError, match="no loaded models"):
        select_local_runtime(
            profile="portable",
            _is_macos_apple_silicon=False,
        )
