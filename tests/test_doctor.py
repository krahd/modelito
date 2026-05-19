from modelito.doctor import ProviderStatus, check_provider_ready, format_provider_status, main


def test_check_provider_ready_omlx_success(monkeypatch):
    class FakeOMLX:
        def __init__(self, **kwargs):
            self.base_url = kwargs.get("base_url")

        def list_models(self):
            return ["omlx", "other"]

    monkeypatch.setattr("modelito.doctor.OMLXProvider", FakeOMLX)

    status = check_provider_ready("omlx", model="omlx")

    assert isinstance(status, ProviderStatus)
    assert status.ready is True
    assert status.provider == "omlx"
    assert status.endpoint == "http://localhost:8000/v1"
    assert "omlx" in status.models


def test_check_provider_ready_ollama_failure(monkeypatch):
    monkeypatch.setattr("modelito.doctor.server_is_up", lambda host, port: False)

    status = check_provider_ready("ollama", model="qwen2.5:7b", host="http://127.0.0.1", port=11434)

    assert status.ready is False
    assert status.provider == "ollama"
    assert "not reachable" in status.reason.lower()
    assert "ollama pull" in status.setup_hint


def test_check_provider_ready_auto_prefers_omlx_on_macos(monkeypatch):
    monkeypatch.setattr("modelito.doctor._is_macos_apple_silicon", lambda: True)
    monkeypatch.setattr(
        "modelito.doctor._probe_omlx",
        lambda model, base_url, api_key, probe_timeout: ProviderStatus(
            provider="omlx",
            ready=True,
            endpoint="http://localhost:8000/v1",
            models=["omlx"],
        ),
    )
    monkeypatch.setattr("modelito.doctor._probe_ollama", lambda *args, **
                        kwargs: ProviderStatus(provider="ollama", ready=False))

    status = check_provider_ready("auto", model="omlx")

    assert status.provider == "omlx"
    assert status.ready is True


def test_format_provider_status_includes_core_fields():
    status = ProviderStatus(
        provider="omlx",
        ready=False,
        endpoint="http://localhost:8000/v1",
        reason="oMLX server not reachable",
        setup_hint="Start oMLX",
    )

    text = format_provider_status(status)

    assert "provider: omlx" in text
    assert "ready: False" in text
    assert "endpoint: http://localhost:8000/v1" in text
    assert "setup_hint: Start oMLX" in text


def test_doctor_main_json_output(monkeypatch, capsys):
    monkeypatch.setattr("modelito.doctor.check_provider_ready", lambda *args, **
                        kwargs: ProviderStatus(provider="omlx", ready=True, endpoint="http://localhost:8000/v1"))

    code = main(["doctor", "--provider", "omlx", "--json"])
    captured = capsys.readouterr()

    assert code == 0
    assert '"provider": "omlx"' in captured.out


def test_doctor_main_non_ready_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setattr("modelito.doctor.check_provider_ready", lambda *args, **
                        kwargs: ProviderStatus(provider="ollama", ready=False, reason="offline"))

    code = main(["doctor", "--provider", "ollama"])
    captured = capsys.readouterr()

    assert code == 1
    assert "offline" in captured.out
