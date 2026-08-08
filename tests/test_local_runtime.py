import pytest

from modelito.local_runtime import (
    LOCAL_PROFILE_MAC_PERFORMANCE,
    LOCAL_PROFILE_PORTABLE,
    LocalRuntimeSelection,
    local_client,
    local_provider_candidates,
    normalize_local_profile,
    select_local_runtime,
)
from modelito.probes import ProviderStatus


def status(provider, ready, model=None, reason=""):
    return ProviderStatus(
        provider=provider,
        ready=ready,
        endpoint=(
            "http://localhost:8000/v1"
            if provider == "omlx"
            else "http://127.0.0.1:11434"
        ),
        models=[model] if ready and model else [],
        reason=reason,
        setup_hint="",
    )


def test_portable_profile_is_ollama_everywhere():
    assert local_provider_candidates(
        "portable", is_macos_apple_silicon=False
    ) == ["ollama"]
    assert local_provider_candidates(
        "portable", is_macos_apple_silicon=True
    ) == ["ollama"]


def test_auto_profile_uses_mac_native_order_on_apple_silicon():
    assert local_provider_candidates("auto", is_macos_apple_silicon=True) == [
        "omlx",
        "ollama",
    ]
    assert local_provider_candidates("auto", is_macos_apple_silicon=False) == [
        "ollama"
    ]


def test_mac_performance_profile_rejects_non_apple_silicon():
    with pytest.raises(ValueError, match="requires macOS on Apple Silicon"):
        local_provider_candidates(
            "mac-performance", is_macos_apple_silicon=False
        )


def test_profile_alias_and_environment(monkeypatch):
    assert normalize_local_profile("mac") == LOCAL_PROFILE_MAC_PERFORMANCE
    monkeypatch.setenv("MODELITO_LOCAL_PROFILE", "cross-platform")
    assert normalize_local_profile(None) == LOCAL_PROFILE_PORTABLE


def test_select_portable_does_not_probe_omlx(monkeypatch):
    monkeypatch.setattr(
        "modelito.local_runtime.probe_omlx_status",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected oMLX probe")),
    )
    monkeypatch.setattr(
        "modelito.local_runtime.probe_ollama_status",
        lambda model, host, port, timeout: status("ollama", True, model),
    )

    selection = select_local_runtime(
        "gemma4:12b-mlx",
        profile="portable",
        _is_macos_apple_silicon=True,
    )

    assert selection.provider == "ollama"
    assert selection.model == "gemma4:12b-mlx"


def test_select_mac_performance_prefers_omlx(monkeypatch):
    monkeypatch.setattr(
        "modelito.local_runtime.probe_omlx_status",
        lambda model, base_url, api_key, timeout: status("omlx", True, model),
    )
    monkeypatch.setattr(
        "modelito.local_runtime.probe_ollama_status",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected Ollama probe")),
    )

    selection = select_local_runtime(
        "mlx-model",
        profile="mac-performance",
        _is_macos_apple_silicon=True,
    )

    assert selection.provider == "omlx"


def test_select_mac_performance_falls_back_to_ollama(monkeypatch):
    monkeypatch.setattr(
        "modelito.local_runtime.probe_omlx_status",
        lambda model, base_url, api_key, timeout: status(
            "omlx", False, reason="not reachable"
        ),
    )
    monkeypatch.setattr(
        "modelito.local_runtime.probe_ollama_status",
        lambda model, host, port, timeout: status("ollama", True, model),
    )

    selection = select_local_runtime(
        profile="mac-performance",
        models={"omlx": "mlx-model", "ollama": "ollama-model"},
        _is_macos_apple_silicon=True,
    )

    assert selection.provider == "ollama"
    assert selection.model == "ollama-model"


def test_provider_specific_model_mapping_is_used(monkeypatch):
    seen = []

    def omlx_probe(model, base_url, api_key, timeout):
        seen.append(("omlx", model))
        return status("omlx", False, reason="not ready")

    def ollama_probe(model, host, port, timeout):
        seen.append(("ollama", model))
        return status("ollama", True, model)

    monkeypatch.setattr("modelito.local_runtime.probe_omlx_status", omlx_probe)
    monkeypatch.setattr("modelito.local_runtime.probe_ollama_status", ollama_probe)

    selection = select_local_runtime(
        model="fallback-model",
        models={"om": "mlx-specific", "ollama": "ollama-specific"},
        profile="mac-performance",
        _is_macos_apple_silicon=True,
    )

    assert seen == [("omlx", "mlx-specific"), ("ollama", "ollama-specific")]
    assert selection.model == "ollama-specific"


def test_prefer_can_reorder_mac_profile_after_benchmarking(monkeypatch):
    monkeypatch.setattr(
        "modelito.local_runtime.probe_ollama_status",
        lambda model, host, port, timeout: status("ollama", True, model),
    )
    monkeypatch.setattr(
        "modelito.local_runtime.probe_omlx_status",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected oMLX probe")),
    )

    selection = select_local_runtime(
        "ollama-model",
        profile="mac-performance",
        prefer=["ollama", "omlx"],
        _is_macos_apple_silicon=True,
    )

    assert selection.provider == "ollama"


def test_local_prefer_rejects_hosted_provider():
    with pytest.raises(ValueError, match="only contain omlx or ollama"):
        select_local_runtime(
            profile="portable",
            prefer=["openai"],
            _is_macos_apple_silicon=False,
        )


def test_no_ready_local_runtime_raises_with_diagnostics(monkeypatch):
    monkeypatch.setattr(
        "modelito.local_runtime.probe_ollama_status",
        lambda model, host, port, timeout: status(
            "ollama", False, reason="requested model not found"
        ),
    )

    with pytest.raises(ValueError, match="requested model not found"):
        select_local_runtime(
            "missing",
            profile="portable",
            _is_macos_apple_silicon=False,
        )


def test_local_client_uses_strict_provider_by_default(monkeypatch):
    called = {}

    class DummyProvider:
        model = "local-model"

        def list_models(self):
            return [self.model]

        def summarize(self, messages, settings=None):
            return "ok"

    monkeypatch.setattr(
        "modelito.local_runtime.select_local_runtime",
        lambda *args, **kwargs: LocalRuntimeSelection(
            profile="portable",
            provider="ollama",
            model="local-model",
            endpoint="http://127.0.0.1:11434",
        ),
    )

    def fake_get_provider(name, **kwargs):
        called["name"] = name
        called["kwargs"] = kwargs
        return DummyProvider()

    monkeypatch.setattr("modelito.client.get_provider", fake_get_provider)

    client = local_client(profile="portable")

    assert client.provider_name == "DummyProvider"
    assert called["name"] == "ollama"
    assert called["kwargs"]["strict"] is True
    assert called["kwargs"]["model"] == "local-model"
